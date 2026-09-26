"""SQLite connection helpers and the database schema."""

from pathlib import Path
import sqlite3


# main.py opens app_data.db relative to the project root; use that same file.
DATABASE_PATH = Path(__file__).resolve().parents[2] / "app_data.db"


def get_connection() -> sqlite3.Connection:
    """Return an open connection; the caller is responsible for closing it."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    # SQLite disables foreign-key checks by default, so enable them per connection.
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_database() -> None:
    """Create the database file and all tables if they do not already exist."""
    connection = get_connection()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                age INTEGER,
                sex TEXT,
                height_cm REAL,
                weight_kg REAL,
                goals TEXT,
                experience_level TEXT,
                weekly_frequency INTEGER,
                injuries TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS Routines (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                week_start TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'initial',
                UNIQUE (user_id, week_start),
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS RoutineDays (
                id INTEGER PRIMARY KEY,
                routine_id INTEGER NOT NULL,
                day_of_week TEXT NOT NULL,
                label TEXT NOT NULL,
                FOREIGN KEY (routine_id) REFERENCES Routines(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS Exercises (
                id INTEGER PRIMARY KEY,
                day_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                sets INTEGER,
                reps TEXT,
                duration_sec INTEGER,
                notes TEXT,
                FOREIGN KEY (day_id) REFERENCES RoutineDays(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS ChatMessages (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                linked_routine_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                FOREIGN KEY (linked_routine_id) REFERENCES Routines(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS CalendarSync (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL CHECK (provider IN ('google', 'apple')),
                last_synced TEXT,
                UNIQUE (user_id, provider),
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
            );

            -- These three tables keep the existing main.py screens compatible.
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY,
                name TEXT,
                age TEXT,
                height TEXT,
                weight TEXT,
                goals TEXT,
                experience TEXT,
                frequency TEXT
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                content TEXT,
                timestamp TEXT,
                linked_routine_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS current_routine (
                id INTEGER PRIMARY KEY,
                routine_json TEXT,
                backend_routine_id INTEGER
            );
            """
        )
        # Add compatibility columns to app_data.db files created by older main.py versions.
        _add_column_if_missing(connection, "chat_history", "timestamp", "TEXT")
        _add_column_if_missing(
            connection, "chat_history", "linked_routine_id", "INTEGER"
        )
        _add_column_if_missing(
            connection, "current_routine", "backend_routine_id", "INTEGER"
        )
        # main.py assumes that a single profile row already exists.
        connection.execute(
            """INSERT OR IGNORE INTO profile
               (id, name, age, height, weight, goals, experience, frequency)
               VALUES (1, '', '', '', '', '', '', '')"""
        )
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        raise
    finally:
        # A SQLite connection's context manager does not close it automatically.
        connection.close()


def _add_column_if_missing(
    connection: sqlite3.Connection, table_name: str, column_name: str, column_type: str
) -> None:
    """Add a new nullable column to an older table without losing its data."""
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )
