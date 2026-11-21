"""Middleware счётчика посещаемости.

Стоит как outer middleware на `dp.message` и `dp.callback_query`, поэтому считает любой заход —
сообщение, команду, нажатие кнопки или файл. Учёт не влияет на работу бота:
любая ошибка записи гасится и пишется в лог, обработка события продолжается.
"""
import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from bot.database import Database
from bot.services.visits import record_event

logger = logging.getLogger(__name__)

# Человекочитаемые названия функций для отчёта «Что делали»
CALLBACK_ACTIONS: Dict[str, str] = {
    "search_scope": "🔍 Поиск вакансий",
    "search_period": "🔍 Поиск вакансий",
    "search_more": "🔍 Поиск вакансий (листание)",
    "search_all": "🔍 Поиск вакансий (показать все)",
    "quick_action:search": "🔍 Поиск вакансий",
    "quick_action:adapt": "✨ Адаптация резюме",
    "quick_action:standards": "📐 Стандарты рынка",
    "profile_edit": "✏️ Правка профиля",
    "std_": "📐 Стандарты рынка",
    "src_": "🌐 Источники вакансий",
    "res_": "🧭 Каналы и сайты",
    "search_scope_menu": "🔍 Поиск вакансий",
}

COMMAND_ACTIONS: Dict[str, str] = {
    "/start": "🚀 /start",
    "/help": "📖 /help",
    "/upload_resume": "📤 Загрузить резюме",
    "/search": "🔍 Поиск вакансий",
    "/standards": "📐 Стандарты рынка",
    "/sources": "🌐 Источники вакансий",
    "/add_source": "🌐 Источники вакансий",
    "/find_resources": "🧭 Каналы и сайты",
    "/my_resume": "📄 Моё резюме",
    "/adapt_resume": "✨ Адаптация резюме",
    "/stats": "📊 Статистика",
}


def describe_action(event: TelegramObject) -> str:
    """Определяет, какой функцией пользуется человек (для топа действий)."""
    if isinstance(event, CallbackQuery):
        data = (event.data or "").strip()
        if not data:
            return "🔘 Кнопка"
        for prefix, label in CALLBACK_ACTIONS.items():
            if data == prefix or data.startswith(prefix):
                return label
        return "🔘 Кнопка"

    if isinstance(event, Message):
        text = (event.text or "").strip()
        if event.document or event.photo:
            return "📤 Загрузить резюме (файл)"
        if text.startswith("/"):
            command = text.split("@", 1)[0].split(" ", 1)[0].lower()
            return COMMAND_ACTIONS.get(command, "⌨️ Команда")
        if text in ("📤 Загрузить резюме", "✨ Адаптировать резюме", "📐 Стандарты рынка",
                    "🔍 Поиск вакансий", "🌐 Источники вакансий", "📄 Моё резюме",
                    "🏛 Пример идеального резюме", "🧭 Найти каналы и сайты"):
            return text
        if text:
            return "✍️ Текст (резюме/другое)"
    return "❔ Другое"


class VisitCounterMiddleware(BaseMiddleware):
    """Считает заходы пользователей и действия по функциям."""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        db: Optional[Database] = data.get("db") or self.db
        user = data.get("event_from_user") or getattr(event, "from_user", None)

        if db is not None and user is not None and not getattr(user, "is_bot", False):
            try:
                await record_event(
                    db=db,
                    user_id=int(user.id),
                    action=describe_action(event),
                    username=getattr(user, "username", "") or "",
                )
            except Exception as exc:  # noqa: BLE001 — счётчик не должен ломать бота
                logger.warning("Не удалось записать посещение: %r", exc)

        return await handler(event, data)


def _extract_event(event: TelegramObject) -> TelegramObject:
    """Достаёт Message/CallbackQuery из Update (если middleware навешен на Update)."""
    if isinstance(event, Update):
        return event.message or event.callback_query or event  # type: ignore[return-value]
    return event
