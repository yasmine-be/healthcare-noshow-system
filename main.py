from datetime import date
from pathlib import Path

import joblib
import pandas as pd
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import case, extract, func
from sqlalchemy.orm import Session, aliased

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


@protected.get("/dashboard/appointments")
def dashboard_appointments(
    appointment_date: date,
    db: Session = Depends(get_db),
    limit: int = Query(default=500, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    appointment = models.Appointment
    previous_appointment = aliased(models.Appointment)
    prior_no_shows = (
        db.query(func.count(previous_appointment.id))
        .filter(
            previous_appointment.patient_id == appointment.patient_id,
            previous_appointment.date_rdv < appointment_date,
            previous_appointment.statut == "no_show",
        )
        .correlate(appointment)
        .scalar_subquery()
    )
    rows = (
        db.query(
            models.Appointment,
            models.Patient.name.label("patient_name"),
            prior_no_shows.label("nb_no_show_precedents"),
        )
        .join(models.Patient, models.Patient.id == models.Appointment.patient_id)
        .filter(models.Appointment.date_rdv == appointment_date)
        .order_by(models.Appointment.date_rdv, models.Appointment.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "patient_id": row.patient_id,
            "patient_name": patient_name,
            "doctor_id": row.doctor_id,
            "date_reservation": row.date_reservation,
            "date_rdv": row.date_rdv,
            "motif_visite": row.motif_visite,
            "statut": row.statut,
            "delai_jours": (row.date_rdv - row.date_reservation).days,
            "jour_semaine": row.date_rdv.weekday(),
            "nb_no_show_precedents": previous_no_shows or 0,
        }
        for row, patient_name, previous_no_shows in rows
    ]


@protected.get("/dashboard/patients")
def search_dashboard_patients(
    db: Session = Depends(get_db),
    query: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    patients = db.query(models.Patient.id, models.Patient.name)
    if query:
        patients = patients.filter(models.Patient.name.ilike(f"%{query}%"))
    return [
        {"id": patient_id, "name": name}
        for patient_id, name in patients.order_by(models.Patient.name, models.Patient.id)
        .offset(offset)
        .limit(limit)
        .all()
    ]


@protected.get("/dashboard/statistics")
def dashboard_statistics(db: Session = Depends(get_db)):
    appointment = models.Appointment
    no_show_count = func.sum(case((appointment.statut == "no_show", 1), else_=0))
    monthly_rows = (
        db.query(
            extract("year", appointment.date_rdv).label("year"),
            extract("month", appointment.date_rdv).label("month"),
            func.count(appointment.id).label("total"),
            no_show_count.label("no_show"),
        )
        .group_by(extract("year", appointment.date_rdv), extract("month", appointment.date_rdv))
        .order_by(extract("year", appointment.date_rdv), extract("month", appointment.date_rdv))
        .all()
    )
    motif_rows = (
        db.query(
            appointment.motif_visite,
            func.count(appointment.id).label("total"),
            no_show_count.label("no_show"),
        )
        .group_by(appointment.motif_visite)
        .order_by(appointment.motif_visite)
        .all()
    )
    return {
        "latest_date": db.query(func.max(appointment.date_rdv)).scalar(),
        "monthly": [
            {
                "month": f"{int(year):04d}-{int(month):02d}",
                "total": total,
                "no_show": no_show or 0,
            }
            for year, month, total, no_show in monthly_rows
        ],
        "motifs": [
            {
                "motif_visite": motif,
                "total": total,
                "no_show": no_show or 0,
            }
            for motif, total, no_show in motif_rows
        ],
    }


@protected.get("/dashboard/patients/{patient_id}/history")
def dashboard_patient_history(
    patient_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(default=500, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    if patient_id < 1:
        raise HTTPException(status_code=422, detail="patient_id must be positive")
    patient_appointments = db.query(models.Appointment).filter(
        models.Appointment.patient_id == patient_id
    )
    if db.query(models.Patient.id).filter(models.Patient.id == patient_id).first() is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    total, no_show_count = (
        db.query(
            func.count(models.Appointment.id),
            func.coalesce(
                func.sum(case((models.Appointment.statut == "no_show", 1), else_=0)),
                0,
            ),
        )
        .filter(models.Appointment.patient_id == patient_id)
        .one()
    )
    rows = (
        patient_appointments.order_by(
            models.Appointment.date_rdv, models.Appointment.id
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "no_show_count": no_show_count,
        "items": rows,
    }


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
