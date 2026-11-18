"""Клиент бесплатных LLM-провайдеров для адаптации резюме.

Задача модуля — дать боту «мозг» посильнее встроенного шаблонизатора **бесплатно**,
и при этом не падать, если у провайдера кончилась квота:

* поддерживаются любые OpenAI-совместимые API (Groq, Cerebras, Mistral, OpenRouter,
  локальная Ollama) и нативный API Google Gemini;
* ключи берутся из переменных окружения, порядок можно задать через ``LLM_ORDER``;
* провайдеры перебираются по очереди: 429/403/таймаут/пустой ответ → следующий;
* если не ответил никто — возвращается ``None``, и бот использует встроенный
  локальный архитектор резюме (то есть адаптация работает всегда).

Актуальные бесплатные лимиты провайдеров меняются (Google не раз уже урезал квоты,
OpenRouter меняет список ``:free`` моделей), поэтому конкретные цифры не зашиты
в код — они только в README, с оговоркой «проверьте в консоли провайдера».
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aiohttp

# Диагностика последнего вызова — её показывает команда /llm
LAST_ATTEMPTS: List[str] = []
LAST_RESULT: Optional["LLMResult"] = None


@dataclass
class Provider:
    """Один бесплатный LLM-провайдер."""

    key: str          # короткий идентификатор для LLM_ORDER / LLM_PROVIDER
    label: str        # как называть в сообщении пользователю
    kind: str         # "openai" (chat/completions) или "gemini"
    api_key: str
    base_url: str
    model: str
    max_tokens: int = 4000

    def masked_key(self) -> str:
        """Ключ в виде «gsk_…7f2a», чтобы его можно было показать в чате."""
        if len(self.api_key) <= 8:
            return "***"
        return f"{self.api_key[:4]}…{self.api_key[-4:]}"


@dataclass
class LLMResult:
    """Успешный ответ модели."""

    text: str
    provider_label: str
    model: str
    attempts: List[str] = field(default_factory=list)

    @property
    def engine_label(self) -> str:
        """Строка для сообщения пользователю: какой моделью сделана адаптация."""
        return f"{self.provider_label} · {self.model}"


# ---------------------------------------------------------------------------
# Конфигурация провайдеров
# ---------------------------------------------------------------------------

def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def build_providers() -> List[Provider]:
    """Собирает список доступных провайдеров (только те, у которых есть ключ).

    Порядок: сначала явный ``LLM_API_KEY`` (любой OpenAI-совместимый эндпоинт,
    в том числе локальная Ollama), затем ``GEMINI_API_KEY``, ``GROQ_API_KEY``,
    ``CEREBRAS_API_KEY``, ``MISTRAL_API_KEY``, ``OPENROUTER_API_KEY``.
    Переопределяется через ``LLM_ORDER=groq,gemini`` и ``LLM_PROVIDER=groq``.
    """
    providers: Dict[str, Provider] = {}

    legacy_key = _env("LLM_API_KEY")
    if legacy_key:
        providers["custom"] = Provider(
            key="custom",
            label="LLM API (свой ключ)",
            kind="openai",
            api_key=legacy_key,
            base_url=_env("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
            model=_env("LLM_MODEL", "llama-3.3-70b-versatile"),
        )

    gemini_key = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
    if gemini_key:
        providers["gemini"] = Provider(
            key="gemini",
            label="Google Gemini (free tier)",
            kind="gemini",
            api_key=gemini_key,
            base_url=_env("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"),
            model=_env("GEMINI_MODEL", "gemini-2.5-flash"),
        )

    groq_key = _env("GROQ_API_KEY")
    if groq_key:
        providers["groq"] = Provider(
            key="groq",
            label="Groq (free tier)",
            kind="openai",
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1",
            model=_env("GROQ_MODEL", "llama-3.3-70b-versatile"),
        )

    cerebras_key = _env("CEREBRAS_API_KEY")
    if cerebras_key:
        providers["cerebras"] = Provider(
            key="cerebras",
            label="Cerebras (free tier)",
            kind="openai",
            api_key=cerebras_key,
            base_url="https://api.cerebras.ai/v1",
            model=_env("CEREBRAS_MODEL", "gpt-oss-120b"),
        )

    mistral_key = _env("MISTRAL_API_KEY")
    if mistral_key:
        providers["mistral"] = Provider(
            key="mistral",
            label="Mistral La Plateforme (free tier)",
            kind="openai",
            api_key=mistral_key,
            base_url="https://api.mistral.ai/v1",
            model=_env("MISTRAL_MODEL", "mistral-large-latest"),
        )

    openrouter_key = _env("OPENROUTER_API_KEY")
    if openrouter_key:
        providers["openrouter"] = Provider(
            key="openrouter",
            label="OpenRouter (:free)",
            kind="openai",
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            model=_env("OPENROUTER_MODEL", "openrouter/free"),
        )

    only = _env("LLM_PROVIDER").lower()
    if only:
        return [p for p in providers.values() if p.key == only]

    ordered = [p for p in providers.values()]
    custom_order = [item.strip().lower() for item in _env("LLM_ORDER").split(",") if item.strip()]
    if custom_order:
        by_key = {p.key: p for p in ordered}
        ordered = [by_key[key] for key in custom_order if key in by_key] + [
            p for p in ordered if p.key not in custom_order
        ]
    return ordered


def describe_providers() -> List[str]:
    """Человекочитаемое описание настроенных провайдеров (для команды /llm)."""
    lines: List[str] = []
    for index, provider in enumerate(build_providers(), start=1):
        lines.append(
            f"{index}. {provider.label} — `{provider.model}` "
            f"(ключ {provider.masked_key()})"
        )
    return lines


# ---------------------------------------------------------------------------
# Запросы к провайдерам
# ---------------------------------------------------------------------------

def _max_input_chars() -> int:
    try:
        return int(_env("LLM_MAX_INPUT_CHARS", "16000"))
    except ValueError:
        return 16000


def _timeout_seconds() -> int:
    try:
        return int(_env("LLM_TIMEOUT", "75"))
    except ValueError:
        return 75


def _truncate(text: str) -> str:
    limit = _max_input_chars()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[… текст резюме обрезан, чтобы влезть в контекст модели …]"


async def _call_openai_compatible(
    session: aiohttp.ClientSession,
    provider: Provider,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> tuple[int, str]:
    payload = {
        "model": provider.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": provider.max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
    }
    url = f"{provider.base_url.rstrip('/')}/chat/completions"
    async with session.post(url, json=payload, headers=headers) as resp:
        if resp.status != 200:
            body = ""
            try:
                body = (await resp.text())[:160]
            except Exception:  # noqa: BLE001
                body = ""
            return resp.status, body
        data = await resp.json()
        content = (
            (data.get("choices") or [{}])[0]
            .get("message", {})
            .get("content", "")
            or ""
        )
        return 200, content.strip()


async def _call_gemini(
    session: aiohttp.ClientSession,
    provider: Provider,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> tuple[int, str]:
    url = (
        f"{provider.base_url.rstrip('/')}/models/{provider.model}:generateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": provider.max_tokens,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": provider.api_key,
    }
    async with session.post(url, json=payload, headers=headers) as resp:
        if resp.status != 200:
            body = ""
            try:
                body = (await resp.text())[:160]
            except Exception:  # noqa: BLE001
                body = ""
            return resp.status, body
        data = await resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return 200, ""
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts)
        return 200, text.strip()


def _looks_like_answer(text: str) -> bool:
    """Отсекает пустые ответы и вежливые отказы модели."""
    if len(text.strip()) < 400:
        return False
    lowered = text.lower()
    refusals = (
        "не могу помочь",
        "не могу выполнить",
        "i can't help",
        "i cannot help",
        "as an ai",
        "я не могу предоставить",
    )
    return not any(marker in lowered for marker in refusals)


async def generate_text(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.25,
    min_length: int = 400,
) -> Optional[LLMResult]:
    """Пробует провайдеров по очереди и возвращает первый осмысленный ответ.

    ``None`` означает «никто не ответил» — вызывающий код обязан иметь
    локальный fallback (у нас это встроенный архитектор резюме).
    """
    global LAST_ATTEMPTS, LAST_RESULT

    providers = build_providers()
    attempts: List[str] = []
    LAST_ATTEMPTS = attempts

    if not providers:
        attempts.append("ни один LLM-ключ не задан (GEMINI_API_KEY / GROQ_API_KEY / LLM_API_KEY …)")
        LAST_RESULT = None
        return None

    user_prompt = _truncate(user_prompt)
    timeout = aiohttp.ClientTimeout(total=_timeout_seconds())

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for provider in providers:
            try:
                if provider.kind == "gemini":
                    status, text = await _call_gemini(
                        session, provider, system_prompt, user_prompt, temperature
                    )
                else:
                    status, text = await _call_openai_compatible(
                        session, provider, system_prompt, user_prompt, temperature
                    )
            except Exception as exc:  # noqa: BLE001 — сеть, DNS, таймаут
                attempts.append(f"{provider.label}: ошибка сети ({type(exc).__name__})")
                continue

            if status != 200:
                hint = ""
                if status in (401, 403):
                    hint = " — проверьте ключ"
                elif status == 429:
                    hint = " — исчерпана бесплатная квота"
                elif status == 404:
                    hint = f" — модель `{provider.model}` недоступна, задайте другую"
                attempts.append(f"{provider.label}: HTTP {status}{hint}")
                continue

            if not _looks_like_answer(text) or len(text) < min_length:
                attempts.append(
                    f"{provider.label}: пустой или слишком короткий ответ ({len(text)} симв.)"
                )
                continue

            attempts.append(f"{provider.label}: OK ({len(text)} симв.)")
            result = LLMResult(
                text=text,
                provider_label=provider.label,
                model=provider.model,
                attempts=list(attempts),
            )
            LAST_RESULT = result
            return result

    LAST_RESULT = None
    return None
