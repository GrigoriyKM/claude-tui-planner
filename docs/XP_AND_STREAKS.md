# XP и стрики

Система геймификации: прогрессия уровней, стрик-бонусы, grace days.

## Ключевые компоненты

- `quest/xp.py` — XP-значения, уровни, streak multiplier
- `quest/streaks.py` — ежедневная сверка, grace days, сброс стрика

## Уровни

Формула: `xp_for_level(n) = floor(100 × n^1.8)`

| Диапазон уровней | Титул |
|-----------------|-------|
| 1–5 | Apprentice |
| 6–10 | Journeyman |
| 11–20 | Craftsman |
| 21–30 | Expert |
| 31–50 | Master |
| 51+ | Grandmaster |

## Streak-бонусы

Бонус добавляется к XP за выполненную задачу:

| Стрик | Бонус |
|-------|-------|
| ≥ 30 дней | +25% |
| ≥ 14 дней | +15% |
| ≥ 7 дней | +10% |
| ≥ 3 дней | +5% |

`calculate_xp(size, streak_days)` возвращает `(base_xp, bonus_xp, total_xp)`.

## Ежедневная сверка (`reconcile_day`)

Вызывается при каждом старте `/quest`:

1. Помечает просроченные задачи (`pending` + `due_date < today` → `overdue`)
2. Если вчера был активен → стрик сохранён
3. Если вчера не было активности и есть grace day → использует grace, стрик сохранён
4. Если grace нет → сбрасывает стрик (XP не теряется!)

**Grace days:** 1 день в неделю, сбрасывается каждый понедельник.

## Поток данных

1. `reconcile_day(db, today)` → определяет действие (`none` / `grace_used` / `streak_reset`)
2. `complete_task(db, id)` → `calculate_xp` → `record_activity` → обновляет стрик и XP
