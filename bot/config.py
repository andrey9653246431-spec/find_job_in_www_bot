"""Конфигурация бота и бесплатных инструментов из переменных окружения."""
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    """Настройки приложения."""
    bot_token: str = os.getenv("BOT_TOKEN", "")
    db_path: str = os.getenv("DB_PATH", str(BASE_DIR / "data" / "bot_database.sqlite3"))

    # Бесплатный LLM API. Ключи опциональны; можно задать несколько — бот перебирает
    # их по очереди (см. bot/services/llm_client.py): Gemini, Groq, Cerebras, Mistral,
    # OpenRouter :free, локальная Ollama или любой свой OpenAI-совместимый эндпоинт.
    # Если ни одного ключа нет, бот работает на встроенном локальном архитекторе резюме.
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    llm_model: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    # Какие провайдеры считать настроенными (для /llm и для логов при старте)
    llm_provider: str = os.getenv("LLM_PROVIDER", "")
    llm_order: str = os.getenv("LLM_ORDER", "")

    # Показывать ли в меню функцию «✨ Адаптировать резюме».
    # По умолчанию СКРЫТА: кнопки нет в главном меню и в клавиатуре после загрузки,
    # /adapt_resume не публикуется в меню команд и отвечает уведомлением.
    # Включить обратно: SHOW_ADAPT_RESUME_UI=1.
    show_adapt_resume_ui: bool = os.getenv("SHOW_ADAPT_RESUME_UI", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    # Показывать ли в меню блок «идеальное резюме» (Золотой стандарт + пример Executive CV).
    # По умолчанию СКРЫТ: пункты не отображаются в меню и команды /gold_standard,
    # /example_cv отвечают коротким уведомлением. Включить обратно: SHOW_IDEAL_RESUME_UI=1.
    show_ideal_resume_ui: bool = os.getenv("SHOW_IDEAL_RESUME_UI", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    # Хранить ли исходный текст загруженного резюме в БД.
    # По умолчанию 0 — ТЕКСТ НЕ ХРАНИТСЯ: в базе остаются только извлечённый профиль
    # (должность + навыки) и криптографический отпечаток резюме (SHA-256).
    # STORE_RAW_RESUME=1 возвращает хранение (нужно для адаптации под стандарты).
    store_raw_resume: bool = os.getenv("STORE_RAW_RESUME", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    # Кто может смотреть статистику посещаемости (/stats). Пусто — команда открыта всем.
    # Задаётся списком ID через запятую: ADMIN_IDS=123456789,987654321
    admin_ids: str = os.getenv("ADMIN_IDS", "")

    # Часовой пояс отчёта посещаемости (по умолчанию Москва)
    stats_tz: str = os.getenv("STATS_TZ", "Europe/Moscow")

    # Таймаут HTTP-запросов при парсинге (сек)
    http_timeout: int = int(os.getenv("HTTP_TIMEOUT", "15"))
    max_vacancies_per_message: int = int(os.getenv("MAX_VACANCIES_PER_MESSAGE", "10"))


config = Config()


def ideal_resume_ui_enabled() -> bool:
    """Включён ли блок «идеальное резюме» (кнопки меню + команды /gold_standard, /example_cv).

    Читает переменную окружения при каждом вызове, поэтому флаг можно менять
    без перезапуска кода (в тестах и при отладке это удобно).
    """
    return os.getenv("SHOW_IDEAL_RESUME_UI", "0").strip().lower() in {"1", "true", "yes", "on"}


def adapt_resume_ui_enabled() -> bool:
    """Включена ли функция «✨ Адаптировать резюме» (кнопки меню + /adapt_resume).

    Читает переменную окружения при каждом вызове — флаг можно переключать
    без перезапуска кода.
    """
    return os.getenv("SHOW_ADAPT_RESUME_UI", "0").strip().lower() in {"1", "true", "yes", "on"}


ADAPT_RESUME_DISABLED_TEXT = (
    "🙈 **Адаптация резюме скрыта.**\n\n"
    "Функция «✨ Адаптировать резюме» отключена в меню.\n\n"
    "Доступные действия: **📤 Загрузить резюме**, **📐 Стандарты рынка**, "
    "**🔍 Поиск вакансий**, **📄 Моё резюме**."
)


IDEAL_RESUME_DISABLED_TEXT = (
    "🙈 **Этот раздел скрыт.**\n\n"
    "Блок «идеальное резюме» (Золотой стандарт и эталонный пример Executive CV) отключён в меню.\n\n"
    "Доступные действия: **📤 Загрузить резюме**, **✨ Адаптировать резюме**, "
    "**📐 Стандарты рынка**, **🔍 Поиск вакансий**."
)


def admin_user_ids() -> tuple:
    """ID администраторов из ``ADMIN_IDS`` (через запятую). Пустой кортеж — доступ всем."""
    return tuple(
        int(chunk) for chunk in (os.getenv("ADMIN_IDS", "") or "").replace(";", ",").split(",")
        if chunk.strip().lstrip("-").isdigit()
    )


def is_stats_admin(user_id: int) -> bool:
    """Может ли пользователь смотреть статистику: админ из списка или список не задан."""
    admins = admin_user_ids()
    return not admins or int(user_id) in admins


def raw_resume_storage_enabled() -> bool:
    """Хранится ли исходный текст резюме в БД (``STORE_RAW_RESUME=1``)."""
    return os.getenv("STORE_RAW_RESUME", "0").strip().lower() in {"1", "true", "yes", "on"}
