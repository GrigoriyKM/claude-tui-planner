"""XP calculations, level progression, and streak bonuses."""

import math

XP_VALUES: dict[str, int] = {
    "tiny": 25,
    "small": 50,
    "medium": 150,
    "large": 400,
    "epic": 1000,
}

# List of (min_streak_days, bonus_fraction) in descending streak order
STREAK_BONUSES: list[tuple[int, float]] = [
    (30, 0.25),
    (14, 0.15),
    (7, 0.10),
    (3, 0.05),
]

# List of (min_level, title) in descending level order
LEVEL_TITLES: list[tuple[int, str]] = [
    (51, "Grandmaster"),
    (31, "Master"),
    (21, "Expert"),
    (11, "Craftsman"),
    (6, "Journeyman"),
    (1, "Apprentice"),
]


def xp_for_level(n: int) -> int:
    """Return the total XP required to reach level n."""
    return math.floor(100 * (n ** 1.8))


def level_for_xp(total_xp: int) -> int:
    """Return the highest level where xp_for_level(level) <= total_xp."""
    level = 1
    while xp_for_level(level + 1) <= total_xp:
        level += 1
    return level


def level_title(level: int) -> str:
    """Return the title string for a given level."""
    for min_level, title in LEVEL_TITLES:
        if level >= min_level:
            return title
    return "Apprentice"


def streak_multiplier(streak_days: int) -> float:
    """Return the XP multiplier for the given streak length."""
    for min_days, bonus in STREAK_BONUSES:
        if streak_days >= min_days:
            return 1.0 + bonus
    return 1.0


def calculate_xp(size: str, streak_days: int) -> tuple[int, int, int]:
    """Return (base_xp, bonus_xp, total_xp) for completing a task."""
    base_xp = XP_VALUES[size]
    multiplier = streak_multiplier(streak_days)
    total_xp = math.floor(base_xp * multiplier)
    bonus_xp = total_xp - base_xp
    return base_xp, bonus_xp, total_xp
