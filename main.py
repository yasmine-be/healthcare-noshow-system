from datetime import date
from pathlib import Path

import joblib
import pandas as pd
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import models
import schemas
from assistant_agent import generate_advice
from auth import create_access_token, get_current_user, verify_password
from database import get_db
from feature_engineering import FEATURE_COLUMNS
from risk import classify_risk

MODEL_PATH = Path(__file__).with_name("model.pkl")
model = joblib.load(MODEL_PATH)

app = FastAPI(title="Healthcare No-Show API")


@app.post("/auth/login", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = (
        db.query(models.User)
        .filter(models.User.username == form_data.username)
        .first()
    )
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    db.add(
        models.AuditLog(
            actor_id=user.id,
            action="POST",
            entity="/auth/login",
        )
    )
    db.commit()
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


protected = APIRouter(dependencies=[Depends(get_current_user)])


def _predict(features: list[schemas.AppointmentInput]) -> list[schemas.RiskPrediction]:
    frame = pd.DataFrame(
        [item.model_dump() for item in features],
        columns=FEATURE_COLUMNS,
    )
    predictions = model.predict(frame)
    class_index = list(model.classes_).index(1)
    probabilities = model.predict_proba(frame)[:, class_index]
    results = []
    for prediction, probability in zip(predictions, probabilities):
        score = round(float(probability), 4)
        results.append(
            schemas.RiskPrediction(
                no_show_predicted=bool(prediction),
                risk_score=score,
                risk_level=classify_risk(score),
            )
        )
    return results


@protected.post("/predict", response_model=schemas.RiskPrediction)
def predict(data: schemas.AppointmentInput):
    return _predict([data])[0]


@protected.post("/predict/batch", response_model=list[schemas.RiskPrediction])
def predict_batch(batch: schemas.PredictionBatch):
    return _predict(batch.items)


@protected.post("/assistant/no-show", response_model=schemas.AgentAdvice)
def no_show_assistant(request: schemas.AgentAdviceRequest):
    return generate_advice(request)


@protected.post("/patients", response_model=schemas.PatientOut)
def create_patient(patient: schemas.PatientCreate, db: Session = Depends(get_db)):
    new_patient = models.Patient(**patient.model_dump())
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)
    return new_patient


@protected.get("/patients", response_model=list[schemas.PatientOut])
def list_patients(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return (
        db.query(models.Patient)
        .order_by(models.Patient.id)
        .offset(offset)
        .limit(limit)
        .all()
    )


@protected.get("/patients/{patient_id}", response_model=schemas.PatientOut)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@protected.put("/patients/{patient_id}", response_model=schemas.PatientOut)
def update_patient(
    patient_id: int, data: schemas.PatientCreate, db: Session = Depends(get_db)
):
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    for key, value in data.model_dump().items():
        setattr(patient, key, value)
    db.commit()
    db.refresh(patient)
    return patient


@protected.post("/doctors", response_model=schemas.DoctorOut)
def create_doctor(doctor: schemas.DoctorCreate, db: Session = Depends(get_db)):
    new_doctor = models.Doctor(**doctor.model_dump())
    db.add(new_doctor)
    db.commit()
    db.refresh(new_doctor)
    return new_doctor


@protected.get("/doctors", response_model=list[schemas.DoctorOut])
def list_doctors(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return (
        db.query(models.Doctor)
        .order_by(models.Doctor.id)
        .offset(offset)
        .limit(limit)
        .all()
    )


@protected.get("/doctors/{doctor_id}", response_model=schemas.DoctorOut)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


@protected.put("/doctors/{doctor_id}", response_model=schemas.DoctorOut)
def update_doctor(
    doctor_id: int, data: schemas.DoctorCreate, db: Session = Depends(get_db)
):
    doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    for key, value in data.model_dump().items():
        setattr(doctor, key, value)
    db.commit()
    db.refresh(doctor)
    return doctor


@protected.post("/appointments", response_model=schemas.AppointmentOut)
def create_appointment(
    appt: schemas.AppointmentCreate, db: Session = Depends(get_db)
):
    if db.query(models.Patient.id).filter(models.Patient.id == appt.patient_id).first() is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    if db.query(models.Doctor.id).filter(models.Doctor.id == appt.doctor_id).first() is None:
        raise HTTPException(status_code=404, detail="Doctor not found")

    new_appt = models.Appointment(**appt.model_dump())
    db.add(new_appt)
    db.commit()
    db.refresh(new_appt)
    return new_appt


@protected.get("/appointments", response_model=list[schemas.AppointmentOut])
def list_appointments(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    from_date: date | None = None,
    to_date: date | None = None,
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date cannot be after to_date")
    query = db.query(models.Appointment)
    if from_date:
        query = query.filter(models.Appointment.date_rdv >= from_date)
    if to_date:
        query = query.filter(models.Appointment.date_rdv <= to_date)
    return (
        query.order_by(models.Appointment.date_rdv, models.Appointment.id)
        .offset(offset)
        .limit(limit)
        .all()
    )


@protected.get("/appointments/{appointment_id}", response_model=schemas.AppointmentOut)
def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appointment = (
        db.query(models.Appointment)
        .filter(models.Appointment.id == appointment_id)
        .first()
    )
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


@protected.put("/appointments/{appointment_id}", response_model=schemas.AppointmentOut)
def update_appointment(
    appointment_id: int, data: schemas.AppointmentCreate, db: Session = Depends(get_db)
):
    appointment = (
        db.query(models.Appointment)
        .filter(models.Appointment.id == appointment_id)
        .first()
    )
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if db.query(models.Patient.id).filter(models.Patient.id == data.patient_id).first() is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    if db.query(models.Doctor.id).filter(models.Doctor.id == data.doctor_id).first() is None:
        raise HTTPException(status_code=404, detail="Doctor not found")

    for key, value in data.model_dump().items():
        setattr(appointment, key, value)
    db.commit()
    db.refresh(appointment)
    return appointment


app.include_router(protected)
