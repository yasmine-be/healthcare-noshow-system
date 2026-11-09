import argparse
import random
from datetime import date, timedelta

from sqlalchemy import text

from database import engine

MOTIFS = [
    "Consultation générale",
    "Suivi",
    "Vaccination",
    "Contrôle annuel",
    "Urgence mineure",
]


def generate_appointments(patient_ids, doctor_ids, count=250, seed=42):
    if not patient_ids or not doctor_ids:
        raise ValueError("Create at least one patient and one doctor before generating data")
    rng = random.Random(seed)
    rows = []
    for _ in range(count):
        reservation_date = date(2026, 6, 1) + timedelta(days=rng.randint(0, 60))
        delay = rng.randint(1, 45)
        appointment_date = reservation_date + timedelta(days=delay)
        probability = min(0.05 + delay * 0.015, 0.7)
        status = "no_show" if rng.random() < probability else "confirmé"
        rows.append(
            {
                "patient_id": rng.choice(patient_ids),
                "doctor_id": rng.choice(doctor_ids),
                "date_reservation": reservation_date,
                "date_rdv": appointment_date,
                "motif_visite": rng.choice(MOTIFS),
                "statut": status,
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description="Generate clearly synthetic appointment data.")
    parser.add_argument("--count", type=int, default=250)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete all existing appointments before inserting synthetic data.",
    )
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")

    with engine.begin() as connection:
        patient_ids = connection.execute(
            text("SELECT id FROM patients ORDER BY id")
        ).scalars().all()
        doctor_ids = connection.execute(
            text("SELECT id FROM doctors ORDER BY id")
        ).scalars().all()
        rows = generate_appointments(patient_ids, doctor_ids, args.count, args.seed)
        if args.replace:
            connection.execute(text("TRUNCATE TABLE appointments RESTART IDENTITY"))
        connection.execute(
            text(
                "INSERT INTO appointments "
                "(patient_id, doctor_id, date_reservation, date_rdv, motif_visite, statut) "
                "VALUES (:patient_id, :doctor_id, :date_reservation, :date_rdv, "
                ":motif_visite, :statut)"
            ),
            rows,
        )
    print(f"Generated {len(rows)} synthetic appointments (seed={args.seed}).")


if __name__ == "__main__":
    main()
