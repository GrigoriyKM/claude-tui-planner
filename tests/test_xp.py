"""Unit tests for quest/xp.py — XP calculations, level progression, streak bonuses."""

from __future__ import annotations

import math

from quest.xp import (
    XP_VALUES,
    calculate_xp,
    level_for_xp,
    level_title,
    streak_multiplier,
    xp_for_level,
)


class TestXpForLevel:
    def test_level_1(self) -> None:
        assert xp_for_level(1) == 100

    def test_level_2(self) -> None:
        assert xp_for_level(2) == math.floor(100 * (2**1.8))

    def test_level_2_exact_value(self) -> None:
        assert xp_for_level(2) == 348

    def test_level_3(self) -> None:
        assert xp_for_level(3) == math.floor(100 * (3**1.8))

    def test_monotonically_increasing(self) -> None:
        values = [xp_for_level(n) for n in range(1, 20)]
        for i in range(len(values) - 1):
            assert values[i] < values[i + 1]

    def test_returns_int(self) -> None:
        result = xp_for_level(5)
        assert isinstance(result, int)


class TestLevelForXp:
    def test_zero_xp_is_level_1(self) -> None:
        assert level_for_xp(0) == 1

    def test_exactly_100_xp_is_level_1(self) -> None:
        # xp_for_level(1) = 100, so 100 XP means still level 1
        # because we need xp_for_level(2) <= total_xp to advance
        assert level_for_xp(100) == 1

    def test_347_xp_is_level_1(self) -> None:
        # xp_for_level(2) = 348, so 347 is still level 1
        assert level_for_xp(347) == 1

    def test_348_xp_is_level_2(self) -> None:
        assert level_for_xp(348) == 2

    def test_xp_just_below_level_3(self) -> None:
        level_3_threshold = xp_for_level(3)
        assert level_for_xp(level_3_threshold - 1) == 2

    def test_xp_at_level_3_threshold(self) -> None:
        level_3_threshold = xp_for_level(3)
        assert level_for_xp(level_3_threshold) == 3

    def test_large_xp_gives_high_level(self) -> None:
        # Just verify it returns something reasonable
        result = level_for_xp(100_000)
        assert result > 10

    def test_returns_int(self) -> None:
        assert isinstance(level_for_xp(0), int)


class TestLevelTitle:
    def test_level_1_is_apprentice(self) -> None:
        assert level_title(1) == "Apprentice"

    def test_level_5_is_apprentice(self) -> None:
        assert level_title(5) == "Apprentice"

    def test_level_6_is_journeyman(self) -> None:
        assert level_title(6) == "Journeyman"

    def test_level_10_is_journeyman(self) -> None:
        assert level_title(10) == "Journeyman"

    def test_level_11_is_craftsman(self) -> None:
        assert level_title(11) == "Craftsman"

    def test_level_20_is_craftsman(self) -> None:
        assert level_title(20) == "Craftsman"

    def test_level_21_is_expert(self) -> None:
        assert level_title(21) == "Expert"

    def test_level_30_is_expert(self) -> None:
        assert level_title(30) == "Expert"

    def test_level_31_is_master(self) -> None:
        assert level_title(31) == "Master"

    def test_level_50_is_master(self) -> None:
        assert level_title(50) == "Master"

    def test_level_51_is_grandmaster(self) -> None:
        assert level_title(51) == "Grandmaster"

    def test_level_100_is_grandmaster(self) -> None:
        assert level_title(100) == "Grandmaster"

    def test_returns_string(self) -> None:
        assert isinstance(level_title(1), str)


class TestStreakMultiplier:
    def test_zero_days_is_1(self) -> None:
        assert streak_multiplier(0) == 1.0

    def test_1_day_is_1(self) -> None:
        assert streak_multiplier(1) == 1.0

    def test_2_days_is_1(self) -> None:
        assert streak_multiplier(2) == 1.0

    def test_3_days_is_1_05(self) -> None:
        assert streak_multiplier(3) == 1.05

    def test_6_days_is_1_05(self) -> None:
        assert streak_multiplier(6) == 1.05

    def test_7_days_is_1_10(self) -> None:
        assert streak_multiplier(7) == 1.10

    def test_13_days_is_1_10(self) -> None:
        assert streak_multiplier(13) == 1.10

    def test_14_days_is_1_15(self) -> None:
        assert streak_multiplier(14) == 1.15

    def test_29_days_is_1_15(self) -> None:
        assert streak_multiplier(29) == 1.15

    def test_30_days_is_1_25(self) -> None:
        assert streak_multiplier(30) == 1.25

    def test_100_days_is_1_25(self) -> None:
        assert streak_multiplier(100) == 1.25

    def test_returns_float(self) -> None:
        assert isinstance(streak_multiplier(0), float)


class TestCalculateXp:
    def test_small_no_streak_returns_correct_base(self) -> None:
        base_xp, _, _ = calculate_xp("small", 0)
        assert base_xp == XP_VALUES["small"]
        assert base_xp == 50

    def test_small_no_streak_no_bonus(self) -> None:
        _, bonus_xp, _ = calculate_xp("small", 0)
        assert bonus_xp == 0

    def test_small_no_streak_total_equals_base(self) -> None:
        base_xp, _, total_xp = calculate_xp("small", 0)
        assert total_xp == base_xp

    def test_small_7_day_streak_base_xp(self) -> None:
        base_xp, _, _ = calculate_xp("small", 7)
        assert base_xp == 50

    def test_small_7_day_streak_bonus_xp(self) -> None:
        _, bonus_xp, _ = calculate_xp("small", 7)
        # multiplier is 1.10, so total = floor(50 * 1.10) = 55, bonus = 5
        assert bonus_xp == 5

    def test_small_7_day_streak_total_xp(self) -> None:
        _, _, total_xp = calculate_xp("small", 7)
        assert total_xp == 55

    def test_base_plus_bonus_equals_total(self) -> None:
        for size in XP_VALUES:
            for days in [0, 3, 7, 14, 30]:
                base_xp, bonus_xp, total_xp = calculate_xp(size, days)
                assert base_xp + bonus_xp == total_xp

    def test_all_sizes_present(self) -> None:
        for size in ("tiny", "small", "medium", "large", "epic"):
            base_xp, _, _ = calculate_xp(size, 0)
            assert base_xp == XP_VALUES[size]

    def test_returns_three_ints(self) -> None:
        result = calculate_xp("medium", 5)
        assert len(result) == 3
        base_xp, bonus_xp, total_xp = result
        assert isinstance(base_xp, int)
        assert isinstance(bonus_xp, int)
        assert isinstance(total_xp, int)

    def test_epic_30_day_streak(self) -> None:
        base_xp, bonus_xp, total_xp = calculate_xp("epic", 30)
        assert base_xp == 1000
        # multiplier = 1.25, total = floor(1000 * 1.25) = 1250
        assert total_xp == 1250
        assert bonus_xp == 250
