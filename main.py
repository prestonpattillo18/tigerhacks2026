from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner


def make_routine(goal, location, wanted_days, current_days):
    """Make a sample routine based on the user's choices."""
    if goal == "Build Muscle":
        workout = "Upper Body, Lower Body, and Full Body"
    elif goal == "Lose Weight":
        workout = "Cardio and Full Body"
    elif goal == "Get Stronger":
        workout = "Strength Training"
    elif goal == "Recovery":
        workout = "Gentle Movement and Stretching"
    else:
        workout = "Cardio and Full Body"

    return (
        f"Your routine for {location}:\n\n"
        f"Goal: {goal}\n"
        f"Current workouts: {current_days} days/week\n"
        f"Desired workouts: {wanted_days} days/week\n\n"
        f"Suggested workout types: {workout}"
    )


class WorkoutApp(App):
    def build(self):
        scroll = ScrollView()

        layout = BoxLayout(
            orientation="vertical",
            padding=20,
            spacing=12,
            size_hint_y=None
        )
        layout.bind(minimum_height=layout.setter("height"))

        title = Label(
            text="Personalized Workout Planner",
            font_size=26,
            size_hint_y=None,
            height=65
        )
        layout.add_widget(title)

        layout.add_widget(self.make_label("Weight (lbs)"))
        self.weight_input = TextInput(
            multiline=False,
            input_filter="int",
            size_hint_y=None,
            height=45
        )
        layout.add_widget(self.weight_input)

        layout.add_widget(self.make_label("Main Goal"))
        self.goal_spinner = Spinner(
            text="Choose a goal",
            values=(
                "Build Muscle",
                "Lose Weight",
                "Get Stronger",
                "Stay in Shape",
                "Recovery"
            ),
            size_hint_y=None,
            height=45
        )
        layout.add_widget(self.goal_spinner)

        layout.add_widget(self.make_label("Workout Location"))
        self.location_spinner = Spinner(
            text="Choose location",
            values=("Just Dumbbells at Home", "Home Gym", "Apartment Gym", "Full Gym"),
            size_hint_y=None,
            height=45
        )
        layout.add_widget(self.location_spinner)

        layout.add_widget(self.make_label("How many days do you want to work out?"))
        self.wanted_days_spinner = Spinner(
            text="Choose days per week",
            values=tuple(str(day) for day in range(1, 8)),
            size_hint_y=None,
            height=45
        )
        layout.add_widget(self.wanted_days_spinner)

        layout.add_widget(self.make_label("How many days do you work out now?"))
        self.current_days_spinner = Spinner(
            text="Choose days per week",
            values=tuple(str(day) for day in range(0, 8)),
            size_hint_y=None,
            height=45
        )
        layout.add_widget(self.current_days_spinner)

        submit_button = Button(
            text="Make My Routine",
            size_hint_y=None,
            height=55
        )
        submit_button.bind(on_press=self.show_routine)
        layout.add_widget(submit_button)

        self.output_label = Label(
            text="",
            size_hint_y=None,
            height=200,
            halign="left",
            valign="top"
        )
        self.output_label.bind(width=self.wrap_output_text)
        layout.add_widget(self.output_label)

        scroll.add_widget(layout)
        return scroll

    def make_label(self, text):
        return Label(
            text=text,
            size_hint_y=None,
            height=30,
            halign="left"
        )

    def wrap_output_text(self, label, width):
        label.text_size = (width, None)

    def show_routine(self, instance):
        goal = self.goal_spinner.text
        location = self.location_spinner.text
        wanted_days = self.wanted_days_spinner.text
        current_days = self.current_days_spinner.text

        if (
            goal == "Choose a goal"
            or location == "Choose location"
            or wanted_days == "Choose days per week"
            or current_days == "Choose days per week"
        ):
            self.output_label.text = "Please answer all the questions above."
            return

        self.output_label.text = make_routine(
            goal, location, wanted_days, current_days
        )


if __name__ == "__main__":
    WorkoutApp().run()