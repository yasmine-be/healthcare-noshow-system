from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from risk import classify_risk

class PatientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    telephone: str = Field(min_length=1, max_length=20)
    email: EmailStr = Field(max_length=100)
    date_naissance: date

    @model_validator(mode="after")
    def validate_birth_date(self):
        if self.date_naissance > date.today():
            raise ValueError("Birth date cannot be in the future")
        return self


class PatientOut(PatientCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class DoctorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    telephone: str = Field(min_length=1, max_length=20)
    email: EmailStr = Field(max_length=100)
    departement: str = Field(min_length=1, max_length=100)


class DoctorOut(DoctorCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class AppointmentCreate(BaseModel):
    patient_id: int = Field(gt=0)
    doctor_id: int = Field(gt=0)
    date_reservation: date
    date_rdv: date
    motif_visite: str = Field(min_length=1, max_length=255)
    statut: Literal[
        "no_show",
        "confirmé",
        "confirmed",
        "scheduled",
        "cancelled",
        "annulé",
        "présent",
        "attended",
        "completed",
    ]

    @model_validator(mode="after")
    def validate_appointment_dates(self):
        if self.date_rdv < self.date_reservation:
            raise ValueError("Appointment date cannot be before reservation date")
        return self


class AppointmentOut(AppointmentCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class AppointmentInput(BaseModel):
    delai_jours: int = Field(ge=0, le=3650)
    jour_semaine: int = Field(ge=0, le=6)
    nb_no_show_precedents: int = Field(ge=0, le=10000)


class PredictionBatch(BaseModel):
    items: list[AppointmentInput] = Field(min_length=1, max_length=500)


class RiskPrediction(BaseModel):
    no_show_predicted: bool
    risk_score: float = Field(ge=0, le=1)
    risk_level: Literal["low", "medium", "high"]


class AgentAdviceRequest(BaseModel):
    risk_score: float = Field(ge=0, le=1)
    risk_level: Literal["low", "medium", "high"]
    delai_jours: int = Field(ge=0, le=3650)
    jour_semaine: int = Field(ge=0, le=6)
    nb_no_show_precedents: int = Field(ge=0, le=10000)

    @model_validator(mode="after")
    def validate_risk_band(self):
        if self.risk_level != classify_risk(self.risk_score):
            raise ValueError("risk_level does not match risk_score")
        return self


class AgentAdvice(BaseModel):
    summary: str = Field(min_length=1, max_length=500)
    actions: list[str] = Field(min_length=1, max_length=4)
    disclaimer: str = Field(min_length=1, max_length=300)


class AgentAdviceDraft(BaseModel):
    summary: str = Field(min_length=1, max_length=500)
    actions: list[
        Literal[
            "send_reminder",
            "request_confirmation",
            "staff_call",
            "no_extra_action",
        ]
    ] = Field(min_length=1, max_length=3)