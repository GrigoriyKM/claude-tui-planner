"""SQL query functions for all database operations."""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timedelta

from quest.models import DailyLog, Task, UserStats
from quest.xp import XP_VALUES, calculate_xp, level_for_xp, level_title

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Task queries
# ---------------------------------------------------------------------------


PRIORITY_SORT = "CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 ELSE 2 END"


def get_tasks_for_today(db: sqlite3.Connection) -> list[Task]:
    """Return pending/in_progress tasks due today or with no due date."""
    today = _today()
    rows = db.execute(
        f"""
        SELECT * FROM tasks
        WHERE status IN ('pending', 'in_progress')
          AND (due_date IS NULL OR due_date <= ?)
        ORDER BY {PRIORITY_SORT}, due_date ASC NULLS LAST, created_at ASC
        """,
        (today,),
    ).fetchall()
    return [Task.from_row(r) for r in rows]


def get_tasks_for_tomorrow(db: sqlite3.Connection) -> list[Task]:
    """Return pending/in_progress tasks with due_date = tomorrow (local calendar day).

    Uses the same date as ``add_task`` / the CLI (Python ``date.today()``), not SQLite
    ``date('now', ...)``, which follows UTC and can disagree with local "tomorrow".
    """
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    rows = db.execute(
        f"""
        SELECT * FROM tasks
        WHERE status IN ('pending', 'in_progress')
          AND due_date = ?
        ORDER BY {PRIORITY_SORT}, created_at ASC
        """,
        (tomorrow,),
    ).fetchall()
    return [Task.from_row(r) for r in rows]


def get_tasks_upcoming(db: sqlite3.Connection) -> list[Task]:
    """Return pending/in_progress tasks with due_date strictly after today (future dates)."""
    today = _today()
    rows = db.execute(
        f"""
        SELECT * FROM tasks
        WHERE status IN ('pending', 'in_progress')
          AND due_date IS NOT NULL
          AND due_date > ?
        ORDER BY due_date ASC, {PRIORITY_SORT}, created_at ASC
        """,
        (today,),
    ).fetchall()
    return [Task.from_row(r) for r in rows]


def get_overdue_tasks(db: sqlite3.Connection) -> list[Task]:
    """Return tasks where due_date < today and status is pending or overdue."""
    today = _today()
    rows = db.execute(
        """
        SELECT * FROM tasks
        WHERE status IN ('pending', 'overdue')
          AND due_date IS NOT NULL
          AND due_date < ?
        ORDER BY due_date ASC
        """,
        (today,),
    ).fetchall()
    return [Task.from_row(r) for r in rows]


def get_snoozed_tasks(db: sqlite3.Connection) -> list[Task]:
    """Return all snoozed tasks."""
    rows = db.execute(
        "SELECT * FROM tasks WHERE status = 'snoozed' ORDER BY snooze_until ASC"
    ).fetchall()
    return [Task.from_row(r) for r in rows]


def get_recent_tasks(db: sqlite3.Connection, days: int = 7) -> list[Task]:
    """Return tasks created within the last N days."""
    rows = db.execute(
        """
        SELECT * FROM tasks
        WHERE created_at >= datetime('now', ?)
        ORDER BY created_at DESC
        """,
        (f"-{days} days",),
    ).fetchall()
    return [Task.from_row(r) for r in rows]


def add_task(
    db: sqlite3.Connection,
    title: str,
    size: str,
    due_date: str | None = None,
    parent_id: int | None = None,
    description: str | None = None,
    priority: str = "normal",
) -> Task:
    """Insert a new task and return it."""
    xp_value = XP_VALUES[size]
    now = _now()
    cursor = db.execute(
        """
        INSERT INTO tasks (title, description, size, xp_value, due_date, parent_id, priority, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (title, description, size, xp_value, due_date, parent_id, priority, now, now),
    )
    task_id = cursor.lastrowid

    # Update tasks_created counter
    db.execute(
        "UPDATE user_stats SET tasks_created = tasks_created + 1, updated_at = ? WHERE id = 1",
        (now,),
    )
    db.commit()

    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return Task.from_row(row)


def complete_task(db: sqlite3.Connection, task_id: int) -> dict:
    """Mark a task as done, calculate XP, update stats. Returns result dict."""
    from quest.streaks import get_streak_state, record_activity

    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise ValueError(f"Task {task_id} not found")

    task = Task.from_row(row)
    if task.status == "done":
        raise ValueError(f"Task {task_id} is already completed")
    if task.status == "cancelled":
        raise ValueError(f"Task {task_id} is cancelled and cannot be completed")

    streak_state = get_streak_state(db)
    base_xp, bonus_xp, total_xp = calculate_xp(task.size, streak_state.current_streak)

    today = _today()
    now = _now()

    db.execute(
        """
        UPDATE tasks SET
            status = 'done',
            xp_earned = ?,
            completed_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (total_xp, now, now, task_id),
    )

    # Update user stats
    stats_row = db.execute("SELECT * FROM user_stats WHERE id = 1").fetchone()
    new_total_xp = stats_row["total_xp"] + total_xp
    new_level = level_for_xp(new_total_xp)
    new_title = level_title(new_level)

    db.execute(
        """
        UPDATE user_stats SET
            total_xp = ?,
            current_level = ?,
            level_title = ?,
            tasks_completed = tasks_completed + 1,
            updated_at = ?
        WHERE id = 1
        """,
        (new_total_xp, new_level, new_title, now),
    )

    # Update daily log
    db.execute(
        """
        INSERT INTO daily_logs (log_date, tasks_completed, xp_earned, streak_active)
        VALUES (?, 1, ?, 1)
        ON CONFLICT(log_date) DO UPDATE SET
            tasks_completed = tasks_completed + 1,
            xp_earned = xp_earned + ?,
            streak_active = 1
        """,
        (today, total_xp, total_xp),
    )
    db.commit()

    # Record streak activity
    new_streak_state = record_activity(db, today)

    return {
        "task_id": task_id,
        "title": task.title,
        "size": task.size,
        "base_xp": base_xp,
        "bonus_xp": bonus_xp,
        "total_xp": total_xp,
        "streak_days": new_streak_state.current_streak,
        "new_total_xp": new_total_xp,
        "new_level": new_level,
        "level_title": new_title,
    }


def snooze_task(db: sqlite3.Connection, task_id: int, until_date: str) -> Task:
    """Snooze a task until the given date. Returns updated task."""
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise ValueError(f"Task {task_id} not found")

    now = _now()
    db.execute(
        """
        UPDATE tasks SET
            status = 'snoozed',
            snooze_until = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (until_date, now, task_id),
    )
    db.commit()

    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return Task.from_row(row)


def cancel_task(db: sqlite3.Connection, task_id: int) -> Task:
    """Cancel a task. Returns updated task."""
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise ValueError(f"Task {task_id} not found")

    now = _now()
    db.execute(
        """
        UPDATE tasks SET
            status = 'cancelled',
            updated_at = ?
        WHERE id = ?
        """,
        (now, task_id),
    )
    db.execute(
        "UPDATE user_stats SET tasks_cancelled = tasks_cancelled + 1, updated_at = ? WHERE id = 1",
        (now,),
    )
    db.commit()

    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return Task.from_row(row)


def update_task_fields(
    db: sqlite3.Connection,
    task_id: int,
    title: str,
    size: str,
    priority: str,
    due_date: str | None,
) -> Task:
    """Update title, size, priority, and due date. Recalculates xp_value from size.

    Raises:
        ValueError: If the task is missing or completed/cancelled.
    """
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise ValueError(f"Task {task_id} not found")
    existing = Task.from_row(row)
    if existing.status in ("done", "cancelled"):
        raise ValueError(
            f"Task {task_id} cannot be edited in status {existing.status!r}"
        )

    xp_value = XP_VALUES[size]
    now = _now()
    db.execute(
        """
        UPDATE tasks SET
            title = ?,
            size = ?,
            xp_value = ?,
            priority = ?,
            due_date = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (title, size, xp_value, priority, due_date, now, task_id),
    )
    db.commit()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return Task.from_row(row)


def get_user_stats(db: sqlite3.Connection) -> UserStats:
    """Fetch user stats row."""
    row = db.execute("SELECT * FROM user_stats WHERE id = 1").fetchone()
    return UserStats.from_row(row)


def get_daily_log(db: sqlite3.Connection, log_date: str) -> DailyLog | None:
    """Fetch daily log for the given date, or None if not found."""
    row = db.execute(
        "SELECT * FROM daily_logs WHERE log_date = ?", (log_date,)
    ).fetchone()
    if row is None:
        return None
    return DailyLog.from_row(row)


def upsert_daily_log(
    db: sqlite3.Connection,
    log_date: str,
    day_rating: int | None = None,
    notes: str | None = None,
) -> DailyLog:
    """Insert or update a daily log entry."""
    existing = get_daily_log(db, log_date)
    if existing is None:
        db.execute(
            """
            INSERT INTO daily_logs (log_date, tasks_completed, xp_earned, streak_active, day_rating, notes)
            VALUES (?, 0, 0, 0, ?, ?)
            """,
            (log_date, day_rating, notes),
        )
    else:
        updates = []
        params: list = []
        if day_rating is not None:
            updates.append("day_rating = ?")
            params.append(day_rating)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if updates:
            params.append(log_date)
            db.execute(
                f"UPDATE daily_logs SET {', '.join(updates)} WHERE log_date = ?",
                params,
            )
    db.commit()

    row = db.execute(
        "SELECT * FROM daily_logs WHERE log_date = ?", (log_date,)
    ).fetchone()
    return DailyLog.from_row(row)


def list_tasks(
    db: sqlite3.Connection, status: str | None = None, limit: int = 50
) -> list[Task]:
    """Return tasks filtered by optional status, ordered by created_at desc."""
    if status is not None:
        rows = db.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [Task.from_row(r) for r in rows]


def get_done_tasks(db: sqlite3.Connection, days: int | None = None) -> list[Task]:
    """Return done tasks ordered by completed_at desc.
    days=0  → today only
    days=N  → last N days
    days=None → all time (limit 300)
    """
    if days is None:
        rows = db.execute(
            "SELECT * FROM tasks WHERE status = 'done' ORDER BY completed_at DESC LIMIT 300"
        ).fetchall()
    elif days == 0:
        today = date.today().isoformat()
        rows = db.execute(
            "SELECT * FROM tasks WHERE status = 'done' AND completed_at LIKE ? ORDER BY completed_at DESC",
            (f"{today}%",),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT * FROM tasks
            WHERE status = 'done'
              AND completed_at >= datetime('now', ?)
            ORDER BY completed_at DESC
            """,
            (f"-{days} days",),
        ).fetchall()
    return [Task.from_row(r) for r in rows]


def search_tasks(db: sqlite3.Connection, query: str) -> list[Task]:
    """Fuzzy title match using LIKE. Returns matching tasks."""
    pattern = f"%{query}%"
    rows = db.execute(
        "SELECT * FROM tasks WHERE title LIKE ? ORDER BY created_at DESC",
        (pattern,),
    ).fetchall()
    return [Task.from_row(r) for r in rows]


def get_persistent_notes(db: sqlite3.Connection) -> str:
    """Return the persistent notes content (never date-bound)."""
    row = db.execute("SELECT content FROM persistent_notes WHERE id = 1").fetchone()
    return row["content"] if row else ""


def save_persistent_notes(db: sqlite3.Connection, content: str) -> None:
    """Upsert the persistent notes content."""
    db.execute(
        "INSERT INTO persistent_notes (id, content) VALUES (1, ?)"
        " ON CONFLICT(id) DO UPDATE SET content = excluded.content",
        (content,),
    )
    db.commit()
