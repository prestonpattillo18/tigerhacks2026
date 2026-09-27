"""Generate structured weekly fitness routines with Google's Gemini API."""

import json
import os
from typing import Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


MODEL_NAME = "gemini-flash-latest"


class RoutineExercise(BaseModel):
    """One exercise and its optional set, rep, duration, and safety details."""

    name: str = Field(description="Name of the exercise")
    sets: Optional[int] = Field(default=None, description="Number of sets, if applicable")
    reps: Optional[str] = Field(default=None, description="Repetitions per set, if applicable")
    duration_sec: Optional[int] = Field(default=None, description="Duration in seconds, if time-based")
    notes: Optional[str] = Field(default=None, description="Form, rest, or safety notes")


class RoutineDay(BaseModel):
    """A scheduled day in the weekly fitness routine."""

    day_of_week: str = Field(description="Day name, Monday through Sunday")
    label: str = Field(description="Short workout or rest-day label")
    exercises: list[RoutineExercise] = Field(description="Exercises for this day; empty on rest days")


class WeeklyRoutine(BaseModel):
    """Structured response wrapper used by Gemini's JSON output mode."""

    days: list[RoutineDay] = Field(description="Exactly seven days, Monday through Sunday")


class CoachResponse(BaseModel):
    """A concise coach reply with an optional complete routine replacement."""

    reply: str = Field(description="A concise, direct answer to the user's latest message")
    routine_update: Optional[WeeklyRoutine] = Field(
        default=None,
        description="A revised complete week when a routine change is needed; otherwise null",
    )


SYSTEM_INSTRUCTION = """You are a fitness routine planner. Return exactly 7 days, Monday through Sunday, in that order. Rest days must still appear with the label 'Rest' and an empty exercises list. Respect the user's experience level and any injuries or limitations; avoid movements that could aggravate them. Choose a number and difficulty of sets and reps that suit the user's weekly frequency and experience level. For beginners, choose fewer, simpler exercises. Do not provide medical diagnoses; use gentle, conservative recommendations when limitations are mentioned."""
COACH_SYSTEM_INSTRUCTION = """You are a friendly, practical fitness and wellbeing coach. Give quick, direct answers, normally one to three sentences, to the user's actual question or issue. Use their profile, recent chat, and current weekly routine as context. You can discuss exercise technique, training consistency, recovery, and general healthy habits. If the user requests a routine change, or a new issue means the current plan should be adjusted, include a complete revised seven-day routine in routine_update. Preserve unaffected days and change only what is needed. For pain or injury, remove or replace movements that could aggravate the issue and use conservative options. If the message does not call for a routine change, set routine_update to null. Any routine_update must contain exactly Monday through Sunday in order; rest days must have label 'Rest' and an empty exercises list. Do not diagnose medical conditions; recommend professional care for serious or worsening symptoms."""


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
    """Ask Gemini for a seven-day routine and return its days as dictionaries.

    Raises RuntimeError when the API key, request, or structured response is invalid.
    """
    if not os.environ.get("GOOGLE_API_KEY", "").strip():
        raise RuntimeError("GOOGLE_API_KEY is not set.")

    try:
        client = genai.Client()
    except Exception as error:
        raise RuntimeError("Could not initialize the Gemini client.") from error

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=_build_prompt(profile, user_message),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=WeeklyRoutine,
                max_output_tokens=4096,
            ),
        )
    except Exception as error:
        raise RuntimeError("Gemini routine request failed; check the API key and network.") from error

    try:
        parsed_response = response.parsed
        if isinstance(parsed_response, WeeklyRoutine):
            routine = parsed_response
        elif parsed_response is not None:
            routine = WeeklyRoutine.model_validate(parsed_response)
        else:
            routine = WeeklyRoutine.model_validate_json(response.text)

        expected_days = [
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
        ]
        actual_days = [day.day_of_week for day in routine.days]
        if actual_days != expected_days:
            raise ValueError("Routine days must be Monday through Sunday in order.")
        return routine.model_dump()["days"]
    except Exception as error:
        raise RuntimeError("Gemini returned malformed routine data.") from error


def generate_coach_reply(
    profile: dict,
    user_message: str,
    conversation_history: Optional[list[dict]] = None,
    current_routine: Optional[dict] = None,
) -> dict:
    """Ask Gemini for a concise answer and an optional revised weekly routine."""
    if not os.environ.get("GOOGLE_API_KEY", "").strip():
        raise RuntimeError("GOOGLE_API_KEY is not set.")

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
        client = genai.Client()
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=COACH_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=CoachResponse,
                max_output_tokens=3072,
            ),
        )
        if isinstance(response.parsed, CoachResponse):
            coach_response = response.parsed
        elif response.parsed is not None:
            coach_response = CoachResponse.model_validate(response.parsed)
        else:
            coach_response = CoachResponse.model_validate_json(response.text)

        if not coach_response.reply.strip():
            raise ValueError("Gemini returned an empty coach reply.")
        if coach_response.routine_update:
            expected_days = [
                "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
            ]
            actual_days = [day.day_of_week for day in coach_response.routine_update.days]
            if actual_days != expected_days:
                raise ValueError("Routine updates must contain all seven days in order.")
        return coach_response.model_dump()
    except Exception as error:
        raise RuntimeError("Gemini coach reply failed; check the API key and network.") from error
