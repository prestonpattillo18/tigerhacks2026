"""A small, dependency-free test of the database and CRUD functions."""

from pathlib import Path
import tempfile

# Import through the package so this test also works when run as a script.
import sys

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.database import database as database_module
from backend.database.crud import (
    add_exercise,
    add_routine_day,
    create_routine,
    create_user,
    get_conversation_history,
    get_current_routine,
    get_user_by_email,
    save_message,
)
from backend.database.database import create_database, get_connection


def run_tests() -> None:
    """Check the tables and one complete user-to-routine-to-exercise flow."""
    original_path = database_module.DATABASE_PATH
    with tempfile.TemporaryDirectory() as temporary_directory:
        database_module.DATABASE_PATH = Path(temporary_directory) / "test_fitness.db"
        try:
            # Start with the older table definitions that main.py creates itself.
            connection = get_connection()
            try:
                connection.executescript(
                    """
                    CREATE TABLE profile (
                        id INTEGER PRIMARY KEY, name TEXT, age TEXT, height TEXT,
                        weight TEXT, goals TEXT, experience TEXT, frequency TEXT
                    );
                    CREATE TABLE chat_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT
                    );
                    CREATE TABLE current_routine (
                        id INTEGER PRIMARY KEY, routine_json TEXT
                    );
                    INSERT INTO profile VALUES (1, '', '', '', '', '', '', '');
                    """
                )
            finally:
                connection.close()
            create_database()

            # Inspect SQLite's built-in catalog to confirm all required tables exist.
            connection = get_connection()
            try:
                table_names = {
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
            finally:
                connection.close()
            assert {
                "Users",
                "Routines",
                "RoutineDays",
                "Exercises",
                "ChatMessages",
                "CalendarSync",
            }.issubset(table_names)

            user_id = create_user(
                "test@example.com",
                "test-password",
                "Taylor Test",
                goals=["build strength"],
                weekly_frequency=3,
            )
            user = get_user_by_email("test@example.com")
            assert user is not None
            assert user["id"] == user_id
            assert user["goals"] == ["build strength"]

            week_start = "2026-09-21"
            # Simulate the profile update statement used directly by main.py.
            connection = get_connection()
            try:
                connection.execute(
                    """UPDATE profile SET name = ?, age = ?, goals = ?,
                       experience = ?, frequency = ? WHERE id = 1""",
                    ("Updated in main.py", "35", "mobility, energy", "beginner", "4"),
                )
                connection.commit()
            finally:
                connection.close()
            user = get_user_by_email("test@example.com")
            assert user is not None
            assert user["name"] == "Updated in main.py"
            assert user["age"] == 35
            assert user["goals"] == ["mobility", "energy"]

            # Simulate the JSON routine written by main.py's chat handler.
            connection = get_connection()
            try:
                connection.execute(
                    """INSERT OR REPLACE INTO current_routine (id, routine_json)
                       VALUES (1, ?)""",
                    ('{"Monday": {"label": "Main Day", "exercises": ["Walk"]}}',),
                )
                connection.commit()
            finally:
                connection.close()
            legacy_routine = get_current_routine(user_id, week_start)
            assert legacy_routine is not None
            assert legacy_routine["days"][0]["label"] == "Main Day"
            assert legacy_routine["days"][0]["exercises"][0]["name"] == "Walk"

            routine_id = create_routine(user_id, week_start)
            day_id = add_routine_day(routine_id, "Monday", "Full Body")
            exercise_id = add_exercise(
                day_id, "Chair squats", sets=3, reps="10", notes="Move slowly."
            )
            routine = get_current_routine(user_id, week_start)
            assert routine is not None
            assert routine["id"] == routine_id
            assert routine["days"][0]["id"]
            assert routine["days"][0]["exercises"][0]["id"] == exercise_id
            assert routine["days"][0]["exercises"][0]["day_id"] == day_id
            connection = get_connection()
            try:
                legacy_json = connection.execute(
                    "SELECT routine_json FROM current_routine WHERE id = 1"
                ).fetchone()["routine_json"]
                assert "Chair squats 3x10" in legacy_json
            finally:
                connection.close()

            # Simulate the legacy chat insert, then check it alongside backend messages.
            connection = get_connection()
            try:
                connection.execute(
                    "INSERT INTO chat_history (role, content) VALUES (?, ?)",
                    ("user", "Message from main.py"),
                )
                connection.commit()
            finally:
                connection.close()
            save_message(user_id, "user", "Can I make this easier?")
            save_message(user_id, "assistant", "Try two sets to start.")
            history = get_conversation_history(user_id)
            assert len(history) == 3
            assert history[0]["content"] == "Message from main.py"
            assert history[1]["role"] == "user"
            assert history[2]["content"] == "Try two sets to start."
        finally:
            # Restore the normal path even if an assertion fails.
            database_module.DATABASE_PATH = original_path

    print("All database checks passed.")


if __name__ == "__main__":
    run_tests()
