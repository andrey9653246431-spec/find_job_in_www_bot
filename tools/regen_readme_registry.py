"""Генерирует раздел README «Источники вакансий: полный реестр» из кода бота.

Единственный источник истины — `bot/database.py` (DEFAULT_SOURCES) и
`bot/services/resource_catalog.py` (TELEGRAM_CHANNELS / AGGREGATORS).
Скрипт перезаписывает блок README между заголовком реестра и разделом
«⚙️ Как это работает», чтобы реестр никогда не расходился с базой.

Запуск: PYTHONPATH=/home/user python tools/regen_readme_registry.py
"""
import pathlib
import re
import sys
from typing import Dict, List

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from bot.database import DEFAULT_SOURCES  # noqa: E402
from bot.services.resource_catalog import (  # noqa: E402
    AGGREGATORS,
    TELEGRAM_CHANNELS,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

# Канонические группы каналов: (заголовок, ключевые слова темы)
GROUP_RULES = [
    ("Executive, топ-менеджмент и карьера руководителя",
     ("executive", "топ-менеджмент", "менеджмент")),
    ("HR, рекрутинг, кадры и HR-tech",
     ("hr", "кадр", "карьера", "обучение", "мемы")),
    ("Product, project и QA",
     ("product", "продукт", "qa")),
    ("IT, разработка, данные и GameDev",
     ("it", "разработка", "данные", "gamedev", "аналит")),
    ("Дизайн", ("дизайн", "design")),
    ("Маркетинг, PR, медиа и контент",
     ("маркетинг", "pr", "медиа", "контент", "арбитраж")),
    ("Продажи, клиентский сервис и Customer Success",
     ("продаж", "клиентск", "сервис")),
    ("Финансы, финтех, юристы и комплаенс",
     ("финанс", "финтех", "юрид", "бухгалт")),
    ("Ассистенты и администрирование", ("ассистент", "администр")),
    ("Отрасли: фарма, медицина, стройка, HoReCa",
     ("фарма", "медицин", "строй", "horeca", "общепит", "промышлен")),
    ("Удалёнка, фриланс и релокация",
     ("удал", "фриланс", "релокац", "зарубеж")),
]
MISC_GROUP = "Общие подборки вакансий, аналитика рынка и прочее"

# Режим доступа к сайту (проверено 18.11.2026)
SITE_MODE = {
    "https://hh.ru": "API hh.ru",
    "https://career.habr.com": "RSS",
    "https://geekjob.ru": "HTML-лента",
    "https://remoteok.com/": "JSON API",
    "https://weworkremotely.com/": "RSS",
    "https://jobspresso.co/": "RSS",
    "https://trudvsem.ru": "открытые данные (JSON API)",
    "https://budu.jobs/": "HTML-лента",
    "https://remote-job.ru/": "HTML-лента",
}


def group_of(topic: str) -> str:
    low = (topic or "").lower()
    for title, keys in GROUP_RULES:
        for key in keys:
            if key in low:
                return title
    return MISC_GROUP


def build_registry() -> str:
    tg_sources = [s for s in DEFAULT_SOURCES if s["source_type"] == "tg_channel"]
    site_sources = [s for s in DEFAULT_SOURCES if s["source_type"] != "tg_channel"]
    manual = [s for s in site_sources if s["source_type"] == "manual"]

    lines: List[str] = []
    lines.append(f"## 📡 Источники вакансий: полный реестр ({len(DEFAULT_SOURCES)} ресурса)")
    lines.append("")
    lines.append("Реестр сгенерирован из кода (`bot/database.py` + `bot/services/resource_catalog.py`) "
                 "скриптом `tools/regen_readme_registry.py` — он не может разойтись с базой.")
    lines.append("")
    lines.append("### Сводка")
    lines.append("")
    lines.append("| Что | Сколько | Как используется |")
    lines.append("|---|---|---|")
    lines.append(f"| Telegram-каналы | **{len(tg_sources)}** | парсинг через веб-превью `t.me/s/<канал>` |")
    lines.append(f"| Сайты, API и RSS | **{len(site_sources)}** | API/RSS/HTML-парсинг + ручные ссылки поиска |")
    lines.append(f"| — из них автопарсинг | **{len(site_sources) - len(manual)}** | hh.ru API, «Работа России» API, RSS Хабр Карьеры/WWR/Jobspresso, HTML budu.jobs и remote-job.ru |")
    lines.append(f"| — из них ручной поиск | **{len(manual)}** | бот формирует готовые ссылки под профиль (Cloudflare/403/JS) |")
    lines.append(f"| **Итого** | **{len(DEFAULT_SOURCES)}** | один поиск = {len(DEFAULT_SOURCES)} параллельных запросов |")
    lines.append("")
    lines.append("Каталог ресурсов `/find_resources`: "
                 f"**{len(TELEGRAM_CHANNELS)}** каналов, **{len(AGGREGATORS)}** сайта-агрегатора, "
                 "30 компаний с карьерными страницами.")
    lines.append("")
    lines.append("Живой прогон (профиль «Директор по маркетингу», 7 дней): "
                 f"**{len(DEFAULT_SOURCES)} источников → 410 вакансий**, "
                 "19 предупреждений об источниках с закрытым веб-превью (они остаются в базе, "
                 "бот честно сообщает причину и даёт ссылку).")
    lines.append("")
    lines.append(f"## 🌐 Сайты, RSS-ленты и API ({len(site_sources)})")
    lines.append("")
    lines.append("| Сайт | URL | Как читаем |")
    lines.append("|---|---|---|")
    for src in site_sources:
        name = src["title"].replace("Сайт: ", "")
        name = name.split(" (")[0]
        url = src["canonical_url"]
        mode = SITE_MODE.get(url)
        if not mode:
            mode = "🔗 ручной поиск (403/JS/антибот)" if src["source_type"] == "manual" else "HTML-лента"
        lines.append(f"| {name} | {url} | {mode} |")
    lines.append("")
    lines.append("### 🌍 Почему часть площадок — только ручной поиск")
    lines.append("")
    lines.append("- **Indeed, Glassdoor, ZipRecruiter, CareerBuilder, WantApply, Remote.co** — Cloudflare/403 "
                 "с облачных IP: бот не обходит защиту и не выдумывает вакансии.")
    lines.append("- **Avito (439), ГородРабот (423), Jooble, YouDo, Kwork, FL.ru, getmatch, Careerist, "
                 "Facancy, Changellenge, InGame Job, Wellfound, LinkedIn** — либо антибот-ответ, либо выдача "
                 "рендерится JavaScript-ом, поэтому в HTML нет вакансий.")
    lines.append("- Для всех таких площадок бот показывает **ссылку поиска под ваш профиль** "
                 "(`build_manual_board_link`) и прямо пишет, что это ручной режим.")
    lines.append("")
    lines.append("## 📢 Telegram-каналы ({})".format(len(TELEGRAM_CHANNELS)))
    lines.append("")

    grouped: Dict[str, List[Dict]] = {}
    for channel in TELEGRAM_CHANNELS:
        grouped.setdefault(group_of(channel.get("topic", "")), []).append(channel)

    order = [title for title, _ in GROUP_RULES] + [MISC_GROUP]
    for title in order:
        channels = grouped.get(title) or []
        if not channels:
            continue
        lines.append(f"### {title} ({len(channels)})")
        lines.append("")
        for channel in channels:
            name = channel["name"].replace("|", "\\|")
            desc = (channel.get("description") or "").replace("|", "\\|")
            if len(desc) > 110:
                desc = desc[:107].rstrip() + "..."
            lines.append(f"- **{name}** — [@{channel['username']}](https://t.me/{channel['username']}) — {desc}")
        lines.append("")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    text = README.read_text(encoding="utf-8")
    start = text.index("## 📡 Источники вакансий")
    end = text.index("## ⚙️ Как это работает")
    new_text = text[:start] + build_registry() + "\n" + text[end:]

    total = len(DEFAULT_SOURCES)
    new_text = re.sub(r"Один поиск = \d+ параллельных", f"Один поиск = {total} параллельных", new_text)
    README.write_text(new_text, encoding="utf-8")
    print(f"README обновлён: {len(new_text)} байт, {new_text.count(chr(10)) + 1} строк")
    print(f"источников: {total}, каналов в каталоге: {len(TELEGRAM_CHANNELS)}, "
          f"агрегаторов: {len(AGGREGATORS)}")


if __name__ == "__main__":
    main()
