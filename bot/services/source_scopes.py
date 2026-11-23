"""Области поиска вакансий: где именно искать.

Пользователь выбирает в меню поиска одну из четырёх областей:

- ``telegram`` — только Telegram-каналы из базы;
- ``web``      — только сайты и агрегаторы вакансий (hh.ru, Хабр Карьера,
                 RemoteOK, «Работа России», международные борды);
- ``career``   — только карьерные страницы компаний (career./job./rabota.
                 домены, разделы /career, /vacancies на сайтах работодателей);
- ``all``      — везде (все активные источники базы).

Модуль только классифицирует источники и фильтрует их. Сам парсинг остаётся
в ``bot/services/vacancy_parser.py``.
"""
from typing import Any, Dict, Iterable, List
import re
from urllib.parse import urlparse

SCOPE_ALL = "all"
SCOPE_TELEGRAM = "telegram"
SCOPE_WEB = "web"
SCOPE_CAREER = "career"

SCOPES: tuple = (SCOPE_ALL, SCOPE_TELEGRAM, SCOPE_WEB, SCOPE_CAREER)
DEFAULT_SCOPE = SCOPE_ALL

SCOPE_LABELS: Dict[str, str] = {
    SCOPE_ALL: "везде (Telegram + сайты и агрегаторы + карьерные страницы)",
    SCOPE_TELEGRAM: "только Telegram-каналы",
    SCOPE_WEB: "только сайты и агрегаторы вакансий",
    SCOPE_CAREER: "только карьерные страницы компаний",
}

SCOPE_SHORT_LABELS: Dict[str, str] = {
    SCOPE_ALL: "Везде",
    SCOPE_TELEGRAM: "Telegram",
    SCOPE_WEB: "Сайты и агрегаторы",
    SCOPE_CAREER: "Карьерные страницы",
}

# Агрегаторы и борды: даже если в домене есть «career»/«job» (career.habr.com,
# budu.jobs), это НЕ карьерная страница одной компании, а агрегатор вакансий.
AGGREGATOR_HOSTS = (
    "recruitmaster.net",
    "hh.ru",
    "trudvsem.ru",
    "career.habr.com",
    "habr.com",
    "geekjob.ru",
    "budu.jobs",
    "remote-job.ru",
    "remoteok.com",
    "weworkremotely.com",
    "jobspresso.co",
    "indeed.com",
    "glassdoor.com",
    "linkedin.com",
    "ziprecruiter.com",
    "careerbuilder.com",
    "avito.ru",
    "superjob.ru",
    "rabota.ru",
    "zarplata.ru",
    "gorodrabot.ru",
    "jooble.org",
    "talent.com",
    "getmatch.ru",
    "wellfound.com",
    "ycombinator.com",
)

# Поддомены/пути, характерные для карьерных страниц работодателей:
# career.company.ru, job.company.ru, rabota.company.ru, company.ru/career/vacancies
CAREER_HOST_PREFIXES = ("career.", "careers.", "job.", "jobs.", "rabota.", "kariera.", "hr.")
CAREER_PATH_RE = re.compile(
    r"/(career|careers|job|jobs|vacanc|vacancies|vakansii|rabota|kariera)(/|$|\.)",
    re.IGNORECASE,
)
CAREER_TITLE_RE = re.compile(
    r"(карьерн\w*\s+страниц|карьера\s*:|работа\s+в\s+|вакансии\s+компании|"
    r"карьера\s+в\s+компании|career\s+page)",
    re.IGNORECASE,
)


def normalize_scope(scope: str | None) -> str:
    """Приводит значение из callback-данных к известной области поиска."""
    value = (scope or "").strip().lower()
    return value if value in SCOPES else DEFAULT_SCOPE


def scope_label(scope: str | None) -> str:
    """Человекочитаемое название области поиска для сообщений бота."""
    return SCOPE_LABELS.get(normalize_scope(scope), SCOPE_LABELS[DEFAULT_SCOPE])


def _host_and_path(url: str) -> tuple:
    try:
        parsed = urlparse((url or "").strip())
    except ValueError:
        return "", ""
    return (parsed.netloc or "").lower(), (parsed.path or "").lower()


def is_aggregator_host(host: str) -> bool:
    """Домен относится к агрегатору вакансий (hh.ru, career.habr.com, …)."""
    host = (host or "").lower().removeprefix("www.")
    return any(host == item or host.endswith("." + item) for item in AGGREGATOR_HOSTS)


def classify_source_scope(source: Dict[str, Any]) -> str:
    """Определяет область поиска для одного источника из базы.

    Возвращает ``telegram`` / ``web`` / ``career``.
    """
    source_type = str(source.get("source_type") or "").lower()
    canonical_url = str(source.get("canonical_url") or "")
    parse_url = str(source.get("parse_url") or canonical_url)
    title = str(source.get("title") or "")

    if source_type == "tg_channel" or "t.me/" in parse_url or "t.me/" in canonical_url:
        return SCOPE_TELEGRAM

    # «Ручные» борды (Indeed, Glassdoor…) и JSON API агрегаторов — это сеть/агрегаторы
    if source_type in ("manual", "json_api"):
        return SCOPE_WEB

    host, path = _host_and_path(canonical_url or parse_url)
    if is_aggregator_host(host):
        return SCOPE_WEB

    if source_type == "career":
        return SCOPE_CAREER

    if host.startswith(CAREER_HOST_PREFIXES) or CAREER_PATH_RE.search(path):
        return SCOPE_CAREER

    if CAREER_TITLE_RE.search(title):
        return SCOPE_CAREER

    return SCOPE_WEB


def filter_sources_by_scope(
    sources: Iterable[Dict[str, Any]], scope: str | None
) -> List[Dict[str, Any]]:
    """Оставляет только источники выбранной области поиска."""
    scope = normalize_scope(scope)
    if scope == SCOPE_ALL:
        return list(sources)
    return [src for src in sources if classify_source_scope(src) == scope]


def count_sources_by_scope(sources: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """Сколько источников в базе относится к каждой области поиска."""
    counts = {SCOPE_ALL: 0, SCOPE_TELEGRAM: 0, SCOPE_WEB: 0, SCOPE_CAREER: 0}
    for src in sources:
        counts[classify_source_scope(src)] += 1
        counts[SCOPE_ALL] += 1
    return counts


def scope_hint(scope: str | None) -> str:
    """Короткая подсказка, если в выбранной области нет источников."""
    scope = normalize_scope(scope)
    return {
        SCOPE_TELEGRAM: "В базе нет активных Telegram-каналов.",
        SCOPE_WEB: "В базе нет активных сайтов и агрегаторов вакансий.",
        SCOPE_CAREER: (
            "В базе нет карьерных страниц компаний. Их можно добавить в разделе "
            "«🌐 Источники вакансий» — например https://team.vk.company/vacancy/"
        ),
    }.get(scope, "")
