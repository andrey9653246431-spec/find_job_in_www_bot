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
from email.utils import parsedate_to_datetime
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup
from bot.config import config
from bot.database import Database

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

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        title_line = lines[0][:95] if lines else "Вакансия из Telegram-канала"
        snippet = " ".join(lines[1:4])[:220] if len(lines) > 1 else raw_text[:220]

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
) -> List[Dict[str, Any]]:
    """Запрашивает вакансии через бесплатный открытый API HeadHunter (api.hh.ru/vacancies)."""
    query_parts = [role] if role and role != "Специалист" else []
    if skills:
        query_parts.extend(skills[:3])
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


async def _parse_single_source(
    session: aiohttp.ClientSession,
    source: Dict[str, Any],
    role: str,
    skills: List[str],
    period_days: int,
    cutoff_dt: datetime,
) -> List[Dict[str, Any]]:
    """Парсит один источник из базы данных (ТГ-канал или веб-сайт)."""
    parse_url = source.get("parse_url", "")
    source_type = source.get("source_type", "website")

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
            )

        # 2. Загружаем страницу ТГ-канала (t.me/s/...) или сайта
        async with session.get(parse_url, headers=DEFAULT_HEADERS) as resp:
            if resp.status != 200:
                return []
            body = await resp.text(errors="ignore")

        if source_type == "tg_channel" or "t.me/s/" in parse_url:
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
    except Exception:
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

    role: str = resume.get("extracted_role") or "Специалист"
    skills: List[str] = resume.get("extracted_skills") or []
    sources = await db.list_sources(active_only=True)

    now_utc = datetime.now(timezone.utc)
    cutoff_dt = now_utc - timedelta(days=period_days)

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
            )
            for src in sources
        ]
        nested_results = await asyncio.gather(*tasks, return_exceptions=True)

    all_vacancies: List[Dict[str, Any]] = []
    seen_links = set()

    for res in nested_results:
        if isinstance(res, list):
            for vac in res:
                url = vac.get("url", "")
                if url and url not in seen_links:
                    seen_links.add(url)
                    all_vacancies.append(vac)

    # Сортируем по релевантности резюме и свежести даты публикации
    all_vacancies.sort(
        key=lambda v: (v.get("relevance_score", 0), v.get("published_at", cutoff_dt)),
        reverse=True,
    )

    return {
        "period_days": period_days,
        "period_label": PERIOD_LABELS.get(period_days, f"{period_days} дн."),
        "role": role,
        "skills": skills,
        "sources_checked": len(sources),
        "total_found": len(all_vacancies),
        "vacancies": all_vacancies[: config.max_vacancies_per_message],
    }


def format_vacancies_search_message(search_result: Dict[str, Any]) -> str:
    """Форматирует сообщение со списком найденных вакансий по результатам поиска."""
    period_label = search_result["period_label"]
    role = search_result["role"]
    skills = search_result["skills"]
    sources_checked = search_result["sources_checked"]
    vacancies = search_result["vacancies"]
    total_found = search_result["total_found"]

    skills_preview = ", ".join(skills[:8]) if skills else "по профилю резюме"

    header = (
        f"🔍 **Результаты поиска вакансий за {period_label}**\n"
        f"👤 **Профиль резюме:** {role}\n"
        f"🛠 **Ключевые навыки:** {skills_preview}\n"
        f"📡 **Проверено источников в БД:** {sources_checked}\n"
        f"📊 **Найдено подходящих вакансий:** {total_found}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )

    if not vacancies:
        return (
            header
            + "\nℹ️ За выбранный период подходящих вакансий по вашим ключевым словам не обнаружено.\n"
            "💡 Попробуйте выбрать больший период (например, **1 неделю** или **1 месяц**) "
            "или добавьте новые профильные Telegram-каналы и сайты в раздел «🌐 Источники вакансий»."
        )

    items_blocks: List[str] = []
    for idx, vac in enumerate(vacancies, start=1):
        pub_dt: datetime = vac["published_at"]
        date_str = pub_dt.strftime("%d.%m.%Y %H:%M UTC")
        matched = ", ".join(vac.get("matched_skills") or []) or "профиль должности"
        icon = "📢" if vac.get("source_type") == "tg_channel" else "🌐"

        block = (
            f"**{idx}. {vac['title']}**\n"
            f"{icon} **Источник:** {vac['source_title']}\n"
            f"🕒 **Дата:** {date_str}\n"
            f"✅ **Совпадения с резюме:** {matched}\n"
            f"📝 _{vac.get('snippet', '')}_\n"
            f"🔗 [Перейти к вакансии]({vac['url']})"
        )
        items_blocks.append(block)

    return header + "\n\n".join(items_blocks)
