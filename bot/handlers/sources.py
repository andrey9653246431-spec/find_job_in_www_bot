"""Обработчики управления источниками вакансий (сайты и Telegram-каналы).

Реализует требование ТЗ:
- Добавление в список источников вакансий сайтов и ссылок на ТГ-каналы.
- Если источник уже есть в базе — бот сообщает об этом пользователю.
- Если источник новый — бот добавляет его в свою базу данных и сообщает, что новый источник добавлен.
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.database import Database
from bot.keyboards import get_sources_keyboard
from bot.services.source_manager import register_source_in_db
from bot.states import SourceStates

router = Router(name="sources")


async def _format_sources_list(db: Database) -> str:
    """Формирует текстовый список всех источников вакансий в БД."""
    sources = await db.list_sources(active_only=True)
    if not sources:
        return "В базе данных пока нет активных источников вакансий."

    tg_list = [s for s in sources if s.get("source_type") == "tg_channel"]
    web_list = [s for s in sources if s.get("source_type") != "tg_channel"]

    lines = [
        f"🌐 **База информационных ресурсов для поиска вакансий (всего: {len(sources)})**\n"
    ]
    if tg_list:
        lines.append("📢 **Telegram-каналы:**")
        for idx, s in enumerate(tg_list, start=1):
            lines.append(f"  {idx}. {s['title']} — `{s['canonical_url']}`")
        lines.append("")

    if web_list:
        lines.append("🌍 **Сайты и интернет-ресурсы:**")
        for idx, s in enumerate(web_list, start=1):
            lines.append(f"  {idx}. {s['title']} — `{s['canonical_url']}`")

    return "\n".join(lines)


@router.message(Command("sources"))
@router.message(F.text == "🌐 Источники вакансий")
async def cmd_sources_menu(
    message: Message, state: FSMContext, db: Database
) -> None:
    """Открывает раздел управления источниками вакансий."""
    await state.clear()
    list_text = await _format_sources_list(db)
    await message.answer(
        list_text
        + "\n\n👇 Вы можете добавить новый сайт или ссылку на ТГ-канал кнопкой ниже "
        "или командой `/add_source <ссылка>`:",
        reply_markup=get_sources_keyboard(),
        parse_mode="Markdown",
    )


@router.message(Command("add_source"))
async def cmd_add_source_direct(
    message: Message, state: FSMContext, db: Database
) -> None:
    """Быстрое добавление источника через команду /add_source <url_или_канал>."""
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await state.set_state(SourceStates.waiting_for_source_url)
        await message.answer(
            "➕ **Добавление нового источника вакансий**\n\n"
            "Отправьте ссылку на сайт вакансий или на Telegram-канал:\n"
            "• Примеры ТГ-каналов: `https://t.me/ru_python_jobs`, `t.me/devjobs`, `@remote_it_jobs`\n"
            "• Примеры сайтов: `https://hh.ru`, `https://career.habr.com`, `https://python.org/jobs`\n\n"
            "_Для отмены введите /cancel_",
            parse_mode="Markdown",
        )
        return

    raw_source = parts[1].strip()
    try:
        _, _, response_msg = await register_source_in_db(
            db=db,
            raw_input=raw_source,
            user_id=message.from_user.id,  # type: ignore
        )
        await message.answer(
            response_msg,
            reply_markup=get_sources_keyboard(),
            parse_mode="Markdown",
        )
    except ValueError as exc:
        await message.answer(f"⚠️ {exc}")


@router.callback_query(F.data == "src_action:list")
async def cb_list_sources(callback: CallbackQuery, db: Database) -> None:
    """Показывает актуальный список всех источников в БД."""
    await callback.answer()
    list_text = await _format_sources_list(db)
    if callback.message:
        await callback.message.edit_text(
            list_text,
            reply_markup=get_sources_keyboard(),
            parse_mode="Markdown",
        )


@router.callback_query(F.data == "src_action:add")
async def cb_start_add_source(callback: CallbackQuery, state: FSMContext) -> None:
    """Запускает диалог добавления нового сайта или ТГ-канала в базу."""
    await callback.answer()
    await state.set_state(SourceStates.waiting_for_source_url)
    if callback.message:
        await callback.message.answer(
            "➕ **Добавление источника в базу данных**\n\n"
            "Пришлите ссылку на **Telegram-канал** (например `https://t.me/python_jobs` или `@python_jobs`) "
            "или на **сайт вакансий** (например `https://career.habr.com` или любой другой ресурс):\n\n"
            "🔎 _Я автоматически проверю, есть ли этот источник в моей базе данных, и если его нет — добавлю!_\n\n"
            "_Для отмены нажмите /cancel_",
            parse_mode="Markdown",
        )


@router.message(SourceStates.waiting_for_source_url, F.text)
async def handle_new_source_input(
    message: Message, state: FSMContext, db: Database
) -> None:
    """Принимает ссылку от пользователя, проверяет наличие в БД и добавляет при отсутствии."""
    raw_input = (message.text or "").strip()

    try:
        _, _, result_message = await register_source_in_db(
            db=db,
            raw_input=raw_input,
            user_id=message.from_user.id,  # type: ignore
        )
        await state.clear()
        await message.answer(
            result_message,
            reply_markup=get_sources_keyboard(),
            parse_mode="Markdown",
        )
    except ValueError as exc:
        await message.answer(
            f"⚠️ {exc}\n\nПопробуйте отправить корректную ссылку или введите /cancel для выхода."
        )
