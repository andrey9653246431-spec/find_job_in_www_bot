"""Точка входа Telegram-бота для формирования резюме и поиска работы.

Запуск рассчитан на GitHub Actions: бот работает сессией (по умолчанию 330 мин),
сам поднимается после падений и по расписанию/по цепочке перезапусков
поднимается следующая сессия. Подробности — в `bot/services/runtime.py`.
"""
import asyncio
from datetime import datetime, timezone
import logging
import signal
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from bot.config import adapt_resume_ui_enabled, config, ideal_resume_ui_enabled
from bot.database import Database
from bot.handlers import register_all_routers
from bot.middlewares import VisitCounterMiddleware
from bot.services.runtime import (
    PollingPlan,
    next_restart_delay,
    polling_plan,
    session_expired,
    session_summary,
)
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


async def run_polling_with_restarts(
    bot: Bot,
    dp: Dispatcher,
    plan: PollingPlan,
    logger: logging.Logger,
) -> None:
    """Держит бота в polling: сам поднимается после сбоев и завершает сессию по таймеру.

    Почему так:
    - одна сессия ограничена ``plan.max_runtime_minutes`` (по умолчанию 330 мин при
      лимите GitHub Actions 360 мин на job) — сессия завершается сама, до того как
      раннер убьёт процесс, и workflow успевает запустить следующую;
    - любое падение polling (сеть, `409 Conflict`, `TelegramNetworkError`) не убивает
      бота: пауза 5 → 10 → 20 → … → 60 секунд и повторный запуск;
    - SIGTERM/SIGINT (остановка workflow, `timeout`, отмена рана) отрабатываются
      как штатное завершение.
    """
    started_at = datetime.now(timezone.utc)
    stop_requested = asyncio.Event()
    loop = asyncio.get_running_loop()
    previous = {}
    polling_task = None
    restarts = 0
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                previous[sig] = signal.getsignal(sig)
                loop.add_signal_handler(sig, stop_requested.set)
            except (NotImplementedError, RuntimeError, ValueError):
                previous.pop(sig, None)
        while not stop_requested.is_set():
            if session_expired(started_at, datetime.now(timezone.utc), plan):
                logger.info(session_summary(started_at, datetime.now(timezone.utc), plan, restarts))
                return
            # Сессию HTTP закрывает main(), а не каждая попытка polling.
            polling_task = asyncio.create_task(dp.start_polling(
                bot, handle_signals=False, close_bot_session=False,
            ))
            while not polling_task.done():
                await asyncio.wait({polling_task}, timeout=1)
                if stop_requested.is_set() or session_expired(
                    started_at, datetime.now(timezone.utc), plan
                ):
                    return
            if polling_task.cancelled():
                return
            error = polling_task.exception()
            restarts += 1
            delay = next_restart_delay(restarts, plan)
            logger.warning("Polling завершён (%r). Повтор №%d через %d с", error, restarts, delay)
            try:
                await asyncio.wait_for(stop_requested.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
    finally:
        if polling_task is not None:
            if not polling_task.done():
                polling_task.cancel()
            await asyncio.gather(polling_task, return_exceptions=True)
        for sig, handler in previous.items():
            loop.remove_signal_handler(sig)
            signal.signal(sig, handler)


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

    plan = polling_plan()
    logger.info(
        "Бот успешно запущен: сессия до %d мин., автоперезапуск после сбоев включён",
        plan.max_runtime_minutes,
    )
    try:
        await run_polling_with_restarts(bot=bot, dp=dp, plan=plan, logger=logger)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
