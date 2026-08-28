from datetime import date, time

from pydantic import BaseModel, Field


class BookAppointmentRequest(BaseModel):
    patient_name: str = Field(min_length=2)
    patient_phone: str = Field(min_length=8)
    doctor_id: int
    date: date
    time: time


class RescheduleAppointmentRequest(BaseModel):
    patient_phone: str = Field(min_length=8)
    new_date: date
    new_time: time


class CancelAppointmentRequest(BaseModel):
    patient_phone: str = Field(min_length=8)