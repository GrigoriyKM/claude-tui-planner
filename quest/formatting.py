"""Terminal formatting utilities for Quest output."""

from __future__ import annotations

from quest.models import StreakState, UserStats
from quest.xp import xp_for_level

SPARK_CHARS = " ▁▂▃▄▅▆▇█"


def progress_bar(current: int, total: int, width: int = 24) -> str:
    """Return a [████████░░░░░░░░] style progress bar."""
    if total <= 0:
        filled = 0
    else:
        ratio = min(max(current, 0) / total, 1.0)
        filled = round(ratio * width)
    empty = width - filled
    return "[" + "█" * filled + "░" * empty + "]"


def sparkline(values: list[int]) -> str:
    """Return a ▂▃▅▇█▇▅ style sparkline from a list of integers."""
    if not values:
        return ""
    max_val = max(values)
    if max_val == 0:
        return SPARK_CHARS[0] * len(values)
    chars = []
    for v in values:
        idx = round((v / max_val) * (len(SPARK_CHARS) - 1))
        chars.append(SPARK_CHARS[idx])
    return "".join(chars)


def format_status_line(stats: UserStats, streak: StreakState) -> str:
    """Return a single-line status summary.

    Example: Level 7 Journeyman · 🔥 12 days · XP: 1,540 / 2,000
    """
    next_level_xp = xp_for_level(stats.current_level + 1)
    streak_part = f"🔥 {streak.current_streak} days" if streak.current_streak > 0 else "no streak"
    return (
        f"Level {stats.current_level} {stats.level_title} · "
        f"{streak_part} · "
        f"XP: {stats.total_xp:,} / {next_level_xp:,}"
    )
