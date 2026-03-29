# TUI-интерфейс

Textual-приложение для интерактивной работы с задачами в терминале.

## Ключевые компоненты

- `tui/app.py` — главное приложение `QuestApp`
- `tui/widgets/stats_panel.py` — панель статистики
- `tui/widgets/task_list.py` — список задач с навигацией
- `tui/__main__.py` — точка входа для `python -m tui`

## Раскладка экрана

```
┌─────────────────────────────────────────┐
│ StatsPanel: Level · 🔥 streak · XP bar  │
│ Filter bar: all | today | overdue | done│
│                                         │
│ TaskListWidget (прокручиваемый список)  │
│   TODAY                                 │
│   [ ] Task A   small   50 XP            │
│ > [ ] Task B   medium  150 XP           │
│                                         │
│ Footer (горячие клавиши)                │
└─────────────────────────────────────────┘
```

## Горячие клавиши

| Клавиша | Действие |
|---------|---------|
| j / ↓ | Вниз по списку |
| k / ↑ | Вверх по списку |
| Enter / Space | Выполнить / отменить выполнение |
| g / G | Первая / последняя задача |
| f | Сменить фильтр (all→today→overdue→done) |
| r | Обновить данные из БД |
| ? | Справка |
| q | Закрыть справку / выйти |

## Поток данных

1. `on_mount` → `_open_db()` → `_load_all()`
2. `_load_all()` читает задачи из БД, обновляет `StatsPanel` и `TaskListWidget`
3. `action_toggle_task()` → `complete_task()` / `_uncomplete_task()` → `_load_all()`

## Запуск

```bash
cd ~/.claude/quest && uv run python -m tui
```
