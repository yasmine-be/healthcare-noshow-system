from sqlalchemy import text

from database import engine


def main():
    with engine.connect() as connection:
        total, first_date, last_date = connection.execute(
            text(
                "SELECT COUNT(*), MIN(date_rdv), MAX(date_rdv) "
                "FROM appointments"
            )
        ).one()
    print(
        f"Appointments: {total}; date range: "
        f"{first_date or 'n/a'} to {last_date or 'n/a'}"
    )


if __name__ == "__main__":
    main()
