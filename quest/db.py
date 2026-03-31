"""Database connection factory and schema initialization."""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path.home() / ".claude" / "quest" / "data" / "quest.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT,
    size        TEXT    NOT NULL CHECK (size IN ('tiny', 'small', 'medium', 'large', 'epic')),
    status      TEXT    NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'in_progress', 'done', 'snoozed', 'overdue', 'cancelled')),
    xp_value    INTEGER NOT NULL,
    xp_earned   INTEGER DEFAULT 0,
    due_date    TEXT,
    snooze_until TEXT,
    parent_id   INTEGER REFERENCES tasks(id),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS daily_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    log_date        TEXT    NOT NULL UNIQUE,
    tasks_completed INTEGER NOT NULL DEFAULT 0,
    xp_earned       INTEGER NOT NULL DEFAULT 0,
    streak_active   INTEGER NOT NULL DEFAULT 0,
    grace_used      INTEGER NOT NULL DEFAULT 0,
    day_rating      INTEGER CHECK (day_rating BETWEEN 1 AND 5),
    notes           TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS streaks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    current_streak  INTEGER NOT NULL DEFAULT 0,
    longest_streak  INTEGER NOT NULL DEFAULT 0,
    last_active_date TEXT,
    grace_days_used_this_week INTEGER NOT NULL DEFAULT 0,
    grace_week_start TEXT,
    streak_freeze_available INTEGER NOT NULL DEFAULT 1,
    streak_freeze_used_this_month INTEGER NOT NULL DEFAULT 0,
    freeze_month    TEXT,
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_stats (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    total_xp        INTEGER NOT NULL DEFAULT 0,
    current_level   INTEGER NOT NULL DEFAULT 1,
    level_title     TEXT    NOT NULL DEFAULT 'Apprentice',
    tasks_created   INTEGER NOT NULL DEFAULT 0,
    tasks_completed INTEGER NOT NULL DEFAULT 0,
    tasks_cancelled INTEGER NOT NULL DEFAULT 0,
    days_active     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO user_stats (id) VALUES (1);
INSERT OR IGNORE INTO streaks (id) VALUES (1);
"""


def get_db() -> sqlite3.Connection:
    """Return a database connection with WAL mode enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def run_migration(conn: sqlite3.Connection, sql: str) -> None:
    """Apply SQL migration string to the given connection."""
    conn.executescript(sql)
    conn.commit()


MIGRATION_ADD_PRIORITY = """
ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal';
"""


def _apply_incremental_migrations(conn: sqlite3.Connection) -> None:
    """Apply migrations that may not yet exist in the DB."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    if "priority" not in columns:
        conn.execute(
            "ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'"
        )
        conn.commit()
        logger.info("Migration applied: added priority column")

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "persistent_notes" not in tables:
        conn.execute(
            """
            CREATE TABLE persistent_notes (
                id      INTEGER PRIMARY KEY CHECK (id = 1),
                content TEXT    NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute("INSERT INTO persistent_notes (id, content) VALUES (1, '')")
        conn.commit()
        logger.info("Migration applied: created persistent_notes table")


def init_db() -> sqlite3.Connection:
    """Create tables and seed rows. Returns open connection."""
    if not DB_PATH.exists():
        logger.info("Initializing new database at %s", DB_PATH)
    conn = get_db()
    run_migration(conn, SCHEMA_SQL)
    _apply_incremental_migrations(conn)
    return conn


def db_exists() -> bool:
    """Return True if the database file exists."""
    return DB_PATH.exists()
