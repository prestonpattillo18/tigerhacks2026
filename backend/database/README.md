# Fitness App SQLite Database

This folder contains the local database layer for the Kivy fitness app. New Kivy screens can call functions in `crud.py`; they do not need to write SQL themselves.

## 1. What SQLite is

SQLite is a small relational database stored in a single file. Python includes the `sqlite3` library, so the app does not need to run a separate database server for the hackathon.

## 2. Why this project uses SQLite

SQLite is quick to set up, works offline, and is a good fit for a local hackathon prototype. The same tables and CRUD functions give the app a clear starting point before a backend is added. The database file is the project-root `app_data.db`, matching the path used by `main.py`.

## 3. Project structure

- `__init__.py` makes this folder a Python package and exposes database initialization.
- `database.py` defines the shared database-file location, opens connections, enables foreign keys, and creates both the normalized tables and the legacy tables expected by `main.py`.
- `models.py` documents the dictionaries returned to screens with Python `TypedDict` types.
- `crud.py` contains the account, profile, routine, exercise, chat, and calendar database functions.
- `seed.py` fills a new database with one demo account, a weekly routine, exercises, and a short chat.
- `test_database.py` checks the schema and common data relationships using plain `assert` statements.
- `app_data.db` is created automatically at runtime; it is not source code.

## 4. Create and seed the database

Use Python 3. Run these commands from the project root:

```bash
python -c "from backend.database.database import create_database; create_database()"
python backend/database/seed.py
```

Run `create_database()` before starting `main.py` if you want both the normalized backend tables and the legacy app tables in the shared file. `main.py` itself is unchanged and still executes SQL directly; it does not automatically initialize or call the backend CRUD module.

You can also run the requested `python seed.py` command from this folder:

```bash
cd backend/database
python seed.py
```

The seed script is safe to run more than once. It reuses the demo account and only adds the routine or chat if they are not already present. Demo login email: `demo@fitcoach.local`; demo password: `demo-password`.

## 5. How Kivy calls the database

Initialize the tables once during app startup, then import CRUD functions into a screen or a small screen-facing service module:

```python
from backend.database.database import create_database
from backend.database.crud import get_current_routine, update_user_profile

create_database()
routine = get_current_routine(user_id)
if routine is not None:
    for day in routine["days"]:
        print(day["label"], day["exercises"])
```

A Kivy button callback can call a CRUD function and use its returned ID, boolean, or dictionary. If database work becomes slow, run it off the UI thread so the screen remains responsive. Keep SQL in `crud.py`, not in Kivy widgets.

The chatbot itself is not implemented here. After it generates a routine, a screen using the backend can call `create_routine()`, `add_routine_day()`, and `add_exercise()`. Save user and assistant turns with `save_message()`; attach the routine ID to the assistant message when it changes the plan. `save_calendar_provider()` and `update_last_sync()` only save local provider metadata. They do not connect to Google or Apple or perform OAuth.

### Compatibility with `main.py`

Both the backend and `main.py` use the same project-root `app_data.db`. The backend initializer creates the `profile`, `chat_history`, and `current_routine` tables used by the existing screens, and adds nullable compatibility columns without deleting existing data. For the single demo account (`Users.id = 1`), backend profile and chat changes are mirrored into the tables that `main.py` reads. Routines are saved in normalized tables and mirrored into the JSON format shown by its Routine tab. Data written directly by `main.py` can also be read by the backend functions.

Because `main.py` was intentionally left unchanged, it continues to perform direct SQLite queries rather than calling `crud.py`. Initialize the backend schema once before using backend CRUD functions with that app, for example with the command above or by running the seed script. Full routing of every screen operation through the CRUD functions would require changing `main.py` to import and call them.

Profile goals are stored as JSON text in the `goals` column and returned as a Python list. Dates and times are ISO-formatted text. The calendar table intentionally stores no access or refresh tokens in this version.

### Database errors and connections

A Python exception is an error signal that interrupts normal execution. SQLite can raise `sqlite3.Error` for problems such as a duplicate email, invalid SQL, or a broken database file. CRUD functions roll back failed work, close the connection, and re-raise the exception so a Kivy screen can handle it:

```python
import sqlite3

try:
    user_id = create_user("person@example.com", "password", "Alex")
except sqlite3.Error as error:
    print(f"Could not save the account: {error}")
```

Always close connections after use. The CRUD helper does this automatically; if a screen calls `get_connection()` directly, close it in a `finally` block. A connection holds operating-system resources, and leaving many open can cause locking or resource problems.

CRUD values are passed with `?` placeholders. SQLite treats those values as data instead of executable SQL, which helps prevent SQL injection. Do not build a query by joining user-provided text into the SQL string.

## 6. Run the tests

From the project root:

```bash
python backend/database/test_database.py
```

Or from this folder:

```bash
cd backend/database
python test_database.py
```

The tests use a temporary database file, so they do not change the demo database. No pytest or third-party packages are required.

## 7. Moving toward FastAPI later

A future FastAPI app can call the same CRUD functions at first, then expose them through API endpoints. Keep Kivy focused on screens and HTTP requests once a server exists; do not let mobile clients open the server's SQLite file directly. Before deploying, hash passwords with a suitable password-hashing library, add real authentication and authorization, validate inputs, and protect secrets. For multiple users or heavier concurrent server traffic, move the same relational design to a server database and add migrations deliberately. Calendar OAuth tokens must be encrypted and managed on the server; this local prototype does not store tokens or implement OAuth.
