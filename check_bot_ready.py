#!/usr/bin/env python3
"""Предполётная проверка бота перед запуском в Telegram.

Запуск:
    python check_bot_ready.py            # проверка окружения и кода
    python check_bot_ready.py --online   # + реальная проверка токена через api.telegram.org

Скрипт ничего не отправляет в Telegram (кроме безопасного getMe) и не меняет файлы
проекта, поэтому его можно запускать сколько угодно раз.
"""
import argparse
import asyncio
import importlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

OK = "✅"
WARN = "⚠️"
FAIL = "❌"

results: list[tuple[str, str, str]] = []


def report(level: str, title: str, detail: str = "") -> None:
    results.append((level, title, detail))
    print(f"{level} {title}" + (f"\n   {detail}" if detail else ""))


def check_python_and_deps() -> None:
    version = sys.version_info
    if version >= (3, 10):
        report(OK, f"Python {version.major}.{version.minor}.{version.micro}", "Нужен Python 3.10+")
    else:
        report(FAIL, f"Python {version.major}.{version.minor}", "Нужен Python 3.10 или новее")

    required = ["aiogram", "aiosqlite", "aiohttp", "docx", "pypdf", "dotenv", "bs4"]
    missing = []
    for module in required:
        try:
            importlib.import_module(module)
        except Exception:  # noqa: BLE001
            missing.append(module)

    if missing:
        report(FAIL, "Не установлены зависимости", f"Нет модулей: {', '.join(missing)}\n   → pip install -r requirements.txt")
    else:
        import aiogram

        report(OK, "Все зависимости установлены", f"aiogram {aiogram.__version__}")

    if importlib.util.find_spec("pytest") is None:
        report(WARN, "pytest не установлен", "Автотесты локально не запустятся (для работы бота не нужен)")


def check_token_format() -> str:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        report(
            FAIL,
            "BOT_TOKEN не задан",
            "Создайте .env (cp .env.example .env) и вставьте токен от @BotFather,\n"
            "   либо задайте переменную окружения: export BOT_TOKEN='123456:AA...'",
        )
        return ""
    if re.fullmatch(r"\d{5,}:[A-Za-z0-9_-]{30,}", token):
        report(OK, "Формат BOT_TOKEN корректный", f"ID бота: {token.split(':', 1)[0]}")
    else:
        report(
            FAIL,
            "BOT_TOKEN выглядит некорректно",
            "Ожидается формат 1234567890:AAH... (длинная строка после двоеточия).\n"
            "   Проверьте, что скопировали токен целиком и без кавычек/пробелов.",
        )
    return token


def check_env_file() -> None:
    env_path = Path(".env")
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"^BOT_TOKEN=\s*\S+", content, re.M):
            report(OK, "Файл .env найден и содержит BOT_TOKEN")
        else:
            report(WARN, "Файл .env есть, но BOT_TOKEN в нём пустой")
        if "1234567890:AAH_your_telegram_bot_token_here" in content:
            report(WARN, "В .env остался токен-заглушка", "Замените его на реальный токен от @BotFather")
    else:
        report(WARN, ".env не найден", "Скопируйте .env.example → .env или задайте переменные окружения")


def check_env_permissions() -> None:
    gitignore = Path(".gitignore")
    env_exists = Path(".env").exists()
    if env_exists:
        if gitignore.exists() and re.search(r"^\.env$", gitignore.read_text(encoding="utf-8"), re.M):
            report(OK, ".env исключён из Git (.gitignore)", "Токен не попадёт в репозиторий")
        else:
            report(FAIL, ".env не исключён из Git", "Добавьте строку .env в .gitignore, иначе токен утечёт")


def check_database() -> None:
    from bot.config import config
    from bot.database import Database

    db_path = config.db_path
    try:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        report(FAIL, "Нет прав на запись каталога БД", f"{db_path}: {exc}")
        return

    async def _probe() -> tuple[int, int]:
        with tempfile.TemporaryDirectory() as tmp:
            probe = Database(str(Path(tmp) / "probe.sqlite3"))
            await probe.init_db()
            sources = await probe.list_sources(active_only=False)
            resume = await probe.get_resume(1)
            assert resume is None
            return len(sources), 1

    try:
        sources_count, _ = asyncio.run(_probe())
        report(
            OK,
            "SQLite: схема создаётся, источники предзаполнены",
            f"{sources_count} источников по умолчанию; рабочий путь: {db_path}",
        )
    except Exception as exc:  # noqa: BLE001
        report(FAIL, "Ошибка инициализации SQLite", str(exc))


def check_code_and_routers() -> None:
    """Импортирует все модули проекта (без создания Dispatcher — это делает dry-run)."""
    modules = [
        "main",
        "bot.config",
        "bot.database",
        "bot.states",
        "bot.keyboards",
        "bot.handlers",
        "bot.handlers.common",
        "bot.handlers.resume",
        "bot.handlers.standards",
        "bot.handlers.sources",
        "bot.handlers.search",
        "bot.handlers.resources",
        "bot.services.file_extractor",
        "bot.services.market_standards",
        "bot.services.source_manager",
        "bot.services.vacancy_parser",
        "bot.services.resource_catalog",
        "bot.services.search_assistant",
    ]
    broken = []
    for module in modules:
        try:
            importlib.import_module(module)
        except Exception as exc:  # noqa: BLE001
            broken.append(f"{module}: {exc!r}")
    if broken:
        report(FAIL, "Не импортируются модули проекта", "\n   ".join(broken))
    else:
        report(OK, f"Все {len(modules)} модулей проекта импортируются без ошибок")


def check_startup_sequence() -> None:
    """Прогоняет ровно ту же последовательность запуска, что и main.py, но без polling.

    Проверяет: инициализацию БД, создание Bot/Dispatcher, регистрацию роутеров,
    установку контекста `db` и список команд — то есть всё, что происходит до сети.
    """
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage

    from bot.handlers import register_all_routers
    import main as entrypoint

    fake_token = "1234567890:AAFakeTokenOnlyForDryRun1234567890abcd"

    async def _dry_run() -> int:
        with tempfile.TemporaryDirectory() as tmp:
            from bot.database import Database

            db = Database(str(Path(tmp) / "dry_run.sqlite3"))
            await db.init_db()

            bot = Bot(token=fake_token)
            dp = Dispatcher(storage=MemoryStorage())
            dp["db"] = db
            register_all_routers(dp)
            handlers = sum(len(router.message.handlers) for router in dp.sub_routers)
            callbacks = sum(len(router.callback_query.handlers) for router in dp.sub_routers)

            assert callable(entrypoint.setup_bot_commands)
            await bot.session.close()
            return handlers, callbacks, len(dp.sub_routers)

    try:
        handlers, callbacks, routers = asyncio.run(_dry_run())
        report(
            OK,
            "Холодный старт проходит без ошибок",
            f"БД + Bot + Dispatcher: {routers} роутеров, {handlers} обработчиков сообщений, "
            f"{callbacks} callback — готово к polling",
        )
    except Exception as exc:  # noqa: BLE001
        report(FAIL, "Ошибка на холодном старте", repr(exc))


def check_optional_llm() -> None:
    key = os.getenv("LLM_API_KEY", "").strip()
    if key:
        base = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
        model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        report(OK, "LLM-режим включён", f"{base} · {model}")
    else:
        report(
            OK,
            "LLM-ключ не задан — работает бесплатный встроенный движок",
            "Бот полностью работоспособен без API-ключей",
        )


def check_telegram_online(token: str) -> None:
    if not token:
        report(WARN, "Онлайн-проверка токена пропущена", "Нет BOT_TOKEN")
        return

    async def _get_me() -> dict:
        import aiohttp

        url = f"https://api.telegram.org/bot{token}/getMe"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url) as response:
                return json.loads(await response.text())

    try:
        data = asyncio.run(_get_me())
    except Exception as exc:  # noqa: BLE001
        report(WARN, "Не удалось связаться с api.telegram.org", f"{exc}\n   Проверьте интернет/прокси")
        return

    if data.get("ok"):
        bot_info = data["result"]
        report(
            OK,
            "Telegram принял токен (getMe)",
            f"@{bot_info.get('username')} · id {bot_info.get('id')}",
        )

        async def _webhook_info() -> dict:
            import aiohttp

            url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(url) as response:
                    return json.loads(await response.text())

        try:
            info = asyncio.run(_webhook_info()).get("result", {})
            if info.get("url"):
                report(
                    FAIL,
                    "У бота установлен webhook — polling не заработает",
                    f"Активный webhook: {info['url']}\n"
                    "   Удалите его: curl 'https://api.telegram.org/bot<TOKEN>/deleteWebhook?drop_pending_updates=true'",
                )
            else:
                report(OK, "Webhook не установлен — long polling будет работать")
        except Exception:  # noqa: BLE001
            report(WARN, "Не удалось проверить webhook", "Проверьте вручную через getWebhookInfo")
    else:
        description = data.get("description", "неизвестная ошибка")
        hint = ""
        if "Unauthorized" in description:
            hint = "\n   Токен отозван или скопирован с ошибкой — выпустите новый в @BotFather (/mybots → API Token)."
        elif "Not Found" in description:
            hint = "\n   Похоже, в токене лишние символы или бот удалён."
        report(FAIL, "Telegram отклонил токен", f"{description}{hint}")


def print_summary() -> int:
    fails = [r for r in results if r[0] == FAIL]
    warns = [r for r in results if r[0] == WARN]
    print("\n" + "=" * 68)
    print(f"ИТОГО: {len([r for r in results if r[0] == OK])} ок · {len(warns)} предупреждений · {len(fails)} ошибок")
    print("=" * 68)
    if fails:
        print("\n❌ Запуск не начнётся, пока не исправлено:")
        for _, title, _ in fails:
            print(f"   • {title}")
        return 1
    if warns:
        print("\n⚠️ Не критично, но стоит проверить:")
        for _, title, _ in warns:
            print(f"   • {title}")
    print("\n🚀 Всё готово. Запускайте:  python main.py")
    print("   (в чате Telegram отправьте боту /start)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка готовности Telegram-бота к запуску")
    parser.add_argument("--online", action="store_true", help="проверить токен через api.telegram.org (getMe)")
    args = parser.parse_args()

    print("🔎 Предполётная проверка Telegram-бота find_job_in_www_bot\n")
    check_python_and_deps()
    check_env_file()
    token = check_token_format()
    check_env_permissions()
    check_database()
    check_code_and_routers()
    check_startup_sequence()
    check_optional_llm()
    if args.online:
        check_telegram_online(token)
    else:
        print(f"{WARN} Онлайн-проверка токена выключена (добавьте флаг --online)")

    return print_summary()


if __name__ == "__main__":
    sys.exit(main())
