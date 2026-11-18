"""Безопасная отправка сообщений с Markdown-разметкой.

Telegram отклоняет сообщение целиком, если в нём есть незакрытая сущность
(`Bad Request: can't find end of the entity starting at byte offset N`).
Причин две: обрезка текста по символам и «сырые» `[`, `*`, `_`, `` ` `` из
названий каналов. Здесь собраны помощники, которые:
1) режут длинный текст по границам строк (`split_message`);
2) при ошибке разметки повторяют отправку тем же текстом без `parse_mode`,
   поэтому пользователь всё равно получает результат, а бот не падает.
"""
from typing import Any, Optional

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from bot.services.message_utils import (
    has_broken_entities,
    split_message,
    strip_markup,
)


def _is_entity_error(exc: Exception) -> bool:
    """Ошибка именно про незакрытую сущность разметки (а не любая 400)."""
    text = str(exc).lower()
    return "entity" in text or "can't parse entities" in text or "can't find end" in text


def prepare_text(text: str, parse_mode: Optional[str]) -> Any:
    """Готовит текст к отправке: при незакрытой разметке сразу снимает её.

    Так бот не доходит до ошибки Telegram «can't find end of the entity»: если в
    тексте осталась «половинка» сущности (например, из названия канала вида
    «[топ вакансии]» или из команды `/find_resources`), сообщение уходит обычным
    текстом. Лучше потерять жирный шрифт, чем не отправить результат вовсе.
    """
    if parse_mode and has_broken_entities(text):
        return strip_markup(text), None
    return text, parse_mode


async def safe_edit_text(text: str, message: Message, **kwargs: Any) -> Optional[Message]:
    """`message.edit_text` с автоматическим откатом на текст без разметки."""
    text, kwargs["parse_mode"] = prepare_text(text, kwargs.get("parse_mode"))
    try:
        return await message.edit_text(text, **kwargs)
    except TelegramBadRequest as exc:
        if not _is_entity_error(exc):
            raise
        retry_kwargs = dict(kwargs)
        retry_kwargs["parse_mode"] = None
        return await message.edit_text(strip_markup(text), **retry_kwargs)


async def safe_answer(text: str, message: Message, **kwargs: Any) -> Optional[Message]:
    """`message.answer` с автоматическим откатом на текст без разметки."""
    text, kwargs["parse_mode"] = prepare_text(text, kwargs.get("parse_mode"))
    try:
        return await message.answer(text, **kwargs)
    except TelegramBadRequest as exc:
        if not _is_entity_error(exc):
            raise
        retry_kwargs = dict(kwargs)
        retry_kwargs["parse_mode"] = None
        return await message.answer(strip_markup(text), **retry_kwargs)


async def send_long_message(
    text: str,
    first_message: Message,
    *,
    limit: int = 3900,
    parse_mode: str = "Markdown",
    keyboard_on_last: Any = None,
    **kwargs: Any,
) -> None:
    """Первую часть пишет в `first_message` (edit), остальные — новыми сообщениями.

    Клавиатура (если передана) крепится к последнему сообщению, чтобы кнопки
    всегда были под рукой у пользователя.
    """
    chunks = split_message(text, limit=limit) or [""]
    await safe_edit_text(chunks[0], first_message, parse_mode=parse_mode, **kwargs)
    for index, chunk in enumerate(chunks[1:], start=2):
        is_last = index == len(chunks)
        await safe_answer(
            chunk,
            first_message,
            parse_mode=parse_mode,
            reply_markup=keyboard_on_last if is_last else None,
            **kwargs,
        )
