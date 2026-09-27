"""Generate structured weekly fitness routines with Google's Gemini API."""

import json
import os
import ssl
import time
from typing import Optional
import urllib.error
import urllib.request

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    SSL_CONTEXT = None

# Preferred models in order of availability and speed
MODELS = ["gemini-flash-lite-latest", "gemini-3.8-flash", "gemini-flash-latest"]
MODEL_NAME = MODELS[0]


SYSTEM_INSTRUCTION = """You are a fitness routine planner. Return exactly 7 days, Monday through Sunday, in that order. Rest days must still appear with the label 'Rest' and an empty exercises list. Respect the user's experience level and any injuries or limitations; avoid movements that could aggravate them. Choose a number and difficulty of sets and reps that suit the user's weekly frequency and experience level. For beginners, choose fewer, simpler exercises. Do not provide medical diagnoses; use gentle, conservative recommendations when limitations are mentioned."""
COACH_SYSTEM_INSTRUCTION = """You are a friendly, practical fitness and wellbeing coach. Give quick, direct answers, normally one to three sentences, to the user's actual question or issue. Use their profile, recent chat, and current weekly routine as context. You can discuss exercise technique, training consistency, recovery, and general healthy habits. If the user requests a routine change, or a new issue means the current plan should be adjusted, include a complete revised seven-day routine in routine_update. Preserve unaffected days and change only what is needed. For pain or injury, remove or replace movements that could aggravate the issue and use conservative options. If the message does not call for a routine change, set routine_update to null. Any routine_update must contain exactly Monday through Sunday in order; rest days must have label 'Rest' and an empty exercises list. Do not diagnose medical conditions; recommend professional care for serious or worsening symptoms."""

WEEKLY_ROUTINE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "days": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "day_of_week": {"type": "STRING"},
                    "label": {"type": "STRING"},
                    "exercises": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "name": {"type": "STRING"},
                                "sets": {"type": "INTEGER"},
                                "reps": {"type": "STRING"},
                                "duration_sec": {"type": "INTEGER"},
                                "notes": {"type": "STRING"},
                            },
                            "required": ["name"],
                        },
                    },
                },
                "required": ["day_of_week", "label", "exercises"],
            },
        }
    },
    "required": ["days"],
}

COACH_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "reply": {"type": "STRING"},
        "routine_update": {
            "type": "OBJECT",
            "properties": {
                "days": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "day_of_week": {"type": "STRING"},
                            "label": {"type": "STRING"},
                            "exercises": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "name": {"type": "STRING"},
                                        "sets": {"type": "INTEGER"},
                                        "reps": {"type": "STRING"},
                                        "duration_sec": {"type": "INTEGER"},
                                        "notes": {"type": "STRING"},
                                    },
                                    "required": ["name"],
                                },
                            },
                        },
                        "required": ["day_of_week", "label", "exercises"],
                    },
                }
            },
            "required": ["days"],
        },
    },
    "required": ["reply"],
}


def _call_gemini_api(contents_text: str, system_instruction: str, schema: dict) -> dict:
    """Call the Gemini REST API with structured JSON output and automatic model fallback."""
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set.")

    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": contents_text}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    last_error = None
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(2):
            req = urllib.request.Request(url, data=data, headers=headers)
            try:
                open_kwargs = {"timeout": 30}
                if SSL_CONTEXT is not None:
                    open_kwargs["context"] = SSL_CONTEXT
                with urllib.request.urlopen(req, **open_kwargs) as resp:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_json.get("candidates", [])
                    if not candidates:
                        raise RuntimeError("Gemini returned no candidates.")
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if not parts:
                        raise RuntimeError("Gemini returned empty parts.")
                    raw_text = parts[0].get("text", "")
                    return json.loads(raw_text)
            except urllib.error.HTTPError as err:
                last_error = err
                if err.code in (429, 503):
                    time.sleep(1.5)
                    continue
                # If model is 404 or deprecated, try next model in MODELS
                break
            except Exception as err:
                last_error = err
                time.sleep(1)
                continue

    raise RuntimeError(f"Gemini API request failed: {last_error}")


def _build_prompt(profile: dict, user_message: str) -> str:
    """Build a prompt from available profile details and the user's request."""
    profile_fields = [
        ("goals", profile.get("goals")),
        ("experience_level", profile.get("experience_level")),
        ("weekly_frequency", profile.get("weekly_frequency")),
        ("injuries", profile.get("injuries")),
        ("height_cm", profile.get("height_cm")),
        ("weight_kg", profile.get("weight_kg")),
    ]
    details = []
    for field_name, value in profile_fields:
        if value is None or value == "" or value == []:
            continue
        if field_name == "goals" and isinstance(value, list):
            value = ", ".join(str(goal) for goal in value)
        details.append(f"- {field_name}: {value}")

    profile_text = "\n".join(details) if details else "- No profile details provided"
    return (
        "Create a personalized weekly fitness routine using this profile:\n"
        f"{profile_text}\n\n"
        f"User's request: {user_message}"
    )


def generate_weekly_routine(profile: dict, user_message: str) -> list[dict]:
    """Ask Gemini for a seven-day routine and return its days as dictionaries."""
    prompt = _build_prompt(profile, user_message)
    try:
        routine = _call_gemini_api(prompt, SYSTEM_INSTRUCTION, WEEKLY_ROUTINE_SCHEMA)
        days = routine.get("days", [])
        expected_days = [
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
        ]
        actual_days = [day.get("day_of_week") for day in days]
        if actual_days != expected_days:
            raise ValueError("Routine days must be Monday through Sunday in order.")
        return days
    except Exception as error:
        raise RuntimeError("Gemini routine request failed; check the API key and network.") from error


def generate_coach_reply(
    profile: dict,
    user_message: str,
    conversation_history: Optional[list[dict]] = None,
    current_routine: Optional[dict] = None,
) -> dict:
    """Ask Gemini for a concise answer and an optional revised weekly routine."""
    profile_fields = [
        ("goals", profile.get("goals")),
        ("experience_level", profile.get("experience_level")),
        ("weekly_frequency", profile.get("weekly_frequency")),
        ("injuries", profile.get("injuries")),
        ("height_cm", profile.get("height_cm")),
        ("weight_kg", profile.get("weight_kg")),
    ]
    profile_details = [
        f"- {name}: {value}"
        for name, value in profile_fields
        if value is not None and value != "" and value != []
    ]
    history_lines = []
    for message in (conversation_history or [])[-10:]:
        speaker = "User" if message.get("role") == "user" else "Coach"
        history_lines.append(f"{speaker}: {message.get('content', '')}")

    routine_days = []
    for day in (current_routine or {}).get("days", []):
        routine_days.append({
            "day_of_week": day.get("day_of_week"),
            "label": day.get("label"),
            "exercises": [
                {
                    "name": exercise.get("name"),
                    "sets": exercise.get("sets"),
                    "reps": exercise.get("reps"),
                    "duration_sec": exercise.get("duration_sec"),
                    "notes": exercise.get("notes"),
                }
                for exercise in day.get("exercises", [])
            ],
        })

    prompt = (
        "User profile:\n"
        f"{chr(10).join(profile_details) if profile_details else '- Not provided'}\n\n"
        "Recent conversation:\n"
        f"{chr(10).join(history_lines) if history_lines else '- No earlier messages'}\n\n"
        "Current weekly routine (change it only when the request or issue calls for it):\n"
        f"{json.dumps(routine_days) if routine_days else '- No current routine'}\n\n"
        f"User's latest message: {user_message}"
    )

    try:
        coach_response = _call_gemini_api(prompt, COACH_SYSTEM_INSTRUCTION, COACH_RESPONSE_SCHEMA)
        reply = (coach_response.get("reply") or "").strip()
        if not reply:
            raise ValueError("Gemini returned an empty coach reply.")
        routine_update = coach_response.get("routine_update")
        if routine_update and isinstance(routine_update, dict):
            expected_days = [
                "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
            ]
            actual_days = [day.get("day_of_week") for day in routine_update.get("days", [])]
            if actual_days != expected_days:
                raise ValueError("Routine updates must contain all seven days in order.")
        return coach_response
    except Exception as error:
        raise RuntimeError("Gemini coach reply failed; check the API key and network.") from error
