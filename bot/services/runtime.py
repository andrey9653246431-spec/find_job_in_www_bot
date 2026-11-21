"""Управление временем работы бота и автоперезапуском.

Зачем это нужно
---------------
Бот живёт на GitHub Actions, а у раннера есть жёсткие ограничения:

* **один job не может идти дольше 6 часов** (360 минут), после чего GitHub его убивает;
* если бот просто «висеть» в polling, необработанная ошибка запуска может завершить процесс — и до следующего ручного запуска бот молчит;
* у публичных репозиториев **запланированные workflow отключаются после 60 дней
  без активности** в репозитории (не «после входа в GitHub», а после коммитов/пушей).

Поэтому сессия строится так: бот работает «пакетом» `BOT_MAX_RUNTIME_MINUTES`
(по умолчанию 330 мин — с запасом до лимита 360), внутри пакета сам поднимается
после падений с растущей паузой, а затем workflow завершает job и перезапускает
следующую сессию (self re-dispatch). Плюс heartbeat-коммит раз в сутки, чтобы
поддерживать активность репозитория (при разрешённом push).

Модуль намеренно не содержит сети и aiogram — всю арифметику можно тестировать.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
import os

# Лимит GitHub Actions на один job — 360 минут. Держим запас на checkout/install/cleanup.
GITHUB_JOB_LIMIT_MINUTES = 360
DEFAULT_MAX_RUNTIME_MINUTES = 330
MIN_MAX_RUNTIME_MINUTES = 5

# Пауза перед перезапуском polling после падения: 5, 10, 20, 40, 60, 60… секунд
DEFAULT_RESTART_DELAY_SECONDS = 5
MAX_RESTART_DELAY_SECONDS = 60


@dataclass(frozen=True)
class PollingPlan:
    """Сколько работать в одной сессии и как перезапускаться после сбоев."""

    max_runtime_minutes: int = DEFAULT_MAX_RUNTIME_MINUTES
    restart_delay_seconds: int = DEFAULT_RESTART_DELAY_SECONDS
    max_restart_delay_seconds: int = MAX_RESTART_DELAY_SECONDS

    @property
    def max_runtime(self) -> timedelta:
        return timedelta(minutes=self.max_runtime_minutes)


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def polling_plan() -> PollingPlan:
    """Настройки сессии из переменных окружения (со ограничением лимитом GitHub)."""
    minutes = _env_int("BOT_MAX_RUNTIME_MINUTES", DEFAULT_MAX_RUNTIME_MINUTES)
    minutes = max(MIN_MAX_RUNTIME_MINUTES, min(minutes, GITHUB_JOB_LIMIT_MINUTES - 10))
    return PollingPlan(
        max_runtime_minutes=minutes,
        restart_delay_seconds=max(1, _env_int("BOT_RESTART_DELAY_SECONDS", DEFAULT_RESTART_DELAY_SECONDS)),
        max_restart_delay_seconds=max(1, _env_int("BOT_MAX_RESTART_DELAY_SECONDS", MAX_RESTART_DELAY_SECONDS)),
    )


def next_restart_delay(attempt: int, plan: PollingPlan) -> int:
    """Пауза перед N-й попыткой перезапуска: экспоненциально, но не больше потолка."""
    attempt = max(1, int(attempt))
    delay = plan.restart_delay_seconds * (2 ** min(attempt - 1, 6))
    return min(delay, plan.max_restart_delay_seconds)


def session_expired(started_at: datetime, now: datetime, plan: PollingPlan) -> bool:
    """Пора ли штатно завершить сессию (чтобы workflow запустил следующую)."""
    return (now - started_at) >= plan.max_runtime


def session_summary(started_at: datetime, now: datetime, plan: PollingPlan, restarts: int) -> str:
    """Строка для лога при завершении сессии."""
    worked = now - started_at
    total_minutes = int(worked.total_seconds() // 60)
    return (
        f"Сессия бота завершена штатно: отработано {total_minutes} мин. "
        f"(лимит {plan.max_runtime_minutes} мин.), перезапусков после сбоев: {restarts}. "
        "Следующая сессия запускается автоматически."
    )
