"""Обработчики для:
1. Отдельной функции загрузки резюме (файлом PDF/DOCX/TXT или текстом).
2. Отдельной функции адаптации резюме под заданные стандарты рынка.
3. Просмотра загруженного резюме.
"""
import io
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from bot.database import Database
from bot.keyboards import (
    get_after_upload_keyboard,
    get_main_menu_keyboard,
)
from bot.services.file_extractor import (
    extract_text_from_file_bytes,
    upload_and_register_resume,
)
from bot.services.market_standards import adapt_resume_to_market_standards
from bot.states import ResumeStates

router = Router(name="resume")


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

        skills_str = (
            ", ".join(saved["extracted_skills"])
            if saved["extracted_skills"]
            else "будут уточнены при адаптации"
        )
        await status_msg.edit_text(
            "✅ **Резюме успешно загружено и сохранено в базе!**\n\n"
            f"📁 **Файл:** `{file_name}`\n"
            f"🎯 **Определена целевая должность:** {saved['extracted_role']}\n"
            f"🛠 **Извлечённые ключевые навыки ({len(saved['extracted_skills'])}):** {skills_str}\n\n"
            "Что сделаем дальше?",
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

        skills_str = (
            ", ".join(saved["extracted_skills"])
            if saved["extracted_skills"]
            else "общий профиль"
        )
        await message.answer(
            "✅ **Текст резюме успешно загружен и проанализирован!**\n\n"
            f"🎯 **Целевая должность:** {saved['extracted_role']}\n"
            f"🛠 **Ключевые навыки ({len(saved['extracted_skills'])}):** {skills_str}\n\n"
            "Выберите следующее действие:",
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

        # Отправляем готовый сгенерированный DOCX-файл адаптированного резюме
        docx_file = BufferedInputFile(
            result["docx_bytes"],
            filename="Adapted_Resume_Market_Standard.docx",
        )
        await message.answer_document(
            document=docx_file,
            caption="📎 Готовый файл адаптированного резюме в формате `.docx` (по стандартам рынка).",
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

    skills = ", ".join(record.get("extracted_skills") or []) or "не выделены"
    has_adapted = "Да ✅" if record.get("adapted_text") else "Ещё не выполнялась (нажмите «✨ Адаптировать резюме»)"
    preview = record["raw_text"][:700] + ("..." if len(record["raw_text"]) > 700 else "")

    await message.answer(
        "📄 **Ваш профиль резюме в базе:**\n\n"
        f"🎯 **Целевая должность:** {record.get('extracted_role')}\n"
        f"🛠 **Ключевые навыки:** {skills}\n"
        f"📁 **Источник:** `{record.get('file_name')}`\n"
        f"✨ **Адаптация под стандарты рынка:** {has_adapted}\n\n"
        f"**Фрагмент исходного текста:**\n```\n{preview}\n```",
        reply_markup=get_after_upload_keyboard(),
        parse_mode="Markdown",
    )
