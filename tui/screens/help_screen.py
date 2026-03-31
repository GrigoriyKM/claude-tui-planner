"""Modal screen for displaying keybinding help."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

HELP_TEXT = """
[bold]QUEST — Keybindings[/bold]

  j / ↓        Move cursor down
  k / ↑        Move cursor up
  ctrl+d       Half-page down
  ctrl+u       Half-page up
  h / ← / S-Tab  Cycle filter backward
  l / → / Tab  Cycle filter forward (all→today→overdue→snoozed→done)
  g / G        First / last task
  Enter/Space  Toggle done / undo
  a            Add new task
  e            Edit selected task
  z            Snooze task until a date
  dd           Delete task (press d twice)
  i            Inspect task (full details)
  y            Yank (copy) task title
  r            Refresh data from DB
  n            Toggle notes panel
  N            Focus notes panel (Esc to return)
  \[           On Today tab: toggle today / tomorrow (or cycle done range in Done filter)
  ?            Toggle this help
  q            Close help / Quit

[bold]Priority icons[/bold]

  [bold][red]↑↑[/red][/bold]  urgent — горит, блокирует других, дедлайн сегодня
  [yellow]↑ [/yellow]  high   — важно, хочется сделать сегодня
      normal — обычная задача
  [dim]↓ [/dim]  low    — когда-нибудь, не срочно

[dim]Press ?, q, or Esc to close.[/dim]
"""


class HelpScreen(ModalScreen):
    """Modal screen showing keybinding help."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-content {
        width: 56;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("q", "dismiss", "Close", show=False),
        Binding("й", "dismiss", "Close", show=False),
        Binding("question_mark", "dismiss", "Close", show=False),
        Binding("escape", "dismiss", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Static(HELP_TEXT, id="help-content", markup=True)
