"""Notes panel widget with debounced auto-save to persistent_notes."""

from __future__ import annotations

import logging
import sqlite3

from textual.app import ComposeResult
from textual.binding import Binding
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Label, TextArea

logger = logging.getLogger(__name__)


class NotesPanel(Widget):
    """Toggleable right-side panel for persistent notes, backed by persistent_notes table."""

    BINDINGS = [
        Binding("escape", "back_to_list", "Back to list", show=False),
    ]

    DEFAULT_CSS = """
    NotesPanel {
        width: 30%;
        border-left: solid $panel;
        padding: 0 0;
        height: 100%;
    }
    NotesPanel > Label {
        height: 1;
        background: $panel;
        width: 100%;
        padding: 0 1;
    }
    NotesPanel > TextArea {
        height: 1fr;
        border: none;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._db: sqlite3.Connection | None = None
        self._save_timer: Timer | None = None
        # Latest notes text for debounced save; avoids querying DOM during unmount
        # when children may already be detached (NoMatches).
        self._notes_text_snapshot: str = ""

    def compose(self) -> ComposeResult:
        yield Label("[bold]NOTES[/bold]", markup=True)
        yield TextArea(id="notes-area")

    def load_notes(self, db: sqlite3.Connection) -> None:
        """Load persistent notes from DB into the text area."""
        self._db = db
        try:
            from quest.queries import get_persistent_notes

            text = get_persistent_notes(db)
            self._notes_text_snapshot = text
            self.query_one("#notes-area", TextArea).load_text(text)
        except Exception:
            logger.exception("Failed to load notes")

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self._notes_text_snapshot = event.text_area.text
        if self._save_timer is not None:
            self._save_timer.stop()
        self._save_timer = self.set_timer(2.0, self._do_save)

    def _do_save(self) -> None:
        if self._db is None:
            return
        try:
            from quest.queries import save_persistent_notes

            save_persistent_notes(self._db, self._notes_text_snapshot)
        except Exception:
            logger.exception("Failed to save notes")

    def action_back_to_list(self) -> None:
        try:
            self.app.query_one("#task-list").focus()
        except Exception:
            pass

    def on_unmount(self) -> None:
        if self._save_timer is not None:
            self._save_timer.stop()
            self._save_timer = None
        self._do_save()
