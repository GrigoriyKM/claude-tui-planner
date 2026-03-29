"""Scrollable task list widget with sections and vim navigation."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Union

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

logger = logging.getLogger(__name__)

import sys as _sys

_QUEST_ROOT = str(Path.home() / ".claude" / "quest")
if _QUEST_ROOT not in _sys.path:
    _sys.path.insert(0, _QUEST_ROOT)

from quest.models import Task


# ---------------------------------------------------------------------------
# Row model — a union of task row and section header
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SectionHeader:
    label: str
    count: int


ListRow = Union[SectionHeader, Task]

FILTER_MODES = ["all", "today", "overdue", "snoozed", "done"]


def _status_icon(status: str) -> str:
    icons = {
        "done": "[green][✓][/green]",
        "pending": "[ ]",
        "in_progress": "[ ]",
        "overdue": "[red][!][/red]",
        "snoozed": "[yellow][z][/yellow]",
        "cancelled": "[dim][x][/dim]",
    }
    return icons.get(status, "[ ]")


def _priority_icon(priority: str) -> str:
    icons = {
        "urgent": "[bold red]↑↑[/bold red]",
        "high":   "[yellow]↑ [/yellow]",
        "normal": "  ",
        "low":    "[dim]↓ [/dim]",
    }
    return icons.get(priority, "  ")


def _size_label(size: str) -> str:
    return f"[dim]{size:8}[/dim]"


def _xp_label(task: Task) -> str:
    if task.status == "done":
        return f"[green]+{task.xp_earned} XP[/green]"
    return f"[dim]{task.xp_value} XP[/dim]"


def _extra_label(task: Task) -> str:
    if task.status == "overdue" and task.due_date:
        try:
            d = date.fromisoformat(task.due_date)
            formatted = d.strftime("%b %-d")
        except ValueError:
            formatted = task.due_date
        return f"[red]  ⚠ {formatted}[/red]"
    if task.status == "snoozed" and task.snooze_until:
        try:
            d = date.fromisoformat(task.snooze_until)
            formatted = d.strftime("%b %-d")
        except ValueError:
            formatted = task.snooze_until
        return f"[yellow]  → {formatted}[/yellow]"
    return ""


def _group_done_by_date(tasks: list[Task]) -> list[ListRow]:
    """Group done tasks into date section headers + task rows."""
    rows: list[ListRow] = []
    current_date: str | None = None
    date_tasks: list[Task] = []

    def _flush() -> None:
        if current_date and date_tasks:
            try:
                d = date.fromisoformat(current_date)
                label = d.strftime("%A, %b %-d")
            except ValueError:
                label = current_date
            rows.append(SectionHeader(label, len(date_tasks)))
            rows.extend(date_tasks)

    for task in tasks:
        task_date = (task.completed_at or "")[:10]
        if task_date != current_date:
            _flush()
            current_date = task_date
            date_tasks = [task]
        else:
            date_tasks.append(task)
    _flush()
    return rows


def _render_task_row(task: Task, selected: bool, max_title: int = 60) -> str:
    title = task.title
    if len(title) > max_title:
        title = title[: max_title - 1] + "…"

    icon = _status_icon(task.status)
    priority = _priority_icon(task.priority)
    size = _size_label(task.size)
    xp = _xp_label(task)
    extra = _extra_label(task)

    if task.status == "done":
        title_markup = f"[green dim]{title}[/green dim]"
    elif task.status == "overdue":
        title_markup = f"[red bold]{title}[/red bold]"
    elif task.status == "snoozed":
        title_markup = f"[yellow dim]{title}[/yellow dim]"
    elif task.status == "cancelled":
        title_markup = f"[dim]{title}[/dim]"
    else:
        title_markup = title

    row = f"  {icon} {priority} {title_markup:<{max_title}}  {size}  {xp}{extra}"

    if selected:
        return f"[reverse]{row}[/reverse]"
    return row


def _render_section_header(header: SectionHeader) -> str:
    count_str = f"  ·  {header.count} task{'s' if header.count != 1 else ''}"
    return f"\n[bold blue]{header.label}[/bold blue][dim]{count_str}[/dim]\n[dim]{'─' * 60}[/dim]"


def build_rows(
    today_tasks: list[Task],
    overdue_tasks: list[Task],
    snoozed_tasks: list[Task],
    done_tasks: list[Task],
    filter_mode: str,
    tomorrow_mode: bool = False,
    upcoming_tasks: list[Task] | None = None,
) -> list[ListRow]:
    """Build the ordered list of rows (headers + tasks) based on filter."""
    rows: list[ListRow] = []
    upcoming = upcoming_tasks if upcoming_tasks is not None else []

    if tomorrow_mode and filter_mode == "today":
        if today_tasks:
            rows.append(SectionHeader("TOMORROW", len(today_tasks)))
            rows.extend(today_tasks)
        return rows

    if filter_mode in ("all", "today") and today_tasks:
        rows.append(SectionHeader("TODAY", len(today_tasks)))
        rows.extend(today_tasks)

    if filter_mode == "all" and upcoming:
        rows.append(SectionHeader("UPCOMING", len(upcoming)))
        rows.extend(upcoming)

    if filter_mode in ("all", "overdue") and overdue_tasks:
        rows.append(SectionHeader("OVERDUE", len(overdue_tasks)))
        rows.extend(overdue_tasks)

    if filter_mode in ("all", "snoozed") and snoozed_tasks:
        rows.append(SectionHeader("SNOOZED", len(snoozed_tasks)))
        rows.extend(snoozed_tasks)

    if filter_mode == "all" and done_tasks:
        rows.append(SectionHeader("DONE TODAY", len(done_tasks)))
        rows.extend(done_tasks)
    elif filter_mode == "done" and done_tasks:
        rows.extend(_group_done_by_date(done_tasks))

    return rows


def _is_selectable(row: ListRow) -> bool:
    return isinstance(row, Task)


class TaskListWidget(Widget):
    """Scrollable task list with vim-style navigation."""

    # Must be focusable so keyboard events bubble to the app instead of staying
    # on a sibling TextArea (notes panel) that would capture printable keys.
    can_focus = True

    DEFAULT_CSS = """
    TaskListWidget {
        height: 1fr;
        overflow-y: auto;
        padding: 0 1;
    }
    """

    cursor_index: reactive[int] = reactive(0)
    filter_index: reactive[int] = reactive(0)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._rows: list[ListRow] = []
        self._selectable_indices: list[int] = []
        self._cursor_selectable_pos: int = 0

    def compose(self) -> ComposeResult:
        yield Static("", id="task-content", markup=True)

    def _render_all(self) -> str:
        if not self._rows:
            return "[dim]No tasks. Run quest_cli.py to add some.[/dim]"

        lines: list[str] = []
        for i, row in enumerate(self._rows):
            if isinstance(row, SectionHeader):
                lines.append(_render_section_header(row))
            else:
                selected = i == self.cursor_index
                lines.append(_render_task_row(row, selected))
        return "\n".join(lines)

    def _refresh_display(self) -> None:
        try:
            widget = self.query_one("#task-content", Static)
            widget.update(self._render_all())
        except Exception:
            pass

    def watch_cursor_index(self, _: int) -> None:
        self._refresh_display()

    def load_data(
        self,
        today_tasks: list[Task],
        overdue_tasks: list[Task],
        snoozed_tasks: list[Task],
        done_tasks: list[Task],
        filter_mode: str,
        tomorrow_mode: bool = False,
        upcoming_tasks: list[Task] | None = None,
    ) -> None:
        """Rebuild rows from task data."""
        self._rows = build_rows(
            today_tasks,
            overdue_tasks,
            snoozed_tasks,
            done_tasks,
            filter_mode,
            tomorrow_mode,
            upcoming_tasks,
        )
        self._selectable_indices = [
            i for i, r in enumerate(self._rows) if _is_selectable(r)
        ]
        # Keep cursor in bounds
        if self._selectable_indices:
            self._cursor_selectable_pos = min(
                self._cursor_selectable_pos, len(self._selectable_indices) - 1
            )
            self.cursor_index = self._selectable_indices[self._cursor_selectable_pos]
        else:
            self._cursor_selectable_pos = 0
            self.cursor_index = 0
        self._refresh_display()

    def move_down(self) -> None:
        if not self._selectable_indices:
            return
        next_pos = self._cursor_selectable_pos + 1
        if next_pos < len(self._selectable_indices):
            self._cursor_selectable_pos = next_pos
            self.cursor_index = self._selectable_indices[next_pos]

    def move_up(self) -> None:
        if not self._selectable_indices:
            return
        prev_pos = self._cursor_selectable_pos - 1
        if prev_pos >= 0:
            self._cursor_selectable_pos = prev_pos
            self.cursor_index = self._selectable_indices[prev_pos]

    def jump_first(self) -> None:
        if not self._selectable_indices:
            return
        self._cursor_selectable_pos = 0
        self.cursor_index = self._selectable_indices[0]

    def jump_last(self) -> None:
        if not self._selectable_indices:
            return
        self._cursor_selectable_pos = len(self._selectable_indices) - 1
        self.cursor_index = self._selectable_indices[-1]

    def current_task(self) -> Task | None:
        """Return the currently selected Task, or None."""
        if not self._rows or not self._selectable_indices:
            return None
        row = self._rows[self.cursor_index]
        if isinstance(row, Task):
            return row
        return None

    def advance_cursor(self) -> None:
        """Move cursor to next task after completion."""
        if not self._selectable_indices:
            return
        # Try to stay at same position (new list will be rebuilt),
        # just move down if possible, else stay.
        next_pos = min(self._cursor_selectable_pos, len(self._selectable_indices) - 1)
        self._cursor_selectable_pos = max(next_pos, 0)
