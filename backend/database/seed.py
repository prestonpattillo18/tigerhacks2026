"""Create a realistic demo account, weekly routine, and coach conversation."""

from datetime import date, timedelta
from pathlib import Path
import sqlite3
import sys

# Add the project root when run as `python seed.py` from this folder.
if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))
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
    from backend.database.database import create_database
else:
    from .crud import (
        add_exercise,
        add_routine_day,
        create_routine,
        create_user,
        get_conversation_history,
        get_current_routine,
        get_user_by_email,
        save_message,
    )
    from .database import create_database


def seed_demo_data() -> int:
    """Create demo records only when they are missing; return the demo user ID."""
    create_database()
    email = "demo@fitcoach.local"
    user = get_user_by_email(email)
    if user is None:
        user_id = create_user(
            email=email,
            password="demo-password",
            name="Jamie Rivera",
            age=28,
            sex="Not specified",
            height_cm=170.0,
            weight_kg=68.0,
            goals=["build strength", "improve energy", "stay consistent"],
            experience_level="beginner",
            weekly_frequency=4,
            injuries="No current injuries",
        )
    else:
        user_id = user["id"]

    monday = date.today() - timedelta(days=date.today().weekday())
    week_start = monday.isoformat()
    if get_current_routine(user_id, week_start) is None:
        routine_id = create_routine(user_id, week_start, source="initial")
        weekly_plan = [
            ("Monday", "Upper Body", [("Incline push-ups", 3, "8-10", None, "Use a wall or bench to adjust difficulty."), ("Bent-over backpack row", 3, "10", None, "Keep your back long and steady."), ("Arm circles", None, None, 30, "Move gently in both directions.")]),
            ("Tuesday", "Walk + Mobility", [("Brisk walk", None, None, 1800, "Keep a pace where you can still talk."), ("Standing quad stretch", None, None, 30, "Hold each side without bouncing.")]),
            ("Wednesday", "Rest", []),
            ("Thursday", "Lower Body", [("Chair squats", 3, "10", None, "Tap the chair, then stand tall."), ("Glute bridges", 3, "12", None, "Pause briefly at the top."), ("Calf raises", 2, "12", None, "Hold a wall for balance if needed.")]),
            ("Friday", "Rest + Recovery", [("Easy full-body stretch", None, None, 300, "Stop if anything feels painful.")]),
            ("Saturday", "Full Body", [("Wall push-ups", 2, "10", None, "Keep your body in one straight line."), ("Step-back lunges", 2, "8 each side", None, "Hold a chair if balance is tricky."), ("Dead bug", 2, "8 each side", None, "Move slowly and keep your back comfortable.")]),
            ("Sunday", "Rest", []),
        ]
        for day_name, label, exercises in weekly_plan:
            day_id = add_routine_day(routine_id, day_name, label)
            for name, sets, reps, duration_sec, notes in exercises:
                add_exercise(day_id, name, sets, reps, duration_sec, notes)

    # Seed a short chat only once so rerunning this script does not duplicate it.
    if not get_conversation_history(user_id, limit=1):
        save_message(user_id, "user", "Can you make me a simple beginner plan?")
        save_message(
            user_id,
            "assistant",
            "Absolutely. I planned three short strength sessions, easy movement, and recovery days. Start gently and tell me if anything feels uncomfortable.",
        )
    return user_id


def main() -> None:
    """Run the seed and show a helpful message if SQLite reports an error."""
    try:
        user_id = seed_demo_data()
        print(f"Demo data is ready for user {user_id}.")
    except sqlite3.Error as error:
        # Catch database exceptions at the script boundary; do not hide the failure.
        print(f"Could not create demo data: {error}")
        raise


if __name__ == "__main__":
    main()
