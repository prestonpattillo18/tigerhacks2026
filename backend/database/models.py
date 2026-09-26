"""Dictionary shapes returned by the CRUD functions for use in Kivy screens."""

from typing import List, Optional, TypedDict


# TypedDict documents the keys in a normal Python dictionary; it adds no runtime layer.
class UserRecord(TypedDict):
    id: int
    email: str
    password: str  # Plain text only for the hackathon; hash this before real use.
    name: str
    age: Optional[int]
    sex: Optional[str]
    height_cm: Optional[float]
    weight_kg: Optional[float]
    goals: List[str]
    experience_level: Optional[str]
    weekly_frequency: Optional[int]
    injuries: Optional[str]
    created_at: str
    updated_at: str


class ExerciseRecord(TypedDict):
    id: int
    day_id: int
    name: str
    sets: Optional[int]
    reps: Optional[str]
    duration_sec: Optional[int]
    notes: Optional[str]


class RoutineDayRecord(TypedDict):
    id: int
    routine_id: int
    day_of_week: str
    label: str
    exercises: List[ExerciseRecord]


class RoutineRecord(TypedDict):
    id: int
    user_id: int
    week_start: str
    generated_at: str
    source: str
    days: List[RoutineDayRecord]


class ChatMessageRecord(TypedDict):
    id: int
    user_id: int
    role: str
    content: str
    timestamp: str
    linked_routine_id: Optional[int]


class CalendarSyncRecord(TypedDict):
    id: int
    user_id: int
    provider: str
    last_synced: Optional[str]
