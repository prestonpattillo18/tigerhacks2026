# imports
import re
from datetime import date, timedelta
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from backend.database.database import create_database
from backend.database.crud import (
    add_exercise,
    add_routine_day,
    create_routine,
    create_user,
    get_conversation_history,
    get_current_routine,
    get_user,
    save_message,
    update_user_profile,
)


#-----------------------------------------------------------------------
# Database Setup (SQLite local persistence)
#-----------------------------------------------------------------------
def init_db():
    """Create the schema and a local account for the single-user prototype."""
    create_database()
    profile = get_user(1)
    if profile is None:
        # This local account is not an authentication system; add real auth later.
        create_user("local@fitworks.app", "local-only", "")
    elif profile["email"] == "local@fitworks.app" and profile["name"] == "Fitness User":
        # Clear the old placeholder name so a fresh install still opens onboarding.
        update_user_profile(
            1,
            "",
            profile["age"],
            profile["sex"],
            profile["height_cm"],
            profile["weight_kg"],
            profile["goals"],
            profile["experience_level"],
            profile["weekly_frequency"],
            profile["injuries"],
        )

init_db()


def _exercise_fields(exercise_text):
    """Extract simple set/rep or duration details from the demo routine text."""
    set_match = re.search(r"(\d+)\s*x\s*(\d+[a-z]*)", exercise_text, re.IGNORECASE)
    if set_match:
        name = exercise_text[:set_match.start()].strip()
        return name, int(set_match.group(1)), set_match.group(2), None

    duration_match = re.search(r"(\d+)\s*(sec|seconds|min|mins|minutes)\b", exercise_text, re.IGNORECASE)
    if duration_match:
        amount = int(duration_match.group(1))
        unit = duration_match.group(2).lower()
        duration_sec = amount * 60 if unit.startswith("m") else amount
        name = exercise_text[:duration_match.start()].strip()
        return name, None, None, duration_sec

    return exercise_text, None, None, None


#-----------------------------------------------------------------------
# Backend Mock / Local Proxy
#-----------------------------------------------------------------------
# Example cases, suitable for conversion into simple assert tests later:
#   ("Build me a fresh exercise schedule", "generate_routine")
#   ("My ankle hurts after training", "update_profile")
#   ("Change my weekly frequency", "update_profile")
#   ("Update my workout plan", "update_profile")  # profile updates take priority
#   ("Thanks for checking in", "general_chat")
def classify_query_intent(user_message: str) -> str:
    """Classify a chat message as generate_routine, update_profile, or general_chat."""
    message_words = set(re.findall(r"\b\w+\b", user_message.lower()))
    update_keywords = {
        "injury", "injuries", "sprain", "sprains", "hurt", "hurts", "hurting",
        "pain", "pains", "update", "updates", "updating", "frequency", "frequencies",
    }

    # Profile and injury changes take priority so a safety note is not treated as a new plan request.
    if message_words.intersection(update_keywords) or re.search(
        r"\bchange\s+my\b", user_message, re.IGNORECASE
    ):
        return "update_profile"

    routine_keywords = {
        "generate", "generates", "generated", "generating", "routine", "routines",
        "workout", "workouts", "plan", "plans", "schedule", "schedules",
        "exercise", "exercises",
    }
    if message_words.intersection(routine_keywords):
        return "generate_routine"
    return "general_chat"


def mock_backend_chat(user_message):
    """
    Simulates /chat API endpoint proxy behavior.
    Updates database/routine data structure depending on context.
    """
    user_id = 1
    save_message(user_id, "user", user_message)
    linked_routine_id = None
    
    intent = classify_query_intent(user_message)

    if intent == "generate_routine":
        # Mock structured output for routine generation (Section 6.2)
        sample_routine = {
            "Monday": {"label": "Push Day", "exercises": ["Bench Press 3x10", "Overhead Press 3x12", "Tricep Dips 3x15"]},
            "Tuesday": {"label": "Pull Day", "exercises": ["Pull-ups 3x8", "Barbell Rows 3x10", "Bicep Curls 3x12"]},
            "Wednesday": {"label": "Rest Day", "exercises": ["Light Stretching / Walking"]},
            "Thursday": {"label": "Leg Day", "exercises": ["Squats 4x10", "Lunge 3x12", "Calf Raises 4x15"]},
            "Friday": {"label": "Core & Cardio", "exercises": ["Plank 3x60s", "HIIT 20 mins"]},
            "Saturday": {"label": "Active Recovery", "exercises": ["Yoga / Mobility Work"]},
            "Sunday": {"label": "Rest Day", "exercises": ["Rest"]}
        }
        current_routine = get_current_routine(user_id)
        week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        routine_id = create_routine(
            user_id,
            week_start,
            source="chat_update" if current_routine else "initial",
        )
        for day_name, details in sample_routine.items():
            day_id = add_routine_day(routine_id, day_name, details["label"])
            for exercise_text in details["exercises"]:
                name, sets, reps, duration_sec = _exercise_fields(exercise_text)
                add_exercise(day_id, name, sets, reps, duration_sec)
        linked_routine_id = routine_id
        response = "I've generated a new 7-day workout routine tailored to your profile! You can view it on the Routine tab."
    elif intent == "update_profile":
        profile = get_user(user_id)
        message_words = set(re.findall(r"\b\w+\b", user_message.lower()))
        injury_keywords = {
            "injury", "injuries", "sprain", "sprains", "hurt", "hurts", "hurting",
            "pain", "pains",
        }
        if profile and message_words.intersection(injury_keywords):
            old_notes = profile["injuries"] or ""
            notes = f"{old_notes}; {user_message}".strip("; ")
            update_user_profile(
                user_id,
                profile["name"],
                profile["age"],
                profile["sex"],
                profile["height_cm"],
                profile["weight_kg"],
                profile["goals"],
                profile["experience_level"],
                profile["weekly_frequency"],
                notes,
            )
            response = "I've saved that recovery note to your profile. Please avoid painful movements and consult a professional about your injury."
        else:
            response = "Tell me which profile detail you'd like to update, such as an injury note or weekly workout frequency."
    else:
        response = f"I'm your AI Fitness Assistant. You said: '{user_message}'. How can I adjust your routine today?"

    save_message(user_id, "assistant", response, linked_routine_id)
    return response


# -------------------------------------------------------------------
# Kivy UI Screens (Avoid KV Language)
# -------------------------------------------------------------------
class WelcomeScreen(Screen):
    def __init__(self, **kwargs):
        super(WelcomeScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        
        lbl = Label(text="AI Fitness & Wellbeing App", font_size=24, size_hint_y=0.4)
        desc = Label(text="Welcome! Let's get your personalized routine set up.", font_size=16, size_hint_y=0.3)
        btn = Button(text="Start Onboarding", size_hint_y=0.2)
        btn.bind(on_release=self.go_next)
        
        layout.add_widget(lbl)
        layout.add_widget(desc)
        layout.add_widget(btn)
        self.add_widget(layout)
        
    def go_next(self, instance):
        self.manager.current = 'profile_setup'


class ProfileSetupScreen(Screen):
    def __init__(self, **kwargs):
        super(ProfileSetupScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
        
        layout.add_widget(Label(text="Onboarding: Profile Setup", font_size=20, size_hint_y=None, height=40))
        
        grid = GridLayout(cols=2, spacing=10, size_hint_y=0.7)
        
        grid.add_widget(Label(text="Name:"))
        self.inp_name = TextInput(multiline=False)
        profile = get_user(1)
        if profile:
            self.inp_name.text = profile["name"] or ""
        grid.add_widget(self.inp_name)
        
        grid.add_widget(Label(text="Age:"))
        self.inp_age = TextInput(multiline=False)
        if profile and profile["age"] is not None:
            self.inp_age.text = str(profile["age"])
        grid.add_widget(self.inp_age)
        
        grid.add_widget(Label(text="Goals:"))
        self.inp_goals = TextInput(multiline=False)
        if profile:
            self.inp_goals.text = ", ".join(profile["goals"])
        grid.add_widget(self.inp_goals)
        
        grid.add_widget(Label(text="Experience Level:"))
        self.inp_exp = TextInput(multiline=False)
        if profile:
            self.inp_exp.text = profile["experience_level"] or ""
        grid.add_widget(self.inp_exp)
        
        grid.add_widget(Label(text="Weekly Frequency:"))
        self.inp_freq = TextInput(multiline=False)
        if profile and profile["weekly_frequency"] is not None:
            self.inp_freq.text = str(profile["weekly_frequency"])
        grid.add_widget(self.inp_freq)
        
        layout.add_widget(grid)
        
        btn_save = Button(text="Generate Routine & Continue", size_hint_y=None, height=50)
        btn_save.bind(on_release=self.save_and_continue)
        layout.add_widget(btn_save)
        
        self.add_widget(layout)
        
    def save_and_continue(self, instance):
        profile = get_user(1)
        has_current_routine = get_current_routine(1) is not None
        age_text = self.inp_age.text.strip()
        frequency_text = self.inp_freq.text.strip()
        goals = [goal.strip() for goal in self.inp_goals.text.split(",") if goal.strip()]
        update_user_profile(
            1,
            self.inp_name.text.strip(),
            int(age_text) if age_text.isdigit() else None,
            profile["sex"] if profile else None,
            profile["height_cm"] if profile else None,
            profile["weight_kg"] if profile else None,
            goals,
            self.inp_exp.text.strip(),
            int(frequency_text) if frequency_text.isdigit() else None,
            profile["injuries"] if profile else None,
        )
        
        # Generate a starter routine only once; profile edits should keep this week's plan.
        if not has_current_routine:
            mock_backend_chat("Please generate my initial routine.")
        
        # Switch to Main App layout
        self.manager.current = 'main_app'


class ChatTab(BoxLayout):
    def __init__(self, **kwargs):
        super(ChatTab, self).__init__(orientation='vertical', padding=10, spacing=10, **kwargs)
        
        # Chat log display
        self.scroll = ScrollView(size_hint=(1, 0.85))
        self.chat_log = Label(text="AI Assistant: Hello! How can I help with your routine today?\n", 
                              size_hint_y=None, halign='left', valign='top')
        messages = get_conversation_history(1)
        if messages:
            self.chat_log.text = "".join(
                f"{'You' if message['role'] == 'user' else 'AI'}: {message['content']}\n"
                for message in messages
            )
        self.chat_log.bind(texture_size=self._update_text_size)
        self.scroll.add_widget(self.chat_log)
        self.add_widget(self.scroll)
        
        # Input controls
        input_box = BoxLayout(orientation='horizontal', size_hint=(1, 0.15), spacing=5)
        self.msg_input = TextInput(multiline=False)
        btn_send = Button(text="Send", size_hint_x=0.25)
        btn_send.bind(on_release=self.send_message)
        
        input_box.add_widget(self.msg_input)
        input_box.add_widget(btn_send)
        self.add_widget(input_box)
        
    def _update_text_size(self, instance, value):
        self.chat_log.height = value[1]
        self.chat_log.text_size = (self.width - 20, None)
        
    def send_message(self, instance):
        text = self.msg_input.text.strip()
        if text:
            self.chat_log.text += f"\nYou: {text}\n"
            reply = mock_backend_chat(text)
            self.chat_log.text += f"AI: {reply}\n"
            self.msg_input.text = ""


class RoutineTab(BoxLayout):
    def __init__(self, **kwargs):
        super(RoutineTab, self).__init__(orientation='vertical', padding=10, spacing=10, **kwargs)
        
        self.scroll = ScrollView(size_hint=(1, 0.85))
        self.routine_display = Label(text="No routine generated yet.", size_hint_y=None, halign='left', valign='top')
        self.routine_display.bind(texture_size=self._update_text_size)
        self.scroll.add_widget(self.routine_display)
        self.add_widget(self.scroll)
        
        btn_box = BoxLayout(orientation='horizontal', size_hint=(1, 0.15), spacing=5)
        btn_refresh = Button(text="Refresh View")
        btn_refresh.bind(on_release=self.load_routine)
        btn_export = Button(text="Export .ics Calendar")
        btn_export.bind(on_release=self.export_ics)
        
        btn_box.add_widget(btn_refresh)
        btn_box.add_widget(btn_export)
        self.add_widget(btn_box)
        
        self.load_routine(None)

    def _update_text_size(self, instance, value):
        self.routine_display.height = value[1]
        self.routine_display.text_size = (self.width - 20, None)

    def load_routine(self, instance):
        routine = get_current_routine(1)
        if routine and routine["days"]:
            out_text = "=== YOUR WEEKLY ROUTINE ===\n\n"
            for day in routine["days"]:
                out_text += f"• {day['day_of_week']}: {day['label']}\n"
                for exercise in day["exercises"]:
                    description = exercise["name"]
                    if exercise["sets"] is not None and exercise["reps"]:
                        description += f" {exercise['sets']}x{exercise['reps']}"
                    if exercise["duration_sec"]:
                        description += f" ({exercise['duration_sec']} sec)"
                    out_text += f"    - {description}\n"
                out_text += "\n"
            self.routine_display.text = out_text
        else:
            self.routine_display.text = "No active routine found. Please ask the AI in the Chat tab to generate one."

    def export_ics(self, instance):
        # Universal .ics fallback export (Section 7)
        ics_content = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//AI Fitness App//EN\n"
        ics_content += "BEGIN:VEVENT\nSUMMARY:AI Workout Session\nDESCRIPTION:Scheduled Fitness Routine\nEND:VEVENT\n"
        ics_content += "END:VCALENDAR"
        
        with open("workout_schedule.ics", "w") as f:
            f.write(ics_content)
        self.routine_display.text += "\n\n[System]: Saved 'workout_schedule.ics' to local storage!"


class AccountTab(BoxLayout):
    def __init__(self, **kwargs):
        super(AccountTab, self).__init__(orientation='vertical', padding=10, spacing=10, **kwargs)
        
        self.add_widget(Label(text="Account & Profile Settings", font_size=18, size_hint_y=0.1))
        
        self.profile_info = Label(text="Loading profile...", size_hint_y=0.7, halign='left', valign='top')
        self.profile_info.bind(texture_size=self._update_text_size)
        self.add_widget(self.profile_info)
        
        btn_reload = Button(text="Reload Profile Data", size_hint_y=0.2)
        btn_reload.bind(on_release=self.load_profile)
        self.add_widget(btn_reload)
        
        self.load_profile(None)

    def _update_text_size(self, instance, value):
        self.profile_info.text_size = (self.width - 20, None)

    def load_profile(self, instance):
        profile = get_user(1)
        if profile:
            goals = ", ".join(profile["goals"])
            text = (
                f"Name: {profile['name']}\nAge: {profile['age'] or ''}\n"
                f"Goals: {goals}\nExperience: {profile['experience_level'] or ''}\n"
                f"Frequency: {profile['weekly_frequency'] or ''} days/week"
            )
            self.profile_info.text = text


class MainAppScreen(Screen):
    """
    Main container screen holding the persistent bottom tab bar and 3 main views (Section 3).
    """
    def __init__(self, **kwargs):
        super(MainAppScreen, self).__init__(**kwargs)
        
        root_layout = BoxLayout(orientation='vertical')
        
        # Content view dynamic container
        self.content_area = BoxLayout(orientation='vertical', size_hint_y=0.9)
        
        # Tab Bar
        tab_bar = BoxLayout(orientation='horizontal', size_hint_y=0.1, spacing=2)
        
        btn_chat = Button(text="Chat")
        btn_chat.bind(on_release=lambda x: self.switch_tab('chat'))
        
        btn_routine = Button(text="Routine")
        btn_routine.bind(on_release=lambda x: self.switch_tab('routine'))
        
        btn_account = Button(text="Account")
        btn_account.bind(on_release=lambda x: self.switch_tab('account'))
        
        tab_bar.add_widget(btn_chat)
        tab_bar.add_widget(btn_routine)
        tab_bar.add_widget(btn_account)
        
        # Instantiate tabs
        self.chat_tab = ChatTab()
        self.routine_tab = RoutineTab()
        self.account_tab = AccountTab()
        
        # Default view
        self.content_area.add_widget(self.chat_tab)
        
        root_layout.add_widget(self.content_area)
        root_layout.add_widget(tab_bar)
        
        self.add_widget(root_layout)

    def switch_tab(self, tab_name):
        self.content_area.clear_widgets()
        if tab_name == 'chat':
            self.content_area.add_widget(self.chat_tab)
        elif tab_name == 'routine':
            self.routine_tab.load_routine(None)
            self.content_area.add_widget(self.routine_tab)
        elif tab_name == 'account':
            self.account_tab.load_profile(None)
            self.content_area.add_widget(self.account_tab)


#-----------------------------------------------------------------------
# Kivy App Initialization
#-----------------------------------------------------------------------
class FitWorksAI(App):
    def build(self):
        sm = ScreenManager(transition=FadeTransition())
        sm.add_widget(WelcomeScreen(name='welcome'))
        sm.add_widget(ProfileSetupScreen(name='profile_setup'))
        sm.add_widget(MainAppScreen(name='main_app'))
        profile = get_user(1)
        if profile and (profile["name"] or "").strip():
            sm.current = "main_app"
        return sm


if __name__ == '__main__':
    FitWorksAI().run()