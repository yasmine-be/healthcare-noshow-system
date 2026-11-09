import joblib
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sqlalchemy import text

from database import engine
from feature_engineering import (
    FEATURE_COLUMNS,
    OBSERVED_ATTENDANCE_STATUSES,
    build_features,
)

MODEL_PATH = "model.pkl"


def train_model(appointments: pd.DataFrame):
    observed = appointments[
        appointments["statut"].isin(OBSERVED_ATTENDANCE_STATUSES)
    ].copy()
    if observed.empty:
        raise ValueError("No completed or no-show appointments are available for training")
    features = build_features(observed)
    if len(features) < 2:
        raise ValueError("At least two appointments are required to train a model")

    dates = features["date_rdv"].drop_duplicates().sort_values().tolist()
    if len(dates) < 2:
        raise ValueError("At least two appointment dates are required for time-based evaluation")

    split_date = dates[max(1, min(len(dates) - 1, int(len(dates) * 0.8)))]
    train = features[features["date_rdv"] < split_date]
    test = features[features["date_rdv"] >= split_date]
    if train.empty or test.empty or train["no_show"].nunique() < 2:
        raise ValueError(
            "The chronological training partition must contain both no-show classes"
        )

    model = xgb.XGBClassifier(
        eval_metric="logloss",
        n_estimators=200,
        random_state=42,
        n_jobs=1,
    )
    model.fit(train[FEATURE_COLUMNS], train["no_show"])

    predictions = model.predict(test[FEATURE_COLUMNS])
    probabilities = model.predict_proba(test[FEATURE_COLUMNS])[
        :, list(model.classes_).index(1)
    ]
    metrics = {
        "split_date": str(split_date),
        "train_rows": len(train),
        "test_rows": len(test),
        "accuracy": float(accuracy_score(test["no_show"], predictions)),
        "precision": float(precision_score(test["no_show"], predictions, zero_division=0)),
        "recall": float(recall_score(test["no_show"], predictions, zero_division=0)),
        "f1": float(f1_score(test["no_show"], predictions, zero_division=0)),
        "roc_auc": (
            float(roc_auc_score(test["no_show"], probabilities))
            if test["no_show"].nunique() == 2
            else None
        ),
        "pr_auc": float(average_precision_score(test["no_show"], probabilities)),
        "brier_score": float(brier_score_loss(test["no_show"], probabilities)),
    }
    return model, metrics, classification_report(
        test["no_show"], predictions, zero_division=0
    )


def main():
    with engine.connect() as connection:
        appointments = pd.read_sql(
            text(
                "SELECT id, patient_id, date_reservation, date_rdv, statut "
                "FROM appointments ORDER BY date_rdv, id"
            ),
            connection,
        )
    model, metrics, report = train_model(appointments)
    joblib.dump(model, MODEL_PATH)
    print("Evaluation metrics:", metrics)
    print(report)
    print(f"Saved trained model to {MODEL_PATH}")


if __name__ == "__main__":
    main()
