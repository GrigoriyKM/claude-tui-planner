# CLI-интерфейс

Click-приложение для всех операций с задачами. Все ответы — JSON в stdout.

## Ключевые компоненты

- `scripts/quest_cli.py` — точка входа CLI

## Команды

| Команда | Описание |
|---------|---------|
| `init` | Создаёт БД и схему |
| `status` | Статистика, задачи на сегодня, стрик, XP-бар |
| `add --title --size [--due --parent-id --description]` | Добавить задачу |
| `complete <id>` | Выполнить задачу, начислить XP |
| `snooze <id> --until YYYY-MM-DD` | Отложить задачу |
| `cancel <id>` | Отменить задачу |
| `list [--status] [--limit]` | Список задач |
| `search <query>` | Поиск по названию (LIKE) |
| `overdue` | Просроченные задачи |
| `reconcile` | Ежедневная сверка стрика |
| `log [--date --rating --notes]` | Запись итогов дня |

## Запуск

```bash
cd ~/.claude/quest && uv run python scripts/quest_cli.py <command>
```

## Поток данных

1. Команда вызывает `_require_db()` → открывает БД или завершается с ошибкой
2. Делегирует в `quest/queries.py` или `quest/streaks.py`
3. Сериализует результат через `_output(dict)` → `json.dumps` → stdout

## Формат ошибок

```json
{"error": "Task 42 not found"}
```

Exit code 1 при ошибках. Успешные команды всегда содержат `"status": "ok"`.
