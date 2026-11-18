"""Безопасная нарезка длинных сообщений для Telegram.

Зачем модуль: у Telegram Bot API жёсткий лимит 4096 символов на сообщение, а при
`parse_mode="Markdown"` любая разрезанная сущность (`**жирный**`, `[текст](url)`,
`` `код` ``) приводит к ошибке:

    Bad Request: can't find end of the entity starting at byte offset 4144

Ошибка возникает из-за «слепой» обрезки текста по символам (`text[:3900]`).
Поэтому здесь текст режется **по границам строк**: каждая карточка вакансии,
ссылка или жирный фрагмент остаются целиком внутри одного сообщения.

Правила:
1. Кусок никогда не длиннее `limit` (по умолчанию 3900 — запас от 4096).
2. Режем только по переводу строки, а не по произвольному символу.
3. Если одна строка сама длиннее лимита — режем её принудительно, но при этом
   снимаем с неё Markdown-разметку, чтобы не оставить «половину» сущности.
4. Пустые строки-разделители по краям куска не теряются внутри текста.
"""
import re
from typing import List

# Лимит Telegram — 4096 символов; 3900 оставляет запас на служебные символы.
MAX_MESSAGE_LENGTH = 3900

def strip_markup(text: str) -> str:
    """Убирает Markdown-маркеры, сохраняя читаемый текст.

    Используется как аварийный вариант: если сообщение с разметкой всё равно
    отклонено Telegram, тот же текст отправляется как обычный.
    """
    plain = text.replace("**", "").replace("__", "")
    plain = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r"\1 — \2", plain)  # ссылка → текст + URL
    plain = plain.replace("`", "")
    return plain


_LINK_RE = re.compile(r"\[([^\[\]]*)\]\(([^()\s]+)\)")


def has_broken_entities(text: str) -> bool:
    """Проверяет, что все Markdown-сущности в тексте закрыты.

    Имитирует разбор legacy-Markdown, который делает Telegram: `**жирный**`,
    `*жирный*`, `_курсив_`, `` `код` ``, ```` ```блок``` ````, `[текст](url)`.
    Экранированные символы (`\\[`, `\\*`) и содержимое code-span'ов считаются
    обычным текстом — внутри `` `/find_resources` `` подчёркивание безопасно.

    Возвращает True, если хоть одна сущность осталась незакрытой — именно на таком
    тексте Telegram отвечает «can't find end of the entity».
    """
    index = 0
    length = len(text)
    bold = italic = 0
    while index < length:
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if text.startswith("```", index):
            end = text.find("```", index + 3)
            if end == -1:
                return True
            index = end + 3
            continue
        if char == "`":
            end = text.find("`", index + 1)
            if end == -1:
                return True
            index = end + 1
            continue
        if text.startswith("**", index):
            bold ^= 1
            index += 2
            continue
        if char == "*":
            bold ^= 1
            index += 1
            continue
        if char == "_":
            italic ^= 1
            index += 1
            continue
        if char == "[":
            match = _LINK_RE.match(text, index)
            if not match:
                return True
            index = match.end()
            continue
        index += 1
    return bool(bold or italic)


def _split_line(line: str, limit: int) -> List[str]:
    """Режет слишком длинную строку по лимиту, снимая с неё разметку.

    Такое бывает, если канал публикует «простыню» без переводов строк.
    Разметку убираем, чтобы куски не начинались/не заканчивались половиной
    сущности — иначе Telegram снова ответит «can't find end of the entity».
    """
    plain = strip_markup(line)
    return [plain[i : i + limit] for i in range(0, len(plain), limit)] or [""]


def split_message(text: str, limit: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """Разбивает текст на куски ≤ `limit`, не разрывая строки и сущности.

    Возвращает список частей в исходном порядке. Пустой текст → пустой список.
    """
    if not text:
        return []
    if limit < 50:
        raise ValueError("limit слишком мал: минимум 50 символов")

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append("\n".join(current).strip("\n"))
            current, current_len = [], 0

    for line in text.split("\n"):
        if len(line) > limit:
            # Строка-«простыня»: сначала закрываем текущий кусок, затем режем её
            flush()
            for piece in _split_line(line, limit):
                chunks.append(piece)
            continue

        extra = len(line) + (1 if current else 0)
        if current_len + extra > limit:
            flush()
        current.append(line)
        current_len += len(line) + (1 if len(current) > 1 else 0)

    flush()
    return [chunk for chunk in chunks if chunk]


def split_markdown_message(text: str, limit: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """Псевдоним `split_message` для мест, где важна именно Markdown-разметка."""
    return split_message(text, limit=limit)


_MD_SPECIAL = frozenset("_*`[]")


def escape_markdown(text: object) -> str:
    """Экранирует Markdown-спецсимволы в динамическом тексте.

    Зачем: названия каналов и тексты вакансий приходят «как есть» и часто содержат
    `[`, `]`, `*`, `_`, `` ` `` (например «TG: TOP LEVEL JOB [топ вакансии]»).
    В legacy Markdown такой `[` открывает сущность, которую Telegram не может
    закрыть → `can't find end of the entity`. Экранирование делает текст literal.
    """
    return "".join(("\\" + ch) if ch in _MD_SPECIAL else ch for ch in str(text))
