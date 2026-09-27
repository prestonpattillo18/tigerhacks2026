from dotenv import load_dotenv

load_dotenv()

# imports
import re
from datetime import date, timedelta
from threading import Thread
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from backend.ai.gemini_client import generate_coach_reply, generate_weekly_routine
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


# Shared colors keep the app consistent without introducing a separate theme system.
COLORS = {
    "background": (0.055, 0.082, 0.075, 1),
    "surface": (0.105, 0.145, 0.13, 1),
    "surface_light": (0.15, 0.20, 0.175, 1),
    "accent": (0.72, 0.91, 0.38, 1),
    "coral": (0.96, 0.48, 0.34, 1),
    "text": (0.94, 0.96, 0.91, 1),
    "muted": (0.65, 0.73, 0.68, 1),
    "ink": (0.08, 0.12, 0.09, 1),
}
Window.clearcolor = COLORS["background"]
Window.softinput_mode = "below_target"


def _style_screen(screen):
    """Paint a screen background and keep it fitted when the phone resizes."""
    with screen.canvas.before:
        Color(*COLORS["background"])
        screen._background_rect = Rectangle(pos=screen.pos, size=screen.size)

    def update_background(widget, _value):
        widget._background_rect.pos = widget.pos
        widget._background_rect.size = widget.size

    screen.bind(pos=update_background, size=update_background)


def _add_card_background(widget, color=None):
    """Draw a rounded panel behind a layout without adding another widget."""
    with widget.canvas.before:
        fill = Color(*(color or COLORS["surface"]))
        rectangle = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(14)])

    def update_card(widget, _value):
        rectangle.pos = widget.pos
        rectangle.size = widget.size

    widget.bind(pos=update_card, size=update_card)
    return fill


def _style_button(button, primary=False):
    """Give a Kivy button a rounded touch target and visible pressed state."""
    button.background_normal = ""
    button.background_down = ""
    button.background_color = (0, 0, 0, 0)
    button.color = COLORS["ink"] if primary else COLORS["text"]
    button.bold = True
    button.font_size = sp(16)
    button._liftforge_primary = primary
    button._liftforge_normal = COLORS["accent"] if primary else COLORS["surface_light"]
    button._liftforge_pressed = COLORS["coral"] if primary else COLORS["surface"]

    with button.canvas.before:
        fill = Color(*button._liftforge_normal)
        rectangle = RoundedRectangle(pos=button.pos, size=button.size, radius=[dp(12)])

    def update_button(widget, _value):
        rectangle.pos = widget.pos
        rectangle.size = widget.size
        fill.rgba = (
            widget._liftforge_pressed
            if widget.state == "down"
            else widget._liftforge_normal
        )

    button._liftforge_fill = fill
    button._liftforge_update = update_button
    button.bind(pos=update_button, size=update_button, state=update_button)


def _set_button_primary(button, primary):
    """Change a styled button's color when it becomes the selected tab."""
    button._liftforge_primary = primary
    button._liftforge_normal = COLORS["accent"] if primary else COLORS["surface_light"]
    button._liftforge_pressed = COLORS["coral"] if primary else COLORS["surface"]
    button.color = COLORS["ink"] if primary else COLORS["text"]
    button._liftforge_update(button, None)


def _style_input(text_input):
    """Use high-contrast input colors and comfortable finger spacing."""
    text_input.background_normal = ""
    text_input.background_active = ""
    text_input.background_color = COLORS["surface_light"]
    text_input.foreground_color = COLORS["text"]
    text_input.cursor_color = COLORS["accent"]
    text_input.hint_text_color = COLORS["muted"]
    text_input.padding = [dp(12), dp(12)]
    text_input.font_size = sp(16)


def _make_wrapping_label(text, color=None, font_size=15, bold=False):
    """Create a left-aligned label whose height follows wrapped text."""
    label = Label(
        text=text,
        size_hint_y=None,
        height=dp(28),
        color=color or COLORS["text"],
        font_size=sp(font_size),
        bold=bold,
        halign="left",
        valign="top",
    )

    def update_width(widget, width):
        widget.text_size = (max(dp(120), width), None)

    def update_height(widget, texture_size):
        widget.height = max(dp(24), texture_size[1] + dp(4))

    label.bind(width=update_width, texture_size=update_height)
    return label


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


def _safe_init_db():
    """Init the database without taking the whole app down if storage fails.

    On Android an unhandled exception at import time kills the process before
    any UI appears, which looks like a random launch crash. Log it instead so
    the app can still start (and so adb logcat shows the real cause).
    """
    try:
        init_db()
    except Exception as error:  # noqa: BLE001 - startup must survive any storage failure
        print(f"Database init failed: {error!r}")

_safe_init_db()


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
        profile = get_user(user_id)
        using_default_routine = False
        try:
            routine_days = generate_weekly_routine(profile or {}, user_message)
        except RuntimeError:
            # Keep the demo usable without an API key or network connection.
            using_default_routine = True
            sample_routine = {
                "Monday": {"label": "Push Day", "exercises": ["Bench Press 3x10", "Overhead Press 3x12", "Tricep Dips 3x15"]},
                "Tuesday": {"label": "Pull Day", "exercises": ["Pull-ups 3x8", "Barbell Rows 3x10", "Bicep Curls 3x12"]},
                "Wednesday": {"label": "Rest Day", "exercises": ["Light Stretching / Walking"]},
                "Thursday": {"label": "Leg Day", "exercises": ["Squats 4x10", "Lunge 3x12", "Calf Raises 4x15"]},
                "Friday": {"label": "Core & Cardio", "exercises": ["Plank 3x60s", "HIIT 20 mins"]},
                "Saturday": {"label": "Active Recovery", "exercises": ["Yoga / Mobility Work"]},
                "Sunday": {"label": "Rest Day", "exercises": ["Rest"]},
            }
            routine_days = []
            for day_name, details in sample_routine.items():
                exercises = []
                for exercise_text in details["exercises"]:
                    name, sets, reps, duration_sec = _exercise_fields(exercise_text)
                    exercises.append({
                        "name": name,
                        "sets": sets,
                        "reps": reps,
                        "duration_sec": duration_sec,
                        "notes": None,
                    })
                routine_days.append({
                    "day_of_week": day_name,
                    "label": details["label"],
                    "exercises": exercises,
                })

        current_routine = get_current_routine(user_id)
        week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        routine_id = create_routine(
            user_id,
            week_start,
            source="chat_update" if current_routine else "initial",
        )
        for day in routine_days:
            day_id = add_routine_day(routine_id, day["day_of_week"], day["label"])
            for exercise in day["exercises"]:
                add_exercise(
                    day_id,
                    exercise["name"],
                    exercise["sets"],
                    exercise["reps"],
                    exercise["duration_sec"],
                    exercise["notes"],
                )
        linked_routine_id = routine_id
        if using_default_routine:
            response = "Gemini was unavailable, so I created a default 7-day workout plan. You can view it on the Routine tab."
        else:
            response = "I've generated a new 7-day workout routine tailored to your profile! You can view it on the Routine tab."
    elif intent in ("update_profile", "general_chat"):
        profile = get_user(user_id)
        injury_note_saved = False
        if intent == "update_profile":
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
                injury_note_saved = True
                profile = get_user(user_id)

        history = get_conversation_history(user_id, limit=12)
        if history and history[-1]["role"] == "user":
            history = history[:-1]
        current_routine = get_current_routine(user_id)
        try:
            coach_result = generate_coach_reply(
                profile or {}, user_message, history, current_routine
            )
            response = coach_result["reply"]
            routine_update = coach_result.get("routine_update")
            if routine_update:
                week_start = (
                    date.today() - timedelta(days=date.today().weekday())
                ).isoformat()
                routine_id = create_routine(
                    user_id,
                    week_start,
                    source="chat_update" if current_routine else "initial",
                )
                for day in routine_update["days"]:
                    day_id = add_routine_day(
                        routine_id, day["day_of_week"], day["label"]
                    )
                    for exercise in day["exercises"]:
                        add_exercise(
                            day_id,
                            exercise["name"],
                            exercise["sets"],
                            exercise["reps"],
                            exercise["duration_sec"],
                            exercise["notes"],
                        )
                linked_routine_id = routine_id
                response += " I've updated this week's routine for you."
        except RuntimeError as error:
            print(f"Gemini coach response unavailable: {error}")
            if injury_note_saved:
                response = "I've saved that recovery note. Avoid movements that cause pain, and consult a healthcare professional if symptoms are serious or worsening."
            else:
                response = "I couldn't reach the AI coach right now. Please try again in a moment."

    save_message(user_id, "assistant", response, linked_routine_id)
    return response


# -------------------------------------------------------------------
# Kivy UI Screens (Avoid KV Language)
# -------------------------------------------------------------------
class WelcomeScreen(Screen):
    def __init__(self, **kwargs):
        super(WelcomeScreen, self).__init__(**kwargs)
        _style_screen(self)
        layout = BoxLayout(
            orientation="vertical",
            padding=[dp(24), dp(32)],
            spacing=dp(20),
        )
        brand = Label(
            text="LIFTFORGE  /  TRAINING, BUILT AROUND YOU",
            color=COLORS["accent"],
            bold=True,
            font_size=sp(13),
            size_hint_y=None,
            height=dp(32),
            halign="left",
            valign="middle",
        )
        brand.bind(size=lambda label, _size: setattr(label, "text_size", label.size))

        hero = BoxLayout(
            orientation="vertical",
            padding=dp(22),
            spacing=dp(12),
        )
        _add_card_background(hero)
        title = Label(
            text="Build strength.\nFind your rhythm.",
            color=COLORS["text"],
            font_size=sp(34),
            bold=True,
            halign="left",
            valign="middle",
            size_hint_y=0.52,
        )
        title.bind(size=lambda label, _size: setattr(label, "text_size", label.size))
        desc = Label(
            text="A weekly plan shaped around your goals, experience, and real life.",
            color=COLORS["muted"],
            font_size=sp(17),
            halign="left",
            valign="top",
            size_hint_y=0.38,
        )
        desc.bind(size=lambda label, _size: setattr(label, "text_size", label.size))
        hero.add_widget(title)
        hero.add_widget(desc)

        steps = Label(
            text="01  Set your goals   ·   02  Get your week   ·   03  Adjust with your coach",
            color=COLORS["muted"],
            font_size=sp(13),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(48),
        )
        steps.bind(size=lambda label, _size: setattr(label, "text_size", label.size))
        btn = Button(text="Build my first routine", size_hint_y=None, height=dp(58))
        _style_button(btn, primary=True)
        btn.bind(on_release=self.go_next)

        layout.add_widget(brand)
        layout.add_widget(hero)
        layout.add_widget(steps)
        layout.add_widget(btn)
        self.add_widget(layout)

    def go_next(self, instance):
        self.manager.current = 'profile_setup'


class ProfileSetupScreen(Screen):
    def __init__(self, **kwargs):
        super(ProfileSetupScreen, self).__init__(**kwargs)
        _style_screen(self)
        layout = BoxLayout(
            orientation="vertical",
            padding=[dp(20), dp(18)],
            spacing=dp(12),
        )

        heading = Label(
            text="Your starting point",
            color=COLORS["text"],
            bold=True,
            font_size=sp(24),
            size_hint_y=None,
            height=dp(40),
            halign="left",
            valign="middle",
        )
        heading.bind(size=lambda label, _size: setattr(label, "text_size", label.size))
        layout.add_widget(heading)

        grid = GridLayout(cols=2, spacing=[dp(12), dp(10)], size_hint_y=0.82)
        grid.row_force_default = True
        grid.row_default_height = dp(50)

        grid.add_widget(self._field_label("Name"))
        self.inp_name = TextInput(multiline=False)
        self.inp_name.hint_text = "What should we call you?"
        _style_input(self.inp_name)
        profile = get_user(1)
        if profile:
            self.inp_name.text = profile["name"] or ""
        grid.add_widget(self.inp_name)

        grid.add_widget(self._field_label("Age"))
        self.inp_age = TextInput(multiline=False, input_filter="int", hint_text="Years")
        _style_input(self.inp_age)
        if profile and profile["age"] is not None:
            self.inp_age.text = str(profile["age"])
        grid.add_widget(self.inp_age)

        grid.add_widget(self._field_label("Goals"))
        self.inp_goals = TextInput(multiline=False)
        self.inp_goals.hint_text = "Strength, energy, mobility..."
        _style_input(self.inp_goals)
        if profile:
            self.inp_goals.text = ", ".join(profile["goals"])
        grid.add_widget(self.inp_goals)

        grid.add_widget(self._field_label("Experience"))
        experience_values = ["beginner", "intermediate", "advanced"]
        if profile and profile["experience_level"] and profile["experience_level"] not in experience_values:
            experience_values.append(profile["experience_level"])
        self.inp_exp = Spinner(
            text=(profile["experience_level"] if profile and profile["experience_level"] else "Choose level"),
            values=experience_values,
            size_hint_y=None,
            height=dp(50),
            background_normal="",
            background_down="",
            background_color=COLORS["surface_light"],
            color=COLORS["text"],
            font_size=sp(15),
        )
        if profile:
            self.inp_exp.text = profile["experience_level"] or "Choose level"
        grid.add_widget(self.inp_exp)

        grid.add_widget(self._field_label("Days per week"))
        self.inp_freq = Spinner(
            text=(str(profile["weekly_frequency"]) if profile and profile["weekly_frequency"] is not None else "Choose days"),
            values=[str(days) for days in range(1, 8)],
            size_hint_y=None,
            height=dp(50),
            background_normal="",
            background_down="",
            background_color=COLORS["surface_light"],
            color=COLORS["text"],
            font_size=sp(15),
        )
        if profile and profile["weekly_frequency"] is not None:
            self.inp_freq.text = str(profile["weekly_frequency"])
        grid.add_widget(self.inp_freq)

        layout.add_widget(grid)

        btn_save = Button(
            text="Save and build my week",
            size_hint_y=None,
            height=dp(58),
        )
        _style_button(btn_save, primary=True)
        btn_save.bind(on_release=self.save_and_continue)
        layout.add_widget(btn_save)

        self.add_widget(layout)

    @staticmethod
    def _field_label(text):
        """Create a consistently styled label for a profile field."""
        return Label(
            text=text,
            color=COLORS["muted"],
            font_size=sp(14),
            halign="left",
            valign="middle",
        )
        
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
        
        # Switch to Main App layout
        self.manager.current = 'main_app'
        # Generate a starter routine off the UI thread only when this week has none.
        if not has_current_routine:
            main_screen = self.manager.get_screen("main_app")
            main_screen.chat_tab.start_background_request(
                "Please generate my initial routine."
            )


class ChatTab(BoxLayout):
    def __init__(self, **kwargs):
        super(ChatTab, self).__init__(
            orientation="vertical",
            padding=[dp(14), dp(12)],
            spacing=dp(12),
            **kwargs,
        )

        header = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(58))
        title = Label(
            text="LiftForge Coach",
            color=COLORS["text"],
            font_size=sp(21),
            bold=True,
            halign="left",
            valign="middle",
        )
        title.bind(size=lambda label, _size: setattr(label, "text_size", label.size))
        subtitle = Label(
            text="Quick answers, practical changes",
            color=COLORS["muted"],
            font_size=sp(13),
            halign="left",
            valign="middle",
        )
        subtitle.bind(size=lambda label, _size: setattr(label, "text_size", label.size))
        header.add_widget(title)
        header.add_widget(subtitle)

        # The scroll panel keeps longer conversations readable on a phone.
        self.scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        _add_card_background(self.scroll)
        self.chat_log = Label(
            text="AI Assistant: Hello! How can I help with your routine today?\n",
            size_hint_y=None,
            halign="left",
            valign="top",
            color=COLORS["text"],
            font_size=sp(15),
            padding=[dp(16), dp(16)],
        )
        messages = get_conversation_history(1)
        if messages:
            self.chat_log.text = "".join(
                f"{'You' if message['role'] == 'user' else 'AI'}: {message['content']}\n"
                for message in messages
            )
        self.chat_log.bind(texture_size=self._update_text_size, width=self._update_text_size)
        self.scroll.add_widget(self.chat_log)
        self.scroll.bind(size=self._update_text_size)
        self.add_widget(self.scroll)

        input_box = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(62),
            spacing=dp(10),
        )
        self.msg_input = TextInput(
            multiline=True,
            hint_text="Ask about your training...",
        )
        _style_input(self.msg_input)
        self.send_button = Button(text="Send", size_hint_x=None, width=dp(84))
        _style_button(self.send_button, primary=True)
        self.send_button.bind(on_release=self.send_message)

        input_box.add_widget(self.msg_input)
        input_box.add_widget(self.send_button)
        self.add_widget(input_box)
        
    def _update_text_size(self, instance, _value):
        self.chat_log.text_size = (max(dp(120), self.scroll.width - dp(32)), None)
        self.chat_log.height = self.chat_log.texture_size[1] + dp(32)
        
    def send_message(self, instance):
        text = self.msg_input.text.strip()
        if text:
            self.start_background_request(text)

    def start_background_request(self, user_message):
        """Show immediate feedback, then handle the chat request off the UI thread."""
        self.chat_log.text += f"\nYou: {user_message}\nAI: Thinking...\n"
        self.scroll.scroll_y = 0
        self.msg_input.text = ""
        self.msg_input.disabled = True
        self.send_button.disabled = True
        try:
            worker = Thread(
                target=self._run_background_request,
                args=(user_message,),
                daemon=True,
            )
            worker.start()
        except Exception as error:
            print(f"Could not start chat worker: {error!r}")
            Clock.schedule_once(
                lambda _dt: self._finish_background_request(
                    "Something went wrong generating a reply, please try again."
                ),
                0,
            )

    def _run_background_request(self, user_message):
        """Run database and Gemini work in a worker and schedule its UI result."""
        try:
            response = mock_backend_chat(user_message)
            if not response:
                response = "I couldn't generate a reply. Please try again."
            Clock.schedule_once(
                lambda _dt: self._finish_background_request(response), 0
            )
        except Exception as error:
            # Keep an unexpected worker failure visible in logs and in the chat.
            print(f"Unexpected error while generating a chat reply: {error!r}")
            Clock.schedule_once(
                lambda _dt: self._finish_background_request(
                    "Something went wrong generating a reply, please try again."
                ),
                0,
            )

    def _finish_background_request(self, response):
        """Update Kivy widgets on the main thread after the worker finishes."""
        self.chat_log.text = self.chat_log.text.replace("AI: Thinking...\n", "", 1)
        self.chat_log.text += f"AI: {response}\n"
        self.scroll.scroll_y = 0
        self.msg_input.disabled = False
        self.send_button.disabled = False

        app = App.get_running_app()
        if app and app.root and "main_app" in app.root.screen_names:
            main_screen = app.root.get_screen("main_app")
            main_screen.routine_tab.load_routine(None)
            main_screen.account_tab.load_profile(None)


class RoutineTab(BoxLayout):
    def __init__(self, **kwargs):
        super(RoutineTab, self).__init__(
            orientation="vertical",
            padding=[dp(14), dp(12)],
            spacing=dp(10),
            **kwargs,
        )

        title = _make_wrapping_label("Your week", font_size=22, bold=True)
        title.height = dp(34)
        self.add_widget(title)

        self.scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        _add_card_background(self.scroll)
        self.routine_content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(10),
            padding=[dp(10), dp(10)],
        )
        self.routine_content.bind(
            minimum_height=self.routine_content.setter("height")
        )
        self.scroll.add_widget(self.routine_content)
        self.add_widget(self.scroll)

        self.routine_display = _make_wrapping_label(
            "Your weekly plan will appear here.", color=COLORS["muted"], font_size=13
        )
        self.routine_display.height = dp(30)
        self.add_widget(self.routine_display)

        btn_box = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(56),
            spacing=dp(10),
        )
        btn_refresh = Button(text="Refresh")
        _style_button(btn_refresh)
        btn_refresh.bind(on_release=self.load_routine)
        btn_export = Button(text="Export calendar")
        _style_button(btn_export, primary=True)
        btn_export.bind(on_release=self.export_ics)

        btn_box.add_widget(btn_refresh)
        btn_box.add_widget(btn_export)
        self.add_widget(btn_box)

        self.load_routine(None)

    def load_routine(self, instance):
        routine = get_current_routine(1)
        self.routine_content.clear_widgets()
        if not routine or not routine["days"]:
            self.routine_display.text = "No plan saved yet. Start in Coach to build your first week."
            empty_card = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                height=dp(126),
                padding=dp(16),
                spacing=dp(8),
            )
            _add_card_background(empty_card)
            empty_card.add_widget(_make_wrapping_label(
                "Your plan will appear here once the coach builds it.",
                color=COLORS["muted"],
            ))
            ask_coach = Button(text="Open Coach", size_hint_y=None, height=dp(48))
            _style_button(ask_coach, primary=True)
            ask_coach.bind(on_release=lambda _button: self._open_coach())
            empty_card.add_widget(ask_coach)
            self.routine_content.add_widget(empty_card)
            return

        training_days = sum(bool(day["exercises"]) for day in routine["days"])
        self.routine_display.text = (
            f"WEEK OF {routine['week_start']}  ·  {training_days} TRAINING DAYS"
        )
        for day in routine["days"]:
            day_card = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                padding=dp(14),
                spacing=dp(8),
            )
            day_card.bind(minimum_height=day_card.setter("height"))
            _add_card_background(day_card)
            day_card.add_widget(_make_wrapping_label(
                f"{day['day_of_week']}  /  {day['label']}",
                color=COLORS["accent"],
                font_size=16,
                bold=True,
            ))
            if not day["exercises"]:
                day_card.add_widget(_make_wrapping_label(
                    "Recovery day · no session scheduled",
                    color=COLORS["muted"],
                    font_size=14,
                ))
            for exercise in day["exercises"]:
                description = exercise["name"]
                if exercise["sets"] is not None and exercise["reps"]:
                    description += f"  ·  {exercise['sets']} × {exercise['reps']}"
                if exercise["duration_sec"]:
                    description += f"  ·  {exercise['duration_sec']} sec"
                day_card.add_widget(_make_wrapping_label(f"•  {description}"))
                if exercise["notes"]:
                    day_card.add_widget(_make_wrapping_label(
                        exercise["notes"], color=COLORS["muted"], font_size=13
                    ))
            self.routine_content.add_widget(day_card)

    def _open_coach(self):
        """Open the coach from the routine's helpful empty state."""
        app = App.get_running_app()
        if app and app.root:
            app.root.get_screen("main_app").switch_tab("chat")

    def export_ics(self, instance):
        # Universal .ics fallback export (Section 7)
        ics_content = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//AI Fitness App//EN\n"
        ics_content += "BEGIN:VEVENT\nSUMMARY:AI Workout Session\nDESCRIPTION:Scheduled Fitness Routine\nEND:VEVENT\n"
        ics_content += "END:VCALENDAR"
        
        with open("workout_schedule.ics", "w") as f:
            f.write(ics_content)
        self.routine_display.text = "Calendar export saved as workout_schedule.ics"


class AccountTab(BoxLayout):
    def __init__(self, **kwargs):
        super(AccountTab, self).__init__(
            orientation="vertical",
            padding=[dp(16), dp(14)],
            spacing=dp(14),
            **kwargs,
        )

        title = _make_wrapping_label("Your profile", font_size=22, bold=True)
        title.height = dp(34)
        self.add_widget(title)

        self.profile_card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(18),
            spacing=dp(12),
        )
        self.profile_card.bind(
            minimum_height=self.profile_card.setter("height")
        )
        _add_card_background(self.profile_card)
        self.profile_card.add_widget(_make_wrapping_label(
            "TRAINING PROFILE", color=COLORS["accent"], font_size=13, bold=True
        ))
        self.profile_info = _make_wrapping_label(
            "Loading profile...", color=COLORS["text"], font_size=16
        )
        self.profile_card.add_widget(self.profile_info)
        self.add_widget(self.profile_card)

        actions = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(116),
            spacing=dp(10),
        )
        btn_edit = Button(text="Edit profile", size_hint_y=None, height=dp(54))
        _style_button(btn_edit, primary=True)
        btn_edit.bind(on_release=self.edit_profile)
        btn_reload = Button(text="Reload profile", size_hint_y=None, height=dp(48))
        _style_button(btn_reload)
        btn_reload.bind(on_release=self.load_profile)
        actions.add_widget(btn_edit)
        actions.add_widget(btn_reload)
        self.add_widget(actions)

        self.load_profile(None)

    def edit_profile(self, instance):
        """Open the existing profile form so users can update their details."""
        app = App.get_running_app()
        if app and app.root:
            app.root.current = "profile_setup"

    def load_profile(self, instance):
        profile = get_user(1)
        if profile:
            goals = ", ".join(profile["goals"])
            text = (
                f"Name: {profile['name']}\nAge: {profile['age'] or ''}\n"
                f"Goals: {goals}\nExperience: {profile['experience_level'] or ''}\n"
                f"Frequency: {profile['weekly_frequency'] or ''} days/week\n"
                f"Notes: {profile['injuries'] or 'None'}"
            )
            self.profile_info.text = text


class MainAppScreen(Screen):
    """
    Main container screen holding the persistent bottom tab bar and 3 main views (Section 3).
    """
    def __init__(self, **kwargs):
        super(MainAppScreen, self).__init__(**kwargs)
        _style_screen(self)
        root_layout = BoxLayout(orientation="vertical", spacing=dp(8))

        # Content view dynamic container
        self.content_area = BoxLayout(orientation="vertical", size_hint_y=0.88)

        # A persistent bottom bar makes the three existing app sections easy to reach.
        tab_bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=0.12,
            spacing=dp(8),
            padding=[dp(10), dp(6)],
        )

        btn_chat = Button(text="Coach")
        _style_button(btn_chat, primary=True)
        btn_chat.bind(on_release=lambda x: self.switch_tab('chat'))

        btn_routine = Button(text="My Week")
        _style_button(btn_routine)
        btn_routine.bind(on_release=lambda x: self.switch_tab('routine'))

        btn_account = Button(text="Profile")
        _style_button(btn_account)
        btn_account.bind(on_release=lambda x: self.switch_tab('account'))

        self.nav_buttons = {
            "chat": btn_chat,
            "routine": btn_routine,
            "account": btn_account,
        }
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
        if tab_name not in self.nav_buttons:
            return
        for name, button in self.nav_buttons.items():
            _set_button_primary(button, name == tab_name)
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
        init_db()
        Window.bind(on_keyboard=self.on_keyboard)
        self.sm = ScreenManager(transition=FadeTransition())
        self.sm.add_widget(WelcomeScreen(name='welcome'))
        self.sm.add_widget(ProfileSetupScreen(name='profile_setup'))
        self.sm.add_widget(MainAppScreen(name='main_app'))
        profile = get_user(1)
        if profile and (profile["name"] or "").strip():
            self.sm.current = "main_app"
        return self.sm

    def on_keyboard(self, window, key, *args):
        # Keycode 27 corresponds to the Android hardware Back button and Desktop Esc
        if key == 27:
            if hasattr(self, "sm") and self.sm.current == "profile_setup":
                self.sm.current = "welcome"
                return True
        return False


if __name__ == '__main__':
    FitWorksAI().run()