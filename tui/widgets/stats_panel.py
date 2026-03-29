"""Stats panel widget — shows level, XP bar, streak, and sparkline."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

logger = logging.getLogger(__name__)

# Inject quest path so imports work when running as module
import sys as _sys

_QUEST_ROOT = str(Path.home() / ".claude" / "quest")
if _QUEST_ROOT not in _sys.path:
    _sys.path.insert(0, _QUEST_ROOT)

from quest.formatting import progress_bar, sparkline
from quest.models import StreakState, UserStats
from quest.xp import xp_for_level


def _build_sparkline_values(db: sqlite3.Connection) -> list[int]:
    """Query last 14 days of XP from daily_logs."""
    rows = db.execute(
        """
        SELECT log_date, xp_earned FROM daily_logs
        WHERE log_date >= date('now', '-14 days')
        ORDER BY log_date ASC
        """
    ).fetchall()
    return [r["xp_earned"] for r in rows]


def render_stats(stats: UserStats, streak: StreakState, spark_values: list[int]) -> str:
    """Build the three-line stats text block."""
    next_level = stats.current_level + 1
    next_xp = xp_for_level(next_level)
    current_xp = stats.total_xp
    xp_in_level = xp_for_level(stats.current_level)
    xp_needed_for_next = next_xp - xp_in_level
    xp_progress = current_xp - xp_in_level
    remaining = next_xp - current_xp

    bar = progress_bar(xp_progress, xp_needed_for_next, width=40)
    spark = sparkline(spark_values) if spark_values else "no data"

    if streak.current_streak > 0:
        streak_part = f"[yellow]🔥 {streak.current_streak} days[/yellow]"
    else:
        streak_part = "[dim]no streak[/dim]"

    line1 = (
        f"[bold cyan]QUEST[/bold cyan]  ·  "
        f"[bold]Level {stats.current_level} {stats.level_title}[/bold]  ·  "
        f"{streak_part}"
    )
    line2 = (
        f"XP: [cyan]{bar}[/cyan] "
        f"[bold]{current_xp:,}[/bold] / {next_xp:,}  "
        f"([dim]+{remaining} to Level {next_level}[/dim])"
    )
    line3 = f"Last 14d: [dim]{spark}[/dim]"

    return f"{line1}\n{line2}\n{line3}"


class StatsPanel(Widget):
    """Displays player stats: level, XP bar, streak, sparkline."""

    DEFAULT_CSS = """
    StatsPanel {
        height: 5;
        border-bottom: solid $panel;
        padding: 0 1;
    }
    """

    stats_text: reactive[str] = reactive("Loading...")

    def compose(self) -> ComposeResult:
        yield Static(self.stats_text, id="stats-content", markup=True)

    def watch_stats_text(self, new_text: str) -> None:
        try:
            widget = self.query_one("#stats-content", Static)
            widget.update(new_text)
        except Exception:
            pass

    def refresh_stats(self, db: sqlite3.Connection) -> None:
        """Pull fresh data from DB and update display."""
        try:
            from quest.queries import get_user_stats
            from quest.streaks import get_streak_state

            stats = get_user_stats(db)
            streak = get_streak_state(db)
            spark_values = _build_sparkline_values(db)
            self.stats_text = render_stats(stats, streak, spark_values)
        except Exception as exc:
            logger.exception("Failed to refresh stats")
            self.stats_text = f"[red]Error loading stats: {exc}[/red]"
