import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text


import os
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

with engine.connect() as conn:
    conn.execute(text("TRUNCATE TABLE appointments RESTART IDENTITY;"))
    conn.commit()

motifs = ['Consultation générale', 'Suivi', 'Vaccination', 'Contrôle annuel', 'Urgence mineure']
nb_patients = 15
nb_doctors = 8
nb_appointments = 250

rows = []
for i in range(nb_appointments):
    patient_id = random.randint(1, nb_patients)
    doctor_id = random.randint(1, nb_doctors)
    date_reservation = datetime(2026, 6, 1) + timedelta(days=random.randint(0, 60))

    delai = random.randint(1, 45)
    date_rdv = date_reservation + timedelta(days=delai, hours=random.randint(8, 17))

    proba_base = 0.05
    proba_no_show = min(proba_base + delai * 0.015, 0.7)
    is_no_show = random.random() < proba_no_show
    statut = 'no_show' if is_no_show else 'confirmé'

    rows.append((patient_id, doctor_id, date_reservation.date(), date_rdv, random.choice(motifs), statut))


# Insertion en base
with engine.connect() as conn:
    for row in rows:
        conn.execute(
            text("""INSERT INTO appointments (patient_id, doctor_id, date_reservation, date_rdv, motif_visite, statut)
                     VALUES (:p, :d, :dr, :dt, :m, :s)"""),
            {"p": row[0], "d": row[1], "dr": row[2], "dt": row[3], "m": row[4], "s": row[5]}
        )
    conn.commit()

print(f"{nb_appointments} rendez-vous générés avec succès.")
