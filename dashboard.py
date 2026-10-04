import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import date

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Suivi No-Show", page_icon="🏥", layout="wide")

# CSS 
st.markdown("""
<style>
    /* Fond général */
    .stApp {
        background-color: #F9FAFB;
    }

    /* Header avec dégradé */
    .hero-header {
        background: linear-gradient(135deg, #1E3A5F 0%, #2563EB 100%);
        padding: 2.5rem 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(37, 99, 235, 0.15);
    }
    .main-title {
        font-size: 3rem;
        font-weight: 800;
        color: white;
        margin-bottom: 0.3rem;
        letter-spacing: -1px;
    }
    .subtitle {
        color: #DBEAFE;
        font-size: 1.1rem;
        margin-top: 0;
        font-weight: 400;
    }

    /* Cartes de métriques */
    div[data-testid="stMetric"] {
        background: white;
        border: none;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
        transition: transform 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1);
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.95rem;
        font-weight: 600;
        color: #6B7280;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1E3A5F;
    }

    /* Badges de risque */
    .risk-high {
        background: linear-gradient(135deg, #FEE2E2, #FECACA);
        color: #991B1B;
        padding: 6px 14px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .risk-medium {
        background: linear-gradient(135deg, #FEF3C7, #FDE68A);
        color: #92400E;
        padding: 6px 14px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .risk-low {
        background: linear-gradient(135deg, #D1FAE5, #A7F3D0);
        color: #065F46;
        padding: 6px 14px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 0.85rem;
    }

    /* Tabs plus stylées */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: white;
        border-radius: 10px;
        padding: 10px 20px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563EB;
        color: white;
    }

    /* Sidebar : texte blanc SAUF à l'intérieur des champs de saisie */
    section[data-testid="stSidebar"] {
        background-color: #1E3A5F;
    }
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] p {
        color: white !important;
    }
    section[data-testid="stSidebar"] input {
        color: #1E3A5F !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero-header">
    <p class="main-title">🏥 Suivi des Rendez-vous</p>
    <p class="subtitle">Prédiction du risque de no-show par intelligence artificielle</p>
</div>
""", unsafe_allow_html=True)

#  Données 
appointments = requests.get(f"{API_URL}/appointments").json()
patients = requests.get(f"{API_URL}/patients").json()

df = pd.DataFrame(appointments)
df_patients = pd.DataFrame(patients)
df = df.merge(df_patients[['id', 'name']], left_on='patient_id', right_on='id', suffixes=('', '_patient'))
df = df.rename(columns={'name': 'patient_name'})
df['date_reservation'] = pd.to_datetime(df['date_reservation'])
df['date_rdv'] = pd.to_datetime(df['date_rdv'])

# Sidebar 
with st.sidebar:
    st.header("⚙️ Filtres")
    selected_date = st.date_input("Date à analyser", value=date(2026, 7, 15))

day_appointments = df[df['date_rdv'].dt.date == selected_date].copy()

if day_appointments.empty:
    st.info(f"Aucun rendez-vous le {selected_date}.")
else:
    risk_scores, risk_levels = [], []
    for _, row in day_appointments.iterrows():
        delai = (row['date_rdv'] - row['date_reservation']).days
        jour = row['date_rdv'].dayofweek
        historique = df[
            (df['patient_id'] == row['patient_id']) &
            (df['date_rdv'] < row['date_rdv']) &
            (df['statut'] == 'no_show')
        ].shape[0]

        response = requests.post(f"{API_URL}/predict", json={
            "delai_jours": delai, "jour_semaine": jour, "nb_no_show_precedents": historique
        })
        result = response.json()
        risk_scores.append(result['risk_score'])
        risk_levels.append(result['risk_level'])

    day_appointments['risk_score'] = risk_scores
    day_appointments['risk_level'] = risk_levels
    day_appointments = day_appointments.sort_values('risk_score', ascending=False)

    # KPIs 
    col1, col2, col3 = st.columns(3)
    col1.metric("📅 Rendez-vous du jour", len(day_appointments))
    col2.metric("⚠️ Absences probables", (day_appointments['risk_score'] > 0.5).sum())
    col3.metric("📊 Risque moyen", f"{day_appointments['risk_score'].mean():.0%}")

    st.divider()

    # Tabs 
    tab1, tab2, tab3 = st.tabs(["📋 Rendez-vous du jour", "📊 Statistiques globales", "🔍 Recherche patient"])

    with tab1:
        def risk_badge(level):
            css_class = {"high": "risk-high", "medium": "risk-medium", "low": "risk-low"}[level]
            label = {"high": "Élevé", "medium": "Moyen", "low": "Faible"}[level]
            return f'<span class="{css_class}">{label}</span>'

        st.subheader(f"Rendez-vous du {selected_date}")
        for _, row in day_appointments.iterrows():
            c1, c2, c3, c4 = st.columns([3, 3, 2, 2])
            c1.write(f"**#{row['patient_id']}** — {row['patient_name']}")
            c2.write(row['motif_visite'])
            c3.write(f"{row['risk_score']:.0%}")
            c4.markdown(risk_badge(row['risk_level']), unsafe_allow_html=True)

    with tab2:
        st.subheader("Taux de no-show par mois")
        df['mois'] = df['date_rdv'].dt.to_period('M').astype(str)
        monthly_stats = df.groupby('mois')['statut'].apply(lambda x: (x == 'no_show').mean() * 100).reset_index()
        monthly_stats.columns = ['Mois', 'Taux de no-show (%)']
        fig = px.bar(monthly_stats, x='Mois', y='Taux de no-show (%)', color='Taux de no-show (%)',
                     color_continuous_scale=['#10B981', '#F59E0B', '#EF4444'])
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Taux de no-show par motif de visite")
        motif_stats = df.groupby('motif_visite')['statut'].apply(lambda x: (x == 'no_show').mean() * 100).reset_index()
        motif_stats.columns = ['Motif', 'Taux de no-show (%)']
        fig2 = px.bar(motif_stats, x='Motif', y='Taux de no-show (%)', color='Taux de no-show (%)',
                      color_continuous_scale=['#10B981', '#F59E0B', '#EF4444'])
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        st.subheader("Rechercher l'historique d'un patient")
        patient_names = df_patients['name'].tolist()
        selected_patient = st.selectbox("Choisir un patient", patient_names)

        patient_id = df_patients[df_patients['name'] == selected_patient]['id'].values[0]
        patient_history = df[df['patient_id'] == patient_id].sort_values('date_rdv')

        nb_no_show = (patient_history['statut'] == 'no_show').sum()
        nb_total = len(patient_history)
        st.metric("Historique de no-show", f"{nb_no_show} / {nb_total} rendez-vous")

        st.dataframe(patient_history[['date_rdv', 'motif_visite', 'statut']])