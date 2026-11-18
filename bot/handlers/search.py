"""Обработчики поиска и парсинга вакансий по резюме за выбранный период:
- 1 день (24 часа)
- 1 неделя (7 дней)
- 1 месяц (30 дней)
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from bot.database import Database
from bot.keyboards import get_search_period_keyboard
from bot.services.vacancy_parser import (
    format_vacancies_search_blocks,
    search_vacancies_by_resume,
)

router = Router(name="search")


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
        body, footer = format_vacancies_search_blocks(search_result)

        if len(body) + len(footer) <= 4000:
            await status_msg.edit_text(
                f"{body}\n{footer}",
                reply_markup=get_search_period_keyboard(),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        else:
            # Длинный список: отправляем основную часть и отдельно подвал,
            # чтобы предупреждения и дисклеймер не обрезались.
            # Обрезаем по границе вакансии, чтобы не рвать карточку посередине
            cut = body[:3900]
            boundary = cut.rfind("\n\n**")
            if boundary > 1000:
                cut = cut[:boundary]
            await status_msg.edit_text(
                cut + "\n…",
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            await callback.message.answer(
                footer.strip()[:4000],
                reply_markup=get_search_period_keyboard(),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
    except ValueError as exc:
        await status_msg.edit_text(f"⚠️ {exc}")
    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка при поиске вакансий: {exc}")
