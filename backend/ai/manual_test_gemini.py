"""Manual, network-using smoke test for a developer's Gemini API key.

Run from the project root with:
    export GOOGLE_API_KEY=your-key-here
    python -m backend.ai.manual_test_gemini
"""

from pprint import pprint

from backend.ai.gemini_client import generate_weekly_routine


if __name__ == "__main__":
    sample_profile = {
        "goals": ["build strength", "improve mobility"],
        "experience_level": "beginner",
        "weekly_frequency": 3,
        "injuries": "No current injuries",
        "height_cm": 170,
        "weight_kg": 68,
    }
    routine = generate_weekly_routine(
        sample_profile,
        "Create a simple full-body plan with short workouts.",
    )
    pprint(routine)
