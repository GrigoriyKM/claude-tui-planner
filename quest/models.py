"""Frozen dataclasses representing database rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PRIORITY_ORDER = {"urgent": 0, "high": 1, "normal": 2, "low": 3}


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
    def from_row(cls, row: Any) -> "Task":
        return cls(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            size=row["size"],
            status=row["status"],
            priority=row["priority"] if row["priority"] is not None else "normal",
            xp_value=row["xp_value"],
            xp_earned=row["xp_earned"] if row["xp_earned"] is not None else 0,
            due_date=row["due_date"],
            snooze_until=row["snooze_until"],
            parent_id=row["parent_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "size": self.size,
            "status": self.status,
            "priority": self.priority,
            "xp_value": self.xp_value,
            "xp_earned": self.xp_earned,
            "due_date": self.due_date,
            "snooze_until": self.snooze_until,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }


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
    def from_row(cls, row: Any) -> "DailyLog":
        return cls(
            id=row["id"],
            log_date=row["log_date"],
            tasks_completed=row["tasks_completed"],
            xp_earned=row["xp_earned"],
            streak_active=row["streak_active"],
            grace_used=row["grace_used"],
            day_rating=row["day_rating"],
            notes=row["notes"],
            created_at=row["created_at"],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "log_date": self.log_date,
            "tasks_completed": self.tasks_completed,
            "xp_earned": self.xp_earned,
            "streak_active": bool(self.streak_active),
            "grace_used": bool(self.grace_used),
            "day_rating": self.day_rating,
            "notes": self.notes,
            "created_at": self.created_at,
        }


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
    def from_row(cls, row: Any) -> "StreakState":
        return cls(
            id=row["id"],
            current_streak=row["current_streak"],
            longest_streak=row["longest_streak"],
            last_active_date=row["last_active_date"],
            grace_days_used_this_week=row["grace_days_used_this_week"],
            grace_week_start=row["grace_week_start"],
            streak_freeze_available=row["streak_freeze_available"],
            streak_freeze_used_this_month=row["streak_freeze_used_this_month"],
            freeze_month=row["freeze_month"],
            updated_at=row["updated_at"],
        )

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
    def from_row(cls, row: Any) -> "UserStats":
        return cls(
            id=row["id"],
            total_xp=row["total_xp"],
            current_level=row["current_level"],
            level_title=row["level_title"],
            tasks_created=row["tasks_created"],
            tasks_completed=row["tasks_completed"],
            tasks_cancelled=row["tasks_cancelled"],
            days_active=row["days_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

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
