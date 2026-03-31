"""Modal screen for editing an existing task."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet

from quest.models import Task
from tui.screens.add_task_screen import AddTaskResult


def _due_date_radios(due: str | None) -> tuple[bool, bool, bool]:
    """Return (today, tomorrow, none) with exactly one True."""
    today_iso = date.today().isoformat()
    tomorrow_iso = (date.today() + timedelta(days=1)).isoformat()
    if due is None:
        return False, False, True
    if due == today_iso:
        return True, False, False
    if due == tomorrow_iso:
        return False, True, False
    return False, False, True


def _due_date_custom(due: str | None) -> str:
    """Return due date for custom field if it is not today/tomorrow."""
    if due is None:
        return ""
    today_iso = date.today().isoformat()
    tomorrow_iso = (date.today() + timedelta(days=1)).isoformat()
    if due in (today_iso, tomorrow_iso):
        return ""
    return due


def _priority_radios(priority: str) -> tuple[bool, bool, bool, bool]:
    order = ("urgent", "high", "normal", "low")
    result = tuple(p == priority for p in order)
    if not any(result):
        return (False, False, True, False)
    return result


def _size_radios(size: str) -> tuple[bool, bool, bool, bool, bool]:
    order = ("tiny", "small", "medium", "large", "epic")
    result = tuple(s == size for s in order)
    if not any(result):
        return (False, True, False, False, False)
    return result


class RichEditTaskScreen(ModalScreen[AddTaskResult | None]):
    """Modal for editing title, priority, size, and due date of a task."""

    def __init__(self, task: Task, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Do not use "_task" — Textual's MessagePump reserves it for asyncio.Task.
        self._quest_task = task

    DEFAULT_CSS = """
    RichEditTaskScreen {
        align: center middle;
    }
    #edit-task-box {
        width: 64;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    #edit-task-title {
        width: 100%;
        margin-bottom: 1;
    }
    .field-label {
        color: $text-muted;
        margin-top: 1;
        height: 1;
    }
    #edit-save-btn {
        margin-top: 1;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_none", "Cancel", show=False),
    ]

    def compose(self) -> ComposeResult:
        t = self._quest_task
        due_today, due_tomorrow, due_none = _due_date_radios(t.due_date)
        pr_urgent, pr_high, pr_normal, pr_low = _priority_radios(t.priority)
        sz_tiny, sz_small, sz_medium, sz_large, sz_epic = _size_radios(t.size)
        custom_date = _due_date_custom(t.due_date)

        with Vertical(id="edit-task-box"):
            yield Label(
                f"[bold]Edit Task[/bold]  [dim]#{t.id} · j/k navigate · Shift+Enter save · Esc cancel[/dim]",
                markup=True,
            )
            yield Input(value=t.title, placeholder="Task title…", id="edit-task-title")

            yield Label("Priority", classes="field-label", markup=False)
            with RadioSet(id="priority-set"):
                yield RadioButton("urgent", value=pr_urgent)
                yield RadioButton("high", value=pr_high)
                yield RadioButton("normal", value=pr_normal)
                yield RadioButton("low", value=pr_low)

            yield Label("Size", classes="field-label", markup=False)
            with RadioSet(id="size-set"):
                yield RadioButton("tiny", value=sz_tiny)
                yield RadioButton("small", value=sz_small)
                yield RadioButton("medium", value=sz_medium)
                yield RadioButton("large", value=sz_large)
                yield RadioButton("epic", value=sz_epic)

            yield Label("Due date", classes="field-label", markup=False)
            with RadioSet(id="date-set"):
                yield RadioButton("today", value=due_today)
                yield RadioButton("tomorrow", value=due_tomorrow)
                yield RadioButton("none", value=due_none)
            yield Label("Custom date (YYYY-MM-DD)", classes="field-label", markup=False)
            yield Input(
                value=custom_date,
                placeholder="e.g. 2026-04-15 — overrides preset above",
                id="edit-custom-date",
            )

            yield Button("Save changes", id="edit-save-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#edit-task-title", Input).focus()

    def _build_result(self) -> AddTaskResult | None:
        title = self.query_one("#edit-task-title", Input).value.strip()
        if not title:
            self.app.notify("Title cannot be empty", severity="warning")
            return None

        priority_btn = self.query_one("#priority-set", RadioSet).pressed_button
        size_btn = self.query_one("#size-set", RadioSet).pressed_button
        date_btn = self.query_one("#date-set", RadioSet).pressed_button

        priority = str(priority_btn.label) if priority_btn else "normal"
        size = str(size_btn.label) if size_btn else "small"
        date_choice = str(date_btn.label) if date_btn else "today"

        custom_raw = self.query_one("#edit-custom-date", Input).value.strip()
        if custom_raw:
            try:
                due_date: str | None = date.fromisoformat(custom_raw).isoformat()
            except ValueError:
                self.app.notify("Invalid date — use YYYY-MM-DD", severity="warning")
                return None
        elif date_choice == "today":
            due_date = date.today().isoformat()
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
        if event.button.id == "edit-save-btn":
            self._submit()

    def on_input_submitted(self, _: Input.Submitted) -> None:
        self.focus_next()

    def on_key(self, event: events.Key) -> None:
        focused = self.focused
        if event.key == "shift+enter":
            self._submit()
            event.stop()
        elif event.key == "j" and isinstance(focused, RadioSet):
            focused.action_next_button()
            event.stop()
        elif event.key == "k" and isinstance(focused, RadioSet):
            focused.action_previous_button()
            event.stop()

    def action_dismiss_none(self) -> None:
        self.dismiss(None)
