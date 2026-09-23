from sqlalchemy import create_engine
import pandas as pd

import os
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
df = pd.read_sql("SELECT * FROM appointments", engine)

# Convertir les colonnes en datetime
df['date_reservation'] = pd.to_datetime(df['date_reservation'])
df['date_rdv'] = pd.to_datetime(df['date_rdv'])

# Feature 1 : délai en jours entre la réservation et le RDV

df['delai_jours'] = (df['date_rdv']-df["date_reservation"]).dt.days

# Feature 2 : jour de la semaine du RDV (0=lundi, 6=dimanche)

df['jour_semaine'] = df["date_rdv"].dt.dayofweek

# Feature 3 : la cible (target) que le modèle doit prédire
df['no_show'] = (df['statut'] == 'no_show').astype(int)

print(df[['patient_id', 'delai_jours', 'jour_semaine', 'no_show']])

df['no_show_cumsum'] = (df.groupby('patient_id')['no_show'].cumsum()).astype(int)
df['nb_no_show_precedents'] = (df.groupby('patient_id')['no_show_cumsum'].shift(1).fillna(0)).astype(int)
print(df['no_show_cumsum'])
print(df[['patient_id', 'date_rdv', 'nb_no_show_precedents']])


print(df[df['patient_id'] == 1][['patient_id', 'date_rdv', 'no_show', 'no_show_cumsum', 'nb_no_show_precedents']])
print(df[df['patient_id'] == 9][['patient_id', 'date_rdv', 'no_show', 'no_show_cumsum', 'nb_no_show_precedents']])