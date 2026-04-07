"""Integration tests for quest/streaks.py using an in-memory SQLite database."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from quest.db import SCHEMA_SQL, _apply_incremental_migrations
from quest.queries import add_task, snooze_task
from quest.streaks import (
    _awaken_snoozed_tasks,
    _mark_overdue_tasks,
    get_streak_state,
    record_activity,
    reconcile_day,
)


@pytest.fixture
def db():  # type: ignore[override]
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    _apply_incremental_migrations(conn)
    yield conn
    conn.close()


def _date(offset: int = 0) -> str:
    """Return ISO date string relative to today."""
    return (date.today() + timedelta(days=offset)).isoformat()


class TestRecordActivity:
    def test_first_activity_sets_streak_to_1(self, db: sqlite3.Connection) -> None:
        state = record_activity(db, _date(0))
        assert state.current_streak == 1

    def test_first_activity_sets_last_active_date(self, db: sqlite3.Connection) -> None:
        today = _date(0)
        state = record_activity(db, today)
        assert state.last_active_date == today

    def test_consecutive_days_increment_streak(self, db: sqlite3.Connection) -> None:
        day1 = _date(-2)
        day2 = _date(-1)
        day3 = _date(0)
        record_activity(db, day1)
        record_activity(db, day2)
        state = record_activity(db, day3)
        assert state.current_streak == 3

    def test_gap_resets_streak_to_1(self, db: sqlite3.Connection) -> None:
        # Record activity 3 days ago, then today — gap of 2 days
        record_activity(db, _date(-3))
        state = record_activity(db, _date(0))
        assert state.current_streak == 1

    def test_same_day_twice_is_idempotent(self, db: sqlite3.Connection) -> None:
        today = _date(0)
        record_activity(db, today)
        state_first = get_streak_state(db)
        record_activity(db, today)
        state_second = get_streak_state(db)
        assert state_first.current_streak == state_second.current_streak
        assert state_first.last_active_date == state_second.last_active_date

    def test_updates_longest_streak(self, db: sqlite3.Connection) -> None:
        # Build up a 3-day streak
        record_activity(db, _date(-2))
        record_activity(db, _date(-1))
        record_activity(db, _date(0))
        state = get_streak_state(db)
        assert state.longest_streak >= 3

    def test_longest_streak_not_decreased_after_reset(self, db: sqlite3.Connection) -> None:
        # Build a 3-day streak
        record_activity(db, _date(-5))
        record_activity(db, _date(-4))
        record_activity(db, _date(-3))
        state_after_streak = get_streak_state(db)
        longest_after_streak = state_after_streak.longest_streak
        # Now gap and restart
        record_activity(db, _date(0))
        state_after_reset = get_streak_state(db)
        assert state_after_reset.longest_streak == longest_after_streak

    def test_returns_streak_state(self, db: sqlite3.Connection) -> None:
        from quest.models import StreakState
        state = record_activity(db, _date(0))
        assert isinstance(state, StreakState)


class TestReconcileDay:
    def test_streak_maintained_when_last_active_is_yesterday(
        self, db: sqlite3.Connection
    ) -> None:
        yesterday = _date(-1)
        today = _date(0)
        record_activity(db, yesterday)
        result = reconcile_day(db, today)
        assert result["action"] in ("none", "streak_maintained")

    def test_grace_day_used_when_no_activity_yesterday_and_grace_available(
        self, db: sqlite3.Connection
    ) -> None:
        # Record activity 2 days ago so there IS a streak to protect
        two_days_ago = _date(-2)
        today = _date(0)
        record_activity(db, two_days_ago)
        # Force last_active_date to be 2 days ago (no yesterday activity)
        # Reconcile today — should use grace
        result = reconcile_day(db, today)
        assert result["action"] == "grace_used"

    def test_streak_reset_when_no_activity_and_no_grace(
        self, db: sqlite3.Connection
    ) -> None:
        # Use up grace first, then reconcile again without activity
        two_days_ago = _date(-2)
        today = _date(0)

        record_activity(db, two_days_ago)
        # Use the grace day for yesterday
        reconcile_day(db, today)
        # Now exhaust grace by setting grace_days_used_this_week to max
        # and reconcile again from further in the past
        # Simpler: set grace as used via direct DB manipulation and do another reconcile
        from quest.streaks import _week_start
        week_start = _week_start(today)
        db.execute(
            "UPDATE streaks SET grace_days_used_this_week = 1, grace_week_start = ? WHERE id = 1",
            (week_start,),
        )
        # Now simulate: last_active is 3 days ago, no grace left
        three_days_ago = _date(-3)
        db.execute(
            "UPDATE streaks SET last_active_date = ?, current_streak = 2 WHERE id = 1",
            (three_days_ago,),
        )
        result = reconcile_day(db, today)
        assert result["action"] == "streak_reset"

    def test_no_action_when_last_active_is_today(self, db: sqlite3.Connection) -> None:
        today = _date(0)
        record_activity(db, today)
        result = reconcile_day(db, today)
        assert result["action"] == "none"

    def test_no_action_when_no_last_active_date(self, db: sqlite3.Connection) -> None:
        today = _date(0)
        result = reconcile_day(db, today)
        assert result["action"] == "none"

    def test_result_includes_streak_count(self, db: sqlite3.Connection) -> None:
        result = reconcile_day(db, _date(0))
        assert "streak" in result

    def test_result_includes_overdue_marked(self, db: sqlite3.Connection) -> None:
        result = reconcile_day(db, _date(0))
        assert "overdue_marked" in result


class TestAwakenSnoozedTasks:
    def test_wakes_task_whose_snooze_until_has_passed(
        self, db: sqlite3.Connection
    ) -> None:
        task = add_task(db, "Snoozed task", "small")
        past_date = _date(-1)
        snooze_task(db, task.id, past_date)

        today = _date(0)
        count = _awaken_snoozed_tasks(db, today)
        assert count == 1

        row = db.execute("SELECT status FROM tasks WHERE id = ?", (task.id,)).fetchone()
        assert row["status"] == "pending"

    def test_clears_snooze_until_on_awakened_task(
        self, db: sqlite3.Connection
    ) -> None:
        task = add_task(db, "Snoozed task", "small")
        past_date = _date(-1)
        snooze_task(db, task.id, past_date)

        _awaken_snoozed_tasks(db, _date(0))

        row = db.execute(
            "SELECT snooze_until FROM tasks WHERE id = ?", (task.id,)
        ).fetchone()
        assert row["snooze_until"] is None

    def test_does_not_wake_task_snoozed_until_future(
        self, db: sqlite3.Connection
    ) -> None:
        task = add_task(db, "Snoozed task", "small")
        future_date = _date(5)
        snooze_task(db, task.id, future_date)

        count = _awaken_snoozed_tasks(db, _date(0))
        assert count == 0

        row = db.execute("SELECT status FROM tasks WHERE id = ?", (task.id,)).fetchone()
        assert row["status"] == "snoozed"

    def test_wakes_multiple_expired_snoozed_tasks(
        self, db: sqlite3.Connection
    ) -> None:
        task1 = add_task(db, "Task 1", "small")
        task2 = add_task(db, "Task 2", "medium")
        task3 = add_task(db, "Task 3", "large")

        past = _date(-2)
        future = _date(3)
        snooze_task(db, task1.id, past)
        snooze_task(db, task2.id, past)
        snooze_task(db, task3.id, future)

        count = _awaken_snoozed_tasks(db, _date(0))
        assert count == 2

    def test_returns_zero_when_no_snoozed_tasks(self, db: sqlite3.Connection) -> None:
        count = _awaken_snoozed_tasks(db, _date(0))
        assert count == 0


class TestMarkOverdueTasks:
    def test_marks_pending_task_with_past_due_date_as_overdue(
        self, db: sqlite3.Connection
    ) -> None:
        past_due = _date(-1)
        task = add_task(db, "Overdue task", "small", due_date=past_due)

        today = _date(0)
        count = _mark_overdue_tasks(db, today)
        assert count == 1

        row = db.execute("SELECT status FROM tasks WHERE id = ?", (task.id,)).fetchone()
        assert row["status"] == "overdue"

    def test_does_not_mark_task_due_today(self, db: sqlite3.Connection) -> None:
        today = _date(0)
        task = add_task(db, "Due today", "small", due_date=today)

        count = _mark_overdue_tasks(db, today)
        assert count == 0

        row = db.execute("SELECT status FROM tasks WHERE id = ?", (task.id,)).fetchone()
        assert row["status"] == "pending"

    def test_does_not_mark_task_with_future_due_date(
        self, db: sqlite3.Connection
    ) -> None:
        future = _date(3)
        add_task(db, "Future task", "small", due_date=future)

        count = _mark_overdue_tasks(db, _date(0))
        assert count == 0

    def test_does_not_mark_task_without_due_date(self, db: sqlite3.Connection) -> None:
        add_task(db, "No due date", "small")

        count = _mark_overdue_tasks(db, _date(0))
        assert count == 0

    def test_marks_multiple_overdue_tasks(self, db: sqlite3.Connection) -> None:
        past1 = _date(-3)
        past2 = _date(-1)
        future = _date(2)
        add_task(db, "Task 1", "small", due_date=past1)
        add_task(db, "Task 2", "small", due_date=past2)
        add_task(db, "Task 3", "small", due_date=future)

        count = _mark_overdue_tasks(db, _date(0))
        assert count == 2

    def test_returns_zero_when_no_overdue_tasks(self, db: sqlite3.Connection) -> None:
        count = _mark_overdue_tasks(db, _date(0))
        assert count == 0
