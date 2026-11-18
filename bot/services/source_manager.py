"""Модуль управления источниками вакансий (сайты и Telegram-каналы).

Выполняет:
1. Распознавание и нормализацию ссылок на Telegram-каналы (@channel, t.me/..., t.me/s/...) и веб-сайты.
2. Проверку наличия источника в базе данных SQLite.
3. Если источник уже есть в базе — сообщает об этом пользователю.
4. Если источник новый — добавляет его в базу данных и сообщает об успешном добавлении.
"""
import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse
import aiohttp
from bot.database import Database

TG_USERNAME_RE = re.compile(r"^@?([a-zA-Z0-9_]{4,64})$")
TG_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?([a-zA-Z0-9_]{4,64})(?:/\d+)?/?$",
    re.IGNORECASE,
)


def normalize_source_input(raw_input: str) -> Dict[str, str]:
    """Нормализует пользовательский ввод (ссылку на ТГ-канал, @username или URL сайта).

    Возвращает словарь:
    - canonical_url: уникальный нормализованный URL для проверки дубликатов в БД
    - parse_url: URL для фактического парсинга (для ТГ-каналов — веб-версия https://t.me/s/<channel>)
    - source_type: 'tg_channel' или 'website'
    - title: человекочитаемое название источника
    """
    cleaned = raw_input.strip()
    if not cleaned:
        raise ValueError("Пустая ссылка. Отправьте ссылку на сайт или Telegram-канал.")

    # 1. Проверяем, является ли ввод ссылкой на Telegram-канал (t.me/... или telegram.me/...)
    tg_url_match = TG_URL_RE.match(cleaned)
    if tg_url_match:
        channel_username = tg_url_match.group(1)
        channel_lower = channel_username.lower()
        return {
            "canonical_url": f"https://t.me/{channel_lower}",
            "parse_url": f"https://t.me/s/{channel_lower}",
            "source_type": "tg_channel",
            "title": f"TG-канал: @{channel_username}",
        }

    # 2. Проверяем, является ли ввод юзернеймом канала вида @channel_name (без точки домена)
    if cleaned.startswith("@") or ("." not in cleaned and "/" not in cleaned):
        tg_user_match = TG_USERNAME_RE.match(cleaned)
        if tg_user_match:
            channel_username = tg_user_match.group(1)
            channel_lower = channel_username.lower()
            return {
                "canonical_url": f"https://t.me/{channel_lower}",
                "parse_url": f"https://t.me/s/{channel_lower}",
                "source_type": "tg_channel",
                "title": f"TG-канал: @{channel_username}",
            }

    # 3. Иначе обрабатываем как веб-сайт / RSS / портал вакансий
    url_candidate = cleaned
    if not re.match(r"^https?://", url_candidate, re.I):
        url_candidate = "https://" + url_candidate

    parsed = urlparse(url_candidate)
    host = (parsed.netloc or "").lower().strip()
    if host.startswith("www."):
        host = host[4:]

    if not host or "." not in host:
        raise ValueError(
            f"Не удалось распознать источник «{raw_input}». "
            "Укажите корректный URL сайта (например, https://career.habr.com) "
            "или ссылку на ТГ-канал (например, https://t.me/ru_python_jobs или @ru_python_jobs)."
        )

    # Если пользователь ввёл t.me с нестандартным путём
    if host in ("t.me", "telegram.me"):
        path_parts = [p for p in parsed.path.split("/") if p and p.lower() != "s"]
        if not path_parts:
            raise ValueError("Укажите конкретный Telegram-канал после https://t.me/...")
        channel_username = path_parts[0]
        channel_lower = channel_username.lower()
        return {
            "canonical_url": f"https://t.me/{channel_lower}",
            "parse_url": f"https://t.me/s/{channel_lower}",
            "source_type": "tg_channel",
            "title": f"TG-канал: @{channel_username}",
        }

    # Нормализуем путь сайта
    clean_path = parsed.path.rstrip("/")
    canonical_url = f"https://{host}{clean_path}"
    parse_url = canonical_url
    if parsed.query:
        parse_url = f"{canonical_url}?{parsed.query}"

    # Специальная настройка для известных порталов с открытыми RSS/API
    if host in ("hh.ru", "m.hh.ru") and not clean_path:
        canonical_url = "https://hh.ru"
        parse_url = "https://api.hh.ru/vacancies"
        title = "Сайт: HeadHunter (hh.ru)"
    elif host == "career.habr.com" and clean_path in ("", "/vacancies"):
        canonical_url = "https://career.habr.com"
        parse_url = "https://career.habr.com/vacancies/rss"
        title = "Сайт: Хабр Карьера (career.habr.com)"
    else:
        title = f"Сайт: {host}{clean_path}"

    return {
        "canonical_url": canonical_url,
        "parse_url": parse_url,
        "source_type": "website",
        "title": title,
    }


async def verify_source_availability(
    normalized: Dict[str, str], timeout: float = 8.0
) -> Optional[bool]:
    """Проверяет, что ресурс реально доступен (защита от несуществующих ссылок).

    Для Telegram-каналов используется публичное веб-превью `https://t.me/s/<channel>`:
    если канал приватный или такого адреса нет, страница не отдаёт ленту сообщений.
    Для сайтов проверяется HTTP-ответ (2xx/3xx).

    Возвращает:
    - True — ресурс доступен;
    - False — ресурс недоступен (приватный канал, 404 и т.п.);
    - None — проверить не удалось (сеть/таймаут), решение остаётся за пользователем.
    """
    url = normalized.get("parse_url") or normalized.get("canonical_url")
    if not url:
        return None
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; find_job_bot/1.0)"}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.get(url, headers=headers, allow_redirects=True) as response:
                if response.status >= 400:
                    return False
                if normalized.get("source_type") != "tg_channel":
                    return True
                html = await response.text(errors="ignore")
                # Признак живого публичного канала — виджет с сообщениями в веб-превью
                return "tgme_widget_message" in html or "tgme_channel_info" in html
    except Exception:  # noqa: BLE001 — сетевые сбои не должны ломать добавление источника
        return None

async def register_source_in_db(
    db: Database,
    raw_input: str,
    user_id: int = 0,
) -> Tuple[bool, Dict[str, Any], str]:
    """Проверяет источник в БД и добавляет его, если он новый.

    Возвращает кортеж (is_new, source_record, user_message):
    - Если источник УЖЕ ЕСТЬ в БД: `is_new = False`, сообщение информирует о наличии.
    - Если источник НОВЫЙ: `is_new = True`, источник сохраняется в БД, сообщение подтверждает добавление.
    """
    normalized = normalize_source_input(raw_input)
    availability = await verify_source_availability(normalized)
    is_new, record = await db.add_source(
        canonical_url=normalized["canonical_url"],
        parse_url=normalized["parse_url"],
        source_type=normalized["source_type"],
        title=normalized["title"],
        added_by_user_id=user_id,
    )

    type_label = (
        "Telegram-канал"
        if record.get("source_type") == "tg_channel"
        else "Веб-сайт / Интернет-ресурс"
    )

    if availability is False:
        availability_note = (
            "⚠️ **Проверьте актуальность ссылки:** ресурс не отдал публичный контент "
            "(приватный канал, неверный адрес или блокировка). Точный адрес может быть изменён."
        )
    elif availability is True:
        availability_note = "🔗 Проверка ссылки: ресурс доступен."
    else:
        availability_note = (
            "ℹ️ Проверка ссылки не удалась (сеть недоступна) — проверьте актуальность адреса вручную."
        )

    if not is_new:
        message = (
            "⚠️ **Этот источник уже есть в моей базе данных!**\n\n"
            f"• **Название:** {record.get('title')}\n"
            f"• **Тип ресурса:** {type_label}\n"
            f"• **Ссылка в базе:** `{record.get('canonical_url')}`\n\n"
            f"{availability_note}\n\n"
            "Повторное добавление не требуется — он уже участвует в поиске вакансий."
        )
    else:
        message = (
            "✅ **Новый источник успешно добавлен в базу данных!**\n\n"
            f"• **Название:** {record.get('title')}\n"
            f"• **Тип ресурса:** {type_label}\n"
            f"• **Ссылка в базе:** `{record.get('canonical_url')}`\n"
            f"• **Адрес парсинга:** `{record.get('parse_url')}`\n\n"
            f"{availability_note}\n\n"
            "Теперь бот будет искать вакансии и по этому ресурсу."
        )

    return is_new, record, message
