"""Rich modal screen for adding a new task with priority, size, and due date."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet


@dataclass(frozen=True)
class AddTaskResult:
    title: str
    priority: str  # urgent | high | normal | low
    size: str  # tiny | small | medium | large | epic
    due_date: str | None  # ISO date string or None


class RichAddTaskScreen(ModalScreen[AddTaskResult | None]):
    """Modal for adding a task with priority, size, and due date."""

    def __init__(
        self, *args: Any, default_due_tomorrow: bool = False, **kwargs: Any
    ) -> None:
        """Create the modal.

        Args:
            default_due_tomorrow: If True, pre-select "tomorrow" in the due date row (e.g. TUI is in tomorrow view).
        """
        super().__init__(*args, **kwargs)
        self._default_due_tomorrow = default_due_tomorrow

    DEFAULT_CSS = """
    RichAddTaskScreen {
        align: center middle;
    }
    #add-task-box {
        width: 64;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    #add-task-title {
        width: 100%;
        margin-bottom: 1;
    }
    .field-label {
        color: $text-muted;
        margin-top: 1;
        height: 1;
    }
    #add-btn {
        margin-top: 1;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_none", "Cancel", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="add-task-box"):
            yield Label(
                "[bold]Add Task[/bold]  [dim](Enter to save · Esc to cancel)[/dim]",
                markup=True,
            )
            yield Input(placeholder="Task title…", id="add-task-title")

            yield Label("Priority", classes="field-label", markup=False)
            with RadioSet(id="priority-set"):
                yield RadioButton("urgent")
                yield RadioButton("high")
                yield RadioButton("normal", value=True)
                yield RadioButton("low")

            yield Label("Size", classes="field-label", markup=False)
            with RadioSet(id="size-set"):
                yield RadioButton("tiny")
                yield RadioButton("small", value=True)
                yield RadioButton("medium")
                yield RadioButton("large")
                yield RadioButton("epic")

            yield Label("Due date", classes="field-label", markup=False)
            with RadioSet(id="date-set"):
                yield RadioButton("today", value=not self._default_due_tomorrow)
                yield RadioButton("tomorrow", value=self._default_due_tomorrow)
                yield RadioButton("none")

            yield Button("Add Task", id="add-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#add-task-title", Input).focus()

    def _build_result(self) -> AddTaskResult | None:
        title = self.query_one("#add-task-title", Input).value.strip()
        if not title:
            self.app.notify("Title cannot be empty", severity="warning")
            return None

        priority_btn = self.query_one("#priority-set", RadioSet).pressed_button
        size_btn = self.query_one("#size-set", RadioSet).pressed_button
        date_btn = self.query_one("#date-set", RadioSet).pressed_button

        priority = str(priority_btn.label) if priority_btn else "normal"
        size = str(size_btn.label) if size_btn else "small"
        date_choice = str(date_btn.label) if date_btn else "today"

        if date_choice == "today":
            due_date: str | None = date.today().isoformat()
        elif date_choice == "tomorrow":
            due_date = (date.today() + timedelta(days=1)).isoformat()
        else:
            due_date = None

        return AddTaskResult(
            title=title, priority=priority, size=size, due_date=due_date
        )

    def _submit(self) -> None:
        result = self._build_result()
        if result is not None:
            self.dismiss(result)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-btn":
            self._submit()

    def on_input_submitted(self, _: Input.Submitted) -> None:
        self._submit()

    def on_key(self, event: events.Key) -> None:
        if event.key == "enter" and isinstance(self.focused, RadioSet):
            self._submit()
            event.stop()

    def action_dismiss_none(self) -> None:
        self.dismiss(None)
