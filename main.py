# imports
import json
import sqlite3
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView


#-----------------------------------------------------------------------
# Database Setup (SQLite local persistence)
#-----------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect("app_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY,
            name TEXT,
            age TEXT,
            height TEXT,
            weight TEXT,
            goals TEXT,
            experience TEXT,
            frequency TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS current_routine (
            id INTEGER PRIMARY KEY,
            routine_json TEXT
        )
    """)
    
    # Initilize empty profile record if missing
    cursor.execute("SELECT COUNT(*) FROM profile WHERE id = 1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO profile (id, name, age, height, weight, goals, experience, frequency)
            VALUES (1, '', '', '', '', '', '', '')
        """)
    conn.commit()
    conn.close()

init_db()


#-----------------------------------------------------------------------
# Backend Mock / Local Proxy
#-----------------------------------------------------------------------
def mock_backend_chat(user_message):
    """
    Simulates /chat API endpoint proxy behavior.
    Updates database/routine data structure depending on context.
    """
    conn = sqlite3.connect("app_data.db")
    cursor = conn.cursor()
    
    # Save user message
    cursor.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", ("user", user_message))
    
    msg_lower = user_message.lower()
    
    if "generate" in msg_lower or "routine" in msg_lower or "workout" in msg_lower:
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
        cursor.execute("INSERT OR REPLACE INTO current_routine (id, routine_json) VALUES (1, ?)", 
                       (json.dumps(sample_routine),))
        response = "I've generated a new 7-day workout routine tailored to your profile! You can view it on the Routine tab."
    elif "sprain" in msg_lower or "injury" in msg_lower or "update" in msg_lower:
        # Mock profile/routine adjustment via conversation (Section 6.3)
        response = "I've updated your profile notes regarding your recovery. I have adjusted your routine to reduce leg intensity."
    else:
        response = f"I'm your AI Fitness Assistant. You said: '{user_message}'. How can I adjust your routine today?"

    # Save assistant message
    cursor.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", ("assistant", response))
    conn.commit()
    conn.close()
    
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
        grid.add_widget(self.inp_name)
        
        grid.add_widget(Label(text="Age:"))
        self.inp_age = TextInput(multiline=False)
        grid.add_widget(self.inp_age)
        
        grid.add_widget(Label(text="Goals:"))
        self.inp_goals = TextInput(multiline=False)
        grid.add_widget(self.inp_goals)
        
        grid.add_widget(Label(text="Experience Level:"))
        self.inp_exp = TextInput(multiline=False)
        grid.add_widget(self.inp_exp)
        
        grid.add_widget(Label(text="Weekly Frequency:"))
        self.inp_freq = TextInput(multiline=False)
        grid.add_widget(self.inp_freq)
        
        layout.add_widget(grid)
        
        btn_save = Button(text="Generate Routine & Continue", size_hint_y=None, height=50)
        btn_save.bind(on_release=self.save_and_continue)
        layout.add_widget(btn_save)
        
        self.add_widget(layout)
        
    def save_and_continue(self, instance):
        conn = sqlite3.connect("app_data.db")
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE profile SET name=?, age=?, goals=?, experience=?, frequency=? WHERE id=1
        """, (self.inp_name.text, self.inp_age.text, self.inp_goals.text, self.inp_exp.text, self.inp_freq.text))
        conn.commit()
        conn.close()
        
        # Trigger initial routine generation via mock backend
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
        conn = sqlite3.connect("app_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT routine_json FROM current_routine WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            routine = json.loads(row[0])
            out_text = "=== YOUR WEEKLY ROUTINE ===\n\n"
            for day, details in routine.items():
                out_text += f"• {day}: {details['label']}\n"
                for ex in details['exercises']:
                    out_text += f"    - {ex}\n"
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
        conn = sqlite3.connect("app_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name, age, goals, experience, frequency FROM profile WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            text = f"Name: {row[0]}\nAge: {row[1]}\nGoals: {row[2]}\nExperience: {row[3]}\nFrequency: {row[4]} days/week"
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
        return sm


if __name__ == '__main__':
    FitWorksAI().run()