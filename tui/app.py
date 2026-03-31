"""Main Textual application for the Quest TUI."""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Footer, Static, TextArea

logger = logging.getLogger(__name__)

import sys as _sys

_QUEST_ROOT = str(Path.home() / ".claude" / "quest")
if _QUEST_ROOT not in _sys.path:
    _sys.path.insert(0, _QUEST_ROOT)

from quest.models import Task
from quest.queries import snooze_task as _snooze_task
from tui.screens.add_task_screen import AddTaskResult, RichAddTaskScreen
from tui.screens.detail_screen import DetailScreen
from tui.screens.edit_task_screen import RichEditTaskScreen
from tui.screens.help_screen import HelpScreen
from tui.screens.snooze_task_screen import SnoozeTaskScreen
from tui.widgets.notes_panel import NotesPanel
from tui.widgets.stats_panel import StatsPanel
from tui.widgets.task_list import FILTER_MODES, TaskListWidget

ARCHIVE_RANGES: list[tuple[str, int | None]] = [
    ("today", 0),
    ("week", 7),
    ("month", 30),
    ("all", None),
]


class QuestApp(App):
    """Textual TUI for the Quest gamified task system."""

    TITLE = "Quest"
    CSS = """
    Screen {
        align-horizontal: center;
    }

    #root-layout {
        height: 1fr;
        max-width: 150;
        width: 100%;
    }

    #main-container {
        width: 1fr;
        height: 100%;
    }

    .hidden {
        display: none;
    }

    #filter-bar {
        height: 1;
        background: $panel;
        padding: 0 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("j", "move_down", "Down", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("k", "move_up", "Up", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("ctrl+d", "half_page_down", "½↓", show=False),
        Binding("ctrl+в", "half_page_down", "½↓", show=False),
        Binding("ctrl+u", "half_page_up", "½↑", show=False),
        Binding("ctrl+г", "half_page_up", "½↑", show=False),
        Binding("enter", "toggle_task", "Toggle", show=True),
        Binding("space", "toggle_task", "Toggle", show=False),
        Binding("g", "jump_first", "First", show=False),
        Binding("G", "jump_last", "Last", show=False),
        Binding("a", "add_task", "Add", show=True),
        Binding("e", "edit_task", "Edit", show=True),
        Binding("z", "snooze_task", "Snooze", show=True),
        Binding("d", "arm_delete", "dd=Del", show=True),
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
        Binding("n", "toggle_notes", "Notes", show=True),
        Binding("N", "focus_notes", "Notes→", show=False),
        Binding("question_mark", "toggle_help", "Help", show=True),
        Binding("q", "quit_or_close", "Quit", show=True),
        # Russian layout equivalents (same physical keys, no UI labels)
        Binding("о", "move_down", "Down", show=False),
        Binding("л", "move_up", "Up", show=False),
        Binding("п", "jump_first", "First", show=False),
        Binding("П", "jump_last", "Last", show=False),
        Binding("ф", "add_task", "Add", show=False),
        Binding("у", "edit_task", "Edit", show=False),
        Binding("я", "snooze_task", "Snooze", show=False),
        Binding("в", "arm_delete", "Delete", show=False),
        Binding("ш", "inspect_task", "Inspect", show=False),
        Binding("н", "yank_task", "Yank", show=False),
        Binding("к", "refresh", "Refresh", show=False),
        Binding("т", "toggle_notes", "Notes", show=False),
        Binding("Т", "focus_notes", "Notes→", show=False),
        Binding("р", "cycle_filter_back", "Filter←", show=False),
        Binding("д", "cycle_filter", "Filter→", show=False),
        Binding("х", "cycle_archive_range", "Range", show=False),
        Binding("й", "quit_or_close", "Quit", show=False),
    ]

    notes_visible: reactive[bool] = reactive(False)
    filter_index: reactive[int] = reactive(0)
    archive_range_index: reactive[int] = reactive(0)
    tomorrow_mode: reactive[bool] = reactive(False)

    def __init__(self) -> None:
        super().__init__()
        self._db: sqlite3.Connection | None = None
        self._no_db = False
        self._delete_armed_task: Task | None = None
        self._delete_timer: Timer | None = None

    def _open_db(self) -> sqlite3.Connection | None:
        """Open DB if it exists; return None otherwise."""
        try:
            from quest.db import db_exists, init_db

            if not db_exists():
                return None
            return init_db()
        except Exception:
            logger.exception("Failed to open DB")
            return None

    def compose(self) -> ComposeResult:
        with Horizontal(id="root-layout"):
            with Vertical(id="main-container"):
                yield StatsPanel(id="stats-panel")
                yield Static(self._filter_label(), id="filter-bar", markup=True)
                yield TaskListWidget(id="task-list")
            yield NotesPanel(id="notes-panel", classes="hidden")
        yield Footer()

    def on_mount(self) -> None:
        self._db = self._open_db()
        if self._db is None:
            self._no_db = True
            self._show_no_db_message()
        else:
            self._load_all()
        # Defer so the task list is mounted; keeps focus off the notes TextArea.
        self.call_later(self._focus_task_list)

    def _focus_task_list(self) -> None:
        """Move focus to the task list so global keybindings are not captured by TextArea."""
        try:
            self.query_one("#task-list", TaskListWidget).focus()
        except Exception:
            pass

    def _filter_label(self) -> str:
        mode = FILTER_MODES[self.filter_index]
        parts = []
        for m in FILTER_MODES:
            if m == mode:
                if m == "done":
                    range_label = ARCHIVE_RANGES[self.archive_range_index][0]
                    parts.append(
                        f"[bold cyan]done: {range_label}[/bold cyan]  [dim]\\[ next range[/dim]"
                    )
                elif m == "today":
                    if self.tomorrow_mode:
                        parts.append(
                            "[bold cyan]tomorrow[/bold cyan]  [dim]\\[ today[/dim]"
                        )
                    else:
                        parts.append(
                            "[bold cyan]today[/bold cyan]  [dim]\\[ tomorrow[/dim]"
                        )
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
                get_tasks_for_tomorrow,
                get_tasks_upcoming,
            )

            filter_mode = FILTER_MODES[self.filter_index]
            _, archive_days = ARCHIVE_RANGES[self.archive_range_index]

            if self.tomorrow_mode and filter_mode == "today":
                today_tasks = get_tasks_for_tomorrow(db)
            else:
                today_tasks = get_tasks_for_today(db)

            upcoming_tasks = get_tasks_upcoming(db)
            overdue_tasks = get_overdue_tasks(db)
            snoozed_tasks = get_snoozed_tasks(db)

            if filter_mode == "done":
                done_tasks = get_done_tasks(db, days=archive_days)
            else:
                done_tasks = get_done_tasks(db, days=0)

            stats_panel = self.query_one("#stats-panel", StatsPanel)
            stats_panel.refresh_stats(db)

            filter_bar = self.query_one("#filter-bar", Static)
            filter_bar.update(self._filter_label())

            task_list = self.query_one("#task-list", TaskListWidget)
            task_list.load_data(
                today_tasks,
                overdue_tasks,
                snoozed_tasks,
                done_tasks,
                filter_mode,
                tomorrow_mode=self.tomorrow_mode,
                upcoming_tasks=upcoming_tasks,
            )

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

    def _disarm_delete(self) -> None:
        if self._delete_armed_task is not None:
            self._delete_armed_task = None
        if self._delete_timer is not None:
            self._delete_timer.stop()
            self._delete_timer = None
        try:
            self.query_one("#task-list", TaskListWidget).armed_task_id = None
        except Exception:
            pass

    def action_move_down(self) -> None:
        if self._no_db:
            return
        self._disarm_delete()
        task_list = self.query_one("#task-list", TaskListWidget)
        task_list.move_down()

    def action_move_up(self) -> None:
        if self._no_db:
            return
        self._disarm_delete()
        task_list = self.query_one("#task-list", TaskListWidget)
        task_list.move_up()

    def action_half_page_down(self) -> None:
        if self._no_db:
            return
        self._disarm_delete()
        task_list = self.query_one("#task-list", TaskListWidget)
        step = max(3, task_list.size.height // 2)
        task_list.move_many(step)

    def action_half_page_up(self) -> None:
        if self._no_db:
            return
        self._disarm_delete()
        task_list = self.query_one("#task-list", TaskListWidget)
        step = max(3, task_list.size.height // 2)
        task_list.move_many(-step)

    def action_jump_first(self) -> None:
        if self._no_db:
            return
        self._disarm_delete()
        task_list = self.query_one("#task-list", TaskListWidget)
        task_list.jump_first()

    def action_jump_last(self) -> None:
        if self._no_db:
            return
        self._disarm_delete()
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

    def action_arm_delete(self) -> None:
        if self._no_db or self._db is None:
            return
        task_list = self.query_one("#task-list", TaskListWidget)
        task = task_list.current_task()
        if task is None:
            return

        if (
            self._delete_armed_task is not None
            and self._delete_armed_task.id == task.id
        ):
            # Second d on the same task — execute
            self._disarm_delete()
            self._do_delete_task(task)
        else:
            # First d — arm
            self._disarm_delete()
            self._delete_armed_task = task
            task_list.armed_task_id = task.id
            self.notify(
                f"Press [bold]d[/bold] again to delete: {task.title[:50]}",
                timeout=1.5,
                markup=True,
            )
            self._delete_timer = self.set_timer(1.5, self._disarm_delete)

    def _do_delete_task(self, task: Task) -> None:
        if self._db is None:
            return
        task_list = self.query_one("#task-list", TaskListWidget)
        try:
            now = datetime.now().isoformat(timespec="seconds")
            self._db.execute("DELETE FROM tasks WHERE id = ?", (task.id,))
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

    def action_toggle_notes(self) -> None:
        if self._no_db or self._db is None:
            return
        panel = self.query_one("#notes-panel", NotesPanel)
        if not self.notes_visible:
            self.notes_visible = True
            panel.remove_class("hidden")
            panel.load_notes(self._db)
            self._focus_task_list()
        else:
            self.notes_visible = False
            panel.add_class("hidden")
            self._focus_task_list()

    def action_focus_notes(self) -> None:
        """Move keyboard focus into the notes TextArea (N key)."""
        if not self.notes_visible or self._db is None:
            return
        try:
            self.query_one("#notes-panel", NotesPanel).query_one(
                "#notes-area", TextArea
            ).focus()
        except Exception:
            pass

    def action_add_task(self) -> None:
        if self._no_db or self._db is None:
            return
        db = self._db

        def _on_result(result: AddTaskResult | None) -> None:
            if result is None:
                return
            try:
                from quest.queries import add_task

                add_task(
                    db,
                    title=result.title,
                    size=result.size,
                    priority=result.priority,
                    due_date=result.due_date,
                )
                self._load_all()
                self.notify(f"Added: {result.title}", timeout=2)
            except Exception as exc:
                logger.exception("Failed to add task")
                self.notify(f"Error: {exc}", severity="error")

        use_tomorrow_default = (
            self.tomorrow_mode and FILTER_MODES[self.filter_index] == "today"
        )
        self.push_screen(
            RichAddTaskScreen(default_due_tomorrow=use_tomorrow_default), _on_result
        )

    def action_edit_task(self) -> None:
        if self._no_db or self._db is None:
            return
        db = self._db
        task_list = self.query_one("#task-list", TaskListWidget)
        task = task_list.current_task()
        if task is None:
            return
        if task.status in ("done", "cancelled"):
            self.notify(
                "Editing is only available for active tasks", severity="warning"
            )
            return

        def _on_result(result: AddTaskResult | None) -> None:
            if result is None:
                return
            try:
                from quest.queries import update_task_fields

                update_task_fields(
                    db,
                    task.id,
                    title=result.title,
                    size=result.size,
                    priority=result.priority,
                    due_date=result.due_date,
                )
                self._load_all()
                self.notify(f"Updated: {result.title}", timeout=2)
            except Exception as exc:
                logger.exception("Failed to update task")
                self.notify(f"Error: {exc}", severity="error")

        self.push_screen(RichEditTaskScreen(task), _on_result)

    def action_snooze_task(self) -> None:
        if self._no_db or self._db is None:
            return
        db = self._db
        task_list = self.query_one("#task-list", TaskListWidget)
        task = task_list.current_task()
        if task is None:
            return
        if task.status in ("done", "cancelled"):
            self.notify("Snooze is only for active tasks", severity="warning")
            return

        def _on_result(until: str | None) -> None:
            if until is None:
                return
            try:
                _snooze_task(db, task.id, until)
                self._load_all()
                self.notify(f"Snoozed until {until}", timeout=2)
            except Exception as exc:
                logger.exception("Failed to snooze task")
                self.notify(f"Error: {exc}", severity="error")

        self.push_screen(SnoozeTaskScreen(task), _on_result)

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

    def _modal_active(self) -> bool:
        """Return True when a modal screen is stacked on top of the main screen."""
        return len(self.screen_stack) > 1

    def action_cycle_filter(self) -> None:
        if self._modal_active():
            self.screen.focus_next()
            return
        self.filter_index = (self.filter_index + 1) % len(FILTER_MODES)
        if FILTER_MODES[self.filter_index] != "today":
            self.tomorrow_mode = False
        if not self._no_db:
            self._load_all()

    def action_cycle_filter_back(self) -> None:
        if self._modal_active():
            self.screen.focus_previous()
            return
        self.filter_index = (self.filter_index - 1) % len(FILTER_MODES)
        if FILTER_MODES[self.filter_index] != "today":
            self.tomorrow_mode = False
        if not self._no_db:
            self._load_all()

    def action_cycle_archive_range(self) -> None:
        mode = FILTER_MODES[self.filter_index]
        if mode == "done":
            self.archive_range_index = (self.archive_range_index + 1) % len(
                ARCHIVE_RANGES
            )
        elif mode == "today":
            self.tomorrow_mode = not self.tomorrow_mode
        if not self._no_db:
            self._load_all()

    def action_inspect_task(self) -> None:
        if self._no_db:
            return
        task_list = self.query_one("#task-list", TaskListWidget)
        task = task_list.current_task()
        if task is None:
            return
        self.push_screen(DetailScreen(task))

    def action_quit_or_close(self) -> None:
        self.exit()

    def action_toggle_help(self) -> None:
        self.push_screen(HelpScreen())
