"""Регистрация всех роутеров обработчиков команд и сообщений Telegram-бота."""
from aiogram import Dispatcher
from bot.handlers.common import router as common_router
from bot.handlers.resume import router as resume_router
from bot.handlers.standards import router as standards_router
from bot.handlers.sources import router as sources_router
from bot.handlers.search import router as search_router


def register_all_routers(dp: Dispatcher) -> None:
    """Подключает модульные роутеры к корневому диспетчеру."""
    dp.include_router(common_router)
    dp.include_router(resume_router)
    dp.include_router(standards_router)
    dp.include_router(sources_router)
    dp.include_router(search_router)
