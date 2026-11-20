"""Обработчики для отдельной функции задания стандартов рынка внутри бота.

Позволяет пользователю:
1. Просмотреть текущие активные стандарты рынка.
2. Выбрать один из готовых отраслевых стандартов (ATS, IT, Data, Маркетинг/Продажи).
3. Задать свои собственные стандарты рынка текстом прямо внутри бота (список разделов, ключевые слова, правила оформления).
4. Сбросить стандарты к базовым.
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from bot.config import (
    IDEAL_RESUME_DISABLED_TEXT,
    adapt_resume_ui_enabled,
    ideal_resume_ui_enabled,
)
from bot.database import Database
from bot.keyboards import get_standards_keyboard
from bot.services.market_standards import (
    build_ideal_executive_cv_2026_example,
    get_market_standards,
    reset_market_standards,
    set_gold_standard_executive_cv_2026,
    set_market_standards,
)
from bot.states import MarketStandardsStates

router = Router(name="standards")


def _format_standards_info(standards: dict) -> str:
    """Форматирует карточку активных стандартов рынка."""
    sections = "\n".join(
        f"  {idx}. {sec}"
        for idx, sec in enumerate(standards.get("required_sections", []), start=1)
    )
    focus_kw = standards.get("rules", {}).get("focus_keywords", [])
    kw_line = (
        f"\n🔑 **Целевые маркеры стандарта:** {', '.join(focus_kw)}\n"
        if focus_kw
        else ""
    )
    return (
        "📐 **Управление стандартами рынка (отдельная функция бота)**\n\n"
        f"🏷 **Активный стандарт:** {standards.get('title')}\n\n"
        f"📑 **Обязательная структура разделов:**\n{sections}\n"
        f"{kw_line}\n"
        f"📋 **Правила и критерии стандарта:**\n{standards.get('standards_text')}\n\n"
        "👇 Вы можете переключить пресет стандарта или **задать собственные стандарты рынка** кнопкой ниже:"
    )


@router.message(Command("gold_standard"))
async def cmd_gold_standard(
    message: Message, state: FSMContext, db: Database
) -> None:
    """Отдельная команда установки Золотого стандарта Executive CV (Framework 2026+)."""
    await state.clear()
    if not ideal_resume_ui_enabled():
        await message.answer(IDEAL_RESUME_DISABLED_TEXT, parse_mode="Markdown")
        return
    updated = await set_gold_standard_executive_cv_2026(
        db=db, user_id=message.from_user.id  # type: ignore
    )
    await message.answer(
        "🏛 **Установлен «Золотой стандарт»: АРХИТЕКТУРА ИДЕАЛЬНОГО EXECUTIVE CV (Framework 2026+)**!\n\n"
        + _format_standards_info(updated),
        reply_markup=get_standards_keyboard(),
        parse_mode="Markdown",
    )


# =============================================================================
# ПОКАЗ ЭТАЛОННОГО ПРИМЕРА ИДЕАЛЬНОГО РЕЗЮМЕ (Executive CV Framework 2026+)
# =============================================================================

async def _send_ideal_cv_example(message: Message) -> None:
    """Отправляет эталонный пример идеального резюме по «Золотому стандарту»:
    пояснение, карту структуры, готовый текст Executive CV и файл `.docx`.
    """
    example = build_ideal_executive_cv_2026_example()
    audit = example["audit"]

    structure_txt = "\n".join(example["structure"])
    header = (
        f"{example['intro']}\n\n"
        f"📊 **ATS Score исходного образца:** `{audit['score']}/100`\n"
        f"🧱 **Карта архитектуры и фильтров:**\n{structure_txt}\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    await message.answer(header, parse_mode="Markdown")

    # Сам эталонный текст отправляем без parse_mode — чтобы Markdown в резюме не ломал разметку
    example_text = example["example_text"]
    for chunk_start in range(0, len(example_text), 3800):
        await message.answer(example_text[chunk_start : chunk_start + 3800])

    await message.answer_document(
        document=BufferedInputFile(
            example["docx_bytes"], filename="Ideal_Executive_CV_2026_Example.docx"
        ),
        caption=(
            "📎 **Эталонный пример Executive CV (Framework 2026+)** в формате `.docx` — "
            "можно использовать как шаблон структуры для своего резюме."
        ),
        parse_mode="Markdown",
    )


@router.message(Command("example_cv"))
@router.message(Command("example"))
@router.message(F.text == "🏛 Пример идеального резюме")
async def cmd_show_ideal_cv_example(message: Message, state: FSMContext) -> None:
    """Отдельная функция показа примера идеального резюме по «Золотому стандарту»."""
    await state.clear()
    if not ideal_resume_ui_enabled():
        await message.answer(IDEAL_RESUME_DISABLED_TEXT, parse_mode="Markdown")
        return
    await _send_ideal_cv_example(message)


@router.callback_query(F.data == "std_action:example")
async def cb_show_ideal_cv_example(callback: CallbackQuery) -> None:
    """Показ примера идеального резюме по inline-кнопке меню стандартов."""
    await callback.answer("Показываю эталонный пример Executive CV")
    if not callback.message:
        return
    if not ideal_resume_ui_enabled():
        await callback.message.answer(  # type: ignore[union-attr]
            IDEAL_RESUME_DISABLED_TEXT, parse_mode="Markdown"
        )
        return
    await _send_ideal_cv_example(callback.message)


@router.message(Command("standards"))
@router.message(Command("set_standards"))
@router.message(F.text == "📐 Стандарты рынка")
async def cmd_market_standards(
    message: Message, state: FSMContext, db: Database
) -> None:
    """Показывает текущие стандарты рынка и меню их настройки внутри бота."""
    await state.clear()
    standards = await get_market_standards(db=db, user_id=message.from_user.id)  # type: ignore
    await message.answer(
        _format_standards_info(standards),
        reply_markup=get_standards_keyboard(),
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "quick_action:standards")
async def cb_quick_standards(callback: CallbackQuery, db: Database) -> None:
    """Открытие меню стандартов рынка по быстрой inline-кнопке."""
    await callback.answer()
    standards = await get_market_standards(db=db, user_id=callback.from_user.id)
    if callback.message:
        await callback.message.answer(
            _format_standards_info(standards),
            reply_markup=get_standards_keyboard(),
            parse_mode="Markdown",
        )


@router.callback_query(F.data.startswith("std_preset:"))
async def cb_select_standards_preset(
    callback: CallbackQuery, db: Database
) -> None:
    """Установка выбранного отраслевого пресета стандартов рынка."""
    preset_key = (callback.data or "").split(":", 1)[1]
    if preset_key == "executive_cv_2026" and not ideal_resume_ui_enabled():
        await callback.answer()
        if callback.message:
            await callback.message.answer(  # type: ignore[union-attr]
                IDEAL_RESUME_DISABLED_TEXT, parse_mode="Markdown"
            )
        return
    updated = await set_market_standards(
        db=db,
        user_id=callback.from_user.id,
        preset_key=preset_key,
    )
    await callback.answer(f"Установлен стандарт: {updated['title']}")
    if callback.message:
        await callback.message.edit_text(
            "✅ **Стандарты рынка успешно обновлены!**\n\n"
            + _format_standards_info(updated),
            reply_markup=get_standards_keyboard(),
            parse_mode="Markdown",
        )


@router.callback_query(F.data == "std_action:reset")
async def cb_reset_standards(callback: CallbackQuery, db: Database) -> None:
    """Сброс стандартов рынка к базовому универсальному ATS-стандарту."""
    if not ideal_resume_ui_enabled():
        # «Вернуть Золотой стандарт» — часть скрытого блока
        await callback.answer()
        if callback.message:
            await callback.message.answer(  # type: ignore[union-attr]
                IDEAL_RESUME_DISABLED_TEXT, parse_mode="Markdown"
            )
        return
    updated = await reset_market_standards(db=db, user_id=callback.from_user.id)
    await callback.answer("Стандарты сброшены к базовым")
    if callback.message:
        await callback.message.edit_text(
            "🔄 **Стандарты рынка сброшены к базовым значениям!**\n\n"
            + _format_standards_info(updated),
            reply_markup=get_standards_keyboard(),
            parse_mode="Markdown",
        )


@router.callback_query(F.data == "std_action:custom_input")
async def cb_start_custom_standards_input(
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Запускает режим ввода собственных стандартов рынка текстом внутри бота."""
    await callback.answer()
    await state.set_state(MarketStandardsStates.waiting_for_custom_standards)
    if callback.message:
        await callback.message.answer(
            "✏️ **Задание собственных стандартов рынка внутри бота**\n\n"
            "Отправьте сообщением требования и правила, которым должно соответствовать адаптированное резюме.\n\n"
            "**Пример формата (можно в свободной форме):**\n"
            "```\n"
            "Разделы: Контакты, Summary, Стек технологий, Коммерческий опыт, Образование\n"
            "Ключевые слова: Python, FastAPI, PostgreSQL, Docker, Asyncio\n"
            "Правила:\n"
            "1. Каждый пункт опыта начинать с глагола результата по формуле XYZ.\n"
            "2. Указать метрики нагрузки (RPS, время отклика, % покрытия тестами).\n"
            "3. Исключить воду и общие фразы.\n"
            "```\n\n"
            "_Для отмены введите /cancel_",
            parse_mode="Markdown",
        )


@router.message(MarketStandardsStates.waiting_for_custom_standards, F.text)
async def handle_custom_standards_text(
    message: Message, state: FSMContext, db: Database
) -> None:
    """Сохраняет введённые пользователем стандарты рынка в БД."""
    custom_text = (message.text or "").strip()
    if len(custom_text) < 10:
        await message.answer(
            "⚠️ Описание стандартов слишком короткое. Пожалуйста, опишите требования подробнее (от 10 символов)."
        )
        return

    updated = await set_market_standards(
        db=db,
        user_id=message.from_user.id,  # type: ignore
        custom_standards_text=custom_text,
    )
    await state.clear()
    await message.answer(
        "✅ **Ваши пользовательские стандарты рынка успешно сохранены внутри бота!**\n\n"
        + _format_standards_info(updated)
        + (
            "\n\nТеперь нажмите **✨ Адаптировать резюме**, чтобы применить эти стандарты."
            if adapt_resume_ui_enabled()
            else "\n\nЭти стандарты будут применены при следующей адаптации резюме."
        ),
        reply_markup=get_standards_keyboard(),
        parse_mode="Markdown",
    )
