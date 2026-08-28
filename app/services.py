from datetime import date, time, datetime, timedelta
from typing import List

from .database import supabase


# ============================================================
# DAY MAPPING
# ============================================================

DAY_MAP = {
    "Monday": "Mon",
    "Tuesday": "Tue",
    "Wednesday": "Wed",
    "Thursday": "Thu",
    "Friday": "Fri",
    "Saturday": "Sat",
    "Sunday": "Sun",
}


# ============================================================
# DOCTOR / SCHEDULE HELPERS
# ============================================================

def is_working_day(
    slot_days: str,
    requested_date: date
) -> bool:
    """
    Check whether a doctor works on the requested date.

    Supported formats in the database:
        Mon-Sat
        Mon
        Tue
        Mon,Tue,Wed
    """

    weekday = DAY_MAP[
        requested_date.strftime("%A")
    ]

    # Handle Mon-Sat schedule
    if slot_days == "Mon-Sat":
        return weekday in {
            "Mon",
            "Tue",
            "Wed",
            "Thu",
            "Fri",
            "Sat",
        }

    # Handle individual/comma-separated days
    allowed_days = {
        day.strip()
        for day in slot_days.split(",")
    }

    return weekday in allowed_days


def generate_slots(
    start: time,
    end: time,
    interval_minutes: int = 30
) -> List[time]:
    """
    Generate appointment slots between start and end.

    Example:
        10:00 - 12:00

    Returns:
        10:00
        10:30
        11:00
        11:30

    The ending time itself is not considered a slot.
    """

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

        slots.append(
            current.time()
        )

        current += timedelta(
            minutes=interval_minutes
        )

    return slots


def get_doctor(
    doctor_id: int
):
    """
    Retrieve a doctor by ID.
    """

    response = (
        supabase
        .table("doctors")
        .select("*")
        .eq("id", doctor_id)
        .execute()
    )

    if not response.data:
        raise ValueError(
            "Doctor not found"
        )

    return response.data[0]


# ============================================================
# AVAILABILITY
# ============================================================

def get_available_slots(
    doctor_id: int,
    requested_date: date
) -> List[time]:
    """
    Return all available 30-minute appointment slots
    for a doctor on a specific date.
    """

    doctor = get_doctor(
        doctor_id
    )

    # --------------------------------------------------------
    # Past date validation
    # --------------------------------------------------------

    if requested_date < date.today():

        raise ValueError(
            "Appointments cannot be booked in the past"
        )

    # --------------------------------------------------------
    # Working-day validation
    # --------------------------------------------------------

    if not is_working_day(
        doctor["slot_days"],
        requested_date
    ):
        return []

    # --------------------------------------------------------
    # Generate doctor's slots
    # --------------------------------------------------------

    start = time.fromisoformat(
        doctor["slot_start"]
    )

    end = time.fromisoformat(
        doctor["slot_end"]
    )

    slots = generate_slots(
        start,
        end
    )

    # --------------------------------------------------------
    # Get already booked appointments
    # --------------------------------------------------------

    appointments_response = (
        supabase
        .table("appointments")
        .select("time")
        .eq(
            "doctor_id",
            doctor_id
        )
        .eq(
            "date",
            requested_date.isoformat()
        )
        .eq(
            "status",
            "booked"
        )
        .execute()
    )

    # --------------------------------------------------------
    # Convert booked times into Python time objects
    # --------------------------------------------------------

    booked_times = {
        time.fromisoformat(
            appointment["time"]
        )
        for appointment
        in appointments_response.data
    }

    # --------------------------------------------------------
    # Remove booked slots
    # --------------------------------------------------------

    available_slots = [
        slot
        for slot in slots
        if slot not in booked_times
    ]

    return available_slots


def validate_slot(
    doctor_id: int,
    requested_date: date,
    requested_time: time
):
    """
    Validate that a requested appointment slot is valid
    for the doctor.

    Checks:
        1. Doctor exists
        2. Date is not in the past
        3. Doctor works that day
        4. Requested time is inside working hours
        5. Requested time matches a valid slot
    """

    doctor = get_doctor(
        doctor_id
    )

    # --------------------------------------------------------
    # Past date
    # --------------------------------------------------------

    if requested_date < date.today():

        raise ValueError(
            "Appointments cannot be booked in the past"
        )

    # --------------------------------------------------------
    # Working day
    # --------------------------------------------------------

    if not is_working_day(
        doctor["slot_days"],
        requested_date
    ):

        raise ValueError(
            f"{doctor['name']} is not available on "
            f"{requested_date.strftime('%A')}"
        )

    # --------------------------------------------------------
    # Doctor working hours
    # --------------------------------------------------------

    start = time.fromisoformat(
        doctor["slot_start"]
    )

    end = time.fromisoformat(
        doctor["slot_end"]
    )

    # --------------------------------------------------------
    # Generate valid slots
    # --------------------------------------------------------

    valid_slots = generate_slots(
        start,
        end
    )

    # --------------------------------------------------------
    # Requested time must be an exact slot
    # --------------------------------------------------------

    if requested_time not in valid_slots:

        raise ValueError(
            "Requested time is not a valid "
            "30-minute appointment slot"
        )


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

    Performs:
        - Doctor validation
        - Date validation
        - Working-day validation
        - Time validation
        - Conflict checking
        - Database insertion
    """

    doctor = get_doctor(
        doctor_id
    )

    # --------------------------------------------------------
    # Validate requested slot
    # --------------------------------------------------------

    validate_slot(
        doctor_id,
        appointment_date,
        appointment_time
    )

    # --------------------------------------------------------
    # Check for an existing booking
    # --------------------------------------------------------

    existing = (
        supabase
        .table("appointments")
        .select("id")
        .eq(
            "doctor_id",
            doctor_id
        )
        .eq(
            "date",
            appointment_date.isoformat()
        )
        .eq(
            "time",
            appointment_time.strftime("%H:%M:%S")
        )
        .eq(
            "status",
            "booked"
        )
        .execute()
    )

    if existing.data:

        raise ValueError(
            "SLOT_UNAVAILABLE"
        )

    # --------------------------------------------------------
    # Insert appointment
    # --------------------------------------------------------

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

    if not response.data:

        raise ValueError(
            "Unable to create appointment"
        )

    appointment = response.data[0]

    # --------------------------------------------------------
    # Return agent-friendly response
    # --------------------------------------------------------

    return {
        "success": True,
        "appointment_id": appointment["id"],
        "patient_name": patient_name,
        "doctor": doctor["name"],
        "department": doctor["department"],
        "date": appointment_date.isoformat(),
        "time": appointment_time.strftime("%H:%M"),
        "status": "booked"
    }


# ============================================================
# FIND PATIENT APPOINTMENTS
# ============================================================

def get_patient_appointments(
    patient_phone: str
):
    """
    Find active appointments belonging to a patient.
    """

    response = (
        supabase
        .table("appointments")
        .select(
            "*, doctors(name, department)"
        )
        .eq(
            "patient_phone",
            patient_phone
        )
        .eq(
            "status",
            "booked"
        )
        .order(
            "date"
        )
        .order(
            "time"
        )
        .execute()
    )

    return response.data


# ============================================================
# CANCEL APPOINTMENT
# ============================================================

def cancel_appointment(
    patient_phone: str
):
    """
    Cancel the patient's active appointment.
    """

    appointments = get_patient_appointments(
        patient_phone
    )

    if not appointments:

        raise ValueError(
            "No active appointment found"
        )

    # For now, use the earliest active appointment.
    appointment = appointments[0]

    # --------------------------------------------------------
    # Update status
    # --------------------------------------------------------

    response = (
        supabase
        .table("appointments")
        .update({
            "status": "cancelled"
        })
        .eq(
            "id",
            appointment["id"]
        )
        .execute()
    )

    if not response.data:

        raise ValueError(
            "Unable to cancel appointment"
        )

    doctor = appointment.get(
        "doctors"
    )

    return {
        "success": True,
        "appointment_id": appointment["id"],
        "doctor": (
            doctor["name"]
            if doctor
            else "Unknown"
        ),
        "date": appointment["date"],
        "time": appointment["time"],
        "status": "cancelled"
    }


# ============================================================
# RESCHEDULE APPOINTMENT
# ============================================================

def reschedule_appointment(
    patient_phone: str,
    new_date: date,
    new_time: time
):

    # --------------------------------------------------------
    # 1. Find the patient's current active appointment
    # --------------------------------------------------------

    response = (
        supabase
        .table("appointments")
        .select("*, doctors(name, department)")
        .eq("patient_phone", patient_phone)
        .eq("status", "booked")
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise ValueError("No active appointment found")

    current_appointment = response.data[0]

    doctor_id = current_appointment["doctor_id"]


    # --------------------------------------------------------
    # 2. Validate that the new date/time is valid
    # --------------------------------------------------------

    doctor = get_doctor(doctor_id)

    # Check whether doctor works on requested date
    if not is_working_day(
        doctor["slot_days"],
        new_date
    ):
        raise ValueError(
            "DOCTOR_NOT_AVAILABLE"
        )

    # Generate valid 30-minute slots
    start = time.fromisoformat(
        doctor["slot_start"]
    )

    end = time.fromisoformat(
        doctor["slot_end"]
    )

    valid_slots = generate_slots(
        start,
        end
    )

    # Check whether requested time is a valid slot
    if new_time not in valid_slots:
        raise ValueError(
            "INVALID_TIME"
        )

    # Check whether the slot is currently free
    available_slots = get_available_slots(
        doctor_id,
        new_date
    )

    if new_time not in available_slots:
        raise ValueError(
            "SLOT_UNAVAILABLE"
        )


    # --------------------------------------------------------
    # 3. Create the new appointment
    # --------------------------------------------------------

    new_appointment_response = (
        supabase
        .table("appointments")
        .insert({
            "patient_name": current_appointment["patient_name"],
            "patient_phone": patient_phone,
            "doctor_id": doctor_id,
            "date": new_date.isoformat(),
            "time": new_time.isoformat(),
            "status": "booked"
        })
        .execute()
    )

    if not new_appointment_response.data:

        raise ValueError(
            "Unable to create new appointment"
        )

    new_appointment = new_appointment_response.data[0]


    # --------------------------------------------------------
    # 4. Mark the old appointment as rescheduled
    # --------------------------------------------------------

    supabase \
        .table("appointments") \
        .update({
            "status": "rescheduled"
        }) \
        .eq(
            "id",
            current_appointment["id"]
        ) \
        .execute()


    # --------------------------------------------------------
    # 5. Return confirmation
    # --------------------------------------------------------

    doctor_info = current_appointment.get("doctors") or {}

    return {
        "success": True,
        "appointment_id": new_appointment["id"],
        "previous_appointment_id": current_appointment["id"],
        "patient_name": current_appointment["patient_name"],
        "doctor": doctor_info.get("name"),
        "department": doctor_info.get("department"),
        "new_date": new_date.isoformat(),
        "new_time": new_time.strftime("%H:%M"),
        "status": "booked"
    }