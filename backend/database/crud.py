"""Small database functions that Kivy screens can call directly."""

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import json
import sqlite3
from typing import Iterator, List, Optional, cast

from .database import get_connection
from .models import (
    CalendarSyncRecord,
    ChatMessageRecord,
    RoutineRecord,
    UserRecord,
)


def _now_iso() -> str:
    """Return the current UTC time as an ISO-formatted string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def _database_connection() -> Iterator[sqlite3.Connection]:
    """Commit successful work, roll back database errors, and always close."""
    connection = get_connection()
    try:
        with connection:
            yield connection
    except sqlite3.Error as error:
        # Exceptions are Python's way to report failures; re-raise so the screen can show an error.
        connection.rollback()
        raise
    finally:
        # Connections hold file resources, so close them even when a query fails.
        connection.close()


def _user_from_row(row: sqlite3.Row) -> UserRecord:
    """Convert a SQLite row to a Kivy-friendly dictionary."""
    user = dict(row)
    try:
        user["goals"] = json.loads(user["goals"] or "[]")
    except (json.JSONDecodeError, TypeError):
        user["goals"] = [goal.strip() for goal in (user["goals"] or "").split(",") if goal.strip()]
    return cast(UserRecord, user)


def _apply_legacy_profile(
    connection: sqlite3.Connection, user: UserRecord
) -> UserRecord:
    """Overlay non-empty values written by main.py's older profile screen."""
    row = connection.execute(
        "SELECT * FROM profile WHERE id = ?", (user["id"],)
    ).fetchone()
    if row is None:
        return user

    if row["name"]:
        user["name"] = row["name"]
    for legacy_key, user_key, converter in (
        ("age", "age", int),
        ("height", "height_cm", float),
        ("weight", "weight_kg", float),
        ("frequency", "weekly_frequency", int),
    ):
        if row[legacy_key]:
            try:
                user[user_key] = converter(row[legacy_key])
            except (TypeError, ValueError):
                pass
    if row["goals"]:
        user["goals"] = [goal.strip() for goal in row["goals"].split(",") if goal.strip()]
    if row["experience"]:
        user["experience_level"] = row["experience"]
    return user


def _sync_legacy_routine(
    connection: sqlite3.Connection, routine_id: int
) -> None:
    """Write a routine snapshot in the JSON shape that main.py displays."""
    routine = connection.execute(
        "SELECT * FROM Routines WHERE id = ?", (routine_id,)
    ).fetchone()
    if routine is None or routine["user_id"] != 1:
        return

    routine_json = {}
    days = connection.execute(
        "SELECT * FROM RoutineDays WHERE routine_id = ? ORDER BY id", (routine_id,)
    ).fetchall()
    for day in days:
        exercises = connection.execute(
            "SELECT * FROM Exercises WHERE day_id = ? ORDER BY id", (day["id"],)
        ).fetchall()
        exercise_names = []
        for exercise in exercises:
            name = exercise["name"]
            if exercise["sets"] is not None and exercise["reps"]:
                name += f" {exercise['sets']}x{exercise['reps']}"
            elif exercise["duration_sec"]:
                name += f" ({exercise['duration_sec']} sec)"
            exercise_names.append(name)
        routine_json[day["day_of_week"]] = {
            "label": day["label"],
            "exercises": exercise_names,
        }

    connection.execute(
        """INSERT INTO current_routine (id, routine_json, backend_routine_id)
           VALUES (1, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               routine_json = excluded.routine_json,
               backend_routine_id = excluded.backend_routine_id""",
        (json.dumps(routine_json), routine_id),
    )


def _routine_from_legacy_row(row: sqlite3.Row, week_start: str) -> Optional[RoutineRecord]:
    """Convert main.py's JSON routine into the nested shape used by the backend."""
    try:
        legacy_days = json.loads(row["routine_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        return None

    days = []
    for day_index, (day_name, details) in enumerate(legacy_days.items(), start=1):
        day_id = -day_index
        exercises = []
        for exercise_index, exercise in enumerate(details.get("exercises", []), start=1):
            exercise_name = exercise if isinstance(exercise, str) else exercise.get("name", "")
            exercises.append(
                {
                    "id": -exercise_index,
                    "day_id": day_id,
                    "name": exercise_name,
                    "sets": None,
                    "reps": None,
                    "duration_sec": None,
                    "notes": "",
                }
            )
        days.append(
            {
                "id": day_id,
                "routine_id": row["id"],
                "day_of_week": day_name,
                "label": details.get("label", day_name),
                "exercises": exercises,
            }
        )
    return cast(
        RoutineRecord,
        {
            "id": row["id"],
            "user_id": 1,
            "week_start": week_start,
            "generated_at": "",
            "source": "chat_update",
            "days": days,
        },
    )


def create_user(
    email: str,
    password: str,
    name: str,
    age: Optional[int] = None,
    sex: Optional[str] = None,
    height_cm: Optional[float] = None,
    weight_kg: Optional[float] = None,
    goals: Optional[List[str]] = None,
    experience_level: Optional[str] = None,
    weekly_frequency: Optional[int] = None,
    injuries: Optional[str] = None,
) -> int:
    """Create an account and return its ID. Hash passwords before real-world use."""
    now = _now_iso()
    with _database_connection() as connection:
        cursor = connection.execute(
            """INSERT INTO Users (
                email, password, name, age, sex, height_cm, weight_kg, goals,
                experience_level, weekly_frequency, injuries, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                email,
                password,
                name,
                age,
                sex,
                height_cm,
                weight_kg,
                json.dumps(goals or []),
                experience_level,
                weekly_frequency,
                injuries,
                now,
                now,
            ),
        )
        user_id = int(cursor.lastrowid)
        if user_id == 1:
            # Keep the original onboarding screen's single profile row populated.
            connection.execute(
                """UPDATE profile SET name = ?, age = ?, height = ?, weight = ?,
                   goals = ?, experience = ?, frequency = ?
                   WHERE id = 1 AND COALESCE(name, '') = ''""",
                (
                    name,
                    str(age or ""),
                    str(height_cm or ""),
                    str(weight_kg or ""),
                    ", ".join(goals or []),
                    experience_level or "",
                    str(weekly_frequency or ""),
                ),
            )
        return user_id


def get_user_by_email(email: str) -> Optional[UserRecord]:
    """Find an account by email, or return None when it does not exist."""
    with _database_connection() as connection:
        row = connection.execute(
            "SELECT * FROM Users WHERE email = ?", (email,)
        ).fetchone()
        user = _user_from_row(row) if row else None
        return _apply_legacy_profile(connection, user) if user else None


def get_user(user_id: int) -> Optional[UserRecord]:
    """Find an account by its ID, or return None when it does not exist."""
    with _database_connection() as connection:
        row = connection.execute(
            "SELECT * FROM Users WHERE id = ?", (user_id,)
        ).fetchone()
        user = _user_from_row(row) if row else None
        return _apply_legacy_profile(connection, user) if user else None


def update_user_profile(
    user_id: int,
    name: str,
    age: Optional[int],
    sex: Optional[str],
    height_cm: Optional[float],
    weight_kg: Optional[float],
    goals: Optional[List[str]],
    experience_level: Optional[str],
    weekly_frequency: Optional[int],
    injuries: Optional[str],
) -> bool:
    """Replace the profile fields and return whether an account was updated."""
    with _database_connection() as connection:
        cursor = connection.execute(
            """UPDATE Users SET name = ?, age = ?, sex = ?, height_cm = ?,
               weight_kg = ?, goals = ?, experience_level = ?, weekly_frequency = ?,
               injuries = ?, updated_at = ? WHERE id = ?""",
            (
                name,
                age,
                sex,
                height_cm,
                weight_kg,
                json.dumps(goals or []),
                experience_level,
                weekly_frequency,
                injuries,
                _now_iso(),
                user_id,
            ),
        )
        updated = cursor.rowcount > 0
        if updated and user_id == 1:
            connection.execute(
                """UPDATE profile SET name = ?, age = ?, height = ?, weight = ?,
                   goals = ?, experience = ?, frequency = ? WHERE id = 1""",
                (
                    name,
                    str(age or ""),
                    str(height_cm or ""),
                    str(weight_kg or ""),
                    ", ".join(goals or []),
                    experience_level or "",
                    str(weekly_frequency or ""),
                ),
            )
        return updated


def delete_user(user_id: int) -> bool:
    """Delete an account and its related records; return whether it existed."""
    with _database_connection() as connection:
        cursor = connection.execute("DELETE FROM Users WHERE id = ?", (user_id,))
        return cursor.rowcount > 0


def create_routine(user_id: int, week_start: str, source: str = "initial") -> int:
    """Create or replace a user's routine for this week and return its ID."""
    with _database_connection() as connection:
        # Regenerating a week replaces its old days and exercises through cascading deletes.
        connection.execute(
            "DELETE FROM Routines WHERE user_id = ? AND week_start = ?",
            (user_id, week_start),
        )
        cursor = connection.execute(
            """INSERT INTO Routines (user_id, week_start, generated_at, source)
               VALUES (?, ?, ?, ?)""",
            (user_id, week_start, _now_iso(), source),
        )
        routine_id = int(cursor.lastrowid)
        _sync_legacy_routine(connection, routine_id)
        return routine_id


def add_routine_day(routine_id: int, day_of_week: str, label: str) -> int:
    """Add a day such as Monday / Upper Body and return its ID."""
    with _database_connection() as connection:
        cursor = connection.execute(
            """INSERT INTO RoutineDays (routine_id, day_of_week, label)
               VALUES (?, ?, ?)""",
            (routine_id, day_of_week, label),
        )
        day_id = int(cursor.lastrowid)
        _sync_legacy_routine(connection, routine_id)
        return day_id


def add_exercise(
    day_id: int,
    name: str,
    sets: Optional[int] = None,
    reps: Optional[str] = None,
    duration_sec: Optional[int] = None,
    notes: Optional[str] = None,
) -> int:
    """Add an exercise to a routine day and return its ID."""
    with _database_connection() as connection:
        cursor = connection.execute(
            """INSERT INTO Exercises (day_id, name, sets, reps, duration_sec, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (day_id, name, sets, reps, duration_sec, notes),
        )
        exercise_id = int(cursor.lastrowid)
        routine = connection.execute(
            """SELECT routine_id FROM RoutineDays WHERE id = ?""", (day_id,)
        ).fetchone()
        if routine:
            _sync_legacy_routine(connection, routine["routine_id"])
        return exercise_id


def get_current_routine(
    user_id: int, week_start: Optional[str] = None
) -> Optional[RoutineRecord]:
    """Return this week's routine with its days and exercises, or None."""
    if week_start is None:
        today = date.today()
        week_start = (today - timedelta(days=today.weekday())).isoformat()

    with _database_connection() as connection:
        legacy_routine = None
        if user_id == 1:
            legacy_routine = connection.execute(
                "SELECT * FROM current_routine WHERE id = 1"
            ).fetchone()
            # main.py replaces this row without setting backend_routine_id.
            if (
                legacy_routine
                and legacy_routine["routine_json"]
                and legacy_routine["backend_routine_id"] is None
            ):
                return _routine_from_legacy_row(legacy_routine, week_start)

        routine = connection.execute(
            "SELECT * FROM Routines WHERE user_id = ? AND week_start = ?",
            (user_id, week_start),
        ).fetchone()
        if routine is None:
            if legacy_routine and legacy_routine["routine_json"]:
                return _routine_from_legacy_row(legacy_routine, week_start)
            return None

        result = dict(routine)
        result["days"] = []
        days = connection.execute(
            "SELECT * FROM RoutineDays WHERE routine_id = ? ORDER BY id",
            (routine["id"],),
        ).fetchall()
        for day in days:
            day_result = dict(day)
            day_result["exercises"] = [
                dict(exercise)
                for exercise in connection.execute(
                    "SELECT * FROM Exercises WHERE day_id = ? ORDER BY id",
                    (day["id"],),
                ).fetchall()
            ]
            result["days"].append(day_result)

    return cast(RoutineRecord, result)


def save_message(
    user_id: int,
    role: str,
    content: str,
    linked_routine_id: Optional[int] = None,
) -> int:
    """Save a user or assistant message and return its ID."""
    with _database_connection() as connection:
        cursor = connection.execute(
            """INSERT INTO ChatMessages
               (user_id, role, content, timestamp, linked_routine_id)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, role, content, _now_iso(), linked_routine_id),
        )
        message_id = int(cursor.lastrowid)
        if user_id == 1:
            # The existing chat screen reads chat_history directly from SQLite.
            legacy_cursor = connection.execute(
                """INSERT INTO chat_history
                   (role, content, timestamp, linked_routine_id)
                   VALUES (?, ?, ?, ?)""",
                (role, content, _now_iso(), linked_routine_id),
            )
            return int(legacy_cursor.lastrowid)
        return message_id


def get_conversation_history(
    user_id: int, limit: int = 100
) -> List[ChatMessageRecord]:
    """Return recent messages in chronological order for a user's chat screen."""
    with _database_connection() as connection:
        if user_id == 1:
            # Legacy main.py messages and mirrored backend messages share this table.
            rows = connection.execute(
                """SELECT id, role, content, COALESCE(timestamp, '') AS timestamp,
                          linked_routine_id
                   FROM (
                       SELECT * FROM chat_history ORDER BY id DESC LIMIT ?
                   ) ORDER BY id""",
                (limit,),
            ).fetchall()
            messages = []
            for row in rows:
                message = dict(row)
                message["user_id"] = user_id
                messages.append(cast(ChatMessageRecord, message))
            return messages

        rows = connection.execute(
            """SELECT * FROM (
                   SELECT * FROM ChatMessages WHERE user_id = ?
                   ORDER BY timestamp DESC, id DESC LIMIT ?
               ) ORDER BY timestamp, id""",
            (user_id, limit),
        ).fetchall()
    return [cast(ChatMessageRecord, dict(row)) for row in rows]


def save_calendar_provider(user_id: int, provider: str) -> int:
    """Connect a provider locally, or return the existing connection's ID."""
    with _database_connection() as connection:
        row = connection.execute(
            "SELECT id FROM CalendarSync WHERE user_id = ? AND provider = ?",
            (user_id, provider),
        ).fetchone()
        if row:
            return int(row["id"])
        cursor = connection.execute(
            "INSERT INTO CalendarSync (user_id, provider) VALUES (?, ?)",
            (user_id, provider),
        )
        return int(cursor.lastrowid)


def update_last_sync(user_id: int, provider: str) -> bool:
    """Record the current time after a calendar sync; return whether it existed."""
    with _database_connection() as connection:
        cursor = connection.execute(
            """UPDATE CalendarSync SET last_synced = ?
               WHERE user_id = ? AND provider = ?""",
            (_now_iso(), user_id, provider),
        )
        return cursor.rowcount > 0


def get_calendar_syncs(user_id: int) -> List[CalendarSyncRecord]:
    """Return the locally saved calendar providers for an account."""
    with _database_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM CalendarSync WHERE user_id = ? ORDER BY id", (user_id,)
        ).fetchall()
    return [cast(CalendarSyncRecord, dict(row)) for row in rows]
