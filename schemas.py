from datetime import date, datetime
from pydantic import BaseModel, ConfigDict
from datetime import date, datetime

class PatientCreate(BaseModel):
    name: str
    telephone: str
    email: str
    date_naissance: date

class PatientOut(PatientCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class DoctorCreate(BaseModel):
    name: str
    telephone: str
    email: str
    departement: str

class DoctorOut(DoctorCreate):
    id:int
    model_config = ConfigDict(from_attributes=True)

class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    date_reservation: date
    date_rdv: datetime
    motif_visite: str
    statut: str

class  AppointmentOut(AppointmentCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)