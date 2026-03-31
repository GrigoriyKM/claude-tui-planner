"""Modal screen for inspecting full task details."""

from __future__ import annotations

import sys as _sys
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

_QUEST_ROOT = str(Path.home() / ".claude" / "quest")
if _QUEST_ROOT not in _sys.path:
    _sys.path.insert(0, _QUEST_ROOT)

from quest.models import Task


class DetailScreen(ModalScreen):
    """Modal that shows full details of a task."""

    DEFAULT_CSS = """
    DetailScreen {
        align: center middle;
    }
    #detail-content {
        width: 62;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("q", "dismiss", "Close", show=False),
        Binding("i", "dismiss", "Close", show=False),
        Binding("escape", "dismiss", "Close", show=False),
    ]

    def __init__(self, task: Task) -> None:
        super().__init__()
        self._quest_task = task

    def compose(self) -> ComposeResult:
        yield Static(self._build_content(), id="detail-content", markup=True)

    def _build_content(self) -> str:
        task = self._quest_task
        lines: list[str] = []
        lines.append(f"[bold]#{task.id} — {task.title}[/bold]\n")

        if task.description:
            lines.append(f"{task.description}\n")

        lines.append(
            f"[dim]Size:[/dim]    {task.size}  ([cyan]{task.xp_value} XP[/cyan])"
        )
        lines.append(f"[dim]Status:[/dim]  {task.status}")

        if task.due_date:
            lines.append(f"[dim]Due:[/dim]     {task.due_date}")
        if task.snooze_until:
            lines.append(f"[dim]Snoozed:[/dim] until {task.snooze_until}")
        if task.parent_id:
            lines.append(f"[dim]Parent:[/dim]  #{task.parent_id}")
        if task.completed_at:
            lines.append(
                f"[dim]Done:[/dim]    {task.completed_at}  (+{task.xp_earned} XP)"
            )

        lines.append(f"\n[dim]Created: {task.created_at}[/dim]")
        lines.append("\n[dim]Press i, q, or Esc to close.[/dim]")

        return "\n".join(lines)
