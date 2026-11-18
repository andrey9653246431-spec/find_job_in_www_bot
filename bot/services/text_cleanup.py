"""Очистка текста резюме от «признаков ИИ» и Markdown-разметки.

Зачем: адаптированное резюме человек копирует в Word/PDF или отправляет рекрутеру.
Если в тексте остаются `##`, `**`, обратные кавычки, длинные тире в каждом
предложении и вступления вроде «Вот готовое резюме:», сразу видно, что текст
сгенерирован. Модуль приводит вывод модели к виду нормального человеческого
резюме: разделы — заглавными буквами, пункты — «•», без служебных символов.

Модуль ничего не выдумывает и не сокращает смысл: только снимает разметку,
убирает мета-фразы модели и нормализует пробелы/тире.
"""
from __future__ import annotations

import re
from typing import List

# Эмодзи и декоративные символы в начале строки («🎯 О СЕБЕ», «✅ …»)
_LEADING_DECOR = re.compile(
    "^[\\s\\u2190-\\u21FF\\u2300-\\u27BF\\u2B00-\\u2BFF\\uFE0F\\u200D\\U0001F000-\\U0001FAFF]+"
)
# Markdown-заголовок: «# Раздел», «### Раздел»
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*(.+?)\s*#*\s*$")
# Горизонтальная линия
_RULE = re.compile(r"^\s*([-*_=]\s*){3,}$")
# Пункты списка: «- текст», «* текст», «+ текст», «– текст»
_BULLET = re.compile(r"^\s{0,3}[-*+–—]\s+(.*)$")
# Жирный/курсив: **текст**, __текст__, *текст*, _текст_
_BOLD_ITALIC = re.compile(r"(\*\*\*|\*\*|__|\*|_)(?=\S)(.+?)(?<=\S)\1")
# Инлайновый код и блоки кода
_CODE_FENCE = re.compile(r"^\s*```.*$", re.MULTILINE)
_INLINE_CODE = re.compile(r"`([^`]*)`")
# Ссылка [текст](url) → «текст (url)»
_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
# Строка markdown-таблицы
_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")

# Мета-фразы модели, которых в резюме быть не должно
_META_PREFIXES = (
    "вот готовое резюме",
    "вот резюме",
    "готовое резюме",
    "надеюсь, это поможет",
    "надеюсь, поможет",
    "если нужно",
    "если хотите",
    "дайте знать",
    "как видите",
    "обратите внимание",
    "данное резюме",
    "это резюме",
    "я могу",
    "могу дополнительно",
    "ниже представлено",
    "ниже — готовое",
    "конечно, вот",
    "конечно! вот",
    "разумеется, вот",
)
_META_PATTERNS = (
    re.compile(r"^\s*\(?\s*(примечание|пояснение|комментарий)\s*[:—-]", re.IGNORECASE),
    re.compile(r"^\s*```?$"),
    re.compile(r"^\s*(итог|вывод)\s*[:—-]?\s*$", re.IGNORECASE),
)

# Длинное тире — характерный признак генерации; заменяем на короткое
_EM_DASH = re.compile(r"\s*—\s*")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def _strip_inline_markup(line: str) -> str:
    """Снимает ** / __ / * / _ (только как парную разметку) и обратные кавычки."""
    line = _INLINE_CODE.sub(r"\1", line)
    previous = None
    while previous != line:
        previous = line
        line = _BOLD_ITALIC.sub(r"\2", line)
    return line


_CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def _upper_cyrillic(text: str) -> str:
    """Заглавные только для русских слов: «ПРОФИЛЬ (Executive Summary)» не ломается."""
    tokens = []
    for token in text.split(" "):
        tokens.append(token.upper() if _CYRILLIC.search(token) else token)
    return " ".join(tokens)


def _normalize_heading(text: str) -> str:
    """Раздел резюме — заглавными буквами, без «#» и эмодзи."""
    heading = _LEADING_DECOR.sub("", text.strip()).strip("*_# ").strip()
    heading = heading.rstrip(":.").strip()
    if not heading:
        return ""
    return _upper_cyrillic(heading)


def clean_ai_artifacts(text: str, *, keep_placeholders: bool = True) -> str:
    """Убирает из текста Markdown-разметку, эмодзи, мета-фразы и лишние тире.

    ``keep_placeholders=True`` сохраняет служебные метки вида ``[уточнить: …]``,
    которые бот оставляет там, где в исходном резюме не было цифры — это
    осознанная подсказка человеку, а не артефакт генерации.
    """
    if not text:
        return ""

    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = _CODE_FENCE.sub("", cleaned)

    out_lines: List[str] = []
    for raw_line in cleaned.split("\n"):
        line = raw_line.rstrip()

        if _RULE.match(line):
            continue

        heading_match = _HEADING.match(line)
        if heading_match:
            heading = _normalize_heading(heading_match.group(1))
            if heading:
                out_lines.append(heading)
            continue

        table_match = _TABLE_ROW.match(line)
        if table_match:
            cells = [cell.strip() for cell in table_match.group(1).split("|")]
            cells = [cell for cell in cells if cell and not set(cell) <= {"-", ":", " "}]
            if cells:
                out_lines.append(" • ".join(_strip_inline_markup(cell) for cell in cells))
            continue

        stripped = line.strip()

        # мета-фразы модели («Вот готовое резюме:», «Надеюсь, это поможет»)
        lowered = stripped.lower().lstrip(" «\"'(")
        if any(lowered.startswith(prefix) for prefix in _META_PREFIXES):
            continue
        if any(pattern.match(stripped) for pattern in _META_PATTERNS):
            continue

        bullet_match = _BULLET.match(line)
        if bullet_match:
            body = _strip_inline_markup(bullet_match.group(1)).strip()
            if body:
                out_lines.append(f"• {body}")
            continue

        line = _strip_inline_markup(line)
        line = _MD_LINK.sub(r"\1 (\2)", line)
        line = line.strip()
        if not line:
            out_lines.append("")
            continue

        if not keep_placeholders:
            line = re.sub(r"\[уточнить:[^\]]*\]", "", line).strip()

        line = _LEADING_DECOR.sub("", line).strip()
        out_lines.append(line)

    result = "\n".join(out_lines)
    result = _EM_DASH.sub(" – ", result)
    result = _MULTI_SPACE.sub(" ", result)
    result = _MULTI_NEWLINE.sub("\n\n", result)

    # Схлопываем пустые строки в начале/конце и висящие пробелы
    lines = [line.strip() for line in result.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def has_markdown_artifacts(text: str) -> bool:
    """Проверка для тестов и логов: остались ли служебные символы разметки."""
    if not text:
        return False
    if re.search(r"(^|\s)#{1,6}\s", text, re.MULTILINE):
        return True
    if "**" in text or "__" in text or "`" in text:
        return True
    if re.search(r"^\s*[-*+]\s+\S", text, re.MULTILINE):
        return True
    return bool(re.search(r"\[[^\]]+\]\([^)]+\)", text))
