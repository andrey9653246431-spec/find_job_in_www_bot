"""Хранилище последних результатов поиска, чтобы листать выдачу без повторного парсинга.

Поиск по 163 источникам занимает 15–20 секунд, поэтому найденный список кладётся
в память и по кнопке «📄 Показать ещё 10» бот просто отдаёт следующую страницу.
Записи живут 60 минут и не переживают перезапуск бота — это осознанно:
устаревшая выдача не должна выглядеть свежей.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

SEARCH_TTL_SECONDS = 60 * 60
_MAX_USERS = 500

# user_id -> {"result": {...}, "created_at": float}
_SESSIONS: Dict[int, Dict[str, Any]] = {}


def _purge_expired(now: Optional[float] = None) -> None:
    """Удаляет просроченные записи, чтобы память не росла."""
    moment = now or time.time()
    expired = [
        user_id
        for user_id, payload in _SESSIONS.items()
        if moment - payload.get("created_at", 0) > SEARCH_TTL_SECONDS
    ]
    for user_id in expired:
        _SESSIONS.pop(user_id, None)


def store_search_result(user_id: int, result: Dict[str, Any]) -> Dict[str, Any]:
    """Кладёт результат поиска в память (перезаписывая предыдущий) и возвращает его."""
    now = time.time()
    _purge_expired(now)
    if len(_SESSIONS) >= _MAX_USERS and user_id not in _SESSIONS:
        # отбрасываем самую старую запись
        oldest = min(_SESSIONS, key=lambda uid: _SESSIONS[uid].get("created_at", 0))
        _SESSIONS.pop(oldest, None)
    _SESSIONS[user_id] = {"result": result, "created_at": now}
    return result


def get_search_result(user_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает последний результат поиска пользователя или None, если он устарел."""
    _purge_expired()
    payload = _SESSIONS.get(user_id)
    if not payload:
        return None
    return payload.get("result")


def clear_search_result(user_id: int) -> None:
    """Забывает результат поиска (например, после нового запроса)."""
    _SESSIONS.pop(user_id, None)


def total_items(result: Dict[str, Any]) -> int:
    """Сколько всего вакансий в сохранённом результате."""
    return len(result.get("all_vacancies") or result.get("vacancies") or [])
