import pandas as pd

FEATURE_COLUMNS = [
    "delai_jours",
    "jour_semaine",
    "nb_no_show_precedents",
]
OBSERVED_ATTENDANCE_STATUSES = {
    "no_show",
    "confirmé",
    "confirmed",
    "présent",
    "attended",
    "completed",
}


def build_features(appointments: pd.DataFrame) -> pd.DataFrame:
    required = {"patient_id", "date_reservation", "date_rdv", "statut"}
    missing = required.difference(appointments.columns)
    if missing:
        raise ValueError(f"Missing appointment columns: {', '.join(sorted(missing))}")

    frame = appointments.copy()
    if frame[list(required)].isna().any().any():
        raise ValueError("Appointment feature inputs cannot contain missing values")
    frame["date_reservation"] = pd.to_datetime(frame["date_reservation"])
    frame["date_rdv"] = pd.to_datetime(frame["date_rdv"])
    if "id" not in frame:
        frame["id"] = range(len(frame))
    elif frame["id"].duplicated().any():
        raise ValueError("Appointment IDs must be unique")

    frame = frame.sort_values(
        ["patient_id", "date_rdv", "id"], kind="stable"
    ).reset_index(drop=True)
    frame["delai_jours"] = (
        frame["date_rdv"].dt.normalize() - frame["date_reservation"].dt.normalize()
    ).dt.days
    if (frame["delai_jours"] < 0).any():
        raise ValueError("Appointment date cannot be before reservation date")
    frame["jour_semaine"] = frame["date_rdv"].dt.dayofweek
    frame["no_show"] = frame["statut"].eq("no_show").astype("int8")

    daily = (
        frame.groupby(["patient_id", frame["date_rdv"].dt.date], sort=False)["no_show"]
        .sum()
        .rename("daily_no_shows")
        .reset_index()
        .rename(columns={"date_rdv": "appointment_date"})
    )
    daily["nb_no_show_precedents"] = daily.groupby(
        "patient_id", sort=False
    )["daily_no_shows"].transform(lambda counts: counts.cumsum().shift(1, fill_value=0))
    frame["appointment_date"] = frame["date_rdv"].dt.date
    frame = frame.merge(
        daily[["patient_id", "appointment_date", "nb_no_show_precedents"]],
        on=["patient_id", "appointment_date"],
        how="left",
        validate="many_to_one",
    )
    frame["nb_no_show_precedents"] = frame["nb_no_show_precedents"].astype("int64")
    return frame


def build_inference_features(appointments: pd.DataFrame) -> pd.DataFrame:
    features = build_features(appointments)
    return features[FEATURE_COLUMNS]
