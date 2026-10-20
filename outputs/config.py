"""Configuration for the offline fast-food ordering system.

Environment variables can override the development defaults. Set
FASTFOOD_DB_PASSWORD before deploying this application outside a local demo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseConfig:
    host: str = os.getenv("FASTFOOD_DB_HOST", "localhost")
    port: int = int(os.getenv("FASTFOOD_DB_PORT", "3306"))
    user: str = os.getenv("FASTFOOD_DB_USER", "root")
    password: str = os.getenv("FASTFOOD_DB_PASSWORD", "ilagan")
    database: str = os.getenv("FASTFOOD_DB_NAME", "fastfood_db")
    connection_timeout: int = int(os.getenv("FASTFOOD_DB_TIMEOUT", "5"))


DB_CONFIG = DatabaseConfig()
CURRENCY_SYMBOL = "₱"
CURRENCY_CODE = "PHP"
RESTAURANT_NAME = os.getenv("FASTFOOD_RESTAURANT_NAME", "WORLD FAST FOOD EXPRESS")
RESTAURANT_BRANCH = os.getenv("FASTFOOD_BRANCH", "Main Branch")
RESTAURANT_ADDRESS = os.getenv("FASTFOOD_ADDRESS", "Manila, Philippines")
RESTAURANT_CONTACT = os.getenv("FASTFOOD_CONTACT", "Not configured")
