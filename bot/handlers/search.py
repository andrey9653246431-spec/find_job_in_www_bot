"""Обработчики поиска и парсинга вакансий по резюме за выбранный период:
- 1 день (24 часа)
- 1 неделя (7 дней)
- 1 месяц (30 дней)
"""
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from bot.database import Database
from bot.config import config
from bot.handlers.messaging import safe_answer, safe_edit_text
from bot.keyboards import get_search_period_keyboard, get_search_results_keyboard
from bot.services.message_utils import MAX_MESSAGE_LENGTH, split_message
from bot.services.search_sessions import get_search_result, store_search_result, total_items
from bot.services.vacancy_parser import (
    format_vacancies_search_blocks,
    search_vacancies_by_resume,
)

router = Router(name="search")

# «Показать все» отдаёт остаток пачками не более этого числа вакансий:
# защита от 20+ сообщений подряд в чате.
MAX_BULK_PAGE = 200


async def _render_search_page(
    message: Message,
    result: dict,
    offset: int,
    limit: Optional[int] = None,
    first_message: Optional[Message] = None,
) -> None:
    """Показывает страницу выдачи (offset/limit) с кнопками листания.

    Если передан ``first_message``, первая часть пишется в него (edit),
    иначе все части отправляются новыми сообщениями.
    """
    total = total_items(result)
    page_size = int(result.get("page_size") or config.max_vacancies_per_message)
    limit = page_size if limit is None else max(1, limit)
    offset = max(0, min(offset, total))

    body, footer = format_vacancies_search_blocks(result, offset=offset, limit=limit)
    combined = f"{body}\n{footer}".strip()
    shown = min(offset + limit, total)

    keyboard = get_search_results_keyboard(shown=shown, total=total, page_size=page_size)
    chunks = split_message(combined, limit=MAX_MESSAGE_LENGTH) or [combined]

    for index, chunk in enumerate(chunks, start=1):
        is_last = index == len(chunks)
        reply_markup = keyboard if is_last else None
        if index == 1 and first_message is not None:
            await safe_edit_text(
                chunk,
                first_message,
                reply_markup=reply_markup,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        else:
            await safe_answer(
                chunk,
                message,
                reply_markup=reply_markup,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )


async def _prompt_search_period(message: Message, user_id: int, db: Database) -> None:
    """Проверяет наличие резюме и предлагает выбрать период поиска (1 день, 1 неделя, 1 месяц)."""
    resume = await db.get_resume(user_id)
    if not resume:
        await message.answer(
            "⚠️ **Сначала необходимо загрузить резюме!**\n\n"
            "Нажмите **📤 Загрузить резюме**, отправьте файл (`PDF`, `DOCX`, `TXT`) или текст, "
            "после чего я смогу искать подходящие вакансии по вашему профилю.",
            parse_mode="Markdown",
        )
        return

    sources = await db.list_sources(active_only=True)
    skills = ", ".join(resume.get("extracted_skills") or []) or "общий профиль"

    await message.answer(
        "🔍 **Поиск вакансий по вашему резюме**\n\n"
        f"🎯 **Целевая должность:** {resume.get('extracted_role')}\n"
        f"🛠 **Ключевые навыки для поиска:** {skills}\n"
        f"📡 **Активных источников в базе (ТГ-каналы и сайты):** {len(sources)}\n\n"
        "👇 **Выберите период, за который нужно спарсить и найти вакансии:**",
        reply_markup=get_search_period_keyboard(),
        parse_mode="Markdown",
    )


@router.message(Command("search"))
@router.message(F.text == "🔍 Поиск вакансий")
async def cmd_search_vacancies(message: Message, db: Database) -> None:
    """Команда /search или кнопка «🔍 Поиск вакансий»."""
    await _prompt_search_period(
        message=message,
        user_id=message.from_user.id,  # type: ignore
        db=db,
    )


@router.callback_query(F.data == "quick_action:search")
async def cb_quick_search_vacancies(callback: CallbackQuery, db: Database) -> None:
    """Открытие выбора периода поиска после загрузки резюме."""
    await callback.answer()
    if callback.message:
        await _prompt_search_period(
            message=callback.message,  # type: ignore
            user_id=callback.from_user.id,
            db=db,
        )


@router.callback_query(F.data.startswith("search_period:"))
async def cb_execute_search_by_period(
    callback: CallbackQuery, db: Database
) -> None:
    """Запускает парсинг всех ТГ-каналов и сайтов из БД за выбранный период (1, 7 или 30 дней)."""
    await callback.answer()
    raw_period = (callback.data or "search_period:7").split(":", 1)[1]
    try:
        period_days = int(raw_period)
    except ValueError:
        period_days = 7

    if not callback.message:
        return

    period_names = {1: "1 день", 7: "1 неделю", 30: "1 месяц"}
    p_label = period_names.get(period_days, f"{period_days} дн.")

    status_msg = await callback.message.answer(
        f"⏳ **Запускаю парсинг ТГ-каналов и сайтов из базы данных за {p_label}...**\n"
        "_Это может занять несколько секунд._",
        parse_mode="Markdown",
    )

    try:
        search_result = await search_vacancies_by_resume(
            db=db,
            user_id=callback.from_user.id,
            period_days=period_days,
        )
        # Кладём полный список в память: «Показать ещё» не запускает парсинг заново
        store_search_result(callback.from_user.id, search_result)

        # Длинный список режется ТОЛЬКО по границам строк (split_message),
        # иначе Telegram отвечает «can't find end of the entity» на обрезанном
        # посередине `**жирном**` или `[ссылке](url)`.
        await _render_search_page(
            message=status_msg,
            result=search_result,
            offset=0,
            first_message=status_msg,
        )
    except ValueError as exc:
        await status_msg.edit_text(f"⚠️ {exc}")
    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка при поиске вакансий: {exc}")


@router.callback_query(F.data.startswith("search_more:"))
async def cb_show_more_vacancies(callback: CallbackQuery) -> None:
    """Показывает следующие 10 вакансий из уже найденного списка (без нового парсинга)."""
    if not callback.message:
        await callback.answer()
        return
    await callback.answer()

    result = get_search_result(callback.from_user.id)
    if not result:
        await safe_answer(
            "⚠️ **Результаты поиска устарели.**\n"
            "Запустите поиск заново: /search → выберите период.",
            callback.message,  # type: ignore[arg-type]
            parse_mode="Markdown",
        )
        return

    try:
        offset = int((callback.data or "search_more:0").split(":", 1)[1])
    except (ValueError, IndexError):
        offset = 0

    total = total_items(result)
    if offset >= total:
        await callback.answer("Больше вакансий нет", show_alert=False)
        return

    await _render_search_page(
        message=callback.message,  # type: ignore[arg-type]
        result=result,
        offset=offset,
    )


@router.callback_query(F.data.startswith("search_all:"))
async def cb_show_all_vacancies(callback: CallbackQuery) -> None:
    """Показывает сразу весь остаток выдачи (не более MAX_BULK_PAGE вакансий за нажатие)."""
    if not callback.message:
        await callback.answer()
        return
    await callback.answer()

    result = get_search_result(callback.from_user.id)
    if not result:
        await safe_answer(
            "⚠️ **Результаты поиска устарели.**\n"
            "Запустите поиск заново: /search → выберите период.",
            callback.message,  # type: ignore[arg-type]
            parse_mode="Markdown",
        )
        return

    try:
        offset = int((callback.data or "search_all:0").split(":", 1)[1])
    except (ValueError, IndexError):
        offset = 0

    total = total_items(result)
    if offset >= total:
        await callback.answer("Больше вакансий нет", show_alert=False)
        return

    await _render_search_page(
        message=callback.message,  # type: ignore[arg-type]
        result=result,
        offset=offset,
        limit=min(total - offset, MAX_BULK_PAGE),
    )
