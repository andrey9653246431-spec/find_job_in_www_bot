"""Дедупликация вакансий в выдаче.

Одна и та же вакансия почти всегда висит в нескольких местах: пост в двух
Telegram-каналах, копия на агрегаторе, ещё одна на карьерной странице компании.
Пользователю нужен **один** вариант из каждой такой группы.

Правила (консервативные, чтобы не склеить разные вакансии с одинаковым
названием вроде «Менеджер по продажам» у разных компаний):

1. Совпал URL — дубль (это делает ещё парсер, здесь на всякий случай тоже).
2. Совпали нормализованное название **и** компания — дубль.
3. Совпал длинный текст описания (>= 120 символов, схожесть >= 0.88) **и**
   названия похожи — дубль (репост одного текста с другим URL/каналом).

«Похожие названия» = одно целиком содержит другое (>= 80 % длины) или
схожесть >= 0.85: «Коммерческий директор» ≈ «Коммерческий директор (Москва)».

Из группы остаётся самый релевантный вариант, при равенстве — самый свежий.
"""
from difflib import SequenceMatcher
import re
from typing import Any, Dict, List, Tuple

# Служебный «шум» в названиях, который не влияет на уникальность вакансии
_TITLE_NOISE_RE = re.compile(
    r"(вакансия|вакансии|требуется|ищем|в поиске|срочно|urgent|hiring|"
    r"открыта\s+вакансия|job\s+offer|looking\s+for)",
    re.IGNORECASE,
)
_PARENS_RE = re.compile(r"\([^)]*\)")
_NON_WORD_RE = re.compile(r"[^0-9a-zа-яё]+", re.IGNORECASE)
_COMPANY_RE = re.compile(
    r"(ООО|ОАО|ЗАО|ПАО|АО|ИП|ГК|АО)\s*[«\"]?([А-ЯЁA-Z][\w\s\-»\"]{1,40})", re.IGNORECASE
)
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2190-\u21FF\u2B00-\u2BFF]+"
)


def _normalize(text: str) -> str:
    """Нижний регистр, без эмодзи/пунктуации, ё → е, одиночные пробелы."""
    value = _EMOJI_RE.sub(" ", str(text or ""))
    value = value.replace("ё", "е").replace("Ё", "Е")
    value = _NON_WORD_RE.sub(" ", value.lower())
    return " ".join(value.split())


def normalize_title(title: str) -> str:
    """Ключ названия вакансии: без скобок-уточнений, эмодзи и служебных слов."""
    value = _EMOJI_RE.sub(" ", str(title or ""))
    value = _PARENS_RE.sub(" ", value)
    value = _TITLE_NOISE_RE.sub(" ", value)
    key = _normalize(value)
    # «Senior»/«Sr» и прочие приставки не делают вакансию другой — но и не мешают:
    # оставляем как есть, чтобы не склеить разные грейды.
    return key


def vacancy_company(vacancy: Dict[str, Any]) -> str:
    """Компания-работодатель, если она есть в данных вакансии."""
    for field in ("company", "company_name", "organization", "employer", "hiring_organization"):
        value = vacancy.get(field)
        if isinstance(value, str) and value.strip():
            return _normalize(value)[:60]

    # Компания может быть упомянута в тексте сниппета: «ООО «Ромашка»», «в ПАО Сбер»
    text = f"{vacancy.get('title', '')} {vacancy.get('snippet', '') or ''}"
    match = _COMPANY_RE.search(text)
    if match:
        return _normalize(f"{match.group(1)} {match.group(2)}")[:60]
    return ""


def vacancy_fingerprint(vacancy: Dict[str, Any]) -> Tuple[str, str]:
    """(ключ названия, ключ компании) — основа для поиска дублей."""
    return normalize_title(vacancy.get("title", "")), vacancy_company(vacancy)


def _description_key(vacancy: Dict[str, Any]) -> str:
    """Нормализованный текст описания для сравнения репостов."""
    text = str(vacancy.get("snippet") or vacancy.get("description") or "")
    return _normalize(text)


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _titles_related(left: str, right: str) -> bool:
    """Одно название содержит другое (или почти совпадает)."""
    if not left or not right:
        return False
    if left == right:
        return True
    short, long = (left, right) if len(left) <= len(right) else (right, left)
    if short in long and len(short) / max(len(long), 1) >= 0.8:
        return True
    return _similarity(left, right) >= 0.85


def _vacancy_date_key(vacancy: Dict[str, Any]) -> float:
    published = vacancy.get("published_at")
    try:
        return published.timestamp()
    except Exception:  # noqa: BLE001 — дата может быть строкой или отсутствовать
        return 0.0


def _rank_key(vacancy: Dict[str, Any]) -> Tuple[int, float]:
    return (
        int(vacancy.get("relevance_score") or 0),
        _vacancy_date_key(vacancy),
    )


def deduplicate_vacancies(
    vacancies: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """Убирает дубли вакансий: возвращает (уникальные, сколько удалено).

    Порядок сохраняется по релевантности: из каждой группы дублей остаётся
    самый релевантный (затем самый свежий) вариант.
    """
    ordered = sorted(vacancies, key=_rank_key, reverse=True)

    seen_urls = set()
    kept: List[Dict[str, Any]] = []
    kept_keys: List[Tuple[str, str, str]] = []  # (title_key, company_key, desc_key)
    removed = 0

    for vacancy in ordered:
        url = str(vacancy.get("url") or "").strip()
        if url and url in seen_urls:
            removed += 1
            continue

        title_key, company_key = vacancy_fingerprint(vacancy)
        desc_key = _description_key(vacancy)

        is_duplicate = False
        for kept_title, kept_company, kept_desc in kept_keys:
            # 2. Совпали название и компания
            if company_key and company_key == kept_company and _titles_related(title_key, kept_title):
                is_duplicate = True
                break
            # 3. Почти одинаковый длинный текст + похожие названия — репост
            if (
                len(desc_key) >= 120
                and len(kept_desc) >= 120
                and _titles_related(title_key, kept_title)
                and _similarity(desc_key, kept_desc) >= 0.88
            ):
                is_duplicate = True
                break
        if is_duplicate:
            removed += 1
            if url:
                seen_urls.add(url)
            continue

        if url:
            seen_urls.add(url)
        kept.append(vacancy)
        kept_keys.append((title_key, company_key, desc_key))

    return kept, removed


def describe_dedupe(removed: int) -> str:
    """Строка для шапки выдачи: сколько дублей убрано."""
    if removed <= 0:
        return ""
    word = "дубль" if removed % 10 == 1 and removed % 100 != 11 else "дубля"
    if removed % 10 in (2, 3, 4) and removed % 100 not in (12, 13, 14):
        word = "дубля"
    elif removed % 10 not in (1, 2, 3, 4) or removed % 100 in (11, 12, 13, 14):
        word = "дублей"
    return f"🔁 **Убрано {removed} {word}** (в выдаче — по одному варианту из каждой группы)"
