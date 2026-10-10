"""Database connection helper for the LMS project."""

import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Open a connection to the configured existing database."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "library_db"),
        autocommit=False,
    )
