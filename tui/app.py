"""Main Textual application for the Quest TUI."""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, Label, Static

logger = logging.getLogger(__name__)

import sys as _sys

_QUEST_ROOT = str(Path.home() / ".claude" / "quest")
if _QUEST_ROOT not in _sys.path:
    _sys.path.insert(0, _QUEST_ROOT)

from quest.models import Task
from tui.widgets.stats_panel import StatsPanel
from tui.widgets.task_list import FILTER_MODES, TaskListWidget

ARCHIVE_RANGES: list[tuple[str, int | None]] = [
    ("today", 0),
    ("week", 7),
    ("month", 30),
    ("all", None),
]

HELP_TEXT = """
[bold]QUEST — Keybindings[/bold]

  j / ↓        Move cursor down
  k / ↑        Move cursor up
  h / ← / S-Tab  Cycle filter backward
  l / → / Tab  Cycle filter forward (all→today→overdue→snoozed→done)
  Enter/Space  Toggle done / undo
  a            Add new task
  d            Delete task
  i            Inspect task (full details)
  y            Yank (copy) task title
  g            Jump to first task
  G            Jump to last task
  r            Refresh data from DB
  \[            Cycle done range (today→week→month→all)
  ?            Toggle this help
  q            Close help / Quit

[bold]Priority icons[/bold]

  [bold red]↑↑[/bold red]  urgent — горит, блокирует других, дедлайн сегодня
  [yellow]↑ [/yellow]  high   — важно, хочется сделать сегодня
      normal — обычная задача
  [dim]↓ [/dim]  low    — когда-нибудь, не срочно

[dim]Press ? or q to close.[/dim]
"""


class AddTaskScreen(ModalScreen[str | None]):
    """Modal for adding a new task by title."""

    DEFAULT_CSS = """
    AddTaskScreen {
        align: center middle;
    }
    #add-task-box {
        width: 60;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    #add-task-box Label {
        margin-bottom: 1;
    }
    #add-task-input {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_none", "Cancel", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="add-task-box"):
            yield Label("[bold]Add Task[/bold]  [dim](Enter to save, Esc to cancel)[/dim]", markup=True)
            yield Input(placeholder="Task title…", id="add-task-input")

    def on_mount(self) -> None:
        self.query_one("#add-task-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        title = event.value.strip()
        self.dismiss(title if title else None)

    def action_dismiss_none(self) -> None:
        self.dismiss(None)


class QuestApp(App):
    """Textual TUI for the Quest gamified task system."""

    TITLE = "Quest"
    CSS = """
    Screen {
        layers: base overlay;
        align-horizontal: center;
    }

    #main-container {
        max-width: 150;
        width: 100%;
    }

    #help-overlay {
        layer: overlay;
        width: 50;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
        align-horizontal: center;
        margin-top: 3;
    }

    #filter-bar {
        height: 1;
        background: $panel;
        padding: 0 1;
        color: $text-muted;
    }

    #detail-overlay {
        layer: overlay;
        width: 60;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
        align-horizontal: center;
        margin-top: 3;
    }
    """

    BINDINGS = [
        Binding("j", "move_down", "Down", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("k", "move_up", "Up", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("enter", "toggle_task", "Toggle", show=True),
        Binding("space", "toggle_task", "Toggle", show=False),
        Binding("g", "jump_first", "First", show=False),
        Binding("G", "jump_last", "Last", show=False),
        Binding("a", "add_task", "Add", show=True),
        Binding("d", "delete_task", "Delete", show=True),
        Binding("i", "inspect_task", "Inspect", show=True),
        Binding("y", "yank_task", "Yank", show=False),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("tab", "cycle_filter", "Filter", show=True, priority=True),
        Binding("shift+tab", "cycle_filter_back", "Filter←", show=False, priority=True),
        Binding("l", "cycle_filter", "Filter→", show=False),
        Binding("right", "cycle_filter", "Filter→", show=False),
        Binding("h", "cycle_filter_back", "Filter←", show=False),
        Binding("left", "cycle_filter_back", "Filter←", show=False),
        Binding("left_square_bracket", "cycle_archive_range", "Range", show=False),
        Binding("question_mark", "toggle_help", "Help", show=True),
        Binding("q", "quit_or_close", "Quit", show=True),
    ]

    show_help: reactive[bool] = reactive(False)
    show_detail: reactive[bool] = reactive(False)
    filter_index: reactive[int] = reactive(0)
    archive_range_index: reactive[int] = reactive(0)

    def __init__(self) -> None:
        super().__init__()
        self._db: sqlite3.Connection | None = None
        self._no_db = False

    def _open_db(self) -> sqlite3.Connection | None:
        """Open DB if it exists; return None otherwise."""
        try:
            from quest.db import db_exists, init_db

            if not db_exists():
                return None
            return init_db()
        except Exception as exc:
            logger.exception("Failed to open DB")
            return None

    def compose(self) -> ComposeResult:
        with Vertical(id="main-container"):
            yield StatsPanel(id="stats-panel")
            yield Static(self._filter_label(), id="filter-bar", markup=True)
            yield TaskListWidget(id="task-list")
        yield Footer()

    def on_mount(self) -> None:
        self._db = self._open_db()
        if self._db is None:
            self._no_db = True
            self._show_no_db_message()
        else:
            self._load_all()

    def _filter_label(self) -> str:
        mode = FILTER_MODES[self.filter_index]
        parts = []
        for m in FILTER_MODES:
            if m == mode:
                if m == "done":
                    range_label = ARCHIVE_RANGES[self.archive_range_index][0]
                    parts.append(f"[bold cyan]done: {range_label}[/bold cyan]  [dim][ next range[/dim]")
                else:
                    parts.append(f"[bold cyan]{m}[/bold cyan]")
            else:
                parts.append(f"[dim]{m}[/dim]")
        return "  Filter: " + "  |  ".join(parts)

    def _show_no_db_message(self) -> None:
        try:
            task_list = self.query_one("#task-list", TaskListWidget)
            content = task_list.query_one("#task-content", Static)
            content.update(
                "[red]Database not found.[/red]\n"
                "Run: [bold]uv run python scripts/quest_cli.py init[/bold]"
            )
        except Exception:
            pass

    def _load_all(self) -> None:
        """Load all data from DB and update widgets."""
        if self._db is None:
            return
        db = self._db

        try:
            from quest.queries import (
                get_done_tasks,
                get_overdue_tasks,
                get_snoozed_tasks,
                get_tasks_for_today,
            )

            today_tasks = get_tasks_for_today(db)
            overdue_tasks = get_overdue_tasks(db)
            snoozed_tasks = get_snoozed_tasks(db)

            filter_mode = FILTER_MODES[self.filter_index]
            _, archive_days = ARCHIVE_RANGES[self.archive_range_index]

            if filter_mode == "done":
                done_tasks = get_done_tasks(db, days=archive_days)
            else:
                # In other modes show only today's completions
                done_tasks = get_done_tasks(db, days=0)

            stats_panel = self.query_one("#stats-panel", StatsPanel)
            stats_panel.refresh_stats(db)

            filter_bar = self.query_one("#filter-bar", Static)
            filter_bar.update(self._filter_label())

            task_list = self.query_one("#task-list", TaskListWidget)
            task_list.load_data(today_tasks, overdue_tasks, snoozed_tasks, done_tasks, filter_mode)

        except Exception as exc:
            logger.exception("Failed to load data")
            try:
                task_list = self.query_one("#task-list", TaskListWidget)
                content = task_list.query_one("#task-content", Static)
                content.update(f"[red]Error loading tasks: {exc}[/red]")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_move_down(self) -> None:
        if self._no_db:
            return
        task_list = self.query_one("#task-list", TaskListWidget)
        task_list.move_down()

    def action_move_up(self) -> None:
        if self._no_db:
            return
        task_list = self.query_one("#task-list", TaskListWidget)
        task_list.move_up()

    def action_jump_first(self) -> None:
        if self._no_db:
            return
        task_list = self.query_one("#task-list", TaskListWidget)
        task_list.jump_first()

    def action_jump_last(self) -> None:
        if self._no_db:
            return
        task_list = self.query_one("#task-list", TaskListWidget)
        task_list.jump_last()

    def action_toggle_task(self) -> None:
        if self._no_db or self._db is None:
            return

        task_list = self.query_one("#task-list", TaskListWidget)
        task = task_list.current_task()
        if task is None:
            return

        try:
            if task.status in ("pending", "in_progress", "overdue"):
                from quest.queries import complete_task

                complete_task(self._db, task.id)
                task_list.advance_cursor()
                self._load_all()
            elif task.status == "done":
                self._uncomplete_task(task.id)
                self._load_all()
        except Exception as exc:
            logger.exception("Failed to toggle task %d", task.id)
            self.notify(f"Error: {exc}", severity="error")

    def _uncomplete_task(self, task_id: int) -> None:
        """Revert a done task back to pending, subtracting XP."""
        if self._db is None:
            return
        db = self._db

        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return

        from quest.models import Task
        from quest.xp import level_for_xp, level_title

        task = Task.from_row(row)
        xp_to_remove = task.xp_earned

        now = datetime.now().isoformat(timespec="seconds")
        today = date.today().isoformat()

        db.execute(
            """
            UPDATE tasks SET status = 'pending', xp_earned = 0,
                completed_at = NULL, updated_at = ?
            WHERE id = ?
            """,
            (now, task_id),
        )

        stats_row = db.execute("SELECT * FROM user_stats WHERE id = 1").fetchone()
        new_total_xp = max(0, stats_row["total_xp"] - xp_to_remove)
        new_level = level_for_xp(new_total_xp)
        new_title = level_title(new_level)

        db.execute(
            """
            UPDATE user_stats SET total_xp = ?, current_level = ?,
                level_title = ?, tasks_completed = MAX(0, tasks_completed - 1),
                updated_at = ?
            WHERE id = 1
            """,
            (new_total_xp, new_level, new_title, now),
        )

        db.execute(
            """
            UPDATE daily_logs SET
                tasks_completed = MAX(0, tasks_completed - 1),
                xp_earned = MAX(0, xp_earned - ?)
            WHERE log_date = ?
            """,
            (xp_to_remove, today),
        )
        db.commit()

    def action_delete_task(self) -> None:
        if self._no_db or self._db is None:
            return

        task_list = self.query_one("#task-list", TaskListWidget)
        task = task_list.current_task()
        if task is None:
            return

        try:
            now = datetime.now().isoformat(timespec="seconds")
            self._db.execute(
                "DELETE FROM tasks WHERE id = ?",
                (task.id,),
            )
            self._db.execute(
                "UPDATE user_stats SET tasks_cancelled = tasks_cancelled + 1, updated_at = ? WHERE id = 1",
                (now,),
            )
            self._db.commit()
            task_list.advance_cursor()
            self._load_all()
            self.notify(f"Deleted: {task.title}", timeout=2)
        except Exception as exc:
            logger.exception("Failed to delete task %d", task.id)
            self.notify(f"Error: {exc}", severity="error")

    def action_refresh(self) -> None:
        if self._no_db:
            return
        self._load_all()
        self.notify("Refreshed", timeout=1)

    def action_add_task(self) -> None:
        if self._no_db or self._db is None:
            return
        db = self._db

        def _on_result(title: str | None) -> None:
            if not title:
                return
            try:
                from quest.queries import add_task

                add_task(db, title=title, size="small")
                self._load_all()
                self.notify(f"Added: {title}", timeout=2)
            except Exception as exc:
                logger.exception("Failed to add task")
                self.notify(f"Error: {exc}", severity="error")

        self.push_screen(AddTaskScreen(), _on_result)

    def action_yank_task(self) -> None:
        if self._no_db:
            return
        task_list = self.query_one("#task-list", TaskListWidget)
        task = task_list.current_task()
        if task is None:
            return
        try:
            self.copy_to_clipboard(task.title)
            self.notify(f"Copied: {task.title}", timeout=2)
        except Exception as exc:
            logger.exception("Failed to copy to clipboard")
            self.notify(f"Copy failed: {exc}", severity="warning")

    def action_cycle_filter(self) -> None:
        self.filter_index = (self.filter_index + 1) % len(FILTER_MODES)
        if not self._no_db:
            self._load_all()

    def action_cycle_filter_back(self) -> None:
        self.filter_index = (self.filter_index - 1) % len(FILTER_MODES)
        if not self._no_db:
            self._load_all()

    def action_cycle_archive_range(self) -> None:
        if FILTER_MODES[self.filter_index] != "done":
            return
        self.archive_range_index = (self.archive_range_index + 1) % len(ARCHIVE_RANGES)
        if not self._no_db:
            self._load_all()

    def action_inspect_task(self) -> None:
        if self._no_db:
            return
        if self.show_detail:
            self.show_detail = False
            self._remove_detail()
            return

        task_list = self.query_one("#task-list", TaskListWidget)
        task = task_list.current_task()
        if task is None:
            return

        self.show_detail = True
        self._mount_detail(task)

    def _mount_detail(self, task: Task) -> None:
        lines: list[str] = []
        lines.append(f"[bold]#{task.id} — {task.title}[/bold]\n")

        if task.description:
            lines.append(f"{task.description}\n")

        lines.append(f"[dim]Size:[/dim]    {task.size}  ([cyan]{task.xp_value} XP[/cyan])")
        lines.append(f"[dim]Status:[/dim]  {task.status}")

        if task.due_date:
            lines.append(f"[dim]Due:[/dim]     {task.due_date}")
        if task.snooze_until:
            lines.append(f"[dim]Snoozed:[/dim] until {task.snooze_until}")
        if task.parent_id:
            lines.append(f"[dim]Parent:[/dim]  #{task.parent_id}")
        if task.completed_at:
            lines.append(f"[dim]Done:[/dim]    {task.completed_at}  (+{task.xp_earned} XP)")

        lines.append(f"\n[dim]Created: {task.created_at}[/dim]")
        lines.append("\n[dim]Press i or q to close.[/dim]")

        content = "\n".join(lines)
        widget = Static(content, id="detail-overlay", markup=True)
        self.mount(widget)

    def _remove_detail(self) -> None:
        try:
            overlay = self.query_one("#detail-overlay", Static)
            overlay.remove()
        except Exception:
            pass

    def action_quit_or_close(self) -> None:
        """If an overlay is open, close it. Otherwise quit."""
        if self.show_detail:
            self.show_detail = False
            self._remove_detail()
        elif self.show_help:
            self.show_help = False
            self._remove_help()
        else:
            self.exit()

    def action_toggle_help(self) -> None:
        self.show_help = not self.show_help
        if self.show_help:
            self._mount_help()
        else:
            self._remove_help()

    def _mount_help(self) -> None:
        help_widget = Static(HELP_TEXT, id="help-overlay", markup=True)
        self.mount(help_widget)

    def _remove_help(self) -> None:
        try:
            overlay = self.query_one("#help-overlay", Static)
            overlay.remove()
        except Exception:
            pass
