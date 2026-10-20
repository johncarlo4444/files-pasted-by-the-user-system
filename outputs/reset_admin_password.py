"""Reset the local admin account password without changing application data."""

from __future__ import annotations

from getpass import getpass

from database import get_connection
from models.user_model import hash_password


def main() -> None:
    password = getpass("New password for admin (at least 8 characters): ")
    confirmation = getpass("Confirm new password: ")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")
    if password != confirmation:
        raise SystemExit("The passwords do not match.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT user_id FROM users WHERE username=%s", ("admin",))
            row = cursor.fetchone()
            password_hash = hash_password(password)
            if row:
                cursor.execute(
                    "UPDATE users SET password_hash=%s, role='Admin', is_active=TRUE "
                    "WHERE user_id=%s",
                    (password_hash, row[0]),
                )
            else:
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role, is_active) "
                    "VALUES (%s, %s, 'Admin', TRUE)",
                    ("admin", password_hash),
                )
        finally:
            cursor.close()
    finally:
        connection.close()

    print("Admin password reset. Sign in with username 'admin' and the new password.")


if __name__ == "__main__":
    main()
