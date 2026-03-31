# Quest

Gamified task management for Claude Code. Turns daily work into XP, levels, and streaks.

```
Level 1 Apprentice · 🔥 2 days · XP: 250 / 348
[█████████████████░░░░░░░]
```

---

## Overview

Quest consists of three layers:

- **`quest/`** — Python domain library (XP math, streak logic, SQLite queries)
- **`scripts/quest_cli.py`** — JSON-output CLI, driven by Claude Code via the `/quest` skill
- **`tui/`** — Interactive terminal UI built with Textual

Storage: SQLite at `~/.claude/quest/data/quest.db` (WAL mode).

---

## Quick Start

```bash
# Initialize the database
uv run python scripts/quest_cli.py init

# Check status
uv run python scripts/quest_cli.py status

# Add a task
uv run python scripts/quest_cli.py add --title "Write tests" --size medium

# Complete a task
uv run python scripts/quest_cli.py complete 1

# Launch TUI
uv run python -m tui
```

---

## CLI Commands

All commands output JSON.

| Command | Description |
|---------|-------------|
| `init` | Initialize the database |
| `status` | User stats, today's tasks, streak, overdue count |
| `add --title "..." --size <size> [--due YYYY-MM-DD] [--parent-id N] [--description "..."] [--priority <p>]` | Create a task |
| `complete <id>` | Mark done, award XP |
| `snooze <id> --until YYYY-MM-DD` | Hide task until date |
| `cancel <id>` | Cancel task (0 XP) |
| `list [--status <s>] [--limit N]` | List tasks with optional status filter |
| `search <query>` | Search tasks by title |
| `overdue` | List overdue tasks |
| `done-today` | List tasks completed today |
| `reconcile` | Daily maintenance: streak check, grace days, overdue marking, snooze awakening |
| `log [--date YYYY-MM-DD] [--rating 1-5] [--notes "..."]` | Add/update daily log entry |

### Task Sizes

| Size | XP |
|------|----|
| tiny | 25 |
| small | 50 |
| medium | 150 |
| large | 400 |
| epic | 1000 |

### Task Priorities

`low` · `normal` (default) · `high` · `urgent`

---

## XP & Levels

Level formula: `floor(100 × n^1.8)`

| Level | XP Required | Title |
|-------|-------------|-------|
| 1 | 100 | Apprentice |
| 6 | 1,551 | Journeyman |
| 11 | 5,179 | Craftsman |
| 21 | 17,429 | Expert |
| 31 | 40,132 | Master |
| 51+ | — | Grandmaster |

### Streak Bonuses

Completing at least one task per day builds a streak and multiplies XP:

| Streak | Bonus |
|--------|-------|
| 3+ days | +5% |
| 7+ days | +10% |
| 14+ days | +15% |
| 30+ days | +25% |

Streak resets lose the multiplier — never earned XP.

### Grace Days

1 grace day per calendar week. Skipping a day without a task uses the grace day automatically (streak preserved). When no grace day is available, the streak resets.

---

## TUI

```bash
uv run python -m tui
```

### Key Bindings

| Key | Action |
|-----|--------|
| `j` / `k` | Move down / up |
| `g` / `G` | Jump to top / bottom |
| `Enter` / `Space` | Complete task (or uncomplete if done) |
| `Tab` / `l` | Cycle filter forward: all → today → overdue → snoozed → done |
| `h` | Cycle filter backward |
| `[` | (In done view) cycle archive range: today → week → month → all |
| `d` | Delete task |
| `z` | Snooze task (pick resume date) |
| `i` | Inspect task details |
| `r` | Refresh |
| `q` | Quit |

---

## Claude Code Skill

Quest is designed to be used via `/quest` in Claude Code. The skill at `.claude/quest/SKILL.md` tells Claude how to:

- Run `reconcile` + `status` on every invocation
- Break user tasks into sized subtasks before adding
- Match "я сделал X" → `search` → `complete`
- Handle snooze with absolute date conversion
- Show end-of-day summary via `done-today` + `log --rating`

---

## Architecture

```
quest/
├── db.py          # Connection factory, schema, migrations
├── models.py      # Task, DailyLog, StreakState, UserStats (frozen dataclasses)
├── xp.py          # XP values, level formula, streak multipliers
├── streaks.py     # record_activity(), reconcile_day(), grace logic
├── queries.py     # All SQL operations
└── formatting.py  # progress_bar(), sparkline(), format_status_line()
```

### `reconcile_day()` — what it does on each `/quest` call

1. Awaken snoozed tasks where `snooze_until <= today`
2. Mark pending tasks with past `due_date` as `overdue`
3. If yesterday had no activity: use grace day or reset streak

---

## Development

```bash
uv sync          # install dependencies
uv run pytest    # run tests
```
