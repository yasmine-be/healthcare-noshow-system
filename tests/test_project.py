import unittest
from datetime import date, timedelta
import json
import os
from unittest.mock import Mock, patch

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-at-least-32-characters")

import pandas as pd
import numpy as np
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from auth import hash_password
from database import Base, get_db
from feature_engineering import FEATURE_COLUMNS, build_features, build_inference_features
from main import app, model
from schemas import AppointmentCreate, AppointmentInput
from train_model import train_model
from risk import classify_risk
from assistant_agent import generate_advice
from schemas import AgentAdviceRequest
from main import _predict


class FeatureEngineeringTests(unittest.TestCase):
    def test_features_use_only_no_shows_from_prior_dates(self):
        source = pd.DataFrame(
            [
                (4, 1, "2026-01-03", "2026-01-04", "confirmé"),
                (2, 1, "2026-01-01", "2026-01-02", "no_show"),
                (3, 1, "2026-01-02", "2026-01-03", "no_show"),
                (1, 1, "2026-01-01", "2026-01-01", "confirmé"),
            ],
            columns=["id", "patient_id", "date_reservation", "date_rdv", "statut"],
        )

        features = build_features(source).set_index("id")

        self.assertEqual(features.loc[1, "nb_no_show_precedents"], 0)
        self.assertEqual(features.loc[2, "nb_no_show_precedents"], 0)
        self.assertEqual(features.loc[3, "nb_no_show_precedents"], 1)
        self.assertEqual(features.loc[4, "nb_no_show_precedents"], 2)

    def test_inference_features_have_model_column_order(self):
        source = pd.DataFrame(
            [(1, 1, "2026-01-01", "2026-01-03", "confirmé")],
            columns=["id", "patient_id", "date_reservation", "date_rdv", "statut"],
        )
        self.assertEqual(list(build_inference_features(source).columns), FEATURE_COLUMNS)

    def test_appointment_before_reservation_is_rejected(self):
        source = pd.DataFrame(
            [(1, 1, "2026-01-03", "2026-01-01", "confirmé")],
            columns=["id", "patient_id", "date_reservation", "date_rdv", "statut"],
        )
        with self.assertRaisesRegex(ValueError, "before reservation"):
            build_features(source)

    def test_missing_appointment_data_is_rejected(self):
        source = pd.DataFrame(
            [(1, None, "2026-01-01", "2026-01-03", "confirmé")],
            columns=["id", "patient_id", "date_reservation", "date_rdv", "statut"],
        )
        with self.assertRaisesRegex(ValueError, "missing values"):
            build_features(source)


class SchemaTests(unittest.TestCase):
    def test_prediction_inputs_are_bounded(self):
        with self.assertRaises(ValueError):
            AppointmentInput(delai_jours=-1, jour_semaine=0, nb_no_show_precedents=0)
        with self.assertRaises(ValueError):
            AppointmentInput(delai_jours=3, jour_semaine=7, nb_no_show_precedents=0)

    def test_appointment_dates_and_status_are_validated(self):
        with self.assertRaises(ValueError):
            AppointmentCreate(
                patient_id=1,
                doctor_id=1,
                date_reservation=date(2026, 1, 2),
                date_rdv=date(2026, 1, 1),
                motif_visite="Consultation",
                statut="confirmé",
            )
        with self.assertRaises(ValueError):
            AppointmentCreate(
                patient_id=1,
                doctor_id=1,
                date_reservation=date(2026, 1, 1),
                date_rdv=date(2026, 1, 2),
                motif_visite="Consultation",
                statut="unknown",
            )

    def test_risk_bands_are_consistent_at_thresholds(self):
        self.assertEqual(classify_risk(0.2999), "low")
        self.assertEqual(classify_risk(0.3), "medium")
        self.assertEqual(classify_risk(0.6), "high")

    def test_patient_email_is_validated(self):
        from schemas import PatientCreate

        with self.assertRaises(ValueError):
            PatientCreate(
                name="Patient",
                telephone="123456",
                email="not-an-email",
                date_naissance=date(1990, 1, 1),
            )


class TrainingTests(unittest.TestCase):
    def test_training_uses_chronological_holdout_and_reports_metrics(self):
        appointments = pd.DataFrame(
            [
                (
                    index,
                    1 + index % 4,
                    date(2026, 1, 1) + timedelta(days=index),
                    date(2026, 1, 2) + timedelta(days=index),
                    "no_show" if index % 3 == 0 else "confirmé",
                )
                for index in range(60)
            ],
            columns=["id", "patient_id", "date_reservation", "date_rdv", "statut"],
        )
        _, metrics, _ = train_model(appointments)
        self.assertGreater(metrics["train_rows"], 0)
        self.assertGreater(metrics["test_rows"], 0)
        self.assertIn("pr_auc", metrics)
        self.assertIn("brier_score", metrics)

    def test_cancelled_appointments_are_not_used_as_negative_labels(self):
        appointments = pd.DataFrame(
            [
                (index, 1 + index % 4, date(2026, 1, 1) + timedelta(days=index),
                 date(2026, 1, 2) + timedelta(days=index),
                 "annulé" if index == 59 else ("no_show" if index % 3 == 0 else "confirmé"))
                for index in range(60)
            ],
            columns=["id", "patient_id", "date_reservation", "date_rdv", "statut"],
        )
        _, metrics, _ = train_model(appointments)
        self.assertEqual(metrics["train_rows"] + metrics["test_rows"], 59)


class LocalAgentTests(unittest.TestCase):
    def test_agent_sends_only_numeric_features_to_loopback(self):
        response_body = {
            "message": {
                "content": json.dumps(
                    {
                        "summary": "Le risque estimé est modéré.",
                        "actions": ["send_reminder"],
                    }
                )
            }
        }
        response = Mock(status_code=200)
        response.json.return_value = response_body
        advice_request = AgentAdviceRequest(
            risk_score=0.4,
            risk_level="medium",
            delai_jours=5,
            jour_semaine=2,
            nb_no_show_precedents=1,
        )
        with patch("assistant_agent.requests.post", return_value=response) as post:
            advice = generate_advice(advice_request)

        self.assertEqual(advice.actions, ["Envoyer un rappel neutre au patient."])
        self.assertIn("ne constitue pas un avis médical", advice.disclaimer)
        args, kwargs = post.call_args
        self.assertTrue(args[0].startswith("http://127.0.0.1:11434/"))
        user_content = json.loads(kwargs["json"]["messages"][1]["content"])
        self.assertEqual(
            set(user_content),
            {
                "risk_score",
                "risk_level",
                "delai_jours",
                "jour_semaine",
                "nb_no_show_precedents",
            },
        )
        self.assertEqual(kwargs["allow_redirects"], False)

    def test_agent_rejects_non_local_endpoint(self):
        request = AgentAdviceRequest(
            risk_score=0.2,
            risk_level="low",
            delai_jours=2,
            jour_semaine=1,
            nb_no_show_precedents=0,
        )
        with patch("assistant_agent.OLLAMA_BASE_URL", "https://example.com"):
            with patch("assistant_agent.requests.post") as post:
                with self.assertRaises(HTTPException) as error:
                    generate_advice(request)
        self.assertEqual(error.exception.status_code, 503)
        post.assert_not_called()


class MigrationTests(unittest.TestCase):
    def test_migration_creates_missing_schema_without_database_settings(self):
        test_engine = create_engine("sqlite://")
        config = Config("alembic.ini")
        with test_engine.connect() as connection:
            models.Patient.__table__.create(bind=connection)
            connection.execute(
                models.Patient.__table__.insert().values(
                    id=23,
                    name="Test Patient",
                    telephone="123456",
                    email="patient@example.test",
                    date_naissance=date(1990, 1, 1),
                )
            )
            connection.commit()
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        table_names = set(inspect(test_engine).get_table_names())
        self.assertTrue({"patients", "doctors", "appointments", "users", "audit_logs"}.issubset(table_names))
        appointment_indexes = {
            index["name"] for index in inspect(test_engine).get_indexes("appointments")
        }
        self.assertIn("ix_appointments_date_rdv", appointment_indexes)
        with test_engine.connect() as connection:
            preserved_patient = connection.execute(
                models.Patient.__table__.select().where(models.Patient.id == 23)
            ).one()
        self.assertEqual(preserved_patient.name, "Test Patient")
        test_engine.dispose()


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine, autoflush=False)

        def override_get_db():
            with cls.Session() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        with cls.Session() as session:
            session.add(
                models.User(
                    username="test-user",
                    hashed_password=hash_password("test-password-123"),
                    role="staff",
                )
            )
            session.commit()
        cls.client = TestClient(app)
        cls.token = cls.client.post(
            "/auth/login",
            data={"username": "test-user", "password": "test-password-123"},
        ).json()["access_token"]

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=cls.engine)
        cls.engine.dispose()

    def test_protected_prediction_requires_authentication(self):
        response = self.client.post(
            "/predict",
            json={"delai_jours": 2, "jour_semaine": 1, "nb_no_show_precedents": 0},
        )
        self.assertEqual(response.status_code, 401)

    def test_prediction_validates_input_and_returns_risk(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        invalid = self.client.post(
            "/predict",
            headers=headers,
            json={"delai_jours": 2, "jour_semaine": 7, "nb_no_show_precedents": 0},
        )
        self.assertEqual(invalid.status_code, 422)

        response = self.client.post(
            "/predict",
            headers=headers,
            json={"delai_jours": 2, "jour_semaine": 1, "nb_no_show_precedents": 0},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["risk_level"], {"low", "medium", "high"})

    def test_batch_prediction_returns_one_result_per_input(self):
        response = self.client.post(
            "/predict/batch",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "items": [
                    {"delai_jours": 2, "jour_semaine": 1, "nb_no_show_precedents": 0},
                    {"delai_jours": 12, "jour_semaine": 4, "nb_no_show_precedents": 2},
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_rounded_risk_score_and_level_remain_consistent(self):
        fake_model = Mock()
        fake_model.classes_ = [0, 1]
        fake_model.predict.return_value = [1]
        fake_model.predict_proba.return_value = np.array([[0.40004, 0.59996]])
        with patch("main.model", fake_model):
            result = _predict(
                [AppointmentInput(delai_jours=5, jour_semaine=2, nb_no_show_precedents=1)]
            )[0]
        self.assertEqual(result.risk_score, 0.6)
        self.assertEqual(result.risk_level, "high")

    def test_authenticated_api_requests_are_audited_without_payload_data(self):
        response = self.client.post(
            "/predict",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"delai_jours": 2, "jour_semaine": 1, "nb_no_show_precedents": 0},
        )
        self.assertEqual(response.status_code, 200)
        with self.Session() as session:
            audit = session.query(models.AuditLog).filter_by(entity="/predict").first()
            self.assertIsNotNone(audit)
            self.assertEqual(audit.action, "POST")

    @patch("assistant_agent.requests.post")
    def test_local_genai_endpoint_is_protected_and_validates_response(self, post):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "message": {
                "content": json.dumps(
                    {
                        "summary": "Le risque est faible.",
                        "actions": ["no_extra_action"],
                    }
                )
            }
        }
        response = self.client.post(
            "/assistant/no-show",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "risk_score": 0.2,
                "risk_level": "low",
                "delai_jours": 2,
                "jour_semaine": 1,
                "nb_no_show_precedents": 0,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"], "Le risque est faible.")


if __name__ == "__main__":
    unittest.main()
