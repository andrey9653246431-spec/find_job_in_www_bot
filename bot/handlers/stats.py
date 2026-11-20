"""Статистика посещаемости бота: команда /stats.

Показывает: сколько всего пользователей, новые за сегодня/7/30 дней, активных
сегодня/вчера/за 7 и 30 дней, количество действий, график по дням и топ функций.

Доступ: если задан ``ADMIN_IDS`` — только этим ID, иначе команда открыта всем.
"""
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import is_stats_admin
from bot.database import Database
from bot.services.message_utils import split_message
from bot.services.visits import collect_visit_stats, format_visit_stats

router = Router(name="stats")

DEFAULT_DAYS = 14
MAX_DAYS = 90


def _parse_days(raw: Optional[str]) -> int:
    """Период графика из аргументов команды: /stats 30 → 30 дней."""
    if not raw:
        return DEFAULT_DAYS
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return DEFAULT_DAYS
    return max(1, min(int(digits), MAX_DAYS))


async def _send_stats(message: Message, db: Database, days: int) -> None:
    """Собирает и отправляет отчёт по посещаемости."""
    stats = await collect_visit_stats(db=db, days=days)
    text = format_visit_stats(stats)
    chunks = split_message(text, limit=3800) or [text]
    for chunk in chunks:
        await message.answer(chunk, parse_mode="Markdown", disable_web_page_preview=True)


@router.message(Command("stats", "visit_stats", "statistics"))
async def cmd_visit_stats(message: Message, db: Database) -> None:
    """Отчёт по посещаемости: /stats [дней] (по умолчанию 14)."""
    if not is_stats_admin(message.from_user.id):  # type: ignore[union-attr]
        await message.answer(
            "⛔️ **Статистика доступна только администратору бота.**\n\n"
            "ID администраторов задаётся переменной `ADMIN_IDS` в `.env` / секретах репозитория.",
            parse_mode="Markdown",
        )
        return

    raw = (message.text or "").split(maxsplit=1)
    days = _parse_days(raw[1] if len(raw) > 1 else None)
    await _send_stats(message, db, days)


@router.callback_query(F.data == "stats:refresh")
async def cb_refresh_stats(callback: CallbackQuery, db: Database) -> None:
    """Обновление отчёта по кнопке «🔄 Обновить»."""
    if not is_stats_admin(callback.from_user.id):
        await callback.answer("Только для администратора", show_alert=True)
        return

    await callback.answer("Обновляю статистику…")
    if callback.message:
        await _send_stats(callback.message, db, DEFAULT_DAYS)  # type: ignore[arg-type]
