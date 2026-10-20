"""Staff authentication and user account operations."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from database import get_connection


HASH_NAME = "pbkdf2_sha256"
HASH_ITERATIONS = 600_000
VALID_ROLES = ("Admin", "Cashier", "Kitchen Staff")


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, HASH_ITERATIONS)
    return "$".join(
        (HASH_NAME, str(HASH_ITERATIONS), base64.b64encode(salt).decode("ascii"),
         base64.b64encode(digest).decode("ascii"))
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != HASH_NAME:
            return False
        salt = base64.b64decode(salt_text, validate=True)
        expected = base64.b64decode(digest_text, validate=True)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def authenticate(username: str, password: str) -> dict | None:
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT user_id, username, password_hash, role, is_active "
                "FROM users WHERE username = %s",
                (username.strip(),),
            )
            user = cursor.fetchone()
        finally:
            cursor.close()
    finally:
        connection.close()
    if not user or not user["is_active"] or not verify_password(password, user["password_hash"]):
        return None
    return {key: user[key] for key in ("user_id", "username", "role")}


def list_users() -> list[dict]:
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT user_id, username, role, is_active, created_at "
                "FROM users ORDER BY username"
            )
            return cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()


def create_user(username: str, password: str, role: str) -> int:
    username = username.strip()
    if not username:
        raise ValueError("Username is required.")
    if role not in VALID_ROLES:
        raise ValueError("Choose a valid staff role.")
    password_hash = hash_password(password)
    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                (username, password_hash, role),
            )
            return int(cursor.lastrowid)
        finally:
            cursor.close()
    finally:
        connection.close()


def update_user(
    user_id: int,
    username: str,
    role: str,
    is_active: bool,
    password: str | None = None,
) -> None:
    username = username.strip()
    if not username:
        raise ValueError("Username is required.")
    if role not in VALID_ROLES:
        raise ValueError("Choose a valid staff role.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            if password:
                cursor.execute(
                    "UPDATE users SET username=%s, role=%s, is_active=%s, password_hash=%s "
                    "WHERE user_id=%s",
                    (username, role, bool(is_active), hash_password(password), user_id),
                )
            else:
                cursor.execute(
                    "UPDATE users SET username=%s, role=%s, is_active=%s WHERE user_id=%s",
                    (username, role, bool(is_active), user_id),
                )
        finally:
            cursor.close()
    finally:
        connection.close()


def deactivate_user(user_id: int) -> None:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("UPDATE users SET is_active=FALSE WHERE user_id=%s", (user_id,))
        finally:
            cursor.close()
    finally:
        connection.close()
