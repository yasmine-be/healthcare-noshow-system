from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import pandas as pd

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
   
