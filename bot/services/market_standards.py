"""Модуль управления стандартами рынка и отдельной функции формирования
Идеального Резюме по «Золотому стандарту» — АРХИТЕКТУРА ИДЕАЛЬНОГО EXECUTIVE CV (Framework 2026+).

Содержит три отдельные ключевые функции:
1. `set_gold_standard_executive_cv_2026` / `build_ideal_executive_cv_2026` —
   отдельная функция формирования идеального резюме по структуре Executive CV (Framework 2026+).
2. `set_market_standards` / `get_market_standards` —
   отдельная функция задания и настройки стандартов рынка внутри бота.
3. `adapt_resume_to_market_standards` —
   отдельная функция адаптации загруженного резюме под активные стандарты рынка (+ генерация DOCX).
"""
import io
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import aiohttp
from docx import Document
from docx.shared import Pt
from bot.config import config
from bot.database import Database

# =============================================================================
# ЗОЛОТОЙ СТАНДАРТ: АРХИТЕКТУРА ИДЕАЛЬНОГО EXECUTIVE CV (Framework 2026+)
# =============================================================================

EXECUTIVE_CV_2026_FRAMEWORK_TEXT = """🏛 АРХИТЕКТУРА ИДЕАЛЬНОГО EXECUTIVE CV (Framework 2026+)
Эта структура рассчитана на 2 страницы (максимум). Первый экран (Page 1, верхняя половина) должен продавать вас за 7–30 секунд.

📌 1. HEADER (Шапка) — Фундамент
• ФИО (крупно).
• Целевая должность (строго под ФИО, задает вектор: Commercial Director | Fashion Retail / Omnichannel).
• Локация: Город + Готовность к релокации/формату (Командировки/международная релокация).
• Контакты: Телефон, Email, LinkedIn / Telegram.
• Правило: Никаких фото, дат рождения, семейного положения. Только факты для связи.

📌 2. ПРОФИЛЬ (Executive Summary) — Продающий хук
• Объем: 3–5 строк.
• Формула: [Уровень + сколько лет опыта] + [Масштаб бизнеса: оборот/магазины/команда] + [Ключевая экспертиза: P&L, Omnichannel, CAP/OTB] + [Главный результат-визитка].
• Важно: Здесь нельзя писать «ответственный и коммуникабельный». Только бизнес-язык.

📌 3. КЛЮЧЕВАЯ ЭКСПЕРТИЗА (Core Expertise / ATS Keywords) — Для роботов и HR
• Формат: Облако тегов через разделитель |.
• Группировка:
  - Business & Strategy: Commercial Strategy | P&L Management | Business Planning | Unit Economics
  - Operations: Category Management | CAP/OTB | Pricing | Inventory | Supply Chain
  - Leadership & Tech: Cross-functional Leadership | Team Building (2-40+) | Change Management | BI | 1C | ERP
• Правило: Использовать точную рыночную лексику (ATS vocabulary). Не добавлять редкие термины ради галочки, если их нет в опыте.

📌 4. ОПЫТ РАБОТЫ (Professional Experience) — Ядро резюме
• В обратном хронологическом порядке (сначала текущее место).
• Шапка компании: Название, сфера, масштаб (например, Fashion-бизнес, 200+ магазинов, оборот 9+ млрд руб.).
• Должность и период (Месяц Год — Месяц Год).
• Контекст роли (1–2 предложения): Зона ответственности (P&L, бюджет), количество прямых подчиненных.
• Scope (Область охвата) — 3–4 пункта: Например, Whole-brand sales plan, Strategy/CAP-OTB, Omnichannel/MP, Operating model.
• Ключевые результаты (Bullet points) — строго 3–4 пункта (не более 4-х пунктов на роль!):
  - Формула: Глагол действия + Метрика (цифра) + Механизм/Влияние.

📌 5. ДОПОЛНИТЕЛЬНЫЕ БЛОКИ (по ситуации)
• ОБРАЗОВАНИЕ И ЯЗЫКИ: Вуз, специальность, год. Языки (с указанием уровня, например, Английский — B2/Upper-Intermediate, опыт переговоров).
• КЛЮЧЕВЫЕ ПРОЕКТЫ (если применимо): 1–2 кейса в формате: Проблема -> Решение -> Результат в цифрах.

⚠️ ПРАВИЛА УПАКОВКИ (Фильтры адаптации):
1. Принцип «Evidence Map» (Карта доказательств): Максимум 2 страницы, не более 4-х буллитов на роль; детали оставляем для интервью.
2. Attribution (Атрибуция цифр): Разделять личный вклад и общекомандный результат компании.
3. Борьба с Red Flags: Убираем фото, возраст, семейное положение, пустые штампы и спорные переходы.
4. Один фокус — один экран: Первая страница содержит самые сильные достижения; опыт 10-летней давности — не более 2–3 строк."""


# «Грязное» демонстрационное резюме для функции показа идеального примера Executive CV 2026+.
# Содержит всё, что должен убрать фильтр Red Flags: фото, дату рождения, возраст,
# семейное положение и клише. На его основе бот показывает эталонную упаковку.
EXECUTIVE_CV_2026_EXAMPLE_RAW = """Сергей Волков
Должность: Commercial Director
Дата рождения: 12.05.1985, 41 год, женат, двое детей, фото приложено
Город: Москва
Контакты: +7 (999) 123-45-67, s.volkov@example.com, linkedin.com/in/svolkov
Навыки: P&L, Commercial Strategy, Category Management, CAP/OTB, Omnichannel, Marketplace, BI, ERP, 1C, Pricing, Inventory, Team Building
О себе: 14+ лет опыта в fashion retail. Ответственный и коммуникабельный руководитель.
Опыт работы:
ООО Фэшн Ритейл Групп, Fashion-бизнес, 200+ магазинов, оборот 9+ млрд руб. (2020 - 2026)
Scope: whole-brand sales plan, стратегия и CAP/OTB, омниканальность и маркетплейсы
- Масштабировал маркетплейсы: продажи выросли х3 (до 20% оборота) за счет выстраивания новой операционной модели.
- Управлял OTB-бюджетом 4,5 млрд руб. и категорийным портфелем из 1200 SKU.
- Внедрил ценовую стратегию: маржинальность выросла на 15%.
- Запустил BI-дашборды для 40+ пользователей (сокращение отчетного цикла с 5 дней до 1 дня).
- Настроил складскую логистику и обучение персонала категорийного блока.
- Занимался подготовкой годовых бюджетов и защитой их в совете директоров.
Образование: ВШЭ, Стратегический менеджмент, 2008
Английский — B2/Upper-Intermediate, опыт переговоров"""


# Предустановленные шаблоны стандартов рынка (по умолчанию — Золотой стандарт Executive CV 2026+)
MARKET_STANDARDS_PRESETS: Dict[str, Dict[str, Any]] = {
    "executive_cv_2026": {
        "preset_key": "executive_cv_2026",
        "title": "🏛 Золотой стандарт: Executive CV (Framework 2026+)",
        "required_sections": [
            "1. HEADER (Шапка: ФИО, Целевая должность | Вектор, Локация и релокация, Контакты — без фото/возраста)",
            "2. ПРОФИЛЬ (Executive Summary: 3–5 строк по формуле Уровень + Масштаб + Экспертиза + Главный результат)",
            "3. КЛЮЧЕВАЯ ЭКСПЕРТИЗА (Core Expertise / ATS Keywords через | : Business & Strategy, Operations, Leadership & Tech)",
            "4. ОПЫТ РАБОТЫ (Professional Experience: Масштаб компании, Контекст роли, Scope 3–4 п., Ключевые результаты ≤ 4 буллитов)",
            "5. ДОПОЛНИТЕЛЬНЫЕ БЛОКИ (Образование и языки, Ключевые проекты: Проблема -> Решение -> Результат)",
        ],
        "standards_text": EXECUTIVE_CV_2026_FRAMEWORK_TEXT,
        "rules": {
            "framework": "executive_cv_2026",
            "max_pages": 2,
            "max_bullets_per_role": 4,
            "require_metrics": True,
            "require_action_verbs": True,
            "remove_cliches": True,
            "remove_personal_demographics": True,
            "require_attribution": True,
            "evidence_map": True,
            "one_focus_one_screen": True,
            "focus_keywords": [
                "P&L Management",
                "Commercial Strategy",
                "Unit Economics",
                "Omnichannel",
                "Cross-functional Leadership",
                "BI",
                "ERP",
            ],
        },
    },
    "universal_ats": {
        "preset_key": "universal_ats",
        "title": "Универсальный стандарт рынка (ATS + STAR/XYZ)",
        "required_sections": [
            "Заголовок и целевая должность",
            "Контакты",
            "Профессиональное резюме (Summary)",
            "Ключевые навыки (Hard Skills)",
            "Опыт работы и измеримые достижения (STAR/XYZ)",
            "Образование и сертификаты",
        ],
        "standards_text": (
            "1. Чёткая структура для прохождения ATS-фильтров (без сложных таблиц и графики).\n"
            "2. Наличие блока Summary (3-4 предложения о ключевой экспертизе и ценности кандидата).\n"
            "3. Раздел «Ключевые навыки» с конкретными инструментами и технологиями.\n"
            "4. Описание опыта через глаголы совершенного вида (Разработал, Внедрил, Увеличил, Оптимизировал) "
            "по формуле XYZ / STAR: «Достиг [X], измеряемого в [Y], за счёт [Z]».\n"
            "5. Обязательное наличие оцифрованных метрик результата (%, время, деньги, объёмы).\n"
            "6. Отсутствие пустых штампов («стрессоустойчивый», «коммуникабельный», «ответственный»)."
        ),
        "rules": {
            "require_metrics": True,
            "require_action_verbs": True,
            "remove_cliches": True,
            "focus_keywords": [],
        },
    },
    "it_dev": {
        "preset_key": "it_dev",
        "title": "Стандарт рынка IT / Разработка ПО (Tech CV)",
        "required_sections": [
            "Целевая позиция и грейд (Junior/Middle/Senior/Lead)",
            "Контакты и ссылки (GitHub, Telegram, Email)",
            "Tech Summary (Опыт и специализация)",
            "Технический стек (Языки, Фреймворки, БД, DevOps)",
            "Коммерческий опыт и архитектурные достижения",
            "Pet-проекты / Open Source и Образование",
        ],
        "standards_text": (
            "1. Указание целевого грейда и специализации в заголовке.\n"
            "2. Наличие ссылок на GitHub / портфолио и Telegram.\n"
            "3. Категоризированный технический стек (Языки, Фреймворки, БД, Инфраструктура/CI-CD).\n"
            "4. В каждом месте работы: описание проекта, используемый стек и 3-4 достижения с метриками "
            "(снижение latency, рост RPS, покрытие тестами %, ускорение релизов).\n"
            "5. Замена пассивных формулировок («писал код», «занимался поддержкой») на инженерные результаты."
        ),
        "rules": {
            "require_metrics": True,
            "require_action_verbs": True,
            "remove_cliches": True,
            "focus_keywords": ["Git", "Docker", "SQL", "API", "CI/CD"],
        },
    },
    "data_analytics": {
        "preset_key": "data_analytics",
        "title": "Стандарт рынка Data Science & Аналитика",
        "required_sections": [
            "Целевая роль (Data Analyst / BI / Data Scientist)",
            "Контакты и портфолио (GitHub / Kaggle)",
            "Профиль аналитика (Summary)",
            "Инструментарий (SQL, Python, BI, Статистика/ML)",
            "Опыт работы и бизнес-эффект (A/B-тесты, дашборды, модели)",
            "Образование и профильные курсы",
        ],
        "standards_text": (
            "1. Акцент на бизнес-эффект от аналитики и моделей (деньги, конверсия, удержание, экономия часов).\n"
            "2. Чёткое разделение стека: БД/DWH, BI-системы, Python/R библиотеки, мат. статистика.\n"
            "3. Формулировка достижений через влияние на продукт и метрики (LTV, Retention, CR, ROC-AUC, MAPE)."
        ),
        "rules": {
            "require_metrics": True,
            "require_action_verbs": True,
            "remove_cliches": True,
            "focus_keywords": ["SQL", "Python", "BI", "A/B", "ETL"],
        },
    },
    "marketing_sales": {
        "preset_key": "marketing_sales",
        "title": "Стандарт рынка Digital-маркетинг и Коммерция",
        "required_sections": [
            "Целевая должность",
            "Контакты и портфолио кейсов",
            "Executive Summary (Ключевые результаты)",
            "Инструменты, каналы трафика и CRM/Аналитика",
            "Опыт работы и выполненные KPI (ROI, ROMI, CAC, выручка)",
            "Образование и сертификация",
        ],
        "standards_text": (
            "1. Обязательная оцифровка воронки, бюджетов и выполнения KPI (ROMI, CPA, CAC, LTV, % роста продаж).\n"
            "2. Перечень рекламных кабинетов, аналитических систем и CRM.\n"
            "3. Кейсовый формат описания опыта: Задача -> Действие -> Оцифрованный результат."
        ),
        "rules": {
            "require_metrics": True,
            "require_action_verbs": True,
            "remove_cliches": True,
            "focus_keywords": ["KPI", "CRM", "ROI", "B2B", "Аналитика"],
        },
    },
}

DEFAULT_PRESET_KEY = "executive_cv_2026"

# Словарь замены слабых глаголов на сильные глаголы действия (Action Verbs)
WEAK_TO_STRONG_VERBS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bзанимался разработкой\b", re.I), "Разработал и внедрил"),
    (re.compile(r"\bзанималась разработкой\b", re.I), "Разработала и внедрила"),
    (re.compile(r"\bзанимался созданием\b", re.I), "Создал и запустил"),
    (re.compile(r"\bзанимался развитием\b", re.I), "Масштабировал и развил"),
    (re.compile(r"\bзанимался управлением\b", re.I), "Управлял операционным контуром"),
    (re.compile(r"\bзанимался продажами\b", re.I), "Увеличил объём продаж"),
    (re.compile(r"\bзанимался настройкой\b", re.I), "Настроил и автоматизировал"),
    (re.compile(r"\bзанимался тестированием\b", re.I), "Провёл комплексное тестирование"),
    (re.compile(r"\bзанимался парсингом\b", re.I), "Реализовал пайплайн парсинга"),
    (re.compile(r"\bзанимался\b", re.I), "Реализовал"),
    (re.compile(r"\bзанималась\b", re.I), "Реализовала"),
    (re.compile(r"\bучаствовал в разработке\b", re.I), "Разработал ключевые модули"),
    (re.compile(r"\bучаствовала в разработке\b", re.I), "Разработала ключевые модули"),
    (re.compile(r"\bпринимал участие в\b", re.I), "Обеспечил результат (при личном участии в проекте)"),
    (re.compile(r"\bработал над\b", re.I), "Спроектировал и масштабировал"),
    (re.compile(r"\bруководил отделом\b", re.I), "Возглавил и трансформировал подразделение"),
    (re.compile(r"\bписал код\b", re.I), "Разрабатывал отказоустойчивую архитектуру и код"),
    (re.compile(r"\bделал\b", re.I), "Выполнил"),
]

# Штампы и клише, запрещённые стандартом Executive CV 2026+
CLICHE_WORDS: List[str] = [
    "стрессоустойчивость",
    "стрессоустойчивый",
    "стрессоустойчивая",
    "коммуникабельность",
    "коммуникабельный",
    "коммуникабельная",
    "ответственный и коммуникабельный",
    "ответственность",
    "ответственный",
    "легкообучаемый",
    "быстро обучаюсь",
    "легко обучаюсь",
    "пунктуальность",
    "пунктуальный",
    "без вредных привычек",
    "уверенный пользователь пк",
    "активная жизненная позиция",
]

# Паттерны демографических данных и Red Flags в шапке (фото, дата рождения, возраст, семейное положение)
DEMOGRAPHIC_RED_FLAG_PATTERNS: List[re.Pattern] = [
    re.compile(r"(?:дата рождения|д\.р\.|год рождения|возраст)\s*[:\-–]?\s*[^\n,;]+", re.I),
    re.compile(
        r"\b\d{1,2}\s+(?:лет|года|год)\b(?!\s*(?:опыта|работы|стажа|в\s+\w))",
        re.I,
    ),
    re.compile(
        r"(?:семейное положение|женат|замужем|холост|не замужем|разведен|разведена|"
        r"(?:двое|трое|четверо|один|одна|два|три)?\s*дет(?:и|ей|ьми)|ребен(?:ок|ка))[^\n,;]*",
        re.I,
    ),
    re.compile(r"(?:фото|фотография|photo)\s*[:\-–]?\s*[^\n,;]*", re.I),
]


# =============================================================================
# 1. ОТДЕЛЬНАЯ ФУНКЦИЯ ЗАДАНИЯ СТАНДАРТОВ РЫНКА ВНУТРИ БОТА
# =============================================================================

async def set_gold_standard_executive_cv_2026(
    db: Database,
    user_id: int,
) -> Dict[str, Any]:
    """Отдельная функция установки «Золотого стандарта» —
    🏛 АРХИТЕКТУРА ИДЕАЛЬНОГО EXECUTIVE CV (Framework 2026+) для пользователя.
    """
    return await set_market_standards(
        db=db,
        user_id=user_id,
        preset_key="executive_cv_2026",
    )


async def set_market_standards(
    db: Database,
    user_id: int,
    preset_key: str = DEFAULT_PRESET_KEY,
    custom_standards_text: Optional[str] = None,
    custom_required_sections: Optional[List[str]] = None,
    custom_title: Optional[str] = None,
) -> Dict[str, Any]:
    """Отдельная функция задания стандартов рынка внутри бота.

    Позволяет:
    - Установить «Золотой стандарт» `executive_cv_2026` (Framework 2026+).
    - Выбрать один из отраслевых пресетов (`universal_ats`, `it_dev`, `data_analytics`, `marketing_sales`).
    - Задать полностью пользовательские стандарты рынка текстом прямо из чата Telegram (`custom_standards_text`).
    """
    base_preset = MARKET_STANDARDS_PRESETS.get(
        preset_key, MARKET_STANDARDS_PRESETS[DEFAULT_PRESET_KEY]
    )

    if custom_standards_text and custom_standards_text.strip():
        cleaned_custom = custom_standards_text.strip()
        sections = custom_required_sections or list(base_preset["required_sections"])

        sec_match = re.search(
            r"(?:обязательные разделы|разделы|структура)\s*[:\-–]\s*([^\n]+)",
            cleaned_custom,
            re.I,
        )
        if sec_match:
            parsed_secs = [
                s.strip(" .-•")
                for s in re.split(r"[,;|]+", sec_match.group(1))
                if s.strip(" .-•")
            ]
            if parsed_secs:
                sections = parsed_secs

        focus_keywords: List[str] = []
        kw_match = re.search(
            r"(?:ключевые слова|обязательные навыки|keywords|стек)\s*[:\-–]\s*([^\n]+)",
            cleaned_custom,
            re.I,
        )
        if kw_match:
            focus_keywords = [
                k.strip(" .-•")
                for k in re.split(r"[,;|]+", kw_match.group(1))
                if k.strip(" .-•")
            ]

        rules = {
            "framework": "custom",
            "max_pages": 2,
            "max_bullets_per_role": 4,
            "require_metrics": True,
            "require_action_verbs": True,
            "remove_cliches": True,
            "remove_personal_demographics": True,
            "focus_keywords": focus_keywords,
            "custom_user_defined": True,
        }
        return await db.save_user_market_standards(
            user_id=user_id,
            preset_key="custom",
            title=custom_title or "Пользовательский стандарт рынка (задан в боте)",
            standards_text=cleaned_custom,
            required_sections=sections,
            rules_dict=rules,
        )

    return await db.save_user_market_standards(
        user_id=user_id,
        preset_key=base_preset["preset_key"],
        title=base_preset["title"],
        standards_text=base_preset["standards_text"],
        required_sections=base_preset["required_sections"],
        rules_dict=base_preset["rules"],
    )


async def get_market_standards(db: Database, user_id: int) -> Dict[str, Any]:
    """Возвращает активные стандарты рынка для пользователя.
    По умолчанию возвращает «Золотой стандарт» — Executive CV (Framework 2026+).
    """
    saved = await db.get_user_market_standards(user_id)
    if saved:
        return saved
    default_preset = MARKET_STANDARDS_PRESETS[DEFAULT_PRESET_KEY]
    return {
        "user_id": user_id,
        "preset_key": default_preset["preset_key"],
        "title": default_preset["title"],
        "standards_text": default_preset["standards_text"],
        "required_sections": default_preset["required_sections"],
        "rules": default_preset["rules"],
    }


async def reset_market_standards(db: Database, user_id: int) -> Dict[str, Any]:
    """Сбрасывает стандарты рынка пользователя к «Золотому стандарту» Executive CV (Framework 2026+)."""
    await db.delete_user_market_standards(user_id)
    return await get_market_standards(db, user_id)


# =============================================================================
# 2. ОТДЕЛЬНАЯ ФУНКЦИЯ ФОРМИРОВАНИЯ ИДЕАЛЬНОГО РЕЗЮМЕ (EXECUTIVE CV 2026+)
# =============================================================================

def _tag_tokens(tag: str) -> Set[str]:
    """Токенизирует тег для проверки дублей («P&L» ≈ «P&L Management»)."""
    stop = {"and", "и", "of", "the", "for", "по", "в"}
    return {
        token
        for token in re.split(r"[^0-9a-zа-яё]+", tag.lower())
        if token and token not in stop
    }


def _is_probable_duplicate_tag(tag: str, used_tokens: List[Set[str]]) -> bool:
    """True, если тег уже присутствует в облаке (полное совпадение или вложенность)."""
    tokens = _tag_tokens(tag)
    if not tokens:
        return True
    for existing in used_tokens:
        if tokens == existing:
            return True
        # «P&L» внутри «P&L Management», «Omnichannel» внутри «Omnichannel & Marketplaces»
        if tokens.issubset(existing) and len(existing) <= 3:
            return True
        # «Omnichannel Strategy» при уже добавленном «Omnichannel & Marketplaces»
        if len(tokens) <= 2 and len(existing) <= 2 and tokens & existing:
            return True
    return False


def categorize_core_expertise_tags(skills: List[str], raw_text: str) -> Dict[str, str]:
    """Формирует 📌 3. КЛЮЧЕВУЮ ЭКСПЕРТИЗУ (Core Expertise / ATS Keywords)
    в виде облака тегов через разделитель `|` по 3 кластерам Executive CV 2026+:
    - Business & Strategy
    - Operations
    - Leadership & Tech

    Используется точная рыночная лексика (ATS vocabulary) без дублей:
    «P&L» не повторяется рядом с «P&L Management» и т.п.
    """
    # Строки-заголовки навыков исключаем: их содержимое приходит отдельным списком
    body_text = "\n".join(
        line
        for line in raw_text.splitlines()
        if not re.match(
            r"^\s*(навыки|ключевые навыки|экспертиза|стек|технологии|skills|competencies)\b",
            line,
            re.I,
        )
    )
    text_lower = body_text.lower()
    business_tags: List[str] = []
    operations_tags: List[str] = []
    leadership_tech_tags: List[str] = []

    business_keywords = {
        "p&l": "P&L Management",
        "p&l management": "P&L Management",
        "стратег": "Commercial & Business Strategy",
        "commercial strategy": "Commercial & Business Strategy",
        "бюджет": "Budgeting & Cost Control",
        "unit": "Unit Economics",
        "юнит": "Unit Economics",
        "b2b": "B2B Development",
        "b2c": "B2C / Retail Growth",
        "roi": "ROI / ROMI Optimization",
        "выручк": "Revenue Growth",
        "маркетплейс": "Omnichannel & Marketplaces",
        "marketplace": "Omnichannel & Marketplaces",
        "omnichannel": "Omnichannel Strategy",
        "омниканал": "Omnichannel Strategy",
        "product": "Product & Go-To-Market Strategy",
    }
    operations_keywords = {
        "категор": "Category Management",
        "category": "Category Management",
        "otb": "CAP / OTB Planning",
        "cap/otb": "CAP / OTB Planning",
        "закуп": "Procurement & Inventory",
        "логист": "Supply Chain & Logistics",
        "supply chain": "Supply Chain & Logistics",
        "ценообраз": "Pricing & Margin Management",
        "pricing": "Pricing Strategy",
        "inventory": "Inventory & Stock Optimization",
        "процесс": "Operating Model & Process Optimization",
        "operating model": "Operating Model & Process Optimization",
        "kpi": "KPI & SLA Management",
        "agile": "Agile / Scrum Delivery",
        "scrum": "Scrum / Kanban",
        "etl": "Data Pipelines & ETL",
        "парсинг": "Automated Data Extraction",
    }
    leadership_keywords = {
        "команд": "Team Building & Leadership",
        "team building": "Team Building & Leadership",
        "управлен": "Cross-functional Leadership",
        "change": "Change Management",
        "трансформац": "Organizational Transformation",
        "1с": "1C / ERP",
        "1c": "1C / ERP",
        "erp": "ERP Systems",
        "1c / erp": "1C / ERP",
        "bi": "BI & Analytics",
        "crm": "CRM Architecture",
    }

    used_tokens: List[Set[str]] = []

    def _add(tag: str, bucket: List[str]) -> None:
        if _is_probable_duplicate_tag(tag, used_tokens):
            return
        bucket.append(tag)
        used_tokens.append(_tag_tokens(tag))

    for key, tag in business_keywords.items():
        if key in text_lower:
            _add(tag, business_tags)

    for key, tag in operations_keywords.items():
        if key in text_lower:
            _add(tag, operations_tags)

    for key, tag in leadership_keywords.items():
        if key in text_lower:
            _add(tag, leadership_tech_tags)

    business_triggers = (
        "b2b", "b2c", "roi", "romi", "стратег", "p&l", "бюджет", "маркетплейс",
        "marketplace", "omnichannel", "product", "выручк", "revenue", "unit",
    )
    operations_triggers = (
        "категор", "category", "otb", "cap", "закуп", "procure", "pricing",
        "ценообраз", "logist", "supply", "inventory", "склад", "agile", "scrum",
        "kpi", "процесс", "process", "erp",
    )

    # Распределяем извлечённые из резюме навыки по профильным кластерам,
    # приводя их к точной рыночной лексике (ATS vocabulary):
    # «P&L» -> «P&L Management», «Omnichannel» -> «Omnichannel Strategy» и т.д.
    for skill in skills:
        skill_clean = skill.strip()
        if not skill_clean or len(skill_clean) > 45:
            continue
        s_low = skill_clean.lower()

        canonical: Optional[str] = None
        canonical_bucket: Optional[List[str]] = None
        for keyword_map, bucket in (
            (business_keywords, business_tags),
            (operations_keywords, operations_tags),
            (leadership_keywords, leadership_tech_tags),
        ):
            mapped = keyword_map.get(s_low)
            if mapped:
                canonical = mapped
                canonical_bucket = bucket
                break
        if canonical and canonical_bucket is not None:
            _add(canonical, canonical_bucket)
            continue

        if any(trigger in s_low for trigger in business_triggers):
            _add(skill_clean, business_tags)
        elif any(trigger in s_low for trigger in operations_triggers):
            _add(skill_clean, operations_tags)
        else:
            has_latin = bool(re.search(r"[A-Za-z]", skill_clean))
            leadership_triggers = ("команд", "лидер", "управлен", "наставн", "ментор")
            if has_latin or any(trigger in s_low for trigger in leadership_triggers):
                _add(skill_clean, leadership_tech_tags)

    # Гарантируем наполненность всех 3 строк релевантной рыночной лексикой (ATS vocabulary)
    if not business_tags:
        business_tags = ["Business Planning", "Operational Efficiency", "Target KPI Delivery"]
    if not operations_tags:
        operations_tags = ["Process Optimization", "Quality & SLA Control", "Cross-team Coordination"]
    if not leadership_tech_tags:
        leadership_tech_tags = ["Cross-functional Collaboration", "Analytical Systems", "Project Execution"]

    return {
        "business_strategy": " | ".join(business_tags[:8]),
        "operations": " | ".join(operations_tags[:8]),
        "leadership_tech": " | ".join(leadership_tech_tags[:10]),
    }


def _clean_residual_fragments(text: str) -> str:
    """Убирает «осиротевшие» запятые и пустые фрагменты после удаления Red Flags."""
    cleaned_lines: List[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        line = re.sub(r"\s{2,}", " ", line)
        fragments = re.split(r"(?<=[,;|])\s+", line)
        kept = [
            frag.strip()
            for frag in fragments
            if re.search(r"[0-9A-Za-zА-Яа-яЁё]", frag.replace(",", "").replace(";", ""))
        ]
        joined = " ".join(kept).strip()
        joined = re.sub(r"([,;:|])(\s*[,;:|])+", r"\1", joined)
        joined = re.sub(r"\s*,\s*$", "", joined).strip()
        if joined:
            cleaned_lines.append(joined)
    return "\n".join(cleaned_lines)


def strip_red_flags_and_demographics(text: str) -> Tuple[str, List[str]]:
    """Фильтр «Борьба с Red Flags»: удаляет фото, дату рождения, возраст, семейное положение и штампы."""
    removed_items: List[str] = []
    cleaned = text

    for pattern in DEMOGRAPHIC_RED_FLAG_PATTERNS:
        matches = pattern.findall(cleaned)
        if matches:
            removed_items.extend(m.strip() for m in matches if m.strip())
            cleaned = pattern.sub("", cleaned)

    for cliche in CLICHE_WORDS:
        if cliche in cleaned.lower():
            removed_items.append(f"штамп «{cliche}»")
            cleaned = re.sub(
                r"[,;\s]*" + re.escape(cliche) + r"[,;.\s]*",
                " ",
                cleaned,
                flags=re.I,
            )

    return _clean_residual_fragments(cleaned).strip(), removed_items


_ROLE_LINE_RE = re.compile(
    r"^(?:должность|позиция|role|position|целевая должность)\s*[:\-–]\s*(.+)$", re.I
)
_YEAR_RANGE_RE = re.compile(
    r"((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2}|наст\.?\s*вр\.?|н\.?\s*в\.?|present|current)",
    re.I,
)
_COMPANY_RE = re.compile(
    r"\b(ооо|оао|зао|пао|ао|групп|group|holding|холдинг|llc|ltd|inc|corp|company|компания|retail|ритейл)\b",
    re.I,
)


def _parse_period(text: str) -> str:
    """Возвращает период в формате «2020 — 2026» или «2020 — настоящее время»."""
    match = _YEAR_RANGE_RE.search(text)
    if not match:
        return ""
    end = match.group(2)
    if not re.fullmatch(r"(?:19|20)\d{2}", end):
        end = "настоящее время"
    return f"{match.group(1)} — {end}"


def _looks_like_company_header(line: str) -> bool:
    if line.startswith(("-", "•", "*", "–", "—")):
        return False
    if len(line) > 190:
        return False
    return bool(_YEAR_RANGE_RE.search(line) or _COMPANY_RE.search(line))


def _split_sentences(text: str) -> List[str]:
    return [s.strip(" .;,") for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def build_ideal_executive_cv_2026(
    raw_text: str,
    extracted_role: str,
    extracted_skills: List[str],
    standards: Dict[str, Any],
    audit: Dict[str, Any],
) -> str:
    """Отдельная функция формирования идеального резюме по «Золотому стандарту»:
    🏛 АРХИТЕКТУРА ИДЕАЛЬНОГО EXECUTIVE CV (Framework 2026+).

    Применяет все 5 архитектурных блоков и 4 фильтра упаковки:
    - Evidence Map (не более 4-х буллитов ключевых результатов на роль)
    - Attribution (прозрачная атрибуция личного и командного вклада)
    - Борьба с Red Flags (удаление фото, возраста, семейного положения и воды)
    - Один фокус — один экран (продающий верх Page 1 за 7–30 секунд)
    """
    cleaned_raw, removed_red_flags = strip_red_flags_and_demographics(raw_text)
    lines = [line.strip() for line in cleaned_raw.splitlines() if line.strip()]

    # -------------------------------------------------------------------------
    # 📌 1. HEADER (Шапка) — Фундамент
    # -------------------------------------------------------------------------
    candidate_name = lines[0] if lines else "ИМЯ ФАМИЛИЯ"
    if len(candidate_name) > 60 or any(
        tok in candidate_name.lower()
        for tok in ("резюме", "опыт", "навыки", "должность", "@", "профиль")
    ):
        candidate_name = "КАНДИДАТ (ФИО)"

    role_title = (extracted_role or "Целевая должность").strip()
    domain_hint = " / ".join(extracted_skills[:2]) if extracted_skills else "Strategy & Operations"

    location_str = "Город | Готовность к командировкам / релокации / гибридному формату"
    contact_items: List[str] = []

    experience_lines: List[str] = []
    education_lines: List[str] = []
    project_lines: List[str] = []
    summary_source_lines: List[str] = []

    current_section = "experience"
    for idx, line in enumerate(lines):
        if idx == 0 and line == candidate_name:
            continue

        # Целевая должность / текущая позиция
        role_match = _ROLE_LINE_RE.match(line)
        if role_match:
            role_title = role_match.group(1).strip()
            continue

        # Локация
        loc_match = re.search(
            r"(?:город|локация|проживание|location)\s*[:\-–]\s*(.+)", line, re.I
        )
        if loc_match:
            raw_location = loc_match.group(1).strip(" .,;")
            if raw_location and "релокац" not in raw_location.lower() and "командиров" not in raw_location.lower():
                raw_location += " | Готовность к командировкам / релокации"
            if raw_location:
                location_str = raw_location
            continue

        # Контакты (Телефон, Email, LinkedIn, Telegram)
        if not _YEAR_RANGE_RE.search(line) and re.search(
            r"(@[\w_]+|[\w\.-]+@[\w\.-]+\.\w+|\+\d[\d\-\s\(\)]{9,}|linkedin\.com|github\.com|t\.me/)",
            line,
            re.I,
        ):
            contact_value = re.sub(
                r"^\s*(?:контакты|contacts|связь)\s*[:\-–]\s*", "", line, flags=re.I
            )
            for part in re.split(r"[,;|]\s*", contact_value):
                part = part.strip(" .,|")
                if part and part not in contact_items:
                    contact_items.append(part)
            continue

        # Определение секций
        edu_inline = re.match(
            r"^(?:образование|вуз|университет|курсы|языки|education|languages)\s*[:\-–]?\s*(.*)",
            line,
            re.I,
        )
        if edu_inline:
            current_section = "education"
            if edu_inline.group(1).strip():
                education_lines.append(edu_inline.group(1).strip())
            continue
        proj_inline = re.match(r"^(?:ключевые проекты|проекты|кейсы|projects)\s*[:\-–]?\s*(.*)", line, re.I)
        if proj_inline:
            current_section = "projects"
            if proj_inline.group(1).strip():
                project_lines.append(proj_inline.group(1).strip())
            continue
        sum_inline = re.match(
            r"^(?:о себе|профиль|summary|executive summary|цель)\s*[:\-–]?\s*(.*)", line, re.I
        )
        if sum_inline:
            current_section = "summary"
            if sum_inline.group(1).strip():
                summary_source_lines.append(sum_inline.group(1).strip())
            continue
        if re.match(r"^(опыт работы|профессиональный опыт|опыт|карьера|experience)\b", line, re.I):
            current_section = "experience"
            continue
        if re.match(
            r"^(навыки|ключевые навыки|экспертиза|стек|технологии|skills|competencies)\b",
            line,
            re.I,
        ):
            continue

        # Усиление глаголов действия по стандарту
        improved_line = line
        for pattern, replacement in WEAK_TO_STRONG_VERBS:
            improved_line = pattern.sub(replacement, improved_line)

        if current_section == "education":
            education_lines.append(improved_line)
        elif current_section == "projects":
            project_lines.append(improved_line)
        elif current_section == "summary":
            summary_source_lines.append(improved_line)
        else:
            experience_lines.append(improved_line)

    if "|" not in role_title and domain_hint:
        target_role_vector = f"{role_title} | {domain_hint}"
    else:
        target_role_vector = role_title

    contacts_line = (
        " | ".join(contact_items)
        if contact_items
        else "Телефон: +7 (XXX) XXX-XX-XX | Email: candidate@example.com | LinkedIn / Telegram: @username"
    )

    # -------------------------------------------------------------------------
    # 📌 3. КЛЮЧЕВАЯ ЭКСПЕРТИЗА (Core Expertise / ATS Keywords через |)
    # -------------------------------------------------------------------------
    core_tags = categorize_core_expertise_tags(extracted_skills, cleaned_raw)

    # -------------------------------------------------------------------------
    # 📌 2. ПРОФИЛЬ (Executive Summary) — Продающий хук (3–5 строк по формуле)
    #    [Уровень + опыт] + [Масштаб бизнеса] + [Ключевая экспертиза] + [Результат]
    # -------------------------------------------------------------------------
    years_number: Optional[int] = None
    years_match = re.search(
        r"(\d{1,2})\s*\+?\s*(?:лет|года|год)\s*(?:опыта|в|работы)?", cleaned_raw, re.I
    )
    if years_match:
        try:
            years_number = int(years_match.group(1))
        except ValueError:
            years_number = None
    if years_number is None:
        years_match_alt = re.search(r"(?:опыт[а-я]*\s*[:\-–]?\s*)(\d{1,2})\s*\+?\s*лет", cleaned_raw, re.I)
        if years_match_alt:
            years_number = int(years_match_alt.group(1))

    if years_number and years_number >= 10:
        seniority = "Senior-level руководитель"
    elif years_number:
        seniority = "Руководитель"
    elif re.search(r"director|директор|head|руководител", role_title, re.I):
        seniority = "Руководитель"
    else:
        seniority = "Специалист"

    experience_phrase = (
        f"с опытом {years_number}+ лет"
        if years_number
        else "с подтверждённым профильным опытом"
    )

    scale_sentences: List[str] = []
    seen_scale: Set[str] = set()
    for src_line in summary_source_lines:
        for sentence in _split_sentences(src_line):
            sentence_low = sentence.lower()
            if len(sentence) < 22:
                continue
            if sentence_low.startswith(("и ", "а ", "также ")):
                continue
            if re.search(r"\d{1,2}\s*\+?\s*(?:лет|года|год)\s*опыта", sentence_low):
                # Стаж уже вынесен в начало формулы — сохраняем только отраслевой контекст
                remainder = re.sub(
                    r"\d{1,2}\s*\+?\s*(?:лет|года|год)\s*(?:опыта|работы)?",
                    "",
                    sentence,
                    flags=re.I,
                ).strip(" .,;")
                remainder = re.sub(r"^(?:в|во)\s+", "", remainder, flags=re.I)
                if len(remainder) >= 10:
                    sentence = f"Отраслевой бэкграунд: {remainder}"
                else:
                    continue
            key = sentence_low[:40]
            if key in seen_scale:
                continue
            seen_scale.add(key)
            scale_sentences.append(sentence)
    scale_block = " ".join(scale_sentences)[:220].strip()
    if scale_block and not scale_block.endswith("."):
        scale_block += "."

    metrics_found = re.findall(
        r"((?:х|x)\s?\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s*%|\d+\+?\s*(?:млрд|млн|тыс|магазинов|человек|сотрудников|SKU|проектов))",
        cleaned_raw,
        re.I,
    )
    metrics_unique: List[str] = []
    for metric in metrics_found:
        metric = metric.strip()
        if metric.lower() not in {m.lower() for m in metrics_unique}:
            metrics_unique.append(metric)
    flagship_metric = (
        f"Ключевой результат-визитка: {', '.join(metrics_unique[:3])}."
        if metrics_unique
        else "Главный результат-визитка: [добавьте 1 результат в цифрах: рост выручки, экономия, запуск контура х2–х3]."
    )

    hook_tags: List[str] = []
    for bucket_key in ("business_strategy", "operations", "leadership_tech"):
        for tag in core_tags[bucket_key].split(" | "):
            if tag and tag not in hook_tags:
                hook_tags.append(tag)
    core_skills_hook = (
        ", ".join(hook_tags[:5])
        if hook_tags
        else "управление эффективностью и развитие направления"
    )

    summary_parts = [f"{seniority} ({role_title}) {experience_phrase}."]
    if scale_block:
        summary_parts.append(scale_block)
    summary_parts.append(f"Ключевая экспертиза: {core_skills_hook}.")
    summary_parts.append(flagship_metric)
    executive_summary = " ".join(summary_parts)

    # -------------------------------------------------------------------------
    # 📌 4. ОПЫТ РАБОТЫ (Professional Experience) — Ядро резюме
    # Правило Evidence Map: НЕ БОЛЕЕ 4 буллитов ключевых результатов на роль.
    # Правило Attribution: прозрачная акрибуция цифр и механизма влияния.
    # -------------------------------------------------------------------------
    max_bullets = int(standards.get("rules", {}).get("max_bullets_per_role", 4))

    roles: List[Dict[str, Any]] = []
    current_role: Optional[Dict[str, Any]] = None
    orphan_lines: List[str] = []

    def _new_role(header: str) -> Dict[str, Any]:
        period = _parse_period(header)
        header_clean = re.sub(r"\(?\s*" + _YEAR_RANGE_RE.pattern + r"\s*\)?", "", header).strip(" ,;—-–")
        return {
            "header": header_clean or header.strip(),
            "period": period,
            "title": "",
            "context": "",
            "scope": [],
            "bullets": [],
        }

    for exp_line in experience_lines:
        clean_b = exp_line.lstrip("•-*–— ").strip()
        if not clean_b:
            continue

        if _looks_like_company_header(clean_b) and len(clean_b) < 190:
            current_role = _new_role(clean_b)
            roles.append(current_role)
            continue

        role_in_bullet = _ROLE_LINE_RE.match(clean_b)
        if role_in_bullet and current_role is not None:
            current_role["title"] = role_in_bullet.group(1).strip()
            continue

        if current_role is None:
            # Строки до первого заголовка компании не создают «фантомную» роль:
            # копим их и прикрепляем к реальной роли ниже (или к fallback-роли).
            orphan_lines.append(exp_line)
            continue

        is_bullet = exp_line.startswith(("-", "•", "*", "–", "—"))
        has_metric = bool(re.search(r"\d", clean_b))
        strong_verb = any(
            clean_b.lower().startswith(verb.lower())
            for verb in (
                "Разработал", "Внедрил", "Создал", "Масштабировал", "Управлял",
                "Увеличил", "Настроил", "Оптимизировал", "Реализовал", "Возглавил",
                "Спроектировал", "Обеспечил", "Вывел", "Сократил", "Запустил",
            )
        )

        if is_bullet or has_metric or strong_verb:
            if not has_metric:
                clean_b += (
                    " -> [Формула: Глагол + Метрика + Механизм: добавьте цифру результата "
                    "(%, х2, руб.) и уточните личный вклад (Attribution)]"
                )
            current_role["bullets"].append(clean_b)
        elif len(clean_b) <= 160:
            scope_text = re.sub(
                r"^(?:scope|область охвата|зона ответственности)\s*[:\-–]\s*",
                "",
                clean_b,
                flags=re.I,
            ).strip(" .,;")
            if scope_text:
                current_role["scope"].append(scope_text)

    if not roles:
        roles = [
            {
                "header": f"{role_title} — [Название компании | Сфера и масштаб бизнеса]",
                "period": "[Месяц Год — Настоящее время]",
                "title": role_title,
                "context": "",
                "scope": [],
                "bullets": [],
            }
        ]

    if roles and orphan_lines:
        # Полезные строки «до первой компании» относим к самой первой роли
        first_role = roles[0]
        for orphan in orphan_lines:
            clean_o = orphan.lstrip("•-*–— ").strip()
            if not clean_o or len(clean_o) > 200:
                continue
            if re.search(r"\d", clean_o):
                first_role["bullets"].insert(0, clean_o)
            elif len(clean_o) <= 160:
                first_role["scope"].insert(0, clean_o)

    # Применяем правило Evidence Map: не более max_bullets результатов на роль
    omitted_bullets_count = 0
    for role in roles:
        if len(role["bullets"]) > max_bullets:
            omitted_bullets_count += len(role["bullets"]) - max_bullets
            role["bullets"] = role["bullets"][:max_bullets]
        if not role["title"]:
            role["title"] = role_title

    role_blocks: List[str] = []
    for role in roles:
        scope_items = role["scope"][:4]
        if not scope_items:
            scope_items = [
                f"Стратегия и целевые KPI направления ({role['title']})",
                f"Управление P&L и бюджетом, операционная модель",
                f"Кросс-функциональное взаимодействие: {', '.join(hook_tags[:3]) or 'профильные функции'}",
            ]
        scope_line = " | ".join(scope_items)

        context_line = (
            f"Зона ответственности: P&L и бюджет направления «{role['title']}»; "
            f"прямые подчинённые и кросс-функциональные команды "
            f"[укажите численность: X прямых подчинённых / Y в матрице]."
        )

        bullets = role["bullets"] or [
            f"• Реализовал ключевые цели на позиции «{role['title']}»: [метрика х2 / +X%] "
            f"за счёт внедрения {core_skills_hook} (личный вклад в архитектуру и запуск).",
            "• Оптимизировал операционную модель: сократил издержки/время цикла на [X%] "
            "благодаря перестройке регламентов и автоматизации.",
            "• Масштабировал целевые показатели направления: выполнение плана на [100%+] "
            "при личном участии в кросс-функциональной команде.",
        ]
        bullets_formatted = "\n".join(
            b if b.lstrip().startswith("•") else f"• {b}" for b in bullets
        )

        role_blocks.extend(
            [
                f"### {role['header']}",
                f"**Должность:** {role['title']} | **Период:** {role['period'] or '[Месяц Год — Месяц Год]'}",
                f"**Контекст роли:** {context_line}",
                f"**Scope (Область охвата):** {scope_line}",
                f"**Ключевые результаты (Глагол действия + Метрика + Механизм/Влияние, макс. {max_bullets} пункта):**",
                bullets_formatted,
                "",
            ]
        )

    # -------------------------------------------------------------------------
    # 📌 5. ДОПОЛНИТЕЛЬНЫЕ БЛОКИ (Образование и языки, Ключевые проекты)
    # -------------------------------------------------------------------------
    edu_formatted = (
        "\n".join(f"• {e.lstrip('•-* ').strip()}" for e in education_lines[:4])
        if education_lines
        else (
            "• Высшее профильное образование: [ВУЗ, специальность, год выпуска]\n"
            "• Иностранные языки: Английский — [уровень: B2 / Upper-Intermediate, опыт переговоров]"
        )
    )

    if project_lines:
        projects_formatted = "\n".join(
            f"• {p.lstrip('•-* ').strip()}" for p in project_lines[:2]
        )
    else:
        projects_formatted = (
            "• **Кейс 1 (Проблема -> Решение -> Результат в цифрах):** "
            "[бизнес-проблема -> решение, внедрённое лично вами -> оцифрованный эффект]."
        )

    # -------------------------------------------------------------------------
    # ⚠️ ОТЧЁТ ПО 4 ПРАВИЛАМ УПАКОВКИ (Packaging Filters Report)
    # -------------------------------------------------------------------------
    red_flags_note = (
        f"Автоматически удалено нежелательных демографических маркеров и штампов: {len(removed_red_flags)} шт."
        if removed_red_flags
        else "Лишние демографические данные (фото, возраст, семейное положение) и штампы отсутствуют."
    )
    evidence_map_note = (
        f"Применён лимит ≤ {max_bullets} буллитов на роль (сокращено второстепенных пунктов для интервью: {omitted_bullets_count})."
        if omitted_bullets_count > 0
        else f"Соблюдён лимит ≤ {max_bullets} самых сильных буллитов результата на роль (структура под 2 страницы макс.)."
    )

    output_blocks: List[str] = [
        f"# {candidate_name.upper()}",
        f"### {target_role_vector}",
        f"📍 **Локация и формат:** {location_str}",
        f"📞 **Контакты:** {contacts_line}",
        "_Правило Header: без фото, даты рождения и семейного положения — только факты для связи._",
        "",
        "## 📌 2. ПРОФИЛЬ (Executive Summary)",
        executive_summary,
        "",
        "## 📌 3. КЛЮЧЕВАЯ ЭКСПЕРТИЗА (Core Expertise / ATS Keywords)",
        f"• **Business & Strategy:** {core_tags['business_strategy']}",
        f"• **Operations:** {core_tags['operations']}",
        f"• **Leadership & Tech:** {core_tags['leadership_tech']}",
        "",
        "## 📌 4. ОПЫТ РАБОТЫ (Professional Experience)",
        "",
        "\n".join(role_blocks).strip(),
        "",
        "## 📌 5. ДОПОЛНИТЕЛЬНЫЕ БЛОКИ",
        "### Образование и языки",
        edu_formatted,
        "",
        "### Ключевые проекты (Проблема -> Решение -> Результат в цифрах)",
        projects_formatted,
        "",
        "---",
        "### ⚠️ Применённые фильтры «Золотого стандарта» (Executive CV Framework 2026+):",
        f"1. **Evidence Map (Карта доказательств):** {evidence_map_note}",
        "2. **Attribution (Атрибуция цифр):** Результаты сформулированы с выделением личного вклада и механизма достижения.",
        f"3. **Борьба с Red Flags:** {red_flags_note}",
        "4. **Один фокус — один экран:** Верхняя половина Page 1 (Header + Executive Summary + Core Expertise) скомпонована для продажи профиля за 7–30 секунд.",
    ]

    return "\n".join(output_blocks).strip()


# =============================================================================
# 2.1 ПОКАЗ ЭТАЛОННОГО ПРИМЕРА ИДЕАЛЬНОГО РЕЗЮМЕ (Executive CV Framework 2026+)
# =============================================================================

def build_ideal_executive_cv_2026_example() -> Dict[str, Any]:
    """Отдельная функция показа примера идеального резюме по «Золотому стандарту».

    Не требует загруженного резюме и не обращается к базе данных: берёт встроенный
    «грязный» образец (`EXECUTIVE_CV_2026_EXAMPLE_RAW`), прогоняет его через
    `build_ideal_executive_cv_2026()` и возвращает:

    - `intro` — короткое пояснение, что показывает пример;
    - `example_text` — готовый эталонный Executive CV (Markdown);
    - `structure` — карта 5 блоков архитектуры и 4 фильтров упаковки;
    - `audit` — ATS-оценка исходного образца по Золотому стандарту;
    - `docx_bytes` — тот же пример в файле `.docx` для скачивания.
    """
    preset = MARKET_STANDARDS_PRESETS[DEFAULT_PRESET_KEY]
    example_role = "Commercial Director"
    example_skills = [
        "P&L",
        "Commercial Strategy",
        "Category Management",
        "CAP/OTB",
        "Omnichannel",
        "BI",
        "ERP",
        "Pricing",
        "Inventory",
        "Team Building",
    ]

    audit = audit_resume_against_standards(
        raw_text=EXECUTIVE_CV_2026_EXAMPLE_RAW,
        extracted_role=example_role,
        extracted_skills=example_skills,
        standards=preset,
    )
    example_text = build_ideal_executive_cv_2026(
        raw_text=EXECUTIVE_CV_2026_EXAMPLE_RAW,
        extracted_role=example_role,
        extracted_skills=example_skills,
        standards=preset,
        audit=audit,
    )

    intro = "\n".join(
        [
            "🏛 **ЭТАЛОННЫЙ ПРИМЕР ИДЕАЛЬНОГО РЕЗЮМЕ — Executive CV (Framework 2026+)**",
            "_Золотой стандарт: 2 страницы максимум, верхняя половина Page 1 продаёт за 7–30 секунд._",
            "",
            "Ниже — резюме, собранное автоматически функцией `build_ideal_executive_cv_2026()` из «грязного» "
            "исходного образца: с фото, датой рождения, семейным положением и клише «ответственный и "
            "коммуникабельный». Обратите внимание, как фильтры убирают Red Flags и оставляют только "
            "продающие факты.",
        ]
    )

    structure = [
        "📌 1. HEADER — ФИО, целевой вектор строго под ФИО, локация + релокация, контакты (без фото и демографии)",
        "📌 2. ПРОФИЛЬ — 3–5 строк: уровень + опыт, масштаб бизнеса, экспертиза, результат-визитка",
        "📌 3. КЛЮЧЕВАЯ ЭКСПЕРТИЗА — ATS-теги через «|»: Business & Strategy / Operations / Leadership & Tech",
        "📌 4. ОПЫТ РАБОТЫ — компания и масштаб, период, контекст роли, Scope 3–4 пункта, результаты ≤ 4 на роль",
        "📌 5. ДОПОЛНИТЕЛЬНЫЕ БЛОКИ — образование и языки с уровнем, ключевые проекты (Проблема -> Решение -> Результат)",
        "⚠️ Фильтры: Evidence Map · Attribution · Red Flags · Один фокус — один экран",
    ]

    return {
        "standard": preset["title"],
        "intro": intro,
        "example_text": example_text,
        "structure": structure,
        "audit": audit,
        "docx_bytes": build_adapted_resume_docx_bytes(example_text),
    }


# =============================================================================
# 3. АУДИТ И АДАПТАЦИЯ РЕЗЮМЕ ПОД АКТИВНЫЕ СТАНДАРТЫ РЫНКА
# =============================================================================

def audit_resume_against_standards(
    raw_text: str,
    extracted_role: str,
    extracted_skills: List[str],
    standards: Dict[str, Any],
) -> Dict[str, Any]:
    """Проводит детальный аудит исходного резюме на соответствие заданным стандартам рынка
    (включая проверки Executive CV Framework 2026+).
    """
    text_lower = raw_text.lower()
    score = 40
    strengths: List[str] = []
    improvements: List[str] = []

    # 1. Проверка контактов в Header
    has_contacts = bool(
        re.search(r"(@[\w_]+|[\w\.-]+@[\w\.-]+\.\w+|\+?\d[\d\-\s\(\)]{8,}|linkedin\.com)", raw_text, re.I)
    )
    if has_contacts:
        score += 10
        strengths.append("Header содержит прямые контакты для связи.")
    else:
        improvements.append(
            "В блоке HEADER указать телефон, Email, LinkedIn / Telegram и город с готовностью к релокации/командировкам."
        )

    # 2. Проверка на Red Flags в шапке (возраст, дата рождения, семейное положение, фото)
    _, red_flags_removed = strip_red_flags_and_demographics(raw_text)
    if red_flags_removed:
        improvements.append(
            f"Фильтр «Борьба с Red Flags»: автоматически убраны лишние данные и клише ({', '.join(red_flags_removed[:4])})."
        )
    else:
        score += 10
        strengths.append("Отсутствуют демографические Red Flags (возраст, семейное положение, фото) и штампы.")

    # 3. Проверка количественных метрик и формулы Глагол + Метрика + Механизм
    metrics_matches = re.findall(
        r"((?:х|x)\d+(?:[.,]\d+)?|\d+\s*%|\bв\s*\d+(?:[.,]\d+)?\s*раз|\d+\+?\s*(?:млрд|млн|тыс|ч|часов|дней|мс|сек|rps|магазинов|проектов|пользователей|клиентов))",
        text_lower,
    )
    if len(metrics_matches) >= 2:
        score += 20
        strengths.append(
            f"Найдены оцифрованные бизнес- и технические показатели ({len(metrics_matches)} метрик)."
        )
    elif len(metrics_matches) == 1:
        score += 10
        improvements.append(
            "Усилить буллиты опыта по формуле «Глагол действия + Метрика (цифра) + Механизм/Влияние» и указать масштаб бизнеса."
        )
    else:
        improvements.append(
            "Добавить оцифрованные результаты в Executive Summary и Опыт работы (оборот, %, рост х2–х3, экономия, KPI) с прозрачной атрибуцией личного вклада (Attribution)."
        )

    # 4. Проверка облака тегов Core Expertise / ATS Keywords
    if len(extracted_skills) >= 5:
        score += 15
        strengths.append(
            f"Сформировано облако тегов Core Expertise ({len(extracted_skills)} рыночных ATS-маркеров)."
        )
    else:
        score += 5
        improvements.append(
            "Расширить блок «Ключевая экспертиза (Core Expertise)» точной рыночной лексикой по кластерам Business & Strategy | Operations | Leadership & Tech."
        )

    # 5. Проверка слабых глаголов
    weak_verbs_count = sum(1 for pattern, _ in WEAK_TO_STRONG_VERBS if pattern.search(raw_text))
    if weak_verbs_count > 0:
        improvements.append(
            f"Заменены пассивные формулировки ({weak_verbs_count} шт.) на сильные глаголы результата."
        )
    else:
        score += 5

    score = min(100, max(15, score))
    return {
        "score": score,
        "strengths": strengths,
        "improvements": improvements,
        "red_flags_removed": red_flags_removed,
        "weak_verbs_replaced": weak_verbs_count,
    }


def _rewrite_resume_locally(
    raw_text: str,
    extracted_role: str,
    extracted_skills: List[str],
    standards: Dict[str, Any],
    audit: Dict[str, Any],
) -> str:
    """Встроенный бесплатный движок адаптации резюме.
    Если активен Золотой стандарт `executive_cv_2026` (по умолчанию),
    применяет полную архитектуру идеального Executive CV (Framework 2026+).
    """
    preset_key = standards.get("preset_key", DEFAULT_PRESET_KEY)
    if preset_key == "executive_cv_2026" or standards.get("rules", {}).get("framework") == "executive_cv_2026":
        return build_ideal_executive_cv_2026(
            raw_text=raw_text,
            extracted_role=extracted_role,
            extracted_skills=extracted_skills,
            standards=standards,
            audit=audit,
        )

    # Для остальных специализированных или кастомных пресетов используем также базу Executive CV 2026+
    # с добавлением специфичных разделов пользователя
    base_cv = build_ideal_executive_cv_2026(
        raw_text=raw_text,
        extracted_role=extracted_role,
        extracted_skills=extracted_skills,
        standards=standards,
        audit=audit,
    )
    custom_header = (
        f"_Применён стандарт: «{standards.get('title', 'Стандарт рынка')}»_\n"
        f"_Обязательные разделы стандарта: {', '.join(standards.get('required_sections', []))}_\n\n"
    )
    return custom_header + base_cv


async def _rewrite_resume_via_free_llm(
    raw_text: str,
    extracted_role: str,
    extracted_skills: List[str],
    standards: Dict[str, Any],
) -> Optional[str]:
    """Если в .env задан бесплатный ключ LLM_API_KEY (Groq / OpenRouter Free / Ollama),
    выполняет интеллектуальную переработку резюме строго по архитектуре Executive CV (Framework 2026+)
    и заданным стандартам рынка.
    """
    if not config.llm_api_key:
        return None

    system_prompt = (
        "Ты — топовый Executive Career Coach и архитектор резюме уровня C-level / Senior.\n"
        "Твоя задача — сформировать идеальное резюме кандидата СТРОГО по следующим требованиям и стандартам рынка:\n\n"
        f"Название стандарта: {standards.get('title')}\n"
        f"Обязательные разделы: {', '.join(standards.get('required_sections', []))}\n\n"
        f"Детальные требования стандарта:\n{standards.get('standards_text')}\n\n"
        "Соблюдай все 4 фильтра упаковки:\n"
        "1. Evidence Map (максимум 2 страницы, не более 4 буллитов результатов на каждую роль).\n"
        "2. Attribution (разделяй личный вклад и командный результат).\n"
        "3. Борьба с Red Flags (никаких фото, дат рождения, семейного положения и штампов вроде «ответственный и коммуникабельный»).\n"
        "4. Один фокус — один экран (верх первой страницы должен продавать кандидата за 7–30 секунд).\n"
        "Ответ верни на русском языке в чёткой структуре Markdown."
    )

    payload = {
        "model": config.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Целевая роль: {extracted_role}\n"
                    f"Распознанные навыки: {', '.join(extracted_skills)}\n\n"
                    f"Исходный текст резюме:\n{raw_text}"
                ),
            },
        ],
        "temperature": 0.25,
    }
    headers = {
        "Authorization": f"Bearer {config.llm_api_key}",
        "Content-Type": "application/json",
    }
    url = f"{config.llm_base_url.rstrip('/')}/chat/completions"

    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                    )
                    if content:
                        return content
    except Exception:
        return None
    return None


async def adapt_resume_to_market_standards(
    db: Database,
    user_id: int,
) -> Dict[str, Any]:
    """Отдельная функция адаптации резюме под стандарты рынка (по умолчанию — Золотой стандарт Executive CV 2026+)."""
    resume_record = await db.get_resume(user_id)
    if not resume_record:
        raise ValueError(
            "Резюме ещё не загружено! Сначала воспользуйтесь функцией «📤 Загрузить резюме»."
        )

    standards = await get_market_standards(db, user_id)
    raw_text = resume_record["raw_text"]
    extracted_role = resume_record.get("extracted_role") or "Специалист"
    extracted_skills = resume_record.get("extracted_skills") or []

    audit = audit_resume_against_standards(
        raw_text=raw_text,
        extracted_role=extracted_role,
        extracted_skills=extracted_skills,
        standards=standards,
    )

    adapted_text = await _rewrite_resume_via_free_llm(
        raw_text=raw_text,
        extracted_role=extracted_role,
        extracted_skills=extracted_skills,
        standards=standards,
    )
    engine_used = (
        "LLM API (Executive CV 2026+ Prompt)"
        if adapted_text
        else "Архитектор Executive CV (Framework 2026+ Золотой стандарт)"
    )

    if not adapted_text:
        adapted_text = _rewrite_resume_locally(
            raw_text=raw_text,
            extracted_role=extracted_role,
            extracted_skills=extracted_skills,
            standards=standards,
            audit=audit,
        )

    await db.save_adapted_resume(user_id=user_id, adapted_text=adapted_text)
    docx_bytes = build_adapted_resume_docx_bytes(adapted_text)

    return {
        "adapted_text": adapted_text,
        "standards": standards,
        "audit": audit,
        "engine_used": engine_used,
        "docx_bytes": docx_bytes,
        "extracted_role": extracted_role,
        "extracted_skills": extracted_skills,
    }


def build_adapted_resume_docx_bytes(adapted_markdown: str) -> bytes:
    """Генерирует готовый файл .docx (рассчитанный на 2 страницы макс. по стандарту Executive CV 2026+)."""
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(10.5)

    for line in adapted_markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            doc.add_heading(stripped[2:].strip(), level=1)
        elif stripped.startswith("## "):
            doc.add_heading(stripped[3:].strip(), level=2)
        elif stripped.startswith("### "):
            doc.add_heading(stripped[4:].strip(), level=3)
        elif stripped.startswith("• ") or stripped.startswith("- "):
            clean_bullet = stripped[2:].replace("**", "")
            doc.add_paragraph(clean_bullet, style="List Bullet")
        elif stripped == "---":
            continue
        else:
            clean_p = stripped.strip("_").replace("**", "")
            doc.add_paragraph(clean_p)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
