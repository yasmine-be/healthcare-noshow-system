from sqlalchemy import Column, Integer, String, Date, TIMESTAMP, ForeignKey
from database import Base

class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    telephone = Column(String(20))
    email = Column(String(100))
    date_naissance = Column(Date)

class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    telephone = Column(String(20))
    email = Column(String(100))
    departement = Column(String(100))

class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    date_reservation = Column(Date, nullable=False)
    date_rdv = Column(Date, nullable=False)
    motif_visite = Column(String, nullable=False)
    statut = Column(String, nullable=False)