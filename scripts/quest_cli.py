#!/usr/bin/env python3
"""Quest CLI - Gamified task management for Claude Code."""

from __future__ import annotations

import json
import logging
import sys
from datetime import date

import click

logging.basicConfig(level=logging.WARNING)


def _require_db():
    """Return an open DB connection or exit with a helpful message."""
    from quest.db import db_exists, init_db

    if not db_exists():
        click.echo(
            json.dumps({"error": "Database not initialized. Run: quest_cli.py init"}),
            err=False,
        )
        sys.exit(1)
    return init_db()


def _output(data: dict | list) -> None:
    click.echo(json.dumps(data, ensure_ascii=False))


@click.group()
def cli() -> None:
    """Quest - Gamified task management."""


@cli.command()
def init() -> None:
    """Initialize the Quest database."""
    from quest.db import init_db

    init_db()
    _output({"status": "ok", "message": "Quest database initialized."})


@cli.command()
def status() -> None:
    """Show user stats, today's tasks, and overdue count."""
    from quest.formatting import format_status_line, progress_bar
    from quest.queries import get_overdue_tasks, get_tasks_for_today, get_user_stats
    from quest.streaks import get_streak_state
    from quest.xp import xp_for_level

    db = _require_db()
    stats = get_user_stats(db)
    streak = get_streak_state(db)
    today_tasks = get_tasks_for_today(db)
    overdue = get_overdue_tasks(db)

    current_level_xp = xp_for_level(stats.current_level) if stats.current_level > 1 else 0
    next_level_xp = xp_for_level(stats.current_level + 1)
    bar = progress_bar(stats.total_xp - current_level_xp,
                       next_level_xp - current_level_xp)

    _output({
        "status_line": format_status_line(stats, streak),
        "xp_bar": bar,
        "stats": stats.to_dict(),
        "streak": streak.to_dict(),
        "today_tasks": [t.to_dict() for t in today_tasks],
        "overdue_count": len(overdue),
    })


@cli.command("add")
@click.option("--title", required=True, help="Task title")
@click.option(
    "--size",
    required=True,
    type=click.Choice(["tiny", "small", "medium", "large", "epic"]),
    help="Task size",
)
@click.option("--due", default=None, help="Due date (YYYY-MM-DD)")
@click.option("--parent-id", default=None, type=int, help="Parent task ID")
@click.option("--description", default=None, help="Task description")
@click.option(
    "--priority",
    default="normal",
    type=click.Choice(["low", "normal", "high", "urgent"]),
    help="Task priority",
)
def add_task(title: str, size: str, due: str | None, parent_id: int | None, description: str | None, priority: str) -> None:
    """Add a new task."""
    from quest.queries import add_task as _add

    db = _require_db()
    task = _add(db, title=title, size=size, due_date=due, parent_id=parent_id, description=description, priority=priority)
    _output({"status": "ok", "task": task.to_dict()})


@cli.command("complete")
@click.argument("task_id", type=int)
def complete(task_id: int) -> None:
    """Mark a task as done and award XP."""
    from quest.queries import complete_task as _complete

    db = _require_db()
    try:
        result = _complete(db, task_id)
        _output({"status": "ok", "result": result})
    except ValueError as exc:
        _output({"error": str(exc)})
        sys.exit(1)


@cli.command("snooze")
@click.argument("task_id", type=int)
@click.option("--until", required=True, help="Snooze until date (YYYY-MM-DD)")
def snooze(task_id: int, until: str) -> None:
    """Snooze a task until a given date."""
    from quest.queries import snooze_task as _snooze

    db = _require_db()
    try:
        task = _snooze(db, task_id, until)
        _output({"status": "ok", "task": task.to_dict()})
    except ValueError as exc:
        _output({"error": str(exc)})
        sys.exit(1)


@cli.command("cancel")
@click.argument("task_id", type=int)
def cancel(task_id: int) -> None:
    """Cancel a task."""
    from quest.queries import cancel_task as _cancel

    db = _require_db()
    try:
        task = _cancel(db, task_id)
        _output({"status": "ok", "task": task.to_dict()})
    except ValueError as exc:
        _output({"error": str(exc)})
        sys.exit(1)


@cli.command("list")
@click.option("--status", default=None, help="Filter by status")
@click.option("--limit", default=50, type=int, help="Max results")
def list_tasks(status: str | None, limit: int) -> None:
    """List tasks with optional status filter."""
    from quest.queries import list_tasks as _list

    db = _require_db()
    tasks = _list(db, status=status, limit=limit)
    _output({"tasks": [t.to_dict() for t in tasks]})


@cli.command("search")
@click.argument("query")
def search(query: str) -> None:
    """Fuzzy search tasks by title."""
    from quest.queries import search_tasks as _search

    db = _require_db()
    tasks = _search(db, query)
    _output({"tasks": [t.to_dict() for t in tasks]})


@cli.command("overdue")
def overdue() -> None:
    """List overdue tasks."""
    from quest.queries import get_overdue_tasks

    db = _require_db()
    tasks = get_overdue_tasks(db)
    _output({"tasks": [t.to_dict() for t in tasks]})


@cli.command("reconcile")
def reconcile() -> None:
    """Run daily reconciliation (check streak, mark overdue)."""
    from quest.streaks import reconcile_day

    db = _require_db()
    today = date.today().isoformat()
    result = reconcile_day(db, today)
    _output({"status": "ok", "reconcile": result})


@cli.command("done-today")
def done_today() -> None:
    """List tasks completed today."""
    from quest.queries import get_done_tasks

    db = _require_db()
    tasks = get_done_tasks(db, days=0)
    _output({"tasks": [t.to_dict() for t in tasks]})


@cli.command("log")
@click.option("--date", "log_date", default=None, help="Date (YYYY-MM-DD), defaults to today")
@click.option("--rating", default=None, type=click.IntRange(1, 5), help="Day rating (1-5)")
@click.option("--notes", default=None, help="Notes for the day")
def log(log_date: str | None, rating: int | None, notes: str | None) -> None:
    """Add or update a daily log entry."""
    from quest.queries import upsert_daily_log

    db = _require_db()
    effective_date = log_date if log_date is not None else date.today().isoformat()
    entry = upsert_daily_log(db, effective_date, day_rating=rating, notes=notes)
    _output({"status": "ok", "log": entry.to_dict()})


if __name__ == "__main__":
    cli()
