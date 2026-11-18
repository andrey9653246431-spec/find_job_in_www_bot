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

    # Таймаут HTTP-запросов при парсинге (сек)
    http_timeout: int = int(os.getenv("HTTP_TIMEOUT", "15"))
    max_vacancies_per_message: int = int(os.getenv("MAX_VACANCIES_PER_MESSAGE", "10"))


config = Config()
