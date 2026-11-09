import unittest
from importlib import import_module
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

import models


class QueryIndexTests(unittest.TestCase):
    def test_appointment_date_index_matches_list_order(self):
        indexes = {
            index.name: tuple(column.name for column in index.columns)
            for index in models.Appointment.__table__.indexes
        }

        self.assertIn(
            "ix_appointments_date_rdv",
            indexes,
        )
        self.assertEqual(
            indexes["ix_appointments_date_rdv"],
            ("date_rdv", "id"),
        )

    def test_migration_replaces_legacy_index_idempotently_without_data_loss(self):
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TABLE appointments ("
                        "id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL, "
                        "doctor_id INTEGER NOT NULL, date_reservation DATE NOT NULL, "
                        "date_rdv DATE NOT NULL, motif_visite VARCHAR NOT NULL, "
                        "statut VARCHAR NOT NULL)"
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX ix_appointments_date_rdv "
                        "ON appointments (date_rdv)"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO appointments VALUES "
                        "(1, 2, 3, '2026-01-01', '2026-01-02', 'consultation', 'confirmé')"
                    )
                )

            config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
            with engine.connect() as connection:
                config.attributes["connection"] = connection
                command.stamp(config, "20261109_01")
                command.upgrade(config, "head")

                migration_context = MigrationContext.configure(connection)
                with Operations.context(migration_context):
                    migration = import_module(
                        "migrations.versions.20261109_02_appointment_date_order_index"
                    )
                    migration.upgrade()

                indexes = {
                    index["name"]: index["column_names"]
                    for index in inspect(connection).get_indexes("appointments")
                }
                self.assertEqual(
                    indexes["ix_appointments_date_rdv"],
                    ["date_rdv", "id"],
                )
                self.assertEqual(
                    connection.execute(
                        text("SELECT id, patient_id FROM appointments")
                    ).one(),
                    (1, 2),
                )
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
