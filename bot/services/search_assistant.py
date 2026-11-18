"""Алгоритм поиска информационных ресурсов для поиска работы (HR-ассистент бота).

Реализует правила из требований:
1. Определение типа поиска по запросу пользователя:
   - «Telegram-каналы / ТГ-каналы / чаты» → ссылки `https://t.me/username` + тематика канала;
   - «агрегаторы / сайты с вакансиями / площадки» → job-борды и агрегаторы;
   - «компании / ТОП-100 / карьерные страницы» → структурированный список компаний;
   - иначе (профессия, например «HR-менеджер») → советы и deep-links агрегаторов с фильтрами.
2. Структурированный вывод в Markdown по блокам (более 15–20 позиций — разбиваем на блоки).
3. Для каждого пункта: название, прямая ссылка, короткое описание.
4. Запрет галлюцинаций: ссылки берутся только из проверенного каталога
   `bot/services/resource_catalog.py`, а для компаний без подтверждённой карьерной
   страницы используется документированный поиск hh.ru.
5. Обязательный дисклеймер в конце и предупреждение при запросе > 50 компаний.
"""
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from bot.services.resource_catalog import (
    AGGREGATORS,
    COMPANIES,
    LINK_WARNING,
    LINKS_DISCLAIMER,
    MAX_COMPANIES_PER_REQUEST,
    MAX_ITEMS_PER_BLOCK,
    MESSAGE_CHUNK_SIZE,
    TELEGRAM_CHANNELS,
    TELEGRAM_SEARCH_HINT,
    _company_vacancies_url,
    _verified_tg_url,
    get_aggregators,
    get_companies,
    get_industries,
    get_telegram_channels,
    hh_search_url,
)

# Типы поиска
SEARCH_TYPE_TELEGRAM = "telegram_channels"
SEARCH_TYPE_AGGREGATORS = "aggregators"
SEARCH_TYPE_COMPANIES = "companies"
SEARCH_TYPE_PROFESSION = "profession"
SEARCH_TYPE_MIXED = "mixed"

SEARCH_TYPE_TITLES = {
    SEARCH_TYPE_TELEGRAM: "📱 Telegram-каналы",
    SEARCH_TYPE_AGGREGATORS: "🌐 Сайты-агрегаторы и job-борды",
    SEARCH_TYPE_COMPANIES: "🏢 Компании и карьерные страницы",
    SEARCH_TYPE_PROFESSION: "🎯 Поиск вакансий по профессии",
    SEARCH_TYPE_MIXED: "📱 Telegram-каналы + 🌐 Агрегаторы",
}


# =============================================================================
# 1. ОПРЕДЕЛЕНИЕ ТИПА ПОИСКА
# =============================================================================

_TELEGRAM_MARKERS = (
    "telegram", "телеграм", "телега", "тг-канал", "тг канал", "тг-каналы", "тг каналы",
    "тг", "канал", "каналы", "чат", "чаты", "t.me",
)
_AGGREGATOR_MARKERS = (
    "агрегатор", "агрегаторы", "сайт с вакансиями", "сайты с вакансиями", "сайт", "сайты",
    "job-борд", "джоб-борд", "борд", "площадк", "hh", "хедхантер", "headhunter", "хабр",
    "зарплата.ру", "работа.ру", "суперджоб", "superjob", "hirify", "getmatch", "geekjob",
    "где искать", "где искать работу", "ресурсы", "источники",
)
_COMPANY_MARKERS = (
    "компани", "компании", "работодател", "карьерн", "карьера", "топ-100", "топ 100",
    "топ-500", "топ 500", "топ-1000", "топ 1000", "крупнейшие", "корпораци", "career",
)


def detect_search_intent(query: str) -> str:
    """Определяет тип поиска по тексту запроса пользователя.

    Приоритет: Telegram-каналы → компании → агрегаторы → поиск по профессии.
    """
    text = (query or "").lower()
    has_telegram = any(marker in text for marker in _TELEGRAM_MARKERS)
    has_aggregator = any(marker in text for marker in _AGGREGATOR_MARKERS)
    has_company = any(marker in text for marker in _COMPANY_MARKERS)

    # Смешанный запрос: «ТГ-каналы и агрегаторы» — показываем оба блока
    if has_telegram and has_aggregator and not has_company:
        return SEARCH_TYPE_MIXED
    if has_telegram:
        return SEARCH_TYPE_TELEGRAM
    if any(marker in text for marker in _COMPANY_MARKERS):
        return SEARCH_TYPE_COMPANIES
    if any(marker in text for marker in _AGGREGATOR_MARKERS):
        return SEARCH_TYPE_AGGREGATORS
    return SEARCH_TYPE_PROFESSION


def extract_company_limit(query: str) -> Optional[int]:
    """Извлекает лимит компаний из запроса («ТОП-100 компаний», «дай 30 компаний»)."""
    match = re.search(r"(?:топ[-\s]?)?(\d{1,4})\s*(?:компани|компаний|работодател)", query or "", re.I)
    if match:
        return int(match.group(1))
    match_top = re.search(r"топ[-\s]?(\d{1,4})", query or "", re.I)
    if match_top:
        return int(match_top.group(1))
    return None


# Порядок важен: сначала узкие отрасли, IT — последним (короткие маркеры вроде «it»/«ит»
# иначе ложно срабатывают внутри слов «ритейл», «маркетплейс» и т.п.)
_INDUSTRY_MARKERS: List[tuple] = [
    ("Ритейл и e-commerce", ("ритейл", "retail", "e-commerce", "ecommerce", "маркетплейс", "магазин", "торгов")),
    ("Банки и финансы", ("банк", "финанс", "fintech", "финтех", "страхов", "инвест")),
    ("Фарма и медицина", ("фарм", "медицин", "клиник", "лаборатор", "здравоохран")),
    ("Логистика и транспорт", ("логист", "транспорт", "доставк", "перевоз", "склад")),
    ("Промышленность и энергетика", ("промышлен", "энергет", "нефт", "газ", "металл", "добыч", "производствен")),
    ("FMCG и производство", ("fmcg", "пищев", "напит", "продуктов")),
    ("IT и Телеком", ("it", "ит", "телеком", "техно", "разработ", "софт", "digital", "интернет")),
]


def detect_industry(query: str) -> Optional[str]:
    """Определяет отрасль из запроса («компании ритейла» → «Ритейл и e-commerce»).

    Короткие маркеры («it», «ит», «газ») проверяются по границе слова, чтобы не
    срабатывать внутри других слов.
    """
    text = (query or "").lower()
    for industry, markers in _INDUSTRY_MARKERS:
        for marker in markers:
            if len(marker) <= 3:
                if re.search(rf"(?<![\wа-яё]){re.escape(marker)}(?![\wа-яё])", text):
                    return industry
            elif marker in text:
                return industry
    return None


# =============================================================================
# 2. ФОРМИРОВАНИЕ БЛОКОВ В MARKDOWN
# =============================================================================

def format_telegram_channels_block(query: str = "") -> str:
    """Блок «Telegram-каналы» в формате `[Название](https://t.me/username) | *описание*`."""
    channels = get_telegram_channels()
    lines: List[str] = [
        "### 📱 Telegram-каналы с вакансиями",
        "",
    ]
    for idx, channel in enumerate(channels[:MAX_ITEMS_PER_BLOCK], start=1):
        url = _verified_tg_url(channel["username"])
        warning = "" if channel.get("verified", True) else f" _{LINK_WARNING}_"
        lines.append(
            f"{idx}. **[{channel['name']}]({url})** | _{channel['topic']}_ | "
            f"*{channel['description']}*{warning}"
        )
    lines.extend(["", f"💡 {TELEGRAM_SEARCH_HINT}"])
    return "\n".join(lines)


def format_aggregators_block(query: str = "") -> str:
    """Блок «Сайты-агрегаторы» с прямой ссылкой и описанием каждого ресурса."""
    aggregators = get_aggregators()
    lines: List[str] = [
        "### 🌐 Сайты-агрегаторы и job-борды",
        "",
    ]
    for idx, aggregator in enumerate(aggregators[:MAX_ITEMS_PER_BLOCK], start=1):
        warning = "" if aggregator.get("verified", True) else f" _{LINK_WARNING}_"
        lines.append(
            f"{idx}. **{aggregator['name']}** — [{aggregator['url']}]({aggregator['url']}) | "
            f"*{aggregator['description']}*{warning}"
        )
    return "\n".join(lines)


_INDUSTRY_ICONS = {
    "IT и Телеком": "💻",
    "Банки и финансы": "🏦",
    "Ритейл и e-commerce": "🛒",
    "Промышленность и энергетика": "🏭",
    "Логистика и транспорт": "🚚",
    "FMCG и производство": "🥫",
    "Фарма и медицина": "💊",
}


def format_companies_blocks(limit: Optional[int] = None, industry: Optional[str] = None) -> str:
    """Структурированный список компаний по отраслям: сайт + вакансии + описание."""
    companies = get_companies(industry=industry, limit=limit)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for company in companies:
        grouped.setdefault(company["industry"], []).append(company)

    blocks: List[str] = []
    counter = 0
    for industry_name in get_industries():
        if industry_name not in grouped:
            continue
        icon = _INDUSTRY_ICONS.get(industry_name, "🏢")
        blocks.append(f"### {icon} {industry_name}")
        blocks.append("")
        for company in grouped[industry_name]:
            counter += 1
            career_url = _company_vacancies_url(company)
            career_label = "Карьера" if company.get("career_url") else "Вакансии на hh.ru"
            note = "" if company.get("career_url") else f" _{LINK_WARNING}_"
            blocks.append(
                f"{counter}. **{company['name']}** — [{company['site']}]({company['site']}) | "
                f"[{career_label}]({career_url}) | *{company['description']}*{note}"
            )
        blocks.append("")
    return "\n".join(blocks).strip()


def format_profession_block(query: str) -> str:
    """Deep-links агрегаторов с фильтрами под конкретную профессию + советы."""
    profession = (query or "").strip() or "ваша профессия"
    quoted = quote(profession, safe="")
    lines: List[str] = [
        f"### 🎯 Поиск вакансий по запросу «{profession}»",
        "",
        "Прямой перебор тысяч сайтов неэффективен — используйте агрегаторы с фильтрами:",
        "",
        f"1. **hh.ru** — [Открыть поиск «{profession}»]({hh_search_url(profession)}) | "
        "*самая большая база, фильтры по зарплате, опыту и компании.*",
        f"2. **Хабр Карьера** — [Открыть поиск](https://career.habr.com/vacancies?q={quoted}) | "
        "*IT и диджитал, прозрачные вилки.*",
        f"3. **SuperJob** — [Открыть поиск](https://www.superjob.ru/vacancy/search/?keywords={quoted}) | "
        "*подписка на новые вакансии по запросу.*",
        f"4. **hirify.me** — [hirify.me](https://hirify.me) | "
        f"*нишевый агрегатор: введите «{profession}» в строку поиска на сайте.*",
        f"5. **getmatch** — [getmatch.ru/vacancies](https://getmatch.ru/vacancies) | "
        "*IT-вакансии с вилками и персональным мэтчингом.*",
        "",
        f"💡 В Telegram ищите каналы по словам «{profession} вакансии» и «{profession} удалённо» "
        "через вкладку «Каналы» — так находятся живые нишевые каналы.",
    ]
    return "\n".join(lines)


# =============================================================================
# 3. СБОРКА ОТВЕТА ПО ТИПУ ПОИСКА
# =============================================================================

def build_resources_answer(query: str, search_type: Optional[str] = None) -> Dict[str, Any]:
    """Собирает готовый ответ бота по правилам HR-ассистента.

    Возвращает словарь:
    - `search_type` — определённый тип поиска;
    - `title` — заголовок блока;
    - `text` — полный Markdown-ответ с дисклеймером;
    - `warnings` — предупреждения (например, о делении на несколько сообщений).
    """
    resolved_type = search_type or detect_search_intent(query)
    warnings: List[str] = []

    header_lines = [
        "**🔎 Ресурсы для поиска работы (РФ и СНГ)**",
        f"_Тип поиска: {SEARCH_TYPE_TITLES[resolved_type]}_",
        f"_Запрос: «{query.strip()}»_" if query and query.strip() else "",
        "",
    ]

    if resolved_type == SEARCH_TYPE_MIXED:
        body = "\n\n".join(
            [format_telegram_channels_block(query), format_aggregators_block(query)]
        )
    elif resolved_type == SEARCH_TYPE_TELEGRAM:
        body = format_telegram_channels_block(query)
    elif resolved_type == SEARCH_TYPE_AGGREGATORS:
        body = "\n\n".join([format_aggregators_block(query), format_telegram_channels_block(query)])
    elif resolved_type == SEARCH_TYPE_COMPANIES:
        limit = extract_company_limit(query)
        catalog_size = len(COMPANIES)
        if limit and limit > MAX_COMPANIES_PER_REQUEST:
            limit = MAX_COMPANIES_PER_REQUEST
            warnings.append(
                f"⚠️ Запрошено больше {MAX_COMPANIES_PER_REQUEST} компаний — ответ будет разделён "
                f"на несколько сообщений. Показываю подборку из каталога бота и предлагаю уточнить отрасль."
            )
        shown = min(limit or catalog_size, catalog_size)
        if limit and limit > catalog_size:
            warnings.append(
                f"ℹ️ В проверенном каталоге бота {catalog_size} компаний с подтверждёнными ссылками — "
                f"показываю {shown}. Полные рейтинги ТОП-100/500/1000 смотрите в рейтингах работодателей "
                "hh.ru и Forbes: там же есть прямые ссылки на карьерные страницы."
            )
        body = format_companies_blocks(limit=limit, industry=detect_industry(query))
    else:
        body = "\n\n".join([format_profession_block(query), format_telegram_channels_block(query)])

    disclaimer = f"\n\n---\n_{LINKS_DISCLAIMER}_"
    text = "\n".join(line for line in header_lines if line is not None).strip() + "\n\n" + body + disclaimer

    return {
        "search_type": resolved_type,
        "title": SEARCH_TYPE_TITLES[resolved_type],
        "text": text,
        "warnings": warnings,
        "parts": split_long_message(text),
    }


def split_long_message(text: str, limit: int = MESSAGE_CHUNK_SIZE) -> List[str]:
    """Делит длинный ответ на части по границам блоков, чтобы уложиться в лимит Telegram."""
    if len(text) <= limit:
        return [text]

    parts: List[str] = []
    current: List[str] = []
    current_len = 0

    for block in text.split("\n"):
        block_len = len(block) + 1
        if current_len + block_len > limit and current:
            parts.append("\n".join(current).strip())
            current = [block]
            current_len = block_len
        else:
            current.append(block)
            current_len += block_len

    if current:
        parts.append("\n".join(current).strip())
    return [part for part in parts if part]


def build_sources_catalog_summary() -> Dict[str, int]:
    """Сводка по каталогу ресурсов (используется в меню и тестах)."""
    return {
        "telegram_channels": len(TELEGRAM_CHANNELS),
        "aggregators": len(AGGREGATORS),
        "companies": len(COMPANIES),
        "industries": len(get_industries()),
    }
