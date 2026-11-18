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

    # Бесплатный LLM API (опционально: Groq, OpenRouter Free, Ollama и любой OpenAI-совместимый эндпоинт)
    # Если ключ не указан, бот автоматически использует встроенный бесплатный локальный анализатор и шаблонизатор!
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    llm_model: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    # Таймаут HTTP-запросов при парсинге (сек)
    http_timeout: int = int(os.getenv("HTTP_TIMEOUT", "15"))
    max_vacancies_per_message: int = int(os.getenv("MAX_VACANCIES_PER_MESSAGE", "10"))


config = Config()
