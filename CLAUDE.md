# Quest

Gamified task management for Claude Code. Turns daily work into XP, levels, and streaks.
Состоит из Python-библиотеки (`quest/`), CLI на Click (`scripts/`) и TUI на Textual (`tui/`).
Хранилище — SQLite с WAL-режимом по пути `~/.claude/quest/data/quest.db`.

---

## Rules

- Always use Context7 MCP for library/API documentation, code generation, setup and configuration steps.

---

## Запуск

```bash
# Инициализация БД
uv run python scripts/quest_cli.py init

# CLI-команды
uv run python scripts/quest_cli.py status
uv run python scripts/quest_cli.py add --title "Task" --size small
uv run python scripts/quest_cli.py complete <id>

# TUI
uv run python -m tui

# Тесты
uv run pytest

# Зависимости
uv sync
```

---

## Навигация

- Точка входа CLI: `scripts/quest_cli.py` — все команды управления задачами
- Точка входа TUI: `tui/__main__.py` — интерактивный терминальный интерфейс
- Домен: `quest/` — читай при работе с XP, стриками, запросами к БД
- Экраны TUI: `tui/screens/` — читай при добавлении модальных диалогов
- Виджеты: `tui/widgets/` — читай при изменении отображения в TUI
- Тесты: `tests/` — читай при добавлении новых тестов
- Конфиг: `config.toml`, `pyproject.toml`

---

## Документация

| Файл | Описание |
|------|---------|
| [docs/MODELS.md](docs/MODELS.md) | Доменные модели: Task, DailyLog, StreakState, UserStats |
| [docs/DATABASE.md](docs/DATABASE.md) | Схема SQLite, инициализация, WAL-режим, миграции |
| [docs/XP_AND_STREAKS.md](docs/XP_AND_STREAKS.md) | Формулы XP, уровни, стрик-бонусы, grace days |
| [docs/CLI.md](docs/CLI.md) | Все CLI-команды и формат JSON-ответов |
| [docs/TUI.md](docs/TUI.md) | Textual-приложение, экраны, горячие клавиши, панель заметок |

---

## Project Structure

```
/home/goryn/.claude/quest
├── data
│   ├── quest.db
│   ├── quest.db-shm
│   └── quest.db-wal
├── quest
│   ├── db.py
│   ├── formatting.py
│   ├── __init__.py
│   ├── models.py
│   ├── queries.py
│   ├── streaks.py
│   └── xp.py
├── scripts
│   └── quest_cli.py
├── tui
│   ├── widgets
│   │   ├── __init__.py
│   │   ├── stats_panel.py
│   │   └── task_list.py
│   ├── app.py
│   ├── __init__.py
│   ├── install_alias.py
│   └── __main__.py
├── config.toml
├── pyproject.toml
├── SKILL.md
└── uv.lock

6 directories, 22 files
```
