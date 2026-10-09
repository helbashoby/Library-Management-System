"""
Database connection for library_db.

Reads MySQL settings from environment variables (see .env.example).
"""

import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Open a new connection to the existing library_db database."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "library_db"),
    )
