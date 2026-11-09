import os
import unittest
from datetime import date

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-at-least-32-characters")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from auth import create_access_token
from database import Base, get_db
from main import app


class DashboardAPITests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.token = create_access_token({"sub": "dashboard-test", "role": "staff"})
        with self.Session() as db:
            db.add_all(
                [
                    models.User(
                        username="dashboard-test",
                        hashed_password="not-used",
                        role="staff",
                    ),
                    models.Patient(
                        id=1,
                        name="Patient One",
                        telephone="111",
                        email="one@example.com",
                        date_naissance=date(1990, 1, 1),
                    ),
                    models.Patient(
                        id=2,
                        name="Patient Two",
                        telephone="222",
                        email="two@example.com",
                        date_naissance=date(1985, 1, 1),
                    ),
                    models.Doctor(
                        id=1,
                        name="Doctor",
                        telephone="333",
                        email="doctor@example.com",
                        departement="General",
                    ),
                ]
            )
            db.add_all(
                [
                    models.Appointment(
                        id=1,
                        patient_id=1,
                        doctor_id=1,
                        date_reservation=date(2026, 1, 1),
                        date_rdv=date(2026, 1, 5),
                        motif_visite="Consultation",
                        statut="no_show",
                    ),
                    models.Appointment(
                        id=2,
                        patient_id=1,
                        doctor_id=1,
                        date_reservation=date(2026, 1, 4),
                        date_rdv=date(2026, 1, 10),
                        motif_visite="Consultation",
                        statut="no_show",
                    ),
                    models.Appointment(
                        id=3,
                        patient_id=1,
                        doctor_id=1,
                        date_reservation=date(2026, 1, 4),
                        date_rdv=date(2026, 1, 10),
                        motif_visite="Consultation",
                        statut="confirmed",
                    ),
                    models.Appointment(
                        id=4,
                        patient_id=2,
                        doctor_id=1,
                        date_reservation=date(2026, 2, 1),
                        date_rdv=date(2026, 2, 10),
                        motif_visite="Follow-up",
                        statut="attended",
                    ),
                ]
            )
            db.commit()
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_dashboard_endpoints_require_authentication(self):
        for path in (
            "/dashboard/statistics",
            "/dashboard/appointments?appointment_date=2026-01-10",
            "/dashboard/patients",
            "/dashboard/patients/1/history",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)

    def test_daily_appointments_are_date_filtered_and_pageable(self):
        response = self.client.get(
            "/dashboard/appointments",
            headers=self.headers,
            params={"appointment_date": "2026-01-10", "limit": 1, "offset": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        appointment = response.json()[0]
        self.assertEqual(appointment["id"], 3)
        self.assertEqual(appointment["patient_name"], "Patient One")
        self.assertEqual(appointment["delai_jours"], 6)
        self.assertEqual(appointment["jour_semaine"], 5)
        self.assertEqual(appointment["nb_no_show_precedents"], 1)

        other_day = self.client.get(
            "/dashboard/appointments",
            headers=self.headers,
            params={"appointment_date": "2026-01-05"},
        )
        self.assertEqual([row["id"] for row in other_day.json()], [1])

    def test_dashboard_aggregates_include_counts_but_no_patient_identity(self):
        response = self.client.get("/dashboard/statistics", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["latest_date"], "2026-02-10")
        self.assertEqual(
            data["monthly"],
            [
                {"month": "2026-01", "total": 3, "no_show": 2},
                {"month": "2026-02", "total": 1, "no_show": 0},
            ],
        )
        self.assertEqual(
            data["motifs"],
            [
                {"motif_visite": "Consultation", "total": 3, "no_show": 2},
                {"motif_visite": "Follow-up", "total": 1, "no_show": 0},
            ],
        )
        serialized = str(data)
        self.assertNotIn("patient_id", serialized)
        self.assertNotIn("Patient One", serialized)
        self.assertNotIn("Patient Two", serialized)

    def test_patient_history_returns_a_bounded_page_and_total_counts(self):
        response = self.client.get(
            "/dashboard/patients/1/history",
            headers=self.headers,
            params={"limit": 1, "offset": 1},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["no_show_count"], 2)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["id"], 2)

    def test_patient_lookup_is_searchable_and_bounded(self):
        response = self.client.get(
            "/dashboard/patients",
            headers=self.headers,
            params={"query": "patient", "limit": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0], {"id": 1, "name": "Patient One"})

        filtered = self.client.get(
            "/dashboard/patients",
            headers=self.headers,
            params={"query": "Two", "limit": 100},
        )
        self.assertEqual(
            filtered.json(),
            [{"id": 2, "name": "Patient Two"}],
        )

    def test_dashboard_date_and_limit_parameters_are_strictly_validated(self):
        invalid_requests = (
            ("/dashboard/appointments", {"appointment_date": "2026-02-30"}),
            ("/dashboard/appointments", {"appointment_date": "2026-01-10", "limit": 0}),
            (
                "/dashboard/appointments",
                {"appointment_date": "2026-01-10", "limit": 501},
            ),
            ("/dashboard/patients/1/history", {"limit": 501}),
            ("/dashboard/patients", {"limit": 101}),
            ("/dashboard/patients", {"query": "x" * 101}),
        )
        for path, params in invalid_requests:
            with self.subTest(path=path, params=params):
                response = self.client.get(
                    path, headers=self.headers, params=params
                )
                self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
