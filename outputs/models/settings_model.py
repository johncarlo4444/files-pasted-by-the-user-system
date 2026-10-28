"""Persisted application settings shared by all screens."""

from __future__ import annotations

from config import (
    RESTAURANT_ADDRESS,
    RESTAURANT_BRANCH,
    RESTAURANT_CONTACT,
    RESTAURANT_NAME,
    RESTAURANT_TAGLINE,
)
from database import get_connection


BRANDING_VERSION = "2"
BRANDING_DEFAULTS = {
    "restaurant_name": RESTAURANT_NAME,
    "tagline": RESTAURANT_TAGLINE,
    "branch": RESTAURANT_BRANCH,
    "address": RESTAURANT_ADDRESS,
    "contact": RESTAURANT_CONTACT,
}


def get_branding_settings() -> dict[str, str]:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT setting_key, setting_value FROM app_settings")
            saved = {str(key): str(value) for key, value in cursor.fetchall()}
            if saved.get("branding_version") != BRANDING_VERSION:
                # Apply this requested brand refresh once to existing installs;
                # later administrator edits remain saved across restarts.
                for key, value in BRANDING_DEFAULTS.items():
                    cursor.execute(
                        "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s) "
                        "ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)",
                        (key, value),
                    )
                cursor.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)",
                    ("branding_version", BRANDING_VERSION),
                )
                return dict(BRANDING_DEFAULTS)
            return {key: saved.get(key, value) for key, value in BRANDING_DEFAULTS.items()}
        finally:
            cursor.close()
    finally:
        connection.close()


def save_branding_settings(
    restaurant_name: str,
    tagline: str,
    branch: str,
    address: str,
    contact: str,
) -> dict[str, str]:
    settings = {
        "restaurant_name": " ".join(str(restaurant_name).split()),
        "tagline": " ".join(str(tagline).split()),
        "branch": " ".join(str(branch).split()),
        "address": " ".join(str(address).split()),
        "contact": " ".join(str(contact).split()),
    }
    if not settings["restaurant_name"]:
        raise ValueError("Restaurant name cannot be blank.")
    limits = {"restaurant_name": 100, "tagline": 160, "branch": 100, "address": 250, "contact": 60}
    for key, value in settings.items():
        if len(value) > limits[key]:
            raise ValueError(f"{key.replace('_', ' ').capitalize()} must be {limits[key]} characters or fewer.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            for key, value in settings.items():
                cursor.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)",
                    (key, value),
                )
            cursor.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)",
                ("branding_version", BRANDING_VERSION),
            )
        finally:
            cursor.close()
    finally:
        connection.close()
    return settings


def get_restaurant_name() -> str:
    """Compatibility helper for callers that need only the brand title."""
    return get_branding_settings()["restaurant_name"]


def set_restaurant_name(name: str) -> str:
    """Compatibility helper that updates the title and preserves other fields."""
    current = get_branding_settings()
    saved = save_branding_settings(
        name, current["tagline"], current["branch"], current["address"], current["contact"]
    )
    return saved["restaurant_name"]
