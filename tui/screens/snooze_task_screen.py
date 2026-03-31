"""Modal screen to snooze a task until a chosen date."""

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


_PRESET_DAYS: dict[str, int] = {
    "tomorrow": 1,
    "in 7 days": 7,
    "in 14 days": 14,
}


class SnoozeTaskScreen(ModalScreen[str | None]):
    """Pick when the task should become active again (snooze_until, YYYY-MM-DD)."""

    def __init__(self, task: Task, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._quest_task = task

    DEFAULT_CSS = """
    SnoozeTaskScreen {
        align: center middle;
    }
    #snooze-task-box {
        width: 64;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    #snooze-custom-date {
        width: 100%;
        margin-top: 1;
    }
    .field-label {
        color: $text-muted;
        margin-top: 1;
        height: 1;
    }
    #snooze-save-btn {
        margin-top: 1;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_none", "Cancel", show=False),
    ]

    def compose(self) -> ComposeResult:
        t = self._quest_task
        with Vertical(id="snooze-task-box"):
            yield Label(
                f"[bold]Snooze task[/bold]  [dim]#{t.id}[/dim]\n"
                f"[dim]{t.title[:52]}{'…' if len(t.title) > 52 else ''}[/dim]\n"
                f"[dim]Wake on or after date · Enter to confirm · Esc to cancel[/dim]\n"
                f"[dim]Typing YYYY-MM-DD below overrides the preset above.[/dim]",
                markup=True,
            )
            yield Label("Resume on", classes="field-label", markup=False)
            with RadioSet(id="snooze-preset"):
                yield RadioButton("tomorrow", value=True)
                yield RadioButton("in 7 days")
                yield RadioButton("in 14 days")
            yield Input(placeholder="YYYY-MM-DD (optional override)", id="snooze-custom-date")
            yield Button("Snooze", id="snooze-save-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#snooze-preset", RadioSet).focus()

    def _parse_custom_date(self, raw: str) -> str | None:
        """Parse YYYY-MM-DD from user input; notify and return None on error."""
        try:
            d = date.fromisoformat(raw)
        except ValueError:
            self.notify("Invalid date — use YYYY-MM-DD", severity="warning")
            return None
        if d <= date.today():
            self.notify("Date must be in the future", severity="warning")
            return None
        return d.isoformat()

    def _until_date_from_choice(self) -> str | None:
        raw = self.query_one("#snooze-custom-date", Input).value.strip()
        if raw:
            return self._parse_custom_date(raw)

        preset_btn = self.query_one("#snooze-preset", RadioSet).pressed_button
        label = str(preset_btn.label) if preset_btn else "tomorrow"
        days = _PRESET_DAYS.get(label, 1)
        return (date.today() + timedelta(days=days)).isoformat()

    def _submit(self) -> None:
        until = self._until_date_from_choice()
        if until is not None:
            self.dismiss(until)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "snooze-save-btn":
            self._submit()

    def on_input_submitted(self, _: Input.Submitted) -> None:
        self._submit()

    def on_key(self, event: events.Key) -> None:
        focused = self.focused
        if event.key == "enter" and isinstance(focused, RadioSet):
            self._submit()
            event.stop()
        elif event.key in ("j", "о") and isinstance(focused, RadioSet):
            focused.action_next_button()
            event.stop()
        elif event.key in ("k", "л") and isinstance(focused, RadioSet):
            focused.action_previous_button()
            event.stop()

    def action_dismiss_none(self) -> None:
        self.dismiss(None)
