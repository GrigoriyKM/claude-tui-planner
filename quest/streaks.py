"""Streak tracking and daily reconciliation logic."""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timedelta

from quest.models import StreakState

logger = logging.getLogger(__name__)

GRACE_DAYS_PER_WEEK = 1


def _today() -> str:
    return date.today().isoformat()


def _yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def _week_start(d: str) -> str:
    """Return ISO date string for Monday of the week containing d."""
    parsed = date.fromisoformat(d)
    monday = parsed - timedelta(days=parsed.weekday())
    return monday.isoformat()


def get_streak_state(db: sqlite3.Connection) -> StreakState:
    """Fetch current streak state from the database."""
    row = db.execute("SELECT * FROM streaks WHERE id = 1").fetchone()
    return StreakState.from_row(row)


def record_activity(db: sqlite3.Connection, activity_date: str) -> StreakState:
    """Called when a task is completed. Updates streak for the given date."""
    state = get_streak_state(db)
    last = state.last_active_date

    # If already recorded activity for this date, no change needed
    if last == activity_date:
        return state

    # Determine if this continues an existing streak
    yesterday = (date.fromisoformat(activity_date) - timedelta(days=1)).isoformat()
    if last == yesterday or last is None:
        new_streak = state.current_streak + 1
    else:
        # Gap in activity — restart streak
        new_streak = 1

    new_longest = max(state.longest_streak, new_streak)
    now = datetime.now().isoformat(timespec="seconds")

    db.execute(
        """
        UPDATE streaks SET
            current_streak = ?,
            longest_streak = ?,
            last_active_date = ?,
            updated_at = ?
        WHERE id = 1
        """,
        (new_streak, new_longest, activity_date, now),
    )
    db.commit()

    return get_streak_state(db)


def _tasks_completed_on(db: sqlite3.Connection, check_date: str) -> int:
    """Return count of tasks completed on check_date."""
    row = db.execute(
        "SELECT COUNT(*) as cnt FROM tasks WHERE completed_at LIKE ? AND status = 'done'",
        (f"{check_date}%",),
    ).fetchone()
    return row["cnt"]


def _grace_available(state: StreakState, today: str) -> bool:
    """Return True if a grace day can be used today."""
    week_start = _week_start(today)
    if state.grace_week_start != week_start:
        # New week — grace resets
        return True
    return state.grace_days_used_this_week < GRACE_DAYS_PER_WEEK


def _use_grace(db: sqlite3.Connection, state: StreakState, today: str, yesterday: str) -> StreakState:
    """Record usage of a grace day, maintaining streak."""
    week_start = _week_start(today)
    if state.grace_week_start != week_start:
        new_grace_used = 1
    else:
        new_grace_used = state.grace_days_used_this_week + 1

    now = datetime.now().isoformat(timespec="seconds")

    db.execute(
        """
        UPDATE streaks SET
            last_active_date = ?,
            grace_days_used_this_week = ?,
            grace_week_start = ?,
            updated_at = ?
        WHERE id = 1
        """,
        (yesterday, new_grace_used, week_start, now),
    )

    # Log the grace day in daily_logs
    db.execute(
        """
        INSERT INTO daily_logs (log_date, tasks_completed, xp_earned, streak_active, grace_used)
        VALUES (?, 0, 0, 1, 1)
        ON CONFLICT(log_date) DO UPDATE SET grace_used = 1, streak_active = 1
        """,
        (yesterday,),
    )
    db.commit()
    logger.info("Grace day used for %s", yesterday)
    return get_streak_state(db)


def _reset_streak(db: sqlite3.Connection) -> StreakState:
    """Reset current streak to 0 (multiplier lost, not XP)."""
    now = datetime.now().isoformat(timespec="seconds")
    db.execute(
        "UPDATE streaks SET current_streak = 0, updated_at = ? WHERE id = 1",
        (now,),
    )
    db.commit()
    logger.info("Streak reset due to missed day")
    return get_streak_state(db)


def _awaken_snoozed_tasks(db: sqlite3.Connection, today: str) -> int:
    """Wake up snoozed tasks whose snooze_until date has passed. Returns count."""
    now = datetime.now().isoformat(timespec="seconds")
    cursor = db.execute(
        """
        UPDATE tasks SET status = 'pending', snooze_until = NULL, updated_at = ?
        WHERE status = 'snoozed' AND snooze_until IS NOT NULL AND snooze_until <= ?
        """,
        (now, today),
    )
    db.commit()
    return cursor.rowcount


def _mark_overdue_tasks(db: sqlite3.Connection, today: str) -> int:
    """Mark pending tasks with due_date < today as overdue. Returns count."""
    now = datetime.now().isoformat(timespec="seconds")
    cursor = db.execute(
        """
        UPDATE tasks SET status = 'overdue', updated_at = ?
        WHERE status = 'pending' AND due_date IS NOT NULL AND due_date < ?
        """,
        (now, today),
    )
    db.commit()
    return cursor.rowcount


def reconcile_day(db: sqlite3.Connection, reconcile_date: str) -> dict:
    """
    Called on /quest invocation. Checks yesterday:
    - If tasks were completed yesterday: streak maintained
    - If no tasks yesterday and grace available: use grace day
    - If no tasks and no grace: reset streak (lose multiplier, not XP)
    Also marks overdue tasks.
    """
    today = reconcile_date
    yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()

    state = get_streak_state(db)

    # Awaken snoozed tasks before marking overdue
    _awaken_snoozed_tasks(db, today)

    # Mark overdue tasks
    overdue_count = _mark_overdue_tasks(db, today)

    # If last_active_date is today or yesterday, streak already up to date
    if state.last_active_date in (today, yesterday):
        return {
            "action": "none",
            "streak": state.current_streak,
            "overdue_marked": overdue_count,
        }

    # If no last_active_date, nothing to reconcile
    if state.last_active_date is None:
        return {
            "action": "none",
            "streak": state.current_streak,
            "overdue_marked": overdue_count,
        }

    # Check if tasks were completed yesterday
    completed_yesterday = _tasks_completed_on(db, yesterday)

    if completed_yesterday > 0:
        # Streak maintained via actual activity (record_activity handles this per task)
        # Just ensure last_active_date is set
        return {
            "action": "streak_maintained",
            "streak": state.current_streak,
            "overdue_marked": overdue_count,
        }

    # No activity yesterday — try grace day
    if _grace_available(state, today):
        new_state = _use_grace(db, state, today, yesterday)
        return {
            "action": "grace_used",
            "streak": new_state.current_streak,
            "grace_remaining": GRACE_DAYS_PER_WEEK - new_state.grace_days_used_this_week,
            "overdue_marked": overdue_count,
        }

    # No grace available — reset streak
    new_state = _reset_streak(db)
    return {
        "action": "streak_reset",
        "streak": new_state.current_streak,
        "overdue_marked": overdue_count,
    }
