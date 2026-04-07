"""Frozen dataclasses representing database rows."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, fields


PRIORITY_ORDER = {"urgent": 0, "high": 1, "normal": 2, "low": 3}

_TASK_DEFAULTS: dict[str, object] = {"priority": "normal", "xp_earned": 0}


def _from_row(
    cls: type, row: sqlite3.Row, defaults: dict[str, object] | None = None
) -> object:
    """Generic factory: build a frozen dataclass from an sqlite3.Row.

    *defaults* is a mapping {field_name: fallback} applied when the DB value
    is ``None`` (handles columns added via migration that lack a NOT NULL
    constraint on old rows).
    """
    defs = defaults or {}
    return cls(
        **{
            f.name: (
                defs[f.name] if row[f.name] is None and f.name in defs else row[f.name]
            )
            for f in fields(cls)
        }
    )


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    description: str | None
    size: str
    status: str
    priority: str
    xp_value: int
    xp_earned: int
    due_date: str | None
    snooze_until: str | None
    parent_id: int | None
    created_at: str
    updated_at: str
    completed_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Task:
        return _from_row(cls, row, _TASK_DEFAULTS)  # type: ignore[return-value]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DailyLog:
    id: int
    log_date: str
    tasks_completed: int
    xp_earned: int
    streak_active: int
    grace_used: int
    day_rating: int | None
    notes: str | None
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> DailyLog:
        return _from_row(cls, row)  # type: ignore[return-value]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["streak_active"] = bool(d["streak_active"])
        d["grace_used"] = bool(d["grace_used"])
        return d


@dataclass(frozen=True)
class StreakState:
    id: int
    current_streak: int
    longest_streak: int
    last_active_date: str | None
    grace_days_used_this_week: int
    grace_week_start: str | None
    streak_freeze_available: int
    streak_freeze_used_this_month: int
    freeze_month: str | None
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> StreakState:
        return _from_row(cls, row)  # type: ignore[return-value]

    def to_dict(self) -> dict:
        return {
            "current_streak": self.current_streak,
            "longest_streak": self.longest_streak,
            "last_active_date": self.last_active_date,
            "grace_days_used_this_week": self.grace_days_used_this_week,
            "streak_freeze_available": bool(self.streak_freeze_available),
            "streak_freeze_used_this_month": self.streak_freeze_used_this_month,
        }


@dataclass(frozen=True)
class UserStats:
    id: int
    total_xp: int
    current_level: int
    level_title: str
    tasks_created: int
    tasks_completed: int
    tasks_cancelled: int
    days_active: int
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> UserStats:
        return _from_row(cls, row)  # type: ignore[return-value]

    def to_dict(self) -> dict:
        return {
            "total_xp": self.total_xp,
            "current_level": self.current_level,
            "level_title": self.level_title,
            "tasks_created": self.tasks_created,
            "tasks_completed": self.tasks_completed,
            "tasks_cancelled": self.tasks_cancelled,
            "days_active": self.days_active,
        }
