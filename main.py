"""Точка входа Telegram-бота для формирования резюме и поиска работы."""
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from bot.config import adapt_resume_ui_enabled, config, ideal_resume_ui_enabled
from bot.database import Database
from bot.handlers import register_all_routers
from bot.middlewares import VisitCounterMiddleware
from bot.config import raw_resume_storage_enabled
from bot.services.file_extractor import (
    purge_stored_resume_texts,
    repair_invalid_resume_profiles,
)


async def setup_bot_commands(bot: Bot) -> None:
    """Устанавливает меню команд в интерфейсе Telegram."""
    commands = [
        BotCommand(command="start", description="Запустить бота / Главное меню"),
        BotCommand(command="upload_resume", description="📤 Загрузить резюме (PDF, DOCX, TXT, текст)"),
        BotCommand(command="find_resources", description="🧭 Каналы, агрегаторы и карьерные страницы"),
        BotCommand(command="standards", description="📐 Задать стандарты рынка внутри бота"),
        BotCommand(command="search", description="🔍 Поиск вакансий: ТГ / сайты / карьерные страницы + период"),
        BotCommand(command="sources", description="🌐 База источников (сайты и ТГ-каналы)"),
        BotCommand(command="add_source", description="➕ Добавить новый сайт или ТГ-канал"),
        BotCommand(command="my_resume", description="📄 Просмотреть загруженное резюме"),
        BotCommand(command="set_role", description="✏️ Указать целевую должность вручную"),
        BotCommand(command="set_skills", description="✏️ Указать ключевые навыки вручную"),
        BotCommand(command="reset_profile", description="🔄 Пересобрать профиль из резюме"),
        BotCommand(command="stats", description="📊 Статистика посещаемости"),
        BotCommand(command="help", description="📖 Справка по функциям"),
    ]
    if adapt_resume_ui_enabled():
        commands.insert(
            2,
            BotCommand(
                command="adapt_resume",
                description="✨ Адаптировать резюме под стандарты рынка",
            ),
        )
    if ideal_resume_ui_enabled():
        # Блок «идеальное резюме» скрыт по умолчанию — команды не показываем в меню Telegram
        commands[2:2] = [
            BotCommand(
                command="gold_standard",
                description="🏛 Золотой стандарт: Executive CV (Framework 2026+)",
            ),
            BotCommand(
                command="example_cv",
                description="👁 Пример идеального резюме (Executive CV 2026+)",
            ),
        ]
    await bot.set_my_commands(commands)


async def main() -> None:
    """Инициализация БД, регистрация роутеров и запуск поллинга Telegram-бота."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger(__name__)

    if not config.bot_token:
        logger.error(
            "Переменная окружения BOT_TOKEN не задана! "
            "Создайте файл .env на основе .env.example и укажите токен от @BotFather."
        )
        sys.exit(1)

    db = Database(config.db_path)
    await db.init_db()
    logger.info("База данных SQLite инициализирована: %s", config.db_path)

    # Досеиваем новые источники вакансий (ТГ-каналы/сайты) в существующую базу
    added_sources = await db.ensure_default_sources()
    if added_sources:
        logger.info("Добавлено новых источников вакансий в БД: %d", added_sources)

    # Приватный режим: текст резюме в базе не хранится. Если в базе остались
    # тексты от прошлых версий — заменяем их на SHA-256 хэш (профиль сохраняется).
    if not raw_resume_storage_enabled():
        purged = await purge_stored_resume_texts(db)
        if purged:
            logger.info(
                "Приватный режим: удалены сохранённые тексты резюме (%d), оставлены SHA-256 хэши",
                purged,
            )

    # Авто-починка профилей, где вместо должности/навыков ранее сохранилось ФИО
    repaired = await repair_invalid_resume_profiles(db)
    if repaired:
        logger.info("Исправлено профилей резюме (ФИО вместо должности/навыков): %d", repaired)

    bot = Bot(token=config.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    # Передаём экземпляр БД в контекст aiogram (доступен во всех хендлерах как аргумент `db: Database`)
    dp["db"] = db

    # Счётчик посещаемости: считает любой заход (сообщение, команда, кнопка).
    # Ошибка записи в лог-файл статистики не ломает обработку события.
    visit_counter = VisitCounterMiddleware(db=db)
    dp.message.middleware(visit_counter)
    dp.callback_query.middleware(visit_counter)

    register_all_routers(dp)

    @dp.error()
    async def on_error(event: object) -> bool:
        """Глобальный перехватчик: одна сломанная отправка не «вешает» обработчик.

        Самая частая причина — `Bad Request: can't find end of the entity`
        (незакрытая Markdown-сущность в длинном сообщении). Пишем понятную
        причину в лог и отвечаем пользователю, что делать, вместо тишины.
        """
        exception = getattr(event, "exception", None)
        message = getattr(event, "update", None)
        logger.exception("Ошибка при обработке обновления: %r", exception)
        try:
            target = getattr(message, "message", None) or getattr(message, "callback_query", None)
            if target is not None and hasattr(target, "answer"):
                await target.answer(
                    "⚠️ Не удалось отобразить ответ (ошибка форматирования сообщения).\n"
                    "Повторите запрос — бот пересоберёт его без разметки.\n"
                    f"Техническая причина: {type(exception).__name__}"
                )
        except Exception:  # noqa: BLE001 — падение уведомления не должно ломать polling
            logger.debug("Не удалось уведомить пользователя об ошибке")
        return True

    await setup_bot_commands(bot)

    try:
        from bot.services.llm_client import build_providers

        _providers = build_providers()
        if _providers:
            logger.info(
                "LLM для адаптации резюме: %s",
                ", ".join(f"{p.label} ({p.model})" for p in _providers),
            )
        else:
            logger.info(
                "LLM-ключи не заданы — адаптация резюме идёт встроенным локальным движком "
                "(команда /llm подскажет, как подключить бесплатную модель)"
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось определить LLM-провайдеров: %s", exc)

    logger.info("Бот успешно запущен и ожидает сообщений...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
