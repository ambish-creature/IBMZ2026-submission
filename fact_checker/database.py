# File: database.py
# Purpose: Create a local SQLite database for reviewed evidence.

import sqlite3
from pathlib import Path
import requests 
# Store the database alongside this Python file.
DATABASE_PATH = Path(__file__).with_name("evidence.db")


def initialise_database():
    # Create a table for claims and their supporting evidence.
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim TEXT NOT NULL,
                verdict TEXT NOT NULL,
                explanation TEXT NOT NULL,
                source_title TEXT NOT NULL,
                source_url TEXT,
                evidence_text TEXT NOT NULL
            )
        """)


if __name__ == "__main__":
    initialise_database()
    print("Local evidence database created successfully.")
    print(f"Database location: {DATABASE_PATH}")
