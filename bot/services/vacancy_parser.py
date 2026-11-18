"""Модуль парсинга и поиска вакансий по резюме пользователя.

Осуществляет:
1. Асинхронный парсинг публичных Telegram-каналов (через веб-превью https://t.me/s/<channel>).
2. Парсинг сайтов вакансий: публичный API HeadHunter (api.hh.ru), RSS/HTML Хабр Карьеры и произвольных веб-сайтов из базы данных.
3. Фильтрацию вакансий строго по выбранному периоду:
   - 1 день (24 часа)
   - 1 неделя (7 дней)
   - 1 месяц (30 дней)
4. Ранжирование найденных вакансий по совпадению с должностью и навыками из резюме.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import json
from email.utils import parsedate_to_datetime
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup
from bot.config import config
from bot.database import Database
from bot.services.message_utils import escape_markdown
from bot.services.resource_catalog import LINKS_DISCLAIMER

PERIOD_LABELS: Dict[int, str] = {
    1: "1 день",
    7: "1 неделю",
    30: "1 месяц",
}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


def parse_iso_or_rfc_date(date_str: str) -> Optional[datetime]:
    """Преобразует строку даты (ISO-8601 или RFC-2822 из RSS/Telegram/API) в UTC datetime."""
    if not date_str:
        return None
    cleaned = date_str.strip()
    try:
        # Пробуем ISO-8601 (например, 2026-11-18T10:20:30+00:00 или 2026-11-18T10:20:30+0300)
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass

    try:
        # Пробуем RFC-2822 (стандарт RSS pubDate)
        dt = parsedate_to_datetime(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def calculate_resume_match(
    text: str,
    role: str,
    skills: List[str],
) -> Dict[str, Any]:
    """Оценивает релевантность текста вакансии резюме кандидата.

    Возвращает:
    - matched_skills: список совпавших навыков/ключевых слов из резюме
    - role_matched: совпала ли целевая роль
    - score: итоговый балл релевантности
    """
    text_lower = text.lower()
    matched_skills: List[str] = []

    for skill in skills:
        skill_low = skill.lower().strip()
        if not skill_low:
            continue
        if skill_low in text_lower:
            matched_skills.append(skill)

    # Проверяем совпадение слов из целевой должности (длиной от 3 символов)
    role_tokens = [
        tok.lower()
        for tok in re.split(r"[\s,/()\-]+", role)
        if len(tok.strip()) >= 3
        and tok.lower() not in ("для", "или", "специалист", "младший", "старший", "ведущий")
    ]
    matched_role_tokens = [tok for tok in role_tokens if tok in text_lower]
    role_matched = len(matched_role_tokens) > 0

    score = len(matched_skills) * 15 + len(matched_role_tokens) * 20
    return {
        "matched_skills": matched_skills,
        "role_matched": role_matched,
        "score": score,
    }


_EMOJI_ONLY_RE = re.compile(
    r"^[\s\W]*$"  # строка без букв и цифр (только эмодзи/символы)
)


# Объявления-рекомендации кандидатов (резюме), а не вакансии.
# Пример: канал «Вакансии от CRC» (@vacancyCRC) публикует посты
# «РЕКОМЕНДУЕМ КАНДИДАТА НА ПОЗИЦИЮ: Финансовый директор / CFO …» — это не вакансия.
EXCLUDED_TITLE_PREFIXES = (
    "рекомендуем кандидат",
    "рекомендуем кандидатов",
    "рекомендую кандидат",
    "рекомендуем специалист",
    "рекомендуем сотрудник",
    "рекомендую специалист",
)


def _normalize_for_filter(text: str) -> str:
    """Приводит заголовок/сниппет к виду для сравнения: без эмодзи, регистра и лишних пробелов."""
    normalized = (text or "").strip().lower().replace("ё", "е")
    normalized = re.sub(r"^[^0-9a-zа-я]+", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


# Посты-резюме в Telegram-каналах: «Резюме: Иван Иванов, Финансовый директор …»
RESUME_POST_PREFIXES = ("резюме", "resume", "cv:", "cv.", "cv,", "cv ", "cv/", "cv-")

REASON_CANDIDATE_RECOMMENDATION = "рекомендация кандидата («Рекомендуем кандидата …»)"
REASON_RESUME_POST = "пост-резюме кандидата («Резюме …»)"


def vacancy_exclusion_reason(vacancy: Dict[str, Any]) -> str:
    """Причина, по которой объявление не является вакансией (пустая строка — оставляем).

    - «Рекомендуем кандидата …» — рекомендация резюме (любой источник).
    - «Резюме …» / «CV …» — пост-резюме кандидата; отсекаем только в Telegram-каналах,
      где такие посты публикуют рекрутеры (на сайтах вакансий это может быть статья).
    """
    title = _normalize_for_filter(vacancy.get("title") or "")
    snippet = _normalize_for_filter(vacancy.get("snippet") or "")

    if title.startswith(EXCLUDED_TITLE_PREFIXES) or snippet.startswith(EXCLUDED_TITLE_PREFIXES):
        return REASON_CANDIDATE_RECOMMENDATION

    # «Резюме не требуется», «резюме не нужно» — это вакансия, а не пост-резюме
    if title.startswith(("резюме не", "резюме: не", "resume not")):
        return ""

    if vacancy.get("source_type") == "tg_channel" and title.startswith(RESUME_POST_PREFIXES):
        return REASON_RESUME_POST

    if title == "cv":
        return REASON_RESUME_POST if vacancy.get("source_type") == "tg_channel" else ""

    return ""


def is_excluded_vacancy(vacancy: Dict[str, Any]) -> bool:
    """Отсекает посты, которые не являются вакансиями: «Рекомендуем кандидата …» и «Резюме …»."""
    return bool(vacancy_exclusion_reason(vacancy))


def _pick_title_and_snippet(raw_text: str) -> tuple[str, str]:
    """Выбирает осмысленный заголовок и сниппет поста.

    В Telegram-каналах первая строка часто содержит только эмодзи («🔥», «🆕», «💰»),
    поэтому берём первую строку, в которой есть буквы/цифры.
    """
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    title = ""
    body_start = 0
    for idx, line in enumerate(lines):
        if _EMOJI_ONLY_RE.match(line) or len(line) < 4:
            continue
        title = line[:95]
        body_start = idx + 1
        break

    if not title:
        title = "Вакансия из Telegram-канала"
        body_start = 0

    snippet_lines = lines[body_start : body_start + 3]
    if not snippet_lines:
        snippet_lines = lines[:3]
    snippet = " ".join(snippet_lines)[:220]
    return title, snippet


def parse_telegram_channel_html(
    html: str,
    source: Dict[str, Any],
    role: str,
    skills: List[str],
    cutoff_dt: datetime,
) -> List[Dict[str, Any]]:
    """Парсит HTML-страницу публичного превью Telegram-канала (https://t.me/s/<channel>)."""
    soup = BeautifulSoup(html, "html.parser")
    results: List[Dict[str, Any]] = []

    message_nodes = soup.select(".tgme_widget_message")
    for msg in message_nodes:
        text_node = msg.select_one(".tgme_widget_message_text")
        if not text_node:
            continue
        raw_text = text_node.get_text(separator="\n", strip=True)
        if len(raw_text) < 30:
            continue

        # Извлекаем время публикации поста
        time_node = msg.select_one(".tgme_widget_message_date time")
        dt_str = time_node.get("datetime", "") if time_node else ""
        published_at = parse_iso_or_rfc_date(str(dt_str))
        if not published_at:
            published_at = datetime.now(timezone.utc)

        # Фильтрация по заданному периоду (1 день, 1 неделя, 1 месяц)
        if published_at < cutoff_dt:
            continue

        # Извлекаем прямую ссылку на пост
        date_link = msg.select_one("a.tgme_widget_message_date")
        post_url = (
            str(date_link.get("href"))
            if date_link and date_link.get("href")
            else source["canonical_url"]
        )

        match_info = calculate_resume_match(raw_text, role, skills)
        if match_info["score"] <= 0:
            continue

        title_line, snippet = _pick_title_and_snippet(raw_text)

        results.append(
            {
                "title": title_line,
                "url": post_url,
                "source_title": source.get("title", source["canonical_url"]),
                "source_type": "tg_channel",
                "published_at": published_at,
                "matched_skills": match_info["matched_skills"],
                "relevance_score": match_info["score"],
                "snippet": snippet,
            }
        )

    return results


def parse_rss_or_xml_feed(
    xml_text: str,
    source: Dict[str, Any],
    role: str,
    skills: List[str],
    cutoff_dt: datetime,
) -> List[Dict[str, Any]]:
    """Парсит RSS / Atom ленту сайта вакансий (например, Хабр Карьера и др.)."""
    soup = BeautifulSoup(xml_text, "html.parser")
    items = soup.find_all(["item", "entry"])
    results: List[Dict[str, Any]] = []

    for item in items:
        title_tag = item.find("title")
        title = title_tag.get_text(strip=True) if title_tag else "Вакансия"

        link_tag = item.find("link")
        link = ""
        if link_tag:
            link = link_tag.get("href") or link_tag.get_text(strip=True) or ""
        if not link:
            guid_tag = item.find("guid")
            link = guid_tag.get_text(strip=True) if guid_tag else source["canonical_url"]

        desc_tag = item.find(["description", "summary", "content"])
        desc_raw = desc_tag.get_text(" ", strip=True) if desc_tag else ""
        desc_clean = BeautifulSoup(desc_raw, "html.parser").get_text(" ", strip=True)

        date_tag = item.find(["pubdate", "pubDate", "published", "updated"])
        published_at = (
            parse_iso_or_rfc_date(date_tag.get_text(strip=True))
            if date_tag
            else datetime.now(timezone.utc)
        ) or datetime.now(timezone.utc)

        if published_at < cutoff_dt:
            continue

        combined_text = f"{title}\n{desc_clean}"
        match_info = calculate_resume_match(combined_text, role, skills)
        if match_info["score"] <= 0:
            continue

        results.append(
            {
                "title": title[:110],
                "url": str(link).strip(),
                "source_title": source.get("title", source["canonical_url"]),
                "source_type": "website",
                "published_at": published_at,
                "matched_skills": match_info["matched_skills"],
                "relevance_score": match_info["score"],
                "snippet": desc_clean[:220] or title,
            }
        )

    return results


def parse_generic_website_html(
    html: str,
    source: Dict[str, Any],
    role: str,
    skills: List[str],
    cutoff_dt: datetime,
) -> List[Dict[str, Any]]:
    """Универсальный парсер веб-страниц с вакансиями для произвольных сайтов, добавленных в БД."""
    soup = BeautifulSoup(html, "html.parser")
    results: List[Dict[str, Any]] = []
    seen_urls = set()

    # Ищем карточки вакансий или ссылки в заголовках
    candidates = soup.select(
        "article, .vacancy, .vacancy-card, .job, .job-card, .serp-item, h2 a, h3 a, a[href*='vacanc'], a[href*='job']"
    )
    now_utc = datetime.now(timezone.utc)

    for node in candidates[:60]:
        if node.name == "a":
            a_tag = node
            card_text = node.get_text(" ", strip=True)
        else:
            a_tag = node.find("a", href=True)
            card_text = node.get_text(" ", strip=True)

        if not a_tag or not a_tag.get("href"):
            continue

        href = str(a_tag.get("href")).strip()
        full_url = urljoin(source["canonical_url"], href)
        if full_url in seen_urls:
            continue

        title_text = a_tag.get_text(" ", strip=True) or card_text[:90]
        if len(title_text) < 5:
            continue

        # Проверяем время публикации, если на карточке есть <time datetime="...">
        time_tag = node.find("time") if node.name != "a" else None
        published_at = (
            parse_iso_or_rfc_date(str(time_tag.get("datetime", "")))
            if time_tag and time_tag.get("datetime")
            else now_utc
        ) or now_utc

        if published_at < cutoff_dt:
            continue

        match_info = calculate_resume_match(f"{title_text} {card_text}", role, skills)
        if match_info["score"] <= 0:
            continue

        seen_urls.add(full_url)
        results.append(
            {
                "title": title_text[:110],
                "url": full_url,
                "source_title": source.get("title", source["canonical_url"]),
                "source_type": "website",
                "published_at": published_at,
                "matched_skills": match_info["matched_skills"],
                "relevance_score": match_info["score"],
                "snippet": card_text[:220],
            }
        )

    return results


async def _fetch_hh_api_vacancies(
    session: aiohttp.ClientSession,
    source: Dict[str, Any],
    role: str,
    skills: List[str],
    period_days: int,
    cutoff_dt: datetime,
    issues: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Запрашивает вакансии через бесплатный открытый API HeadHunter (api.hh.ru/vacancies)."""
    # Ищем по должности: государственные и корпоративные API плохо переносят
    # длинные запросы «должность + все навыки» и возвращают 0 вакансий.
    query_parts = [role] if role and role != "Специалист" else []
    if not query_parts:
        query_parts = skills[:2]
    search_query = " ".join(query_parts).strip() or "Python"

    params = {
        "text": search_query,
        "period": str(period_days),
        "per_page": "15",
        "order_by": "publication_time",
    }

    results: List[Dict[str, Any]] = []
    async with session.get(
        "https://api.hh.ru/vacancies", params=params, headers=DEFAULT_HEADERS
    ) as resp:
        if resp.status != 200:
            # hh.ru отдаёт 403 анонимным запросам с облачных IP (Cloudflare/антибот):
            # молчать нельзя — пользователь должен знать, что вакансии hh не получены.
            if issues is not None:
                issues.append(
                    {
                        "title": source.get("title", "Сайт: HeadHunter (hh.ru API)"),
                        "url": source.get("canonical_url", "https://hh.ru"),
                        "reason": (
                            f"HTTP {resp.status} — API hh.ru отклонил анонимный запрос "
                            "(блокировка облачных IP); откройте hh.ru вручную"
                        ),
                    }
                )
            return []
        data = await resp.json()

    for item in data.get("items", []):
        name = item.get("name", "Вакансия")
        employer = (item.get("employer") or {}).get("name", "Компания")
        snippet_obj = item.get("snippet") or {}
        req = BeautifulSoup(snippet_obj.get("requirement") or "", "html.parser").get_text(" ", strip=True)
        resp_txt = BeautifulSoup(snippet_obj.get("responsibility") or "", "html.parser").get_text(" ", strip=True)
        combined_snippet = " ".join(x for x in (req, resp_txt) if x).strip()

        pub_dt = parse_iso_or_rfc_date(item.get("published_at", "")) or datetime.now(timezone.utc)
        if pub_dt < cutoff_dt:
            continue

        salary_obj = item.get("salary")
        salary_str = ""
        if salary_obj:
            s_from = salary_obj.get("from")
            s_to = salary_obj.get("to")
            curr = salary_obj.get("currency", "RUR")
            if s_from and s_to:
                salary_str = f" ({s_from}–{s_to} {curr})"
            elif s_from:
                salary_str = f" (от {s_from} {curr})"
            elif s_to:
                salary_str = f" (до {s_to} {curr})"

        match_info = calculate_resume_match(f"{name} {combined_snippet}", role, skills)
        # Поскольку HH уже отфильтровал по поисковому запросу, даём базовый балл
        score = max(15, match_info["score"])
        matched = match_info["matched_skills"] or skills[:2]

        results.append(
            {
                "title": f"{name} — {employer}{salary_str}",
                "url": item.get("alternate_url", "https://hh.ru"),
                "source_title": source.get("title", "Сайт: HeadHunter (hh.ru)"),
                "source_type": "website",
                "published_at": pub_dt,
                "matched_skills": matched,
                "relevance_score": score,
                "snippet": combined_snippet[:220] or f"Вакансия в компании {employer}",
            }
        )

    return results


# =============================================================================
# Международные job-борды: RemoteOK (JSON API) и «ручные» площадки
# =============================================================================

# Базовые адреса площадок, которые закрыты для автопарсинга (Cloudflare/403).
# Шаблон подставляет должность из резюме; для Glassdoor шаблона нет — только база.
MANUAL_BOARD_LINK_TEMPLATES: Dict[str, str] = {
    "https://www.indeed.com/": "https://www.indeed.com/jobs?q={q}&fromage={days}",
    "https://www.ziprecruiter.ie/": "https://www.ziprecruiter.ie/jobs?search={q}",
    "https://www.careerbuilder.com/": "https://www.careerbuilder.com/jobs?keywords={q}",
    "https://wantapply.com/": "https://wantapply.com/?s={q}",
}


def build_manual_board_link(board_url: str, role: str, period_days: int) -> Tuple[str, bool]:
    """Строит ссылку поиска на «ручной» площадке под профиль пользователя.

    Возвращает (url, has_query): has_query=False, если шаблона нет и открывается
    просто главная страница площадки (честно, без угадывания параметров).
    """
    from urllib.parse import quote_plus

    template = MANUAL_BOARD_LINK_TEMPLATES.get(board_url)
    if not template or not role:
        return board_url, False
    return template.format(q=quote_plus(role), days=period_days), True


def parse_remoteok_api(
    json_text: str,
    source: Dict[str, Any],
    role: str,
    skills: List[str],
    cutoff_dt: datetime,
) -> List[Dict[str, Any]]:
    """Парсит открытый JSON API RemoteOK (https://remoteok.com/api)."""
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []

    results: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict) or not item.get("position"):
            continue  # первый элемент списка — юридическое уведомление API

        epoch = item.get("epoch") or 0
        try:
            published_at = datetime.fromtimestamp(float(epoch), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            published_at = datetime.now(timezone.utc)
        if published_at < cutoff_dt:
            continue

        tags = [str(t) for t in (item.get("tags") or [])]
        body = " ".join(
            [
                str(item.get("position", "")),
                str(item.get("company", "")),
                " ".join(tags),
                BeautifulSoup(str(item.get("description", "")), "html.parser").get_text(" ", strip=True),
            ]
        )

        match_info = calculate_resume_match(body, role, skills)
        if match_info["score"] <= 0:
            continue

        title = f"{item.get('position')} — {item.get('company', '')}".strip(" —")
        location = item.get("location") or "Remote"
        snippet_parts = [f"📍 {location}"]
        if item.get("salary_min"):
            snippet_parts.append(f"💰 от ${item.get('salary_min')}")
        if tags:
            snippet_parts.append("🏷 " + ", ".join(tags[:6]))

        results.append(
            {
                "title": title[:95],
                "url": item.get("url") or source.get("canonical_url", ""),
                "source_title": source.get("title", source["canonical_url"]),
                "source_type": "website",
                "published_at": published_at,
                "matched_skills": match_info["matched_skills"],
                "relevance_score": match_info["score"],
                "snippet": " · ".join(snippet_parts)[:220],
            }
        )

    return results


# =============================================================================
# Открытые данные портала «Работа России» (trudvsem.ru, opendata API)
# =============================================================================

TRUDVSEM_API_URL = "https://opendata.trudvsem.ru/api/v1/vacancies"


def parse_trudvsem_api(
    json_text: str,
    source: Dict[str, Any],
    role: str,
    skills: List[str],
    cutoff_dt: datetime,
) -> List[Dict[str, Any]]:
    """Парсит открытый JSON API портала «Работа России» (opendata.trudvsem.ru).

    Источник данных — государственный портал trudvsem.ru (открытые данные,
    https://opendata.trudvsem.ru). Обязательна ссылка на первоисточник — она
    берётся из поля `vac_url`, которое отдаёт сам API.
    """
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return []
    items = ((data.get("results") or {}).get("vacancies") or [])
    if not isinstance(items, list):
        return []

    results: List[Dict[str, Any]] = []
    for item in items:
        vacancy = (item or {}).get("vacancy") or {}
        name = str(vacancy.get("job-name") or "").strip()
        if not name:
            continue

        published_at = (
            parse_iso_or_rfc_date(str(vacancy.get("date_modify") or ""))
            or parse_iso_or_rfc_date(str(vacancy.get("creation-date") or ""))
            or datetime.now(timezone.utc)
        )
        if published_at < cutoff_dt:
            continue

        company = str(((vacancy.get("company") or {}).get("name")) or "Работодатель").strip()
        region = str(((vacancy.get("region") or {}).get("name")) or "").strip()
        duty = str(vacancy.get("duty") or "")
        requirements = str(vacancy.get("requirements") or "")

        salary_min = str(vacancy.get("salary_min") or "").strip()
        salary_max = str(vacancy.get("salary_max") or "").strip()
        salary = ""
        if salary_min and salary_max:
            salary = f" ({salary_min}–{salary_max} ₽)"
        elif salary_min:
            salary = f" (от {salary_min} ₽)"
        elif salary_max:
            salary = f" (до {salary_max} ₽)"

        match_info = calculate_resume_match(f"{name} {duty} {requirements}", role, skills)
        # API уже отфильтровал выдачу по поисковому запросу — даём базовый балл
        score = max(15, match_info["score"])
        matched = match_info["matched_skills"] or skills[:2]

        snippet_parts = []
        if region:
            snippet_parts.append(f"📍 {region}")
        if vacancy.get("employment"):
            snippet_parts.append(str(vacancy["employment"]))
        text = (duty or requirements or "").replace("\n", " ").strip()
        if text:
            snippet_parts.append(text[:120])

        results.append(
            {
                "title": f"{name} — {company}{salary}"[:120],
                "url": str(vacancy.get("vac_url") or source.get("canonical_url", "")),
                "source_title": source.get("title", "Сайт: Работа России (trudvsem.ru API)"),
                "source_type": "website",
                "published_at": published_at,
                "matched_skills": matched,
                "relevance_score": score,
                "snippet": " · ".join(snippet_parts)[:220] or f"Вакансия в компании {company}",
            }
        )

    return results


async def _fetch_trudvsem_api_vacancies(
    session: aiohttp.ClientSession,
    source: Dict[str, Any],
    role: str,
    skills: List[str],
    period_days: int,
    cutoff_dt: datetime,
) -> List[Dict[str, Any]]:
    """Запрашивает открытые данные «Работа России» по должности из резюме."""
    # Тот же принцип: у «Работы России» поиск строго по словам, поэтому
    # запрос строится по должности, а навыки используются только для ранжирования.
    query_parts = [role] if role and role != "Специалист" else []
    if not query_parts:
        query_parts = skills[:2]
    search_query = " ".join(query_parts).strip() or "менеджер"

    params = {"text": search_query, "offset": "0", "limit": "20"}
    try:
        async with session.get(
            TRUDVSEM_API_URL, params=params, headers=DEFAULT_HEADERS
        ) as resp:
            if resp.status != 200:
                return []
            body = await resp.text(errors="ignore")
    except Exception:  # noqa: BLE001 — сбой источника не ломает общий поиск
        return []

    return parse_trudvsem_api(
        json_text=body,
        source=source,
        role=role,
        skills=skills,
        cutoff_dt=cutoff_dt,
    )


async def _parse_single_source(
    session: aiohttp.ClientSession,
    source: Dict[str, Any],
    role: str,
    skills: List[str],
    period_days: int,
    cutoff_dt: datetime,
    issues: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Парсит один источник из базы данных (ТГ-канал или веб-сайт).

    Если источник не удалось прочитать (закрыто веб-превью, HTTP-ошибка, сеть),
    в список `issues` добавляется запись с причиной — она показывается пользователю,
    чтобы «пустая выдача» не выглядела как «вакансий нет».
    """
    parse_url = source.get("parse_url", "")
    source_type = source.get("source_type", "website")

    # «Ручные» площадки (Indeed, Glassdoor, ZipRecruiter…) закрыты Cloudflare —
    # их не парсим, но показываем пользователю готовые ссылки поиска.
    if source_type == "manual":
        return []

    def _report(reason: str) -> None:
        if issues is not None:
            issues.append(
                {
                    "title": source.get("title", parse_url),
                    "url": source.get("canonical_url", parse_url),
                    "reason": reason,
                }
            )

    try:
        # 1. Если это API HeadHunter
        if "api.hh.ru/vacancies" in parse_url:
            return await _fetch_hh_api_vacancies(
                session=session,
                source=source,
                role=role,
                skills=skills,
                period_days=period_days,
                cutoff_dt=cutoff_dt,
                issues=issues,
            )

        # 2. Открытые данные «Работа России» (trudvsem.ru) — JSON API с параметрами
        if "opendata.trudvsem.ru/api/v1/vacancies" in parse_url:
            return await _fetch_trudvsem_api_vacancies(
                session=session,
                source=source,
                role=role,
                skills=skills,
                period_days=period_days,
                cutoff_dt=cutoff_dt,
            )

        # 3. Загружаем страницу ТГ-канала (t.me/s/...) или сайта
        async with session.get(parse_url, headers=DEFAULT_HEADERS) as resp:
            if resp.status != 200:
                _report(f"HTTP {resp.status}")
                return []
            body = await resp.text(errors="ignore")

        # JSON API (RemoteOK): отдаётся список объектов, а не HTML
        if source_type == "json_api" or body.lstrip()[:1] == "[":
            return parse_remoteok_api(
                json_text=body,
                source=source,
                role=role,
                skills=skills,
                cutoff_dt=cutoff_dt,
            )

        if source_type == "tg_channel" or "t.me/s/" in parse_url:
            # Канал может быть закрыт для публичного веб-превью (владелец отключил ленту):
            # тогда t.me/s/ отдаёт страницу-визитку без сообщений.
            if "tgme_widget_message" not in body:
                _report(
                    "канал не отдаёт публичное веб-превью — автопоиск невозможен, "
                    "проверьте вручную по ссылке"
                )
                return []
            return parse_telegram_channel_html(
                html=body,
                source=source,
                role=role,
                skills=skills,
                cutoff_dt=cutoff_dt,
            )

        # Проверяем, является ли ответ RSS/Atom XML
        if "<rss" in body[:500].lower() or "<feed" in body[:500].lower() or parse_url.endswith("rss"):
            return parse_rss_or_xml_feed(
                xml_text=body,
                source=source,
                role=role,
                skills=skills,
                cutoff_dt=cutoff_dt,
            )

        return parse_generic_website_html(
            html=body,
            source=source,
            role=role,
            skills=skills,
            cutoff_dt=cutoff_dt,
        )
    except Exception as exc:  # noqa: BLE001 — сбой одного источника не ломает поиск
        _report(f"ошибка загрузки ({exc.__class__.__name__})")
        return []


async def search_vacancies_by_resume(
    db: Database,
    user_id: int,
    period_days: int = 7,
) -> Dict[str, Any]:
    """Основная функция парсинга и поиска вакансий по резюме за заданный период.

    Параметры:
    - period_days: 1 (1 день), 7 (1 неделя), 30 (1 месяц).
    """
    if period_days not in (1, 7, 30):
        period_days = 7

    resume = await db.get_resume(user_id)
    if not resume:
        raise ValueError(
            "Резюме не найдено! Сначала загрузите резюме через меню «📤 Загрузить резюме»."
        )

    role: str = (resume.get("extracted_role") or "").strip()
    skills: List[str] = resume.get("extracted_skills") or []

    if not role and not skills:
        raise ValueError(
            "В профиле резюме не определена ни должность, ни навыки — искать не по чему.\n"
            "Укажите их вручную:\n"
            "• `/set_role Коммерческий директор`\n"
            "• `/set_skills P&L, Excel, CRM, 1C`\n"
            "или пересоберите профиль командой `/reset_profile`."
        )
    sources = await db.list_sources(active_only=True)

    now_utc = datetime.now(timezone.utc)
    cutoff_dt = now_utc - timedelta(days=period_days)

    manual_sources: List[Dict[str, Any]] = [
        {
            "title": src.get("title", src.get("canonical_url", "")),
            "url": src.get("canonical_url", ""),
        }
        for src in sources
        if src.get("source_type") == "manual"
    ]

    source_issues: List[Dict[str, Any]] = []
    timeout = aiohttp.ClientTimeout(total=config.http_timeout)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [
            _parse_single_source(
                session=session,
                source=src,
                role=role,
                skills=skills,
                period_days=period_days,
                cutoff_dt=cutoff_dt,
                issues=source_issues,
            )
            for src in sources
        ]
        nested_results = await asyncio.gather(*tasks, return_exceptions=True)

    all_vacancies: List[Dict[str, Any]] = []
    seen_links = set()
    excluded_breakdown: Dict[str, int] = {}

    for res in nested_results:
        if isinstance(res, list):
            for vac in res:
                url = vac.get("url", "")
                if not url or url in seen_links:
                    continue
                # «Рекомендуем кандидата …» / «Резюме …» — это резюме кандидата, а не вакансия
                reason = vacancy_exclusion_reason(vac)
                if reason:
                    excluded_breakdown[reason] = excluded_breakdown.get(reason, 0) + 1
                    continue
                seen_links.add(url)
                all_vacancies.append(vac)

    # Сортируем по релевантности резюме и свежести даты публикации
    all_vacancies.sort(
        key=lambda v: (v.get("relevance_score", 0), v.get("published_at", cutoff_dt)),
        reverse=True,
    )

    page_size = config.max_vacancies_per_message
    return {
        "period_days": period_days,
        "period_label": PERIOD_LABELS.get(period_days, f"{period_days} дн."),
        "role": role,
        "skills": skills,
        "sources_checked": len(sources),
        "total_found": len(all_vacancies),
        # полный список хранится в результате: листать «Показать ещё» можно без повторного парсинга
        "all_vacancies": all_vacancies,
        "page_size": page_size,
        "vacancies": all_vacancies[:page_size],
        "excluded_count": sum(excluded_breakdown.values()),
        "excluded_breakdown": excluded_breakdown,
        "excluded_reason": "посты-резюме кандидатов — это не вакансии",
        "source_issues": source_issues,
        "manual_sources": manual_sources,
    }


def _format_source_issues(issues: List[Dict[str, Any]], limit: int = 5) -> str:
    """Формирует блок предупреждений о источниках, которые не удалось прочитать."""
    if not issues:
        return ""
    lines = ["", "━━━━━━━━━━━━━━━━━━━━", "⚠️ **Часть источников не удалось прочитать:**"]
    for issue in issues[:limit]:
        lines.append(
            f"• {escape_markdown(issue['title'])} — {escape_markdown(issue['reason'])}"
        )
        if issue.get("url"):
            # URL печатается обычным текстом (не ссылкой), поэтому `_` и `*` в нём
            # надо экранировать — иначе Telegram «съест» их как разметку.
            lines.append(f"  🔗 {escape_markdown(issue['url'])}")
    if len(issues) > limit:
        lines.append(f"• …и ещё {len(issues) - limit}")
    return "\n".join(lines) + "\n"


def _format_manual_boards(
    manual_sources: List[Dict[str, Any]],
    role: str,
    period_days: int,
    limit: int = 12,
) -> str:
    """Блок ссылок на площадки, которые нельзя парсить (Indeed, Glassdoor, Avito…)."""
    if not manual_sources:
        return ""
    lines = [
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "🌍 **Международные job-борды и площадки для ручного поиска:**",
        "_Эти площадки закрыты для автопарсинга (Cloudflare/403) или отдают вакансии "
        "только через JavaScript. Ссылки подставлены под ваш профиль:_",
    ]
    for board in manual_sources[:limit]:
        name = escape_markdown(board["title"].replace("Сайт: ", "").split(" (")[0])
        url, has_query = build_manual_board_link(board["url"], role, period_days)
        hint = "" if has_query else " _(введите должность в строке поиска)_"
        lines.append(f"• **{name}** — [открыть поиск]({url}){hint}")
    if len(manual_sources) > limit:
        lines.append(
            f"• …и ещё {len(manual_sources) - limit} площадок — полный список в `/find_resources`"
        )
    return "\n".join(lines) + "\n"


def format_vacancies_search_blocks(
    search_result: Dict[str, Any],
    offset: int = 0,
    limit: Optional[int] = None,
) -> Tuple[str, str]:
    """Формирует сообщение поиска вакансий как два блока: (основная часть, подвал).

    ``offset``/``limit`` задают «страницу» выдачи: нумерация вакансий сквозная,
    поэтому по кнопке «Показать ещё» список продолжается, а не начинается заново.

    Подвал (предупреждения об источниках, международные борды и обязательный
    дисклеймер) выносится отдельно, чтобы при разбиении длинного списка на части
    дисклеймер гарантированно доходил до пользователя.
    """
    period_label = search_result["period_label"]
    role = search_result["role"]
    skills = search_result["skills"]
    sources_checked = search_result["sources_checked"]
    total_found = search_result["total_found"]
    manual_sources = search_result.get("manual_sources") or []

    all_items: List[Dict[str, Any]] = (
        search_result.get("all_vacancies") or search_result.get("vacancies") or []
    )
    page_size = limit if limit is not None else int(
        search_result.get("page_size") or config.max_vacancies_per_message
    )
    offset = max(0, min(offset, len(all_items)))
    vacancies = all_items[offset: offset + page_size] if page_size > 0 else all_items[offset:]
    shown_from = offset + 1 if vacancies else 0
    shown_to = offset + len(vacancies)

    skills_preview = ", ".join(skills[:8]) if skills else "по профилю резюме"
    manual_note = f" (в т.ч. ручной поиск: {len(manual_sources)})" if manual_sources else ""

    if vacancies and total_found > len(vacancies):
        page_note = f" (показаны {shown_from}–{shown_to} из {len(all_items)})"
    else:
        page_note = " (показаны все)" if vacancies else ""

    excluded_count = int(search_result.get("excluded_count") or 0)
    excluded_note = ""
    if excluded_count:
        breakdown = search_result.get("excluded_breakdown") or {}
        if breakdown:
            details = ", ".join(
                f"{count} — {escape_markdown(reason)}" for reason, count in breakdown.items()
            )
            excluded_note = (
                f"🚫 **Отфильтровано постов-резюме:** {excluded_count} ({details})\n"
            )
        else:
            excluded_note = (
                f"🚫 **Отфильтровано постов-резюме:** {excluded_count} "
                "(«Рекомендуем кандидата …», «Резюме …»)\n"
            )

    header = (
        f"🔍 **Результаты поиска вакансий за {period_label}**\n"
        f"👤 **Профиль резюме:** {escape_markdown(role) if role else 'не указана (задайте `/set_role`)'}\n"
        f"🛠 **Ключевые навыки:** {escape_markdown(skills_preview)}\n"
        f"📡 **Проверено источников в БД:** {sources_checked}{manual_note}\n"
        f"📊 **Найдено подходящих вакансий:** {total_found}{page_note}\n"
        f"{excluded_note}"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )

    issues_block = _format_source_issues(search_result.get("source_issues") or [])
    boards_block = _format_manual_boards(
        manual_sources,
        role=role,
        period_days=search_result.get("period_days", 7),
    )
    is_last_page = offset + len(vacancies) >= len(all_items)
    if offset == 0 or is_last_page:
        footer = issues_block + boards_block + f"\n_{LINKS_DISCLAIMER}_"
    else:
        footer = ""

    if not vacancies:
        body = (
            header
            + "\nℹ️ За выбранный период подходящих вакансий по вашим ключевым словам не обнаружено.\n"
            "💡 Попробуйте выбрать больший период (например, **1 неделю** или **1 месяц**) "
            "или добавьте новые профильные Telegram-каналы и сайты в раздел «🌐 Источники вакансий»."
        )
        return body, footer

    items_blocks: List[str] = []
    for idx, vac in enumerate(vacancies, start=shown_from or 1):
        pub_dt: datetime = vac["published_at"]
        date_str = pub_dt.strftime("%d.%m.%Y %H:%M UTC")
        matched = ", ".join(vac.get("matched_skills") or []) or "профиль должности"
        icon = "📢" if vac.get("source_type") == "tg_channel" else "🌐"

        block = (
            f"**{idx}. {escape_markdown(vac['title'])}**\n"
            f"{icon} **Источник:** {escape_markdown(vac['source_title'])}\n"
            f"🕒 **Дата:** {date_str}\n"
            f"✅ **Совпадения с резюме:** {escape_markdown(matched)}\n"
            f"📝 _{escape_markdown(vac.get('snippet', ''))}_\n"
            f"🔗 [Перейти к вакансии]({vac['url']})"
        )
        items_blocks.append(block)

    return header + "\n\n".join(items_blocks), footer


def format_vacancies_search_message(
    search_result: Dict[str, Any], offset: int = 0, limit: Optional[int] = None
) -> str:
    """Единое сообщение со списком вакансий (основная часть + подвал с дисклеймером)."""
    body, footer = format_vacancies_search_blocks(search_result, offset=offset, limit=limit)
    return f"{body}\n{footer}".strip()
