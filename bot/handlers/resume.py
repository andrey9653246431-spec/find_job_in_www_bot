"""Обработчики для:
1. Отдельной функции загрузки резюме (файлом PDF/DOCX/TXT или текстом).
2. Отдельной функции адаптации резюме под заданные стандарты рынка.
3. Просмотра загруженного резюме.
"""
import io
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from bot.database import Database
from bot.keyboards import (
    get_after_upload_keyboard,
    get_main_menu_keyboard,
    get_profile_edit_keyboard,
)
from bot.services.file_extractor import (
    build_resume_profile,
    extract_text_from_file_bytes,
    upload_and_register_resume,
)
from bot.services.market_standards import adapt_resume_to_market_standards
from bot.services.message_utils import escape_markdown
from bot.states import ResumeStates

router = Router(name="resume")




def _profile_report(record: dict) -> str:
    """Формирует блок «профиль резюме» + подсказки, если данные не распознаны."""
    role = (record.get("extracted_role") or "").strip()
    skills = record.get("extracted_skills") or []

    role_line = (
        f"🎯 **Целевая должность:** {escape_markdown(role)}"
        if role
        else "🎯 **Целевая должность:** ⚠️ не распознана в резюме"
    )
    skills_line = (
        f"🛠 **Ключевые навыки ({len(skills)}):** {escape_markdown(', '.join(skills))}"
        if skills
        else "🛠 **Ключевые навыки:** ⚠️ не найдены в резюме"
    )

    hints: list[str] = []
    if not role:
        hints.append("• задать должность: `/set_role Коммерческий директор`")
    if not skills:
        hints.append("• задать навыки: `/set_skills P&L, Excel, CRM, 1C`")
    hint_block = (
        "\n\n💡 **Уточните профиль вручную — иначе поиск вакансий будет неточным:**\n"
        + "\n".join(hints)
        if hints
        else ""
    )
    edit_hint = (
        "\n✏️ Распознано неточно? Поправьте кнопками **«Изменить должность»** / "
        "**«Изменить навыки»** — поиск пойдёт уже по исправленному профилю."
    )
    return f"{role_line}\n{skills_line}{hint_block}{edit_hint}"

# =============================================================================
# 1. ОТДЕЛЬНАЯ ФУНКЦИЯ ЗАГРУЗКИ РЕЗЮМЕ
# =============================================================================

@router.message(Command("upload_resume"))
@router.message(F.text == "📤 Загрузить резюме")
async def start_upload_resume(message: Message, state: FSMContext) -> None:
    """Переводит бота в режим приёма резюме от пользователя."""
    await state.set_state(ResumeStates.waiting_for_resume)
    await message.answer(
        "📤 **Загрузка резюме**\n\n"
        "Отправьте ваше резюме одним из способов:\n"
        "• Прикрепите файл в формате `.pdf`, `.docx`, `.txt` или `.md`;\n"
        "• Или просто пришлите текст резюме ответным сообщением.\n\n"
        "_Для отмены нажмите /cancel_",
        parse_mode="Markdown",
    )


@router.message(ResumeStates.waiting_for_resume, F.document)
async def handle_resume_document(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
) -> None:
    """Обработка резюме, отправленного в виде документа (PDF, DOCX, TXT, MD)."""
    doc = message.document
    if not doc:
        return

    file_name = doc.file_name or "resume.txt"
    status_msg = await message.answer("⏳ Читаю и анализирую файл резюме...")

    try:
        file_info = await bot.get_file(doc.file_id)
        buffer = io.BytesIO()
        await bot.download_file(file_info.file_path, destination=buffer)  # type: ignore
        raw_text = extract_text_from_file_bytes(buffer.getvalue(), file_name)

        saved = await upload_and_register_resume(
            db=db,
            user_id=message.from_user.id,  # type: ignore
            raw_text=raw_text,
            file_name=file_name,
            username=message.from_user.username or "",  # type: ignore
        )
        await state.clear()

        await status_msg.edit_text(
            "✅ **Резюме успешно загружено и сохранено в базе!**\n\n"
            f"📁 **Файл:** `{file_name}`\n"
            + _profile_report(saved)
            + "\n\nЧто сделаем дальше?",
            reply_markup=get_after_upload_keyboard(),
            parse_mode="Markdown",
        )
    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка при загрузке файла резюме: {exc}")


@router.message(ResumeStates.waiting_for_resume, F.text)
async def handle_resume_text(
    message: Message,
    state: FSMContext,
    db: Database,
) -> None:
    """Обработка резюме, отправленного обычным текстовым сообщением."""
    raw_text = (message.text or "").strip()

    # Если пользователь нажал кнопку главного меню вместо текста резюме
    menu_buttons = {
        "📤 Загрузить резюме",
        "✨ Адаптировать резюме",
        "📐 Стандарты рынка",
        "🔍 Поиск вакансий",
        "🌐 Источники вакансий",
        "📄 Моё резюме",
        "🏛 Пример идеального резюме",
        "🧭 Найти каналы и сайты",
    }
    if raw_text in menu_buttons:
        await state.clear()
        await message.answer(
            "Режим загрузки резюме завершён. Повторите нажатие нужной кнопки меню.",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    try:
        saved = await upload_and_register_resume(
            db=db,
            user_id=message.from_user.id,  # type: ignore
            raw_text=raw_text,
            file_name="text_message.txt",
            username=message.from_user.username or "",  # type: ignore
        )
        await state.clear()

        await message.answer(
            "✅ **Текст резюме успешно загружен и проанализирован!**\n\n"
            + _profile_report(saved)
            + "\n\nВыберите следующее действие:",
            reply_markup=get_after_upload_keyboard(),
            parse_mode="Markdown",
        )
    except ValueError as exc:
        await message.answer(f"⚠️ {exc}")


# =============================================================================
# 2. ОТДЕЛЬНАЯ ФУНКЦИЯ АДАПТАЦИИ РЕЗЮМЕ ПОД СТАНДАРТЫ РЫНКА
# =============================================================================

async def _run_adaptation_flow(message: Message, user_id: int, db: Database) -> None:
    """Выполняет адаптацию резюме под активные стандарты рынка и отправляет отчёт + DOCX."""
    wait_msg = await message.answer(
        "⚙️ **Адаптирую резюме под заданные стандарты рынка...**",
        parse_mode="Markdown",
    )
    try:
        result = await adapt_resume_to_market_standards(db=db, user_id=user_id)
        audit = result["audit"]
        standards = result["standards"]
        adapted_text: str = result["adapted_text"]

        strengths_txt = (
            "\n".join(f"  ✅ {s}" for s in audit["strengths"])
            if audit["strengths"]
            else "  • Базовая структура распознана"
        )
        improvements_txt = (
            "\n".join(f"  🔸 {i}" for i in audit["improvements"])
            if audit["improvements"]
            else "  • Все ключевые требования стандарта выполнены"
        )

        report_header = (
            "✨ **Резюме адаптировано под стандарты рынка!**\n\n"
            f"📐 **Применённый стандарт:** {standards['title']}\n"
            f"📊 **Индекс соответствия стандарту (ATS Score):** `{audit['score']}/100%`\n"
            f"🤖 **Модуль обработки:** {result['engine_used']}\n\n"
            f"**Сильные стороны:**\n{strengths_txt}\n\n"
            f"**Выполненные улучшения и рекомендации стандарта:**\n{improvements_txt}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        # Отправляем текст адаптированного резюме (с учётом лимита длины сообщения Telegram 4096 символов)
        full_text = report_header + adapted_text
        if len(full_text) <= 4000:
            await wait_msg.edit_text(full_text)
        else:
            await wait_msg.edit_text(report_header[:4000])
            for chunk_start in range(0, len(adapted_text), 3800):
                await message.answer(adapted_text[chunk_start : chunk_start + 3800])

        # Имя файла зависит от активного стандарта: для «Золотого стандарта» —
        # Executive CV (Framework 2026+), иначе универсальное имя.
        if standards.get("preset_key") == "executive_cv_2026":
            docx_filename = "Ideal_Executive_CV_2026.docx"
            docx_caption = (
                "📎 Готовый файл **Executive CV** в формате `.docx` "
                "(Золотой стандарт: Framework 2026+, максимум 2 страницы)."
            )
        else:
            docx_filename = "Adapted_Resume_Market_Standard.docx"
            docx_caption = (
                "📎 Готовый файл адаптированного резюме в формате `.docx` "
                "(по стандартам рынка)."
            )

        # Отправляем готовый сгенерированный DOCX-файл адаптированного резюме
        docx_file = BufferedInputFile(
            result["docx_bytes"],
            filename=docx_filename,
        )
        await message.answer_document(
            document=docx_file,
            caption=docx_caption,
            parse_mode="Markdown",
        )
    except ValueError as exc:
        await wait_msg.edit_text(f"⚠️ {exc}")
    except Exception as exc:
        await wait_msg.edit_text(f"❌ Ошибка при адаптации резюме: {exc}")


@router.message(Command("adapt_resume"))
@router.message(F.text == "✨ Адаптировать резюме")
async def cmd_adapt_resume(message: Message, db: Database) -> None:
    """Запуск отдельной функции адаптации резюме из главного меню или по команде."""
    await _run_adaptation_flow(
        message=message,
        user_id=message.from_user.id,  # type: ignore
        db=db,
    )


@router.callback_query(F.data == "quick_action:adapt")
async def cb_quick_adapt_resume(callback: CallbackQuery, db: Database) -> None:
    """Быстрый запуск адаптации резюме по inline-кнопке после загрузки."""
    await callback.answer()
    if callback.message:
        await _run_adaptation_flow(
            message=callback.message,  # type: ignore
            user_id=callback.from_user.id,
            db=db,
        )


# =============================================================================
# 3. ПРОСМОТР ТЕКУЩЕГО РЕЗЮМЕ ПОЛЬЗОВАТЕЛЯ
# =============================================================================

@router.message(Command("my_resume"))
@router.message(F.text == "📄 Моё резюме")
async def cmd_my_resume(message: Message, db: Database) -> None:
    """Показывает информацию о загруженном резюме пользователя."""
    record = await db.get_resume(message.from_user.id)  # type: ignore
    if not record:
        await message.answer(
            "ℹ️ У вас пока нет загруженного резюме.\n"
            "Нажмите **📤 Загрузить резюме**, чтобы отправить файл или текст.",
            parse_mode="Markdown",
        )
        return

    has_adapted = "Да ✅" if record.get("adapted_text") else "Ещё не выполнялась (нажмите «✨ Адаптировать резюме»)"
    preview = record["raw_text"][:700] + ("..." if len(record["raw_text"]) > 700 else "")

    await message.answer(
        "📄 **Ваш профиль резюме в базе:**\n\n"
        + _profile_report(record)
        + f"\n📁 **Источник:** `{record.get('file_name')}`\n"
        f"✨ **Адаптация под стандарты рынка:** {has_adapted}\n\n"
        f"**Фрагмент исходного текста:**\n```\n{preview}\n```",
        reply_markup=get_after_upload_keyboard(),
        parse_mode="Markdown",
    )


# =============================================================================
# 3.1 ИНТЕРАКТИВНАЯ ПРАВКА ПРОФИЛЯ ПЕРЕД ПОИСКОМ (кнопки «Изменить должность/навыки»)
# =============================================================================

MENU_BUTTON_TEXTS = {
    "📤 Загрузить резюме",
    "✨ Адаптировать резюме",
    "📐 Стандарты рынка",
    "🔍 Поиск вакансий",
    "🌐 Источники вакансий",
    "📄 Моё резюме",
    "🏛 Пример идеального резюме",
    "🧭 Найти каналы и сайты",
}

CANCEL_TEXTS = {"/cancel", "отмена", "cancel", "стоп"}


def _clean_role_input(raw: str) -> str:
    """Чистит введённую должность: кавычки, маркеры списка, лишние пробелы."""
    value = " ".join((raw or "").split())
    value = value.strip(" .,;:•-–—\"'«»`")
    return value[:120]


def _parse_skills_input(raw: str) -> list[str]:
    """Разбирает навыки из текста: через запятую, точку с запятой, слэш или с новой строки."""
    items = re.split(r"[,;|/\n]+", raw or "")
    skills: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = " ".join(item.split()).strip(" .•-–—\"'«»`")
        if not cleaned or len(cleaned) > 40:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        skills.append(cleaned)
    return skills[:30]


async def _ask_role_edit(target: Message, state: FSMContext, record: dict) -> None:
    """Просит пользователя прислать новое название должности."""
    await state.set_state(ResumeStates.waiting_for_role)
    current = (record.get("extracted_role") or "").strip() or "не распознана"
    await target.answer(
        "✏️ **Изменение целевой должности**\n\n"
        f"Сейчас в профиле: **{escape_markdown(current)}**\n\n"
        "Пришлите новое название одним сообщением, например:\n"
        "`Руководитель продукта`\n"
        "`Директор по маркетингу`\n\n"
        "_Для отмены — /cancel_",
        parse_mode="Markdown",
    )


async def _ask_skills_edit(target: Message, state: FSMContext, record: dict) -> None:
    """Просит пользователя прислать новый список навыков."""
    await state.set_state(ResumeStates.waiting_for_skills)
    skills = record.get("extracted_skills") or []
    current = escape_markdown(", ".join(skills)) if skills else "не найдены"
    await target.answer(
        "🛠 **Изменение ключевых навыков**\n\n"
        f"Сейчас в профиле ({len(skills)}): **{current}**\n\n"
        "Пришлите навыки через запятую — список **заменит** прежний, например:\n"
        "`P&L, Excel, CRM, 1C, управление командой`\n\n"
        "Чтобы очистить список — отправьте `очистить`.\n"
        "_Для отмены — /cancel_",
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "profile_edit:role")
async def cb_edit_profile_role(
    callback: CallbackQuery, state: FSMContext, db: Database
) -> None:
    """Кнопка «✏️ Изменить должность»: включает режим ввода новой должности."""
    await callback.answer()
    if not callback.message:
        return
    record = await db.get_resume(callback.from_user.id)  # type: ignore
    if not record:
        await callback.message.answer(  # type: ignore[union-attr]
            "ℹ️ Сначала загрузите резюме: **📤 Загрузить резюме**.",
            parse_mode="Markdown",
        )
        return
    await _ask_role_edit(callback.message, state, record)  # type: ignore[arg-type]


@router.callback_query(F.data == "profile_edit:skills")
async def cb_edit_profile_skills(
    callback: CallbackQuery, state: FSMContext, db: Database
) -> None:
    """Кнопка «🛠 Изменить навыки»: включает режим ввода нового списка навыков."""
    await callback.answer()
    if not callback.message:
        return
    record = await db.get_resume(callback.from_user.id)  # type: ignore
    if not record:
        await callback.message.answer(  # type: ignore[union-attr]
            "ℹ️ Сначала загрузите резюме: **📤 Загрузить резюме**.",
            parse_mode="Markdown",
        )
        return
    await _ask_skills_edit(callback.message, state, record)  # type: ignore[arg-type]


@router.message(ResumeStates.waiting_for_role, F.text)
async def handle_profile_role_input(
    message: Message, state: FSMContext, db: Database
) -> None:
    """Принимает новую должность и сохраняет её в профиль резюме."""
    raw = (message.text or "").strip()

    if raw in MENU_BUTTON_TEXTS:
        await state.clear()
        await message.answer(
            "Изменение должности отменено. Повторите нажатие нужной кнопки меню.",
            reply_markup=get_main_menu_keyboard(),
        )
        return
    if raw.lower() in CANCEL_TEXTS:
        await state.clear()
        await message.answer(
            "Изменение должности отменено — профиль остался прежним.",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    role = _clean_role_input(raw)
    if len(role) < 2:
        await message.answer(
            "⚠️ Не понял должность. Пришлите название одним сообщением, например: "
            "`Руководитель продукта`",
            parse_mode="Markdown",
        )
        return

    updated = await db.update_resume_profile(user_id=message.from_user.id, role=role)  # type: ignore
    if updated is None:
        await state.clear()
        await message.answer("⚠️ Резюме не найдено — загрузите его заново: **📤 Загрузить резюме**.")
        return

    await state.clear()
    await message.answer(
        "✅ **Целевая должность обновлена!**\n\n"
        + _profile_report(updated)
        + "\n\nТеперь можно запускать поиск вакансий.",
        reply_markup=get_after_upload_keyboard(),
        parse_mode="Markdown",
    )


@router.message(ResumeStates.waiting_for_skills, F.text)
async def handle_profile_skills_input(
    message: Message, state: FSMContext, db: Database
) -> None:
    """Принимает новый список навыков и сохраняет его в профиль резюме."""
    raw = (message.text or "").strip()

    if raw in MENU_BUTTON_TEXTS:
        await state.clear()
        await message.answer(
            "Изменение навыков отменено. Повторите нажатие нужной кнопки меню.",
            reply_markup=get_main_menu_keyboard(),
        )
        return
    if raw.lower() in CANCEL_TEXTS:
        await state.clear()
        await message.answer(
            "Изменение навыков отменено — профиль остался прежним.",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    if raw.lower() in {"очистить", "нет", "-", "пусто"}:
        skills: list[str] = []
    else:
        skills = _parse_skills_input(raw)
        if not skills:
            await message.answer(
                "⚠️ Не удалось разобрать навыки. Пример: `P&L, Excel, CRM, 1C`",
                parse_mode="Markdown",
            )
            return

    updated = await db.update_resume_profile(
        user_id=message.from_user.id,  # type: ignore
        skills=skills,
    )
    if updated is None:
        await state.clear()
        await message.answer("⚠️ Резюме не найдено — загрузите его заново: **📤 Загрузить резюме**.")
        return

    await state.clear()
    await message.answer(
        "✅ **Ключевые навыки обновлены!**\n\n"
        + _profile_report(updated)
        + "\n\nТеперь можно запускать поиск вакансий.",
        reply_markup=get_after_upload_keyboard(),
        parse_mode="Markdown",
    )


# =============================================================================
# 4. РУЧНАЯ КОРРЕКТИРОВКА ПРОФИЛЯ РЕЗЮМЕ (/set_role, /set_skills)
# =============================================================================

@router.message(Command("set_role"))
async def cmd_set_role(message: Message, db: Database) -> None:
    """Позволяет вручную задать целевую должность (если бот её не распознал)."""
    raw = (message.text or "").split(maxsplit=1)
    if len(raw) < 2 or not raw[1].strip():
        await message.answer(
            "✏️ **Укажите целевую должность** после команды, например:\n"
            "`/set_role Коммерческий директор`",
            parse_mode="Markdown",
        )
        return

    role = raw[1].strip()[:120]
    record = await db.get_resume(message.from_user.id)  # type: ignore
    if not record:
        await message.answer(
            "ℹ️ Сначала загрузите резюме: **📤 Загрузить резюме**.",
            parse_mode="Markdown",
        )
        return

    updated = await db.update_resume_profile(user_id=message.from_user.id, role=role)  # type: ignore
    await message.answer(
        "✅ **Целевая должность обновлена!**\n\n"
        + _profile_report(updated or record)
        + "\n\nТеперь можно запускать поиск вакансий: `/search`",
        parse_mode="Markdown",
    )


@router.message(Command("set_skills"))
async def cmd_set_skills(message: Message, db: Database) -> None:
    """Позволяет вручную задать ключевые навыки через запятую."""
    raw = (message.text or "").split(maxsplit=1)
    if len(raw) < 2 or not raw[1].strip():
        await message.answer(
            "✏️ **Укажите навыки через запятую**, например:\n"
            "`/set_skills P&L, Excel, CRM, 1C, управление командой`",
            parse_mode="Markdown",
        )
        return

    skills = [
        item.strip()
        for item in re.split(r"[,;|]+", raw[1])
        if item.strip()
    ][:30]
    if not skills:
        await message.answer("⚠️ Не удалось разобрать список навыков. Пример: `/set_skills Excel, CRM, 1C`")
        return

    record = await db.get_resume(message.from_user.id)  # type: ignore
    if not record:
        await message.answer(
            "ℹ️ Сначала загрузите резюме: **📤 Загрузить резюме**.",
            parse_mode="Markdown",
        )
        return

    updated = await db.update_resume_profile(user_id=message.from_user.id, skills=skills)  # type: ignore
    await message.answer(
        "✅ **Ключевые навыки обновлены!**\n\n"
        + _profile_report(updated or record)
        + "\n\nТеперь можно запускать поиск вакансий: `/search`",
        parse_mode="Markdown",
    )


@router.message(Command("reset_profile"))
async def cmd_reset_profile(message: Message, db: Database) -> None:
    """Повторно извлекает должность и навыки из загруженного резюме автоматически."""
    record = await db.get_resume(message.from_user.id)  # type: ignore
    if not record:
        await message.answer("ℹ️ Резюме пока не загружено.")
        return

    profile = build_resume_profile(record["raw_text"])
    updated = await db.update_resume_profile(
        user_id=message.from_user.id,  # type: ignore
        role=profile["role"],
        skills=profile["skills"],
        manual=False,
    )
    await message.answer(
        "🔄 **Профиль пересобран автоматически.**\n\n"
        + _profile_report(updated or record),
        parse_mode="Markdown",
    )
