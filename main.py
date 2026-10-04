from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import pandas as pd
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models, schemas

app = FastAPI()
model = joblib.load('model.pkl')

class AppointmentInput(BaseModel):
    delai_jours: int
    jour_semaine: int
    nb_no_show_precedents: int

@app.post("/predict")
def predict(data: AppointmentInput):
    # Transformer les données reçues en DataFrame pandas
    df = pd.DataFrame(
        [[data.delai_jours, data.jour_semaine, data.nb_no_show_precedents]],
        columns=['delai_jours', 'jour_semaine', 'nb_no_show_precedents']
    )
    prediction = model.predict(df)[0]
    proba = model.predict_proba(df)[0][1]  # probabilité de la classe "1" (no_show)

    if proba < 0.3:
      risk_level = "low"
    elif proba < 0.6:
      risk_level = "medium"
    else:
      risk_level = "high"

    return {
    "no_show_predicted": bool(prediction),
    "risk_score": round(float(proba), 2),
    "risk_level": risk_level
}
   
@app.post("/patients", response_model=schemas.PatientOut)
def create_patient(patient: schemas.PatientCreate, db: Session = Depends(get_db)):
    new_patient = models.Patient(**patient.model_dump())
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)
    return new_patient

@app.get("/patients", response_model=list[schemas.PatientOut])
def list_patients(db: Session = Depends(get_db)):
    return db.query(models.Patient).all()

@app.get("/patients/{patient_id}", response_model=schemas.PatientOut)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient

@app.put("/patients/{patient_id}", response_model=schemas.PatientOut)
def update_patient(patient_id: int, data: schemas.PatientCreate, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    for key, value in data.model_dump().items():
        setattr(patient, key, value)
    db.commit()
    db.refresh(patient)
    return patient
@app.post("/doctors", response_model=schemas.DoctorOut)
def create_doctor(doctor: schemas.DoctorCreate, db: Session = Depends(get_db)):
    new_doctor = models.Doctor(**doctor.model_dump())
    db.add(new_doctor)
    db.commit()
    db.refresh(new_doctor)
    return new_doctor

@app.get("/doctors", response_model=list[schemas.DoctorOut])
def list_doctors(db: Session = Depends(get_db)):
    return db.query(models.Doctor).all()

@app.get("/doctors/{doctor_id}", response_model=schemas.DoctorOut)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor

@app.put("/doctors/{doctor_id}", response_model=schemas.DoctorOut)
def update_doctor(doctor_id: int, data: schemas.DoctorCreate, db: Session = Depends(get_db)):
    doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    for key, value in data.model_dump().items():
        setattr(doctor, key, value)
    db.commit()
    db.refresh(doctor)
    return doctor

@app.post("/appointments", response_model=schemas.AppointmentOut)
def create_appointment(appt: schemas.AppointmentCreate, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.id == appt.patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    doctor = db.query(models.Doctor).filter(models.Doctor.id == appt.doctor_id).first()
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")

    new_appt = models.Appointment(**appt.model_dump())
    db.add(new_appt)
    db.commit()
    db.refresh(new_appt)
    return new_appt
@app.get("/appointments", response_model=list[schemas.AppointmentOut])
def list_appointments(db: Session = Depends(get_db)):
    return db.query(models.Appointment).all()

@app.get("/appointments/{appointment_id}", response_model=schemas.AppointmentOut)
def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appointment = db.query(models.Appointment).filter(models.Appointment.id == appointment_id).first()
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment

@app.put("/appointments/{appointment_id}", response_model=schemas.AppointmentOut)
def update_appointment(appointment_id: int, data: schemas.AppointmentCreate, db: Session = Depends(get_db)):
    appointment = db.query(models.Appointment).filter(models.Appointment.id == appointment_id).first()
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    for key, value in data.model_dump().items():
            setattr(appointment, key, value)
    db.commit()
    db.refresh(appointment)
    return appointment
          
          
        