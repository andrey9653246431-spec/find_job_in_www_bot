"""Точка входа Telegram-бота для формирования резюме и поиска работы."""
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from bot.config import config
from bot.database import Database
from bot.handlers import register_all_routers
from bot.services.file_extractor import repair_invalid_resume_profiles


async def setup_bot_commands(bot: Bot) -> None:
    """Устанавливает меню команд в интерфейсе Telegram."""
    commands = [
        BotCommand(command="start", description="Запустить бота / Главное меню"),
        BotCommand(command="upload_resume", description="📤 Загрузить резюме (PDF, DOCX, TXT, текст)"),
        BotCommand(command="gold_standard", description="🏛 Золотой стандарт: Executive CV (Framework 2026+)"),
        BotCommand(command="example_cv", description="👁 Пример идеального резюме (Executive CV 2026+)"),
        BotCommand(command="find_resources", description="🧭 Каналы, агрегаторы и карьерные страницы"),
        BotCommand(command="standards", description="📐 Задать стандарты рынка внутри бота"),
        BotCommand(command="adapt_resume", description="✨ Адаптировать резюме под стандарты рынка"),
        BotCommand(command="search", description="🔍 Поиск вакансий (1 день / 1 неделя / 1 месяц)"),
        BotCommand(command="sources", description="🌐 База источников (сайты и ТГ-каналы)"),
        BotCommand(command="add_source", description="➕ Добавить новый сайт или ТГ-канал"),
        BotCommand(command="my_resume", description="📄 Просмотреть загруженное резюме"),
        BotCommand(command="set_role", description="✏️ Указать целевую должность вручную"),
        BotCommand(command="set_skills", description="✏️ Указать ключевые навыки вручную"),
        BotCommand(command="reset_profile", description="🔄 Пересобрать профиль из резюме"),
        BotCommand(command="help", description="📖 Справка по функциям"),
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

    # Авто-починка профилей, где вместо должности/навыков ранее сохранилось ФИО
    repaired = await repair_invalid_resume_profiles(db)
    if repaired:
        logger.info("Исправлено профилей резюме (ФИО вместо должности/навыков): %d", repaired)

    bot = Bot(token=config.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    # Передаём экземпляр БД в контекст aiogram (доступен во всех хендлерах как аргумент `db: Database`)
    dp["db"] = db

    register_all_routers(dp)
    await setup_bot_commands(bot)

    logger.info("Бот успешно запущен и ожидает сообщений...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
