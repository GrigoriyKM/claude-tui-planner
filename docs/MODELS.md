# Модели данных

Слой доменных объектов Quest — неизменяемые dataclass'ы, отображающие строки БД.

## Ключевые компоненты

- `quest/models.py` — все четыре модели

## Модели

| Модель | Таблица | Назначение |
|--------|---------|-----------|
| `Task` | `tasks` | Задача с размером, статусом, XP и датами |
| `DailyLog` | `daily_logs` | Итог дня: выполнено задач, XP, стрик |
| `StreakState` | `streaks` | Текущий стрик, grace days, freeze |
| `UserStats` | `user_stats` | Уровень, суммарный XP, счётчики задач |

Все модели — `@dataclass(frozen=True)`: объекты неизменяемы после создания.

## Поток данных

1. SQLite-запрос возвращает `sqlite3.Row`
2. `Model.from_row(row)` конвертирует в frozen dataclass
3. `model.to_dict()` сериализует для JSON-вывода CLI

## Статусы задачи

`pending` → `in_progress` → `done`
`pending` → `snoozed` → `pending`
`pending` / `in_progress` → `overdue`
Любой → `cancelled`

## Размеры задачи и XP

| Размер | XP |
|--------|-----|
| tiny | 25 |
| small | 50 |
| medium | 150 |
| large | 400 |
| epic | 1000 |
