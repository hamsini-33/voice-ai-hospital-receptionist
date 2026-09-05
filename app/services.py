from datetime import date, time, datetime, timedelta
from zoneinfo import ZoneInfo

from .database import supabase


# ============================================================
# TIMEZONE
# ============================================================

HOSPITAL_TIMEZONE = ZoneInfo("Asia/Kolkata")


def get_hospital_now() -> datetime:
    """
    Return the current date/time in the hospital's timezone.
    """
    return datetime.now(HOSPITAL_TIMEZONE)


# ============================================================
# DAY MAP
# ============================================================

DAY_MAP = {
    0: "Mon",
    1: "Tue",
    2: "Wed",
    3: "Thu",
    4: "Fri",
    5: "Sat",
    6: "Sun",
}


# ============================================================
# WORKING DAY
# ============================================================

def is_working_day(
    slot_days: str,
    requested_date: date
) -> bool:
    """
    Check whether the doctor works on the requested date.

    Supports:
    - Mon-Sat
    - Mon
    - Tue
    - Mon,Tue,Wed
    """

    if not slot_days:
        return False

    day_name = DAY_MAP[requested_date.weekday()]
    normalized = slot_days.replace(" ", "")

    if normalized == "Mon-Sat":
        return requested_date.weekday() <= 5

    working_days = normalized.split(",")

    return day_name in working_days


# ============================================================
# TIME CONVERSION
# ============================================================

def normalize_time(value) -> time:
    """
    Convert a Supabase time value into a Python time object.
    """

    if isinstance(value, time):
        return value

    if isinstance(value, str):
        return time.fromisoformat(value)

    raise ValueError("Invalid time value")


# ============================================================
# SLOT GENERATION
# ============================================================

def generate_slots(
    start: time,
    end: time,
    interval_minutes: int = 30
):
    """
    Generate appointment slots from start inclusive
    to end exclusive.
    """

    if interval_minutes <= 0:
        raise ValueError("Invalid slot interval")

    slots = []

    current = datetime.combine(
        date.today(),
        start
    )

    end_datetime = datetime.combine(
        date.today(),
        end
    )

    while current < end_datetime:

        slots.append(current.time())

        current += timedelta(
            minutes=interval_minutes
        )

    return slots


# ============================================================
# GET DOCTOR
# ============================================================

def get_doctor(doctor_id: int):
    response = (
        supabase
        .table("doctors")
        .select("*")
        .eq("id", doctor_id)
        .execute()
    )

    if not response.data:
        raise ValueError("Doctor not found")

    return response.data[0]


# ============================================================
# GET AVAILABLE SLOTS
# ============================================================

def get_available_slots(
    doctor_id: int,
    requested_date: date
):
    """
    Return available 30-minute slots for a doctor/date.

    Uses the real appointments table to remove booked slots.
    """

    doctor = get_doctor(doctor_id)

    hospital_now = get_hospital_now()
    today = hospital_now.date()

    # --------------------------------------------------------
    # Reject past dates
    # --------------------------------------------------------

    if requested_date < today:
        raise ValueError(
            "Cannot check availability for a past date"
        )

    # --------------------------------------------------------
    # Check doctor's working day
    # --------------------------------------------------------

    if not is_working_day(
        doctor["slot_days"],
        requested_date
    ):
        return []

    # --------------------------------------------------------
    # Generate doctor's real slots
    # --------------------------------------------------------

    start_time = normalize_time(
        doctor["slot_start"]
    )

    end_time = normalize_time(
        doctor["slot_end"]
    )

    all_slots = generate_slots(
        start=start_time,
        end=end_time
    )

    # --------------------------------------------------------
    # Remove slots that have already passed TODAY
    # --------------------------------------------------------

    if requested_date == today:

        current_time = hospital_now.time()

        all_slots = [
            slot
            for slot in all_slots
            if slot > current_time
        ]

    # --------------------------------------------------------
    # Get real booked appointments
    # --------------------------------------------------------

    response = (
        supabase
        .table("appointments")
        .select("time")
        .eq("doctor_id", doctor_id)
        .eq(
            "date",
            requested_date.isoformat()
        )
        .eq("status", "booked")
        .execute()
    )

    booked_times = set()

    for appointment in response.data:

        appointment_time = normalize_time(
            appointment["time"]
        )

        booked_times.add(
            appointment_time.strftime("%H:%M")
        )

    # --------------------------------------------------------
    # Return only currently available slots
    # --------------------------------------------------------

    return [
        slot
        for slot in all_slots
        if slot.strftime("%H:%M")
        not in booked_times
    ]


# ============================================================
# VALIDATE SLOT
# ============================================================

def validate_slot(
    doctor_id: int,
    requested_date: date,
    requested_time: time
):
    """
    Validate the complete doctor/date/time combination.
    """

    doctor = get_doctor(doctor_id)

    hospital_now = get_hospital_now()
    today = hospital_now.date()

    # --------------------------------------------------------
    # Reject past dates
    # --------------------------------------------------------

    if requested_date < today:
        raise ValueError(
            "Cannot book an appointment in the past"
        )

    # --------------------------------------------------------
    # Reject dates when doctor does not work
    # --------------------------------------------------------

    if not is_working_day(
        doctor["slot_days"],
        requested_date
    ):
        raise ValueError("DOCTOR_NOT_AVAILABLE")

    # --------------------------------------------------------
    # Reject past times when booking TODAY
    # --------------------------------------------------------

    if requested_date == today:

        current_time = hospital_now.time()

        if requested_time <= current_time:
            raise ValueError(
                "Cannot book an appointment in the past"
            )

    # --------------------------------------------------------
    # Get doctor's working hours
    # --------------------------------------------------------

    start_time = normalize_time(
        doctor["slot_start"]
    )

    end_time = normalize_time(
        doctor["slot_end"]
    )

    # --------------------------------------------------------
    # Generate valid appointment slots
    # --------------------------------------------------------

    valid_slots = generate_slots(
        start=start_time,
        end=end_time
    )

    # --------------------------------------------------------
    # Requested time must be an actual slot
    # --------------------------------------------------------

    if requested_time not in valid_slots:
        raise ValueError("INVALID_TIME")

    return doctor


# ============================================================
# BOOK APPOINTMENT
# ============================================================

def book_appointment(
    patient_name: str,
    patient_phone: str,
    doctor_id: int,
    appointment_date: date,
    appointment_time: time
):
    """
    Book an appointment.

    The database unique index provides the final
    race-condition protection.
    """

    doctor = validate_slot(
        doctor_id=doctor_id,
        requested_date=appointment_date,
        requested_time=appointment_time
    )

    # --------------------------------------------------------
    # Check current availability
    # --------------------------------------------------------

    existing = (
        supabase
        .table("appointments")
        .select("id")
        .eq("doctor_id", doctor_id)
        .eq(
            "date",
            appointment_date.isoformat()
        )
        .eq(
            "time",
            appointment_time.strftime("%H:%M:%S")
        )
        .eq("status", "booked")
        .execute()
    )

    if existing.data:
        raise ValueError("SLOT_UNAVAILABLE")

    # --------------------------------------------------------
    # Insert booking
    # --------------------------------------------------------

    try:

        response = (
            supabase
            .table("appointments")
            .insert({
                "patient_name": patient_name,
                "patient_phone": patient_phone,
                "doctor_id": doctor_id,
                "date": appointment_date.isoformat(),
                "time": appointment_time.strftime("%H:%M:%S"),
                "status": "booked"
            })
            .execute()
        )

    except Exception as error:

        # PostgreSQL duplicate key / unique index conflict
        if (
            "23505" in str(error)
            or "duplicate" in str(error).lower()
        ):
            raise ValueError("SLOT_UNAVAILABLE")

        raise

    if not response.data:
        raise ValueError("BOOKING_FAILED")

    appointment = response.data[0]

    return {
        "success": True,
        "appointment_id": appointment["id"],
        "patient_name": patient_name,
        "patient_phone": patient_phone,
        "doctor_id": doctor_id,
        "doctor": doctor["name"],
        "department": doctor["department"],
        "date": appointment_date.isoformat(),
        "time": appointment_time.strftime("%H:%M"),
        "status": "booked"
    }


# ============================================================
# GET PATIENT APPOINTMENTS
# ============================================================

def get_patient_appointments(
    patient_phone: str
):
    """
    Retrieve all appointments for a patient.

    Includes historical records so the voice agent can
    distinguish booked, cancelled, and rescheduled records.
    """

    response = (
        supabase
        .table("appointments")
        .select(
            "id,patient_name,patient_phone,doctor_id,"
            "date,time,status,doctors(name,department)"
        )
        .eq("patient_phone", patient_phone)
        .order("date", desc=False)
        .order("time", desc=False)
        .execute()
    )

    appointments = []

    for appointment in response.data:

        doctor_data = (
            appointment.get("doctors")
            or {}
        )

        appointment_time = normalize_time(
            appointment["time"]
        )

        appointments.append({
            "id": appointment["id"],
            "patient_name": appointment["patient_name"],
            "patient_phone": appointment["patient_phone"],
            "doctor_id": appointment["doctor_id"],
            "doctor": doctor_data.get("name"),
            "department": doctor_data.get("department"),
            "date": appointment["date"],
            "time": appointment_time.strftime("%H:%M"),
            "status": appointment["status"]
        })

    return appointments


# ============================================================
# FIND EXACT ACTIVE APPOINTMENT
# ============================================================

def get_active_appointment(
    patient_phone: str,
    appointment_id: int
):
    """
    Find one specific active appointment belonging
    to the supplied phone number.

    Appointment ID is the authoritative selector.
    """

    response = (
        supabase
        .table("appointments")
        .select(
            "id,patient_name,patient_phone,doctor_id,"
            "date,time,status,doctors(name,department)"
        )
        .eq("id", appointment_id)
        .eq("patient_phone", patient_phone)
        .eq("status", "booked")
        .execute()
    )

    if not response.data:
        raise ValueError(
            "No active appointment found"
        )

    return response.data[0]


# ============================================================
# CANCEL APPOINTMENT
# ============================================================

def cancel_appointment(
    patient_phone: str,
    appointment_id: int
):
    """
    Cancel the EXACT appointment selected by the patient.
    """

    appointment = get_active_appointment(
        patient_phone=patient_phone,
        appointment_id=appointment_id
    )

    response = (
        supabase
        .table("appointments")
        .update({
            "status": "cancelled"
        })
        .eq("id", appointment_id)
        .eq("patient_phone", patient_phone)
        .eq("status", "booked")
        .execute()
    )

    if not response.data:
        raise ValueError(
            "Appointment could not be cancelled"
        )

    doctor_data = (
        appointment.get("doctors")
        or {}
    )

    appointment_time = normalize_time(
        appointment["time"]
    )

    return {
        "success": True,
        "appointment_id": appointment_id,
        "patient_name": appointment["patient_name"],
        "doctor": doctor_data.get("name"),
        "department": doctor_data.get("department"),
        "date": appointment["date"],
        "time": appointment_time.strftime("%H:%M"),
        "status": "cancelled"
    }


# ============================================================
# RESCHEDULE APPOINTMENT
# ============================================================

def reschedule_appointment(
    patient_phone: str,
    appointment_id: int,
    new_date: date,
    new_time: time
):
    """
    Reschedule the EXACT appointment selected by the patient.

    The doctor remains unchanged.
    """

    # --------------------------------------------------------
    # Find exact active appointment
    # --------------------------------------------------------

    old_appointment = get_active_appointment(
        patient_phone=patient_phone,
        appointment_id=appointment_id
    )

    doctor_id = old_appointment["doctor_id"]

    # --------------------------------------------------------
    # Validate new slot
    # --------------------------------------------------------

    doctor = validate_slot(
        doctor_id=doctor_id,
        requested_date=new_date,
        requested_time=new_time
    )

    # --------------------------------------------------------
    # Check whether requested new slot is occupied
    # --------------------------------------------------------

    existing = (
        supabase
        .table("appointments")
        .select("id")
        .eq("doctor_id", doctor_id)
        .eq(
            "date",
            new_date.isoformat()
        )
        .eq(
            "time",
            new_time.strftime("%H:%M:%S")
        )
        .eq("status", "booked")
        .execute()
    )

    occupied_by_other = [
        row
        for row in existing.data
        if row["id"] != appointment_id
    ]

    if occupied_by_other:
        raise ValueError("SLOT_UNAVAILABLE")

    # --------------------------------------------------------
    # Check whether the requested slot is unchanged
    # --------------------------------------------------------

    old_time = normalize_time(
        old_appointment["time"]
    )

    if (
        old_appointment["date"]
        == new_date.isoformat()

        and old_time.strftime("%H:%M")
        == new_time.strftime("%H:%M")
    ):

        return {
            "success": True,
            "appointment_id": appointment_id,
            "previous_appointment_id": appointment_id,
            "patient_name": old_appointment["patient_name"],
            "doctor": doctor["name"],
            "department": doctor["department"],
            "date": new_date.isoformat(),
            "time": new_time.strftime("%H:%M"),
            "status": "booked"
        }

    # --------------------------------------------------------
    # Create replacement appointment first
    # --------------------------------------------------------

    try:

        new_response = (
            supabase
            .table("appointments")
            .insert({
                "patient_name": old_appointment["patient_name"],
                "patient_phone": patient_phone,
                "doctor_id": doctor_id,
                "date": new_date.isoformat(),
                "time": new_time.strftime("%H:%M:%S"),
                "status": "booked"
            })
            .execute()
        )

    except Exception as error:

        if (
            "23505" in str(error)
            or "duplicate" in str(error).lower()
        ):
            raise ValueError("SLOT_UNAVAILABLE")

        raise

    if not new_response.data:
        raise ValueError("RESCHEDULE_FAILED")

    new_appointment = new_response.data[0]

    # --------------------------------------------------------
    # Mark old appointment as rescheduled
    # --------------------------------------------------------

    try:

        old_update = (
            supabase
            .table("appointments")
            .update({
                "status": "rescheduled"
            })
            .eq("id", appointment_id)
            .eq("patient_phone", patient_phone)
            .eq("status", "booked")
            .execute()
        )

        if not old_update.data:
            raise ValueError(
                "OLD_APPOINTMENT_UPDATE_FAILED"
            )

    except Exception:

        # Compensation:
        # remove the newly created booking so we don't
        # leave two active appointments behind.

        try:

            supabase \
                .table("appointments") \
                .delete() \
                .eq("id", new_appointment["id"]) \
                .execute()

        except Exception:
            pass

        raise ValueError(
            "RESCHEDULE_FAILED"
        )

    return {
        "success": True,
        "appointment_id": new_appointment["id"],
        "previous_appointment_id": appointment_id,
        "patient_name": old_appointment["patient_name"],
        "doctor": doctor["name"],
        "department": doctor["department"],
        "date": new_date.isoformat(),
        "time": new_time.strftime("%H:%M"),
        "status": "booked"
    }