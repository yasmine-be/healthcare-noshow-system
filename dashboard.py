import os
from datetime import date

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from feature_engineering import build_features
from risk import HIGH_RISK_LOWER_BOUND

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
PAGE_SIZE = 500
REQUEST_TIMEOUT = 10

st.set_page_config(page_title="Suivi No-Show", page_icon="🏥", layout="wide")
st.markdown(
    """
    <style>
        .stApp { background-color: #F9FAFB; }
        .hero-header {
            background: linear-gradient(135deg, #1E3A5F 0%, #2563EB 100%);
            padding: 2rem; border-radius: 20px; margin-bottom: 1.5rem;
        }
        .main-title { font-size: 2.5rem; font-weight: 800; color: white; }
        .subtitle { color: #DBEAFE; font-size: 1.1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <div class="hero-header">
        <p class="main-title">Suivi des rendez-vous</p>
        <p class="subtitle">Tableau de bord du risque de no-show</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if "token" not in st.session_state:
    st.session_state.token = None
if "expired" not in st.session_state:
    st.session_state.expired = False


def api_request(method, path, *, authenticated=True, **kwargs):
    headers = kwargs.pop("headers", {})
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    if authenticated:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        response = requests.request(
            method,
            f"{API_URL}{path}",
            headers=headers,
            timeout=timeout,
            **kwargs,
        )
    except requests.RequestException as exc:
        st.error(f"Impossible de joindre l'API ({exc}). Vérifiez qu'elle est démarrée.")
        st.stop()
    if response.status_code == 401 and authenticated:
        st.session_state.token = None
        st.session_state.expired = True
        st.rerun()
    try:
        response.raise_for_status()
    except requests.HTTPError:
        st.error(f"L'API a répondu avec le statut {response.status_code}.")
        st.stop()
    return response.json()


def fetch_all(path):
    records = []
    offset = 0
    while True:
        page = api_request(
            "GET",
            path,
            params={"limit": PAGE_SIZE, "offset": offset},
        )
        records.extend(page)
        if len(page) < PAGE_SIZE:
            return records
        offset += PAGE_SIZE


if st.session_state.token is None:
    st.subheader("Connexion")
    if st.session_state.expired:
        st.warning("Votre session a expiré. Veuillez vous reconnecter.")
    with st.form("login_form"):
        username = st.text_input("Nom d'utilisateur")
        password = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Se connecter")
    if submitted:
        try:
            response = requests.post(
                f"{API_URL}/auth/login",
                data={"username": username, "password": password},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            st.error(f"Impossible de joindre l'API ({exc}).")
        else:
            if response.status_code == 200:
                st.session_state.token = response.json()["access_token"]
                st.session_state.expired = False
                st.rerun()
            elif response.status_code == 401:
                st.error("Identifiants incorrects.")
            else:
                st.error(f"Échec de connexion à l'API (statut {response.status_code}).")
    st.stop()

with st.sidebar:
    st.header("Filtres")
    if st.button("Se déconnecter"):
        st.session_state.token = None
        st.rerun()

appointments = fetch_all("/appointments")
patients = fetch_all("/patients")
df = pd.DataFrame(
    appointments,
    columns=[
        "id",
        "patient_id",
        "doctor_id",
        "date_reservation",
        "date_rdv",
        "motif_visite",
        "statut",
    ],
)
df_patients = pd.DataFrame(patients, columns=["id", "name"])
if not df.empty:
    df["date_reservation"] = pd.to_datetime(df["date_reservation"])
    df["date_rdv"] = pd.to_datetime(df["date_rdv"])
    features = build_features(df)
    df = df.merge(
        df_patients[["id", "name"]],
        left_on="patient_id",
        right_on="id",
        how="left",
        suffixes=("", "_patient"),
    ).rename(columns={"name": "patient_name"})
    df["patient_name"] = df["patient_name"].fillna("Patient inconnu")
    default_date = df["date_rdv"].max().date()
else:
    features = pd.DataFrame(columns=["id", "date_rdv", "patient_id", "delai_jours",
                                     "jour_semaine", "nb_no_show_precedents"])
    default_date = date.today()

selected_date = st.sidebar.date_input("Date à analyser", value=default_date)
day_appointments = (
    df[df["date_rdv"].dt.date == selected_date].copy() if not df.empty else df.copy()
)

if day_appointments.empty:
    st.info(f"Aucun rendez-vous le {selected_date}.")
else:
    day_features = features[features["date_rdv"].dt.date == selected_date]
    batch = [
        {
            "delai_jours": int(row.delai_jours),
            "jour_semaine": int(row.jour_semaine),
            "nb_no_show_precedents": int(row.nb_no_show_precedents),
        }
        for row in day_features.itertuples()
    ]
    predictions = []
    for start in range(0, len(batch), PAGE_SIZE):
        predictions.extend(
            api_request(
                "POST",
                "/predict/batch",
                json={"items": batch[start : start + PAGE_SIZE]},
            )
        )
    prediction_frame = pd.DataFrame(predictions)
    day_appointments = day_appointments.merge(
        features[
            [
                "id",
                "delai_jours",
                "jour_semaine",
                "nb_no_show_precedents",
            ]
        ].assign(_feature_order=range(len(features))),
        on="id",
        how="left",
    ).sort_values("_feature_order")
    day_appointments["risk_score"] = prediction_frame["risk_score"].to_numpy()
    day_appointments["risk_level"] = prediction_frame["risk_level"].to_numpy()
    day_appointments = day_appointments.sort_values("risk_score", ascending=False)

    col1, col2, col3 = st.columns(3)
    col1.metric("Rendez-vous du jour", len(day_appointments))
    col2.metric(
        "Risque élevé",
        (day_appointments["risk_score"] >= HIGH_RISK_LOWER_BOUND).sum(),
    )
    col3.metric("Risque moyen", f"{day_appointments['risk_score'].mean():.0%}")
    st.subheader(f"Rendez-vous du {selected_date}")
    st.dataframe(
        day_appointments[
            ["patient_id", "patient_name", "motif_visite", "risk_score", "risk_level"]
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.subheader("Assistant GenAI local")
    st.caption(
        "Les suggestions sont générées localement à partir des indicateurs de risque. "
        "Elles ne remplacent pas le jugement du personnel et doivent être validées."
    )
    selected_index = st.selectbox(
        "Rendez-vous à examiner",
        options=list(range(len(day_appointments))),
        format_func=lambda index: (
            f"Patient #{day_appointments.iloc[index]['patient_id']} — "
            f"{day_appointments.iloc[index]['risk_score']:.0%} de risque"
        ),
    )
    if st.button("Générer une suggestion IA"):
        selected = day_appointments.iloc[selected_index]
        advice = api_request(
            "POST",
            "/assistant/no-show",
            timeout=90,
            json={
                "risk_score": float(selected["risk_score"]),
                "risk_level": selected["risk_level"],
                "delai_jours": int(selected["delai_jours"]),
                "jour_semaine": int(selected["jour_semaine"]),
                "nb_no_show_precedents": int(
                    selected["nb_no_show_precedents"]
                ),
            },
        )
        st.info(advice["summary"])
        st.markdown("\n".join(f"- {action}" for action in advice["actions"]))
        st.caption(advice["disclaimer"])

if not df.empty:
    tab_stats, tab_patient = st.tabs(["Statistiques globales", "Recherche patient"])
    with tab_stats:
        monthly_stats = (
            df.assign(mois=df["date_rdv"].dt.to_period("M").astype(str))
            .groupby("mois")["statut"]
            .apply(lambda status: status.eq("no_show").mean() * 100)
            .rename("Taux de no-show (%)")
            .reset_index()
        )
        st.subheader("Taux de no-show par mois")
        st.plotly_chart(
            px.bar(monthly_stats, x="mois", y="Taux de no-show (%)"),
            use_container_width=True,
        )
        motif_stats = (
            df.groupby("motif_visite")["statut"]
            .apply(lambda status: status.eq("no_show").mean() * 100)
            .rename("Taux de no-show (%)")
            .reset_index()
        )
        st.subheader("Taux de no-show par motif")
        st.plotly_chart(
            px.bar(motif_stats, x="motif_visite", y="Taux de no-show (%)"),
            use_container_width=True,
        )

    with tab_patient:
        patient_options = sorted(
            ((int(row.id), str(row.name)) for row in df_patients.itertuples()),
            key=lambda item: (item[1].casefold(), item[0]),
        )
        if not patient_options:
            st.info("Aucun patient enregistré.")
        else:
            selected_id = st.selectbox(
                "Choisir un patient",
                options=[option[0] for option in patient_options],
                format_func=lambda patient_id: next(
                    name for current_id, name in patient_options if current_id == patient_id
                ),
            )
            patient_history = df[df["patient_id"] == selected_id].sort_values("date_rdv")
            no_shows = patient_history["statut"].eq("no_show").sum()
            st.metric("Historique de no-show", f"{no_shows} / {len(patient_history)}")
            st.dataframe(
                patient_history[["date_rdv", "motif_visite", "statut"]],
                use_container_width=True,
                hide_index=True,
            )
