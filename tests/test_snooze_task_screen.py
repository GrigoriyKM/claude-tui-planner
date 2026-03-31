"""Tests for SnoozeTaskScreen date logic."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

from tui.screens.snooze_task_screen import SnoozeTaskScreen, _PRESET_DAYS


def _make_screen(task_id: int = 1, title: str = "Test task") -> SnoozeTaskScreen:
    """Build a SnoozeTaskScreen with a minimal fake Task."""
    task = MagicMock()
    task.id = task_id
    task.title = title
    screen = SnoozeTaskScreen.__new__(SnoozeTaskScreen)
    screen._quest_task = task
    return screen


class TestPresetDays:
    def test_all_presets_present(self) -> None:
        assert "tomorrow" in _PRESET_DAYS
        assert "in 7 days" in _PRESET_DAYS
        assert "in 14 days" in _PRESET_DAYS

    def test_tomorrow_is_1(self) -> None:
        assert _PRESET_DAYS["tomorrow"] == 1

    def test_week_is_7(self) -> None:
        assert _PRESET_DAYS["in 7 days"] == 7

    def test_fortnight_is_14(self) -> None:
        assert _PRESET_DAYS["in 14 days"] == 14


class TestParseCustomDate:
    def _parse(self, screen: SnoozeTaskScreen, raw: str) -> str | None:
        screen.notify = MagicMock()  # type: ignore[method-assign]
        return screen._parse_custom_date(raw)

    def test_valid_future_date(self) -> None:
        screen = _make_screen()
        future = (date.today() + timedelta(days=3)).isoformat()
        result = self._parse(screen, future)
        assert result == future
        screen.notify.assert_not_called()

    def test_tomorrow_is_accepted(self) -> None:
        screen = _make_screen()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        result = self._parse(screen, tomorrow)
        assert result == tomorrow

    def test_today_is_rejected(self) -> None:
        screen = _make_screen()
        screen.notify = MagicMock()  # type: ignore[method-assign]
        result = screen._parse_custom_date(date.today().isoformat())
        assert result is None
        screen.notify.assert_called_once()
        assert "future" in screen.notify.call_args[0][0]

    def test_past_date_is_rejected(self) -> None:
        screen = _make_screen()
        screen.notify = MagicMock()  # type: ignore[method-assign]
        past = (date.today() - timedelta(days=1)).isoformat()
        result = screen._parse_custom_date(past)
        assert result is None
        screen.notify.assert_called_once()

    def test_invalid_format_is_rejected(self) -> None:
        screen = _make_screen()
        screen.notify = MagicMock()  # type: ignore[method-assign]
        result = screen._parse_custom_date("31-12-2099")
        assert result is None
        screen.notify.assert_called_once()
        assert "YYYY-MM-DD" in screen.notify.call_args[0][0]

    def test_garbage_input_is_rejected(self) -> None:
        screen = _make_screen()
        screen.notify = MagicMock()  # type: ignore[method-assign]
        result = screen._parse_custom_date("not a date")
        assert result is None
        screen.notify.assert_called_once()
