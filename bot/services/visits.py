"""Счётчик посещаемости бота: учёт заходов и сводная статистика.

Как считается
-------------
* **Заход** — любое событие от пользователя (сообщение, команда, нажатие кнопки).
  В таблице ``visits`` на каждую пару «пользователь + календарная дата» хранится
  количество событий (``events``) и время первого/последнего захода.
* **Уникальный пользователь за день** — одна строка ``visits`` за эту дату.
* **Новый пользователь** — тот, у кого самый ранний заход приходится на этот день.
* **Действия по функциям** — таблица ``visit_actions``: «🔍 Поиск вакансий», «📤 Загрузить
  резюме» и т.д. (название функции + дата + количество).

Календарные даты считаются в часовом поясе отчёта (``STATS_TZ``, по умолчанию
``Europe/Moscow``), а не в UTC — иначе «сегодня» в Москве и в логах не совпадает.
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bot.database import Database

DEFAULT_TZ = "Europe/Moscow"
DEFAULT_PERIOD_DAYS = 14


def stats_timezone(name: Optional[str] = None) -> ZoneInfo:
    """Часовой пояс отчёта: ``STATS_TZ`` → ``Europe/Moscow`` → UTC."""
    import os

    candidate = (name or os.getenv("STATS_TZ") or DEFAULT_TZ).strip()
    try:
        return ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def today_in_tz(tz: Optional[ZoneInfo] = None) -> date:
    """Сегодняшняя дата в часовом поясе отчёта."""
    return datetime.now(tz or stats_timezone()).date()


def _plural(number: int, one: str, few: str, many: str) -> str:
    """Русская форма слова для числа: 1 заход, 2 захода, 5 заходов."""
    number = abs(int(number))
    if number % 10 == 1 and number % 100 != 11:
        return one
    if number % 10 in (2, 3, 4) and number % 100 not in (12, 13, 14):
        return few
    return many


def format_number(value: int) -> str:
    """1234 → «1 234» (неразрывные пробелы не нужны, обычный пробел читаемее)."""
    return f"{int(value):,}".replace(",", " ")


async def record_event(
    db: Database,
    user_id: int,
    action: str = "",
    username: str = "",
    tz: Optional[ZoneInfo] = None,
) -> None:
    """Учитывает один заход пользователя и (если задано) действие по функции."""
    zone = tz or stats_timezone()
    now = datetime.now(zone)
    visit_date = now.date().isoformat()
    timestamp = now.isoformat(timespec="seconds")
    await db.record_visit(
        user_id=int(user_id),
        visit_date=visit_date,
        timestamp=timestamp,
        username=username or "",
        action=action,
    )


async def collect_visit_stats(
    db: Database,
    days: int = DEFAULT_PERIOD_DAYS,
    tz: Optional[ZoneInfo] = None,
) -> Dict[str, Any]:
    """Собирает сводку по посещаемости: итоги, сегодня/вчера, серия по дням, топ функций."""
    zone = tz or stats_timezone()
    today = today_in_tz(zone)
    days = max(1, min(int(days or DEFAULT_PERIOD_DAYS), 90))

    first_day = today - timedelta(days=max(days, 30) - 1)
    rows = await db.get_visits_rows(since_date=first_day.isoformat())
    first_seen_rows = await db.get_first_seen_dates()
    action_rows = await db.get_visit_action_rows(since_date=(today - timedelta(days=6)).isoformat())

    # user_id → дата первого захода (для подсчёта новых пользователей)
    first_seen: Dict[int, str] = {int(row[0]): str(row[1]) for row in first_seen_rows}

    daily: Dict[str, Dict[str, Any]] = {}
    for user_id, visit_date, events, _first_at, _last_at, _username in rows:
        bucket = daily.setdefault(str(visit_date), {"users": set(), "events": 0})
        bucket["users"].add(int(user_id))
        bucket["events"] += int(events or 0)

    def unique_users(period_days: int) -> int:
        since = (today - timedelta(days=period_days - 1)).isoformat()
        return len(
            {
                int(user_id)
                for user_id, visit_date, _events, *_rest in rows
                if str(visit_date) >= since
            }
        )

    def new_users(period_days: int) -> int:
        since = (today - timedelta(days=period_days - 1)).isoformat()
        return sum(1 for first_date in first_seen.values() if first_date >= since)

    def events_sum(period_days: int) -> int:
        since = (today - timedelta(days=period_days - 1)).isoformat()
        return sum(bucket["events"] for day, bucket in daily.items() if day >= since)

    series: List[Tuple[date, int, int]] = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        bucket = daily.get(day.isoformat())
        series.append(
            (day, len(bucket["users"]) if bucket else 0, bucket["events"] if bucket else 0)
        )

    last_7 = [users for _day, users, _events in series[-7:]]
    average_7 = (sum(last_7) / len(last_7)) if last_7 else 0.0

    return {
        "today": today,
        "timezone": str(zone),
        "days": days,
        "users_total": len(first_seen),
        "new_today": new_users(1),
        "new_7": new_users(7),
        "new_30": new_users(30),
        "active_today": len(daily.get(today.isoformat(), {}).get("users", set())),
        "active_yesterday": len(
            daily.get((today - timedelta(days=1)).isoformat(), {}).get("users", set())
        ),
        "active_7": unique_users(7),
        "active_30": unique_users(30),
        "average_7": average_7,
        "events_today": daily.get(today.isoformat(), {}).get("events", 0),
        "events_7": events_sum(7),
        "events_all": sum(bucket["events"] for bucket in daily.values()),
        "series": series,
        "top_actions": [(str(action), int(total or 0)) for action, total in action_rows[:8]],
    }


def _sparkline(values: List[int]) -> str:
    """Мини-график для ряда чисел: ▁▂▃▄▅▆▇█ (одна палочка на день)."""
    blocks = "▁▂▃▄▅▆▇█"
    peak = max(values) if values else 0
    if peak <= 0:
        return blocks[0] * len(values)
    return "".join(blocks[min(len(blocks) - 1, round(value / peak * (len(blocks) - 1)))] for value in values)


def _bar(value: int, peak: int, width: int = 12) -> str:
    """Текстовая гистограмма в одну строку."""
    if peak <= 0 or value <= 0:
        return ""
    filled = max(1, round(value / peak * width))
    return "█" * filled


def format_visit_stats(stats: Dict[str, Any]) -> str:
    """Текст отчёта для Telegram (Markdown)."""
    series = stats.get("series") or []
    peak = max((users for _day, users, _events in series), default=0)
    spark = _sparkline([users for _day, users, _events in series])

    lines: List[str] = [
        "📊 **Статистика посещаемости бота**",
        f"_Часовой пояс отчёта: {stats.get('timezone')} · период графика: {stats.get('days')} дн._",
        "",
        "👥 **Пользователи**",
        f"• Всего заходило: **{format_number(stats.get('users_total', 0))}**",
        f"• Новых сегодня: **{stats.get('new_today', 0)}** · за 7 дней: **{stats.get('new_7', 0)}** · за 30 дней: **{stats.get('new_30', 0)}**",
        "",
        "🔥 **Активность**",
        f"• Сегодня: **{stats.get('active_today', 0)}** "
        f"{_plural(stats.get('active_today', 0), 'человек', 'человека', 'человек')} "
        f"· вчера: **{stats.get('active_yesterday', 0)}** · в среднем за 7 дней: **{stats.get('average_7', 0):.1f}**",
        f"• Уникальных за 7 дней: **{stats.get('active_7', 0)}** · за 30 дней: **{stats.get('active_30', 0)}**",
        "",
        "💬 **Действия**",
        f"• Сегодня: **{format_number(stats.get('events_today', 0))}** · за 7 дней: **{format_number(stats.get('events_7', 0))}**",
        "",
        f"📈 **Активность по дням** (уникальных пользователей за день):",
        f"`{spark}`",
    ]

    for day, users, events in series[-int(stats.get("days") or 14):]:
        bar = _bar(users, peak)
        lines.append(f"`{day.strftime('%d.%m')}` {bar:<12} {users:>3} · {events} действий")

    top_actions = stats.get("top_actions") or []
    if top_actions:
        lines.extend(["", "🧭 **Что делали за 7 дней**"])
        for index, (action, total) in enumerate(top_actions, start=1):
            lines.append(f"{index}. {action} — **{format_number(total)}**")
    else:
        lines.extend(["", "🧭 _Статистики по функциям пока нет._"])

    return "\n".join(line for line in lines if line is not None).strip()
