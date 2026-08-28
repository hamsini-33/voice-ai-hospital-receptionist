from datetime import date, time

from fastapi import (
    FastAPI,
    Query,
    HTTPException
)

from pydantic import BaseModel

from .database import supabase

from .services import (
    get_available_slots,
    book_appointment,
    get_patient_appointments,
    cancel_appointment,
    reschedule_appointment
)

app = FastAPI(
    title="Voice AI Hospital Receptionist",
    version="1.0.0"
)


# ============================================================
# REQUEST MODELS
# ============================================================

class BookingRequest(BaseModel):

    patient_name: str
    patient_phone: str
    doctor_id: int
    appointment_date: date
    appointment_time: time

class RescheduleRequest(BaseModel):

    patient_phone: str
    new_date: date
    new_time: time

# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok"
    }


# ============================================================
# GET DOCTORS
# ============================================================

@app.get("/doctors")
def get_doctors(
    department: str | None = Query(
        default=None
    )
):

    query = (
        supabase
        .table("doctors")
        .select("*")
    )

    if department:

        query = query.ilike(
            "department",
            f"%{department}%"
        )

    response = query.execute()

    return response.data


# ============================================================
# GET AVAILABLE SLOTS
# ============================================================

@app.get("/availability")
def availability(
    doctor_id: int,
    date: date
):

    try:

        slots = get_available_slots(
            doctor_id,
            date
        )

        return {
            "doctor_id": doctor_id,
            "date": date.isoformat(),
            "available_slots": [
                slot.strftime("%H:%M")
                for slot in slots
            ]
        }

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


# ============================================================
# BOOK APPOINTMENT
# ============================================================

@app.post("/appointments/book")
def create_booking(
    request: BookingRequest
):

    try:

        result = book_appointment(
            patient_name=request.patient_name,
            patient_phone=request.patient_phone,
            doctor_id=request.doctor_id,
            appointment_date=request.appointment_date,
            appointment_time=request.appointment_time
        )

        return result

    except ValueError as e:

        if str(e) == "SLOT_UNAVAILABLE":

            raise HTTPException(
                status_code=409,
                detail=(
                    "The requested slot is "
                    "no longer available"
                )
            )

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@app.post("/appointments/cancel")
def cancel_booking(
    patient_phone: str
):

    try:

        result = cancel_appointment(
            patient_phone
        )

        return result

    except ValueError as e:

        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

@app.post("/appointments/reschedule")
@app.post("/appointments/reschedule")
def reschedule_booking(
    request: RescheduleRequest
):

    try:

        result = reschedule_appointment(
            patient_phone=request.patient_phone,
            new_date=request.new_date,
            new_time=request.new_time
        )

        return result

    except ValueError as e:

        error = str(e)

        if error == "SLOT_UNAVAILABLE":

            raise HTTPException(
                status_code=409,
                detail="The requested slot is not available"
            )

        if error == "DOCTOR_NOT_AVAILABLE":

            raise HTTPException(
                status_code=400,
                detail="Doctor is not available on that date"
            )

        if error == "INVALID_TIME":

            raise HTTPException(
                status_code=400,
                detail="Requested time is not a valid appointment slot"
            )

        if error == "No active appointment found":

            raise HTTPException(
                status_code=404,
                detail="No active appointment found"
            )

        raise HTTPException(
            status_code=400,
            detail=error
        )

@app.get("/appointments/{patient_phone}")
def get_appointments(
    patient_phone: str
):

    appointments = get_patient_appointments(
        patient_phone
    )

    return {
        "patient_phone": patient_phone,
        "appointments": appointments
    }