import getpass

from database import SessionLocal
import models
from auth import hash_password


def main():
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    role = input("Role (admin/staff) [staff]: ").strip().lower() or "staff"

    if not username or len(username) > 50:
        raise ValueError("Username must contain between 1 and 50 characters")
    if len(password) < 8 or len(password.encode("utf-8")) > 72:
        raise ValueError("Password must contain at least 8 characters and at most 72 UTF-8 bytes")
    if role not in {"admin", "staff"}:
        raise ValueError("Role must be either 'admin' or 'staff'")

    with SessionLocal() as db:
        if db.query(models.User).filter(models.User.username == username).first():
            raise ValueError("Cet utilisateur existe déjà.")
        db.add(
            models.User(
                username=username,
                hashed_password=hash_password(password),
                role=role,
            )
        )
        db.commit()
    print(f"Utilisateur '{username}' créé.")


if __name__ == "__main__":
    main()