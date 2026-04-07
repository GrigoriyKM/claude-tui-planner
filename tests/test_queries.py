"""Integration tests for quest/queries.py using an in-memory SQLite database."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from quest.db import SCHEMA_SQL, _apply_incremental_migrations
from quest.queries import (
    add_task,
    cancel_task,
    complete_task,
    delete_task,
    get_persistent_notes,
    get_task,
    get_user_stats,
    save_persistent_notes,
    search_tasks,
    snooze_task,
    uncomplete_task,
    update_task_fields,
)
from quest.xp import XP_VALUES


@pytest.fixture
def db():  # type: ignore[override]
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    _apply_incremental_migrations(conn)
    yield conn
    conn.close()


class TestAddTask:
    def test_creates_task_with_correct_xp_value(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Test task", "small")
        assert task.xp_value == XP_VALUES["small"]

    def test_creates_task_with_correct_title(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "My title", "medium")
        assert task.title == "My title"

    def test_creates_task_with_correct_size(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "large")
        assert task.size == "large"

    def test_creates_task_with_pending_status(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "tiny")
        assert task.status == "pending"

    def test_increments_tasks_created_in_user_stats(self, db: sqlite3.Connection) -> None:
        stats_before = get_user_stats(db)
        add_task(db, "Task 1", "small")
        stats_after = get_user_stats(db)
        assert stats_after.tasks_created == stats_before.tasks_created + 1

    def test_increments_tasks_created_multiple_times(self, db: sqlite3.Connection) -> None:
        stats_before = get_user_stats(db)
        add_task(db, "Task 1", "small")
        add_task(db, "Task 2", "medium")
        add_task(db, "Task 3", "large")
        stats_after = get_user_stats(db)
        assert stats_after.tasks_created == stats_before.tasks_created + 3

    def test_task_with_due_date(self, db: sqlite3.Connection) -> None:
        due = (date.today() + timedelta(days=3)).isoformat()
        task = add_task(db, "Task", "small", due_date=due)
        assert task.due_date == due

    def test_task_without_due_date(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        assert task.due_date is None

    def test_task_with_priority(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small", priority="high")
        assert task.priority == "high"

    def test_task_default_priority_is_normal(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        assert task.priority == "normal"

    def test_all_sizes_have_correct_xp_value(self, db: sqlite3.Connection) -> None:
        for size, expected_xp in XP_VALUES.items():
            task = add_task(db, f"Task {size}", size)
            assert task.xp_value == expected_xp

    def test_returns_task_with_id(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        assert task.id is not None
        assert task.id > 0


class TestCompleteTask:
    def test_marks_task_as_done(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        complete_task(db, task.id)
        updated = get_task(db, task.id)
        assert updated.status == "done"

    def test_awards_xp_to_task(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        complete_task(db, task.id)
        updated = get_task(db, task.id)
        assert updated.xp_earned > 0

    def test_updates_user_stats_total_xp(self, db: sqlite3.Connection) -> None:
        stats_before = get_user_stats(db)
        task = add_task(db, "Task", "small")
        complete_task(db, task.id)
        stats_after = get_user_stats(db)
        assert stats_after.total_xp > stats_before.total_xp

    def test_increments_tasks_completed_in_user_stats(self, db: sqlite3.Connection) -> None:
        stats_before = get_user_stats(db)
        task = add_task(db, "Task", "small")
        complete_task(db, task.id)
        stats_after = get_user_stats(db)
        assert stats_after.tasks_completed == stats_before.tasks_completed + 1

    def test_creates_daily_log_entry(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        complete_task(db, task.id)
        today = date.today().isoformat()
        row = db.execute(
            "SELECT * FROM daily_logs WHERE log_date = ?", (today,)
        ).fetchone()
        assert row is not None
        assert row["tasks_completed"] >= 1

    def test_returns_result_dict_with_expected_keys(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        result = complete_task(db, task.id)
        assert "task_id" in result
        assert "base_xp" in result
        assert "bonus_xp" in result
        assert "total_xp" in result
        assert "new_total_xp" in result
        assert "new_level" in result

    def test_raises_on_already_done_task(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        complete_task(db, task.id)
        with pytest.raises(ValueError, match="already completed"):
            complete_task(db, task.id)

    def test_raises_on_cancelled_task(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        cancel_task(db, task.id)
        with pytest.raises(ValueError, match="cancelled"):
            complete_task(db, task.id)

    def test_sets_completed_at(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        complete_task(db, task.id)
        updated = get_task(db, task.id)
        assert updated.completed_at is not None


class TestUncompleteTask:
    def test_reverts_status_to_pending(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        complete_task(db, task.id)
        uncomplete_task(db, task.id)
        updated = get_task(db, task.id)
        assert updated.status == "pending"

    def test_subtracts_xp_from_user_stats(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        complete_task(db, task.id)
        stats_after_complete = get_user_stats(db)
        uncomplete_task(db, task.id)
        stats_after_uncomplete = get_user_stats(db)
        assert stats_after_uncomplete.total_xp < stats_after_complete.total_xp

    def test_decrements_tasks_completed_in_stats(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        complete_task(db, task.id)
        stats_after_complete = get_user_stats(db)
        uncomplete_task(db, task.id)
        stats_after_uncomplete = get_user_stats(db)
        assert stats_after_uncomplete.tasks_completed == stats_after_complete.tasks_completed - 1

    def test_clears_xp_earned_on_task(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        complete_task(db, task.id)
        uncomplete_task(db, task.id)
        updated = get_task(db, task.id)
        assert updated.xp_earned == 0

    def test_clears_completed_at(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        complete_task(db, task.id)
        uncomplete_task(db, task.id)
        updated = get_task(db, task.id)
        assert updated.completed_at is None

    def test_raises_on_non_done_pending_task(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        with pytest.raises(ValueError, match="not done"):
            uncomplete_task(db, task.id)

    def test_raises_on_cancelled_task(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        cancel_task(db, task.id)
        with pytest.raises(ValueError, match="not done"):
            uncomplete_task(db, task.id)


class TestDeleteTask:
    def test_removes_row_from_database(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        delete_task(db, task.id)
        with pytest.raises(ValueError):
            get_task(db, task.id)

    def test_does_not_increment_tasks_cancelled(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        stats_before = get_user_stats(db)
        delete_task(db, task.id)
        stats_after = get_user_stats(db)
        assert stats_after.tasks_cancelled == stats_before.tasks_cancelled

    def test_raises_on_missing_id(self, db: sqlite3.Connection) -> None:
        with pytest.raises(ValueError):
            delete_task(db, 99999)

    def test_returns_dict_with_id_and_title(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "My task", "small")
        result = delete_task(db, task.id)
        assert result["id"] == task.id
        assert result["title"] == "My task"


class TestCancelTask:
    def test_sets_status_to_cancelled(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        cancel_task(db, task.id)
        updated = get_task(db, task.id)
        assert updated.status == "cancelled"

    def test_increments_tasks_cancelled(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        stats_before = get_user_stats(db)
        cancel_task(db, task.id)
        stats_after = get_user_stats(db)
        assert stats_after.tasks_cancelled == stats_before.tasks_cancelled + 1

    def test_returns_updated_task(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        result = cancel_task(db, task.id)
        assert result.status == "cancelled"


class TestGetTask:
    def test_returns_task_by_id(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "My task", "medium")
        fetched = get_task(db, task.id)
        assert fetched.id == task.id
        assert fetched.title == "My task"

    def test_raises_on_missing_id(self, db: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="not found"):
            get_task(db, 99999)


class TestUpdateTaskFields:
    def test_updates_title(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Old title", "small")
        updated = update_task_fields(db, task.id, "New title", "small", "normal", None)
        assert updated.title == "New title"

    def test_updates_size(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        updated = update_task_fields(db, task.id, "Task", "large", "normal", None)
        assert updated.size == "large"

    def test_recalculates_xp_value_on_size_change(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        updated = update_task_fields(db, task.id, "Task", "epic", "normal", None)
        assert updated.xp_value == XP_VALUES["epic"]

    def test_updates_priority(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        updated = update_task_fields(db, task.id, "Task", "small", "urgent", None)
        assert updated.priority == "urgent"

    def test_updates_due_date(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        due = (date.today() + timedelta(days=5)).isoformat()
        updated = update_task_fields(db, task.id, "Task", "small", "normal", due)
        assert updated.due_date == due

    def test_clears_due_date_when_none(self, db: sqlite3.Connection) -> None:
        due = (date.today() + timedelta(days=5)).isoformat()
        task = add_task(db, "Task", "small", due_date=due)
        updated = update_task_fields(db, task.id, "Task", "small", "normal", None)
        assert updated.due_date is None

    def test_raises_on_done_task(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        complete_task(db, task.id)
        with pytest.raises(ValueError):
            update_task_fields(db, task.id, "New title", "small", "normal", None)

    def test_raises_on_cancelled_task(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        cancel_task(db, task.id)
        with pytest.raises(ValueError):
            update_task_fields(db, task.id, "New title", "small", "normal", None)


class TestSnoozeTask:
    def test_sets_status_to_snoozed(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        until = (date.today() + timedelta(days=3)).isoformat()
        snooze_task(db, task.id, until)
        updated = get_task(db, task.id)
        assert updated.status == "snoozed"

    def test_stores_snooze_until_date(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        until = (date.today() + timedelta(days=3)).isoformat()
        snooze_task(db, task.id, until)
        updated = get_task(db, task.id)
        assert updated.snooze_until == until

    def test_returns_updated_task(self, db: sqlite3.Connection) -> None:
        task = add_task(db, "Task", "small")
        until = (date.today() + timedelta(days=3)).isoformat()
        result = snooze_task(db, task.id, until)
        assert result.status == "snoozed"
        assert result.snooze_until == until


class TestSearchTasks:
    def test_returns_matching_task_by_title(self, db: sqlite3.Connection) -> None:
        add_task(db, "Fix the login bug", "small")
        add_task(db, "Write documentation", "medium")
        results = search_tasks(db, "login")
        assert len(results) == 1
        assert results[0].title == "Fix the login bug"

    def test_returns_empty_for_no_match(self, db: sqlite3.Connection) -> None:
        add_task(db, "Fix the login bug", "small")
        results = search_tasks(db, "xyz_no_match")
        assert len(results) == 0

    def test_match_is_case_insensitive_via_like(self, db: sqlite3.Connection) -> None:
        # SQLite LIKE is case-insensitive for ASCII by default
        add_task(db, "Fix Login Bug", "small")
        results = search_tasks(db, "login")
        assert len(results) == 1

    def test_returns_multiple_matches(self, db: sqlite3.Connection) -> None:
        add_task(db, "Fix the login bug", "small")
        add_task(db, "Update login page", "medium")
        add_task(db, "Write docs", "tiny")
        results = search_tasks(db, "login")
        assert len(results) == 2

    def test_partial_match(self, db: sqlite3.Connection) -> None:
        add_task(db, "Refactor authentication module", "large")
        results = search_tasks(db, "auth")
        assert len(results) == 1


class TestPersistentNotes:
    def test_get_persistent_notes_returns_empty_string_initially(
        self, db: sqlite3.Connection
    ) -> None:
        content = get_persistent_notes(db)
        assert content == ""

    def test_save_and_retrieve_notes(self, db: sqlite3.Connection) -> None:
        save_persistent_notes(db, "My important notes")
        content = get_persistent_notes(db)
        assert content == "My important notes"

    def test_save_overwrites_previous_content(self, db: sqlite3.Connection) -> None:
        save_persistent_notes(db, "First content")
        save_persistent_notes(db, "Second content")
        content = get_persistent_notes(db)
        assert content == "Second content"

    def test_save_empty_string(self, db: sqlite3.Connection) -> None:
        save_persistent_notes(db, "Some notes")
        save_persistent_notes(db, "")
        content = get_persistent_notes(db)
        assert content == ""

    def test_round_trip_multiline_content(self, db: sqlite3.Connection) -> None:
        multiline = "Line 1\nLine 2\nLine 3"
        save_persistent_notes(db, multiline)
        content = get_persistent_notes(db)
        assert content == multiline
