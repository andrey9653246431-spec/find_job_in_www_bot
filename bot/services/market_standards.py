"""Модуль управления стандартами рынка и адаптации резюме под стандарты рынка.

Содержит две отдельные ключевые функции согласно ТЗ:
1. `set_market_standards` / `get_market_standards` — отдельная функция задания стандартов рынка внутри бота.
2. `adapt_resume_to_market_standards` — отдельная функция адаптации загруженного резюме под заданные стандарты рынка.
"""
import io
import re
from typing import Any, Dict, List, Optional, Tuple
import aiohttp
from docx import Document
from docx.shared import Pt
from bot.config import config
from bot.database import Database

# Предустановленные шаблоны стандартов рынка (пользователь может выбрать их или задать свои собственные)
MARKET_STANDARDS_PRESETS: Dict[str, Dict[str, Any]] = {
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
            "Целевая позиция и грейд (Junior/Middle/Senior)",
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
            "4. В каждом месте работы: описание проекта, используемый стек и 3-5 достижений с метриками "
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
        "title": "Стандарт рынка Digital-маркетинг и Продажи",
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

# Словарь замены слабых глаголов на сильные глаголы действия (Action Verbs)
WEAK_TO_STRONG_VERBS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bзанимался разработкой\b", re.I), "Разработал и внедрил"),
    (re.compile(r"\bзанималась разработкой\b", re.I), "Разработала и внедрила"),
    (re.compile(r"\bзанимался созданием\b", re.I), "Создал и запустил"),
    (re.compile(r"\bзанимался настройкой\b", re.I), "Настроил и автоматизировал"),
    (re.compile(r"\bзанимался тестированием\b", re.I), "Провёл комплексное тестирование"),
    (re.compile(r"\bзанимался парсингом\b", re.I), "Реализовал пайплайн парсинга"),
    (re.compile(r"\bзанимался\b", re.I), "Реализовал"),
    (re.compile(r"\bзанималась\b", re.I), "Реализовала"),
    (re.compile(r"\bучаствовал в разработке\b", re.I), "Разработал ключевые модули"),
    (re.compile(r"\bучаствовала в разработке\b", re.I), "Разработала ключевые модули"),
    (re.compile(r"\bпринимал участие в\b", re.I), "Реализовал в рамках проекта"),
    (re.compile(r"\bработал над\b", re.I), "Спроектировал и развивал"),
    (re.compile(r"\bписал код\b", re.I), "Разрабатывал масштабируемый код"),
    (re.compile(r"\bделал\b", re.I), "Выполнил"),
]

# Штампы и клише, которые снижают качество резюме по стандартам рынка
CLICHE_WORDS: List[str] = [
    "стрессоустойчивость",
    "стрессоустойчивый",
    "стрессоустойчивая",
    "коммуникабельность",
    "коммуникабельный",
    "коммуникабельная",
    "легкообучаемый",
    "быстро обучаюсь",
    "легко обучаюсь",
    "пунктуальность",
    "пунктуальный",
    "без вредных привычек",
    "уверенный пользователь пк",
]


# =============================================================================
# 1. ОТДЕЛЬНАЯ ФУНКЦИЯ ЗАДАНИЯ СТАНДАРТОВ РЫНКА ВНУТРИ БОТА
# =============================================================================

async def set_market_standards(
    db: Database,
    user_id: int,
    preset_key: str = "universal_ats",
    custom_standards_text: Optional[str] = None,
    custom_required_sections: Optional[List[str]] = None,
    custom_title: Optional[str] = None,
) -> Dict[str, Any]:
    """Отдельная функция задания стандартов рынка внутри бота.

    Позволяет:
    - Выбрать один из отраслевых пресетов стандартов рынка (`universal_ats`, `it_dev`, `data_analytics`, `marketing_sales`).
    - Задать полностью пользовательские стандарты рынка текстом прямо из чата Telegram (`custom_standards_text`).
    """
    base_preset = MARKET_STANDARDS_PRESETS.get(
        preset_key, MARKET_STANDARDS_PRESETS["universal_ats"]
    )

    if custom_standards_text and custom_standards_text.strip():
        cleaned_custom = custom_standards_text.strip()
        # Если пользователь перечислил разделы или правила построчно — извлекаем их
        sections = custom_required_sections or list(base_preset["required_sections"])
        # Проверим, указал ли пользователь свои обязательные разделы через "Разделы:"
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

        # Извлекаем обязательные ключевые слова, если пользователь их указал ("Ключевые слова: ...")
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
            "require_metrics": True,
            "require_action_verbs": True,
            "remove_cliches": True,
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

    # Сохраняем выбранный пресет стандарта рынка
    return await db.save_user_market_standards(
        user_id=user_id,
        preset_key=base_preset["preset_key"],
        title=base_preset["title"],
        standards_text=base_preset["standards_text"],
        required_sections=base_preset["required_sections"],
        rules_dict=base_preset["rules"],
    )


async def get_market_standards(db: Database, user_id: int) -> Dict[str, Any]:
    """Возвращает активные стандарты рынка для пользователя (или стандарт по умолчанию)."""
    saved = await db.get_user_market_standards(user_id)
    if saved:
        return saved
    default_preset = MARKET_STANDARDS_PRESETS["universal_ats"]
    return {
        "user_id": user_id,
        "preset_key": default_preset["preset_key"],
        "title": default_preset["title"],
        "standards_text": default_preset["standards_text"],
        "required_sections": default_preset["required_sections"],
        "rules": default_preset["rules"],
    }


async def reset_market_standards(db: Database, user_id: int) -> Dict[str, Any]:
    """Сбрасывает стандарты рынка пользователя к базовому ATS-стандарту."""
    await db.delete_user_market_standards(user_id)
    return await get_market_standards(db, user_id)


# =============================================================================
# 2. ОТДЕЛЬНАЯ ФУНКЦИЯ АДАПТАЦИИ РЕЗЮМЕ ПОД ЗАДАННЫЕ СТАНДАРТЫ РЫНКА
# =============================================================================

def audit_resume_against_standards(
    raw_text: str,
    extracted_role: str,
    extracted_skills: List[str],
    standards: Dict[str, Any],
) -> Dict[str, Any]:
    """Проводит детальный аудит исходного резюме на соответствие заданным стандартам рынка."""
    text_lower = raw_text.lower()
    score = 40  # Базовый балл за наличие текста резюме
    strengths: List[str] = []
    improvements: List[str] = []

    # 1. Проверка контактов
    has_contacts = bool(
        re.search(r"(@[\w_]+|[\w\.-]+@[\w\.-]+\.\w+|\+?\d[\d\-\s\(\)]{8,})", raw_text)
    )
    if has_contacts:
        score += 10
        strengths.append("Указаны контактные данные для быстрой связи.")
    else:
        improvements.append(
            "Добавить блок контактов (Telegram @username, Email, телефон, ссылки на GitHub/LinkedIn)."
        )

    # 2. Проверка количественных метрик (%, x, числа, показатели)
    metrics_matches = re.findall(
        r"(\d+\s*%|\bв\s*\d+(?:[.,]\d+)?\s*раз|\d+\s*(?:тыс|млн|ч|часов|дней|мс|сек|rps|проектов|пользователей|клиентов))",
        text_lower,
    )
    if len(metrics_matches) >= 2:
        score += 20
        strengths.append(
            f"Найдены оцифрованные достижения ({len(metrics_matches)} метрик по стандарту STAR/XYZ)."
        )
    elif len(metrics_matches) == 1:
        score += 10
        improvements.append(
            "Увеличить количество числовых метрик результата (%, время, деньги, KPI) в каждом месте работы."
        )
    else:
        improvements.append(
            "Оцифровать достижения по формуле XYZ («Достиг X, измеряемого в Y, за счёт Z» — добавить %, сроки, объёмы)."
        )

    # 3. Проверка ключевых навыков
    if len(extracted_skills) >= 5:
        score += 15
        strengths.append(
            f"Выявлен релевантный стек для ATS-скрининга ({len(extracted_skills)} навыков)."
        )
    else:
        score += 5
        improvements.append(
            "Расширить раздел «Ключевые навыки» (добавить минимум 6–10 профильных технологий и инструментов для прохождения ATS)."
        )

    # 4. Проверка обязательных ключевых слов из пользовательского стандарта рынка
    focus_keywords = standards.get("rules", {}).get("focus_keywords", [])
    missing_focus = [
        kw for kw in focus_keywords if kw.lower() not in text_lower
    ]
    if focus_keywords and not missing_focus:
        score += 10
        strengths.append("Присутствуют все целевые маркеры из заданного стандарта рынка.")
    elif missing_focus:
        improvements.append(
            f"По заданному стандарту рынка рекомендуется отразить владение: {', '.join(missing_focus)}."
        )
    else:
        score += 5

    # 5. Проверка на слабые глаголы и клише
    found_cliches = [c for c in CLICHE_WORDS if c in text_lower]
    if found_cliches:
        improvements.append(
            f"Исключены шаблонные клише без доказательств: {', '.join(found_cliches[:4])}."
        )
    else:
        score += 5
        strengths.append("Отсутствуют устаревшие штампы и вода.")

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
        "found_cliches": found_cliches,
        "weak_verbs_replaced": weak_verbs_count,
    }


def _rewrite_resume_locally(
    raw_text: str,
    extracted_role: str,
    extracted_skills: List[str],
    standards: Dict[str, Any],
    audit: Dict[str, Any],
) -> str:
    """Встроенный бесплатный алгоритмический движок адаптации резюме под заданные стандарты рынка.
    Работает мгновенно, бесплатно и без внешних платных ключей API.
    """
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    # 1. Извлекаем имя и контакты из верхних строк, если они есть
    candidate_name = lines[0] if lines else "Кандидат"
    if len(candidate_name) > 65 or any(
        w in candidate_name.lower() for w in ("опыт", "навыки", "обязанности")
    ):
        candidate_name = "Кандидат"

    contact_lines: List[str] = []
    experience_lines: List[str] = []
    education_lines: List[str] = []
    about_lines: List[str] = []

    current_bucket = "experience"
    for idx, line in enumerate(lines):
        low = line.lower()
        # Определяем контакты
        if re.search(r"(@[\w_]+|[\w\.-]+@[\w\.-]+\.\w+|\+?\d[\d\-\s\(\)]{8,}|github\.com|t\.me/)", line):
            if line not in contact_lines:
                contact_lines.append(line)
            continue

        # Переключение секций
        if re.match(r"^(образование|вуз|университет|курсы|сертификаты|education)\b", low):
            current_bucket = "education"
            continue
        if re.match(r"^(о себе|summary|профиль|цель|информация)\b", low):
            current_bucket = "about"
            continue
        if re.match(r"^(опыт работы|опыт|карьера|места работы|проекты|experience)\b", low):
            current_bucket = "experience"
            continue
        if re.match(r"^(навыки|ключевые навыки|стек|технологии|skills)\b", low):
            continue

        if idx == 0 and line == candidate_name:
            continue

        # Очищаем строку от клише
        cleaned_line = line
        for cliche in CLICHE_WORDS:
            cleaned_line = re.sub(
                r"[,;\s]*" + re.escape(cliche) + r"[,;\s]*", " ", cleaned_line, flags=re.I
            ).strip()

        # Усиливаем глаголы действия
        for pattern, replacement in WEAK_TO_STRONG_VERBS:
            cleaned_line = pattern.sub(replacement, cleaned_line)

        if not cleaned_line:
            continue

        if current_bucket == "education":
            education_lines.append(cleaned_line)
        elif current_bucket == "about":
            about_lines.append(cleaned_line)
        else:
            experience_lines.append(cleaned_line)

    # Формируем блоки согласно разделу `required_sections` из активного стандарта рынка
    required_sections = standards.get("required_sections") or [
        "Заголовок и целевая должность",
        "Контакты",
        "Профессиональное резюме (Summary)",
        "Ключевые навыки (Hard Skills)",
        "Опыт работы и измеримые достижения (STAR/XYZ)",
        "Образование и сертификаты",
    ]

    skills_str = ", ".join(extracted_skills) if extracted_skills else "Указать профильные инструменты"
    focus_kw = standards.get("rules", {}).get("focus_keywords", [])
    recommended_kw = [k for k in focus_kw if k.lower() not in {s.lower() for s in extracted_skills}]

    summary_block = (
        " ".join(about_lines)
        if about_lines
        else (
            f"Профильный специалист на позицию «{extracted_role}» с практическим опытом применения "
            f"стека ({', '.join(extracted_skills[:6]) or 'ключевых инструментов отрасли'}). "
            f"Ориентирован на достижение измеримых бизнес- и технических показателей."
        )
    )

    formatted_exp: List[str] = []
    for exp_line in experience_lines:
        bullet = exp_line.lstrip("•-*–— ")
        # Проверяем, есть ли в строке цифровая метрика; если это глагол действия без метрики — добавляем подсказку ATS
        has_number = bool(re.search(r"\d+", bullet))
        if not has_number and any(
            bullet.startswith(v)
            for v in ("Разработал", "Внедрил", "Создал", "Настроил", "Оптимизировал", "Реализовал", "Повысил")
        ):
            bullet = f"{bullet} [рекомендуется уточнить метрику: например, ускорение на X% / снижение затрат на Y]"
        formatted_exp.append(f"• {bullet}")

    if not formatted_exp:
        formatted_exp = [
            f"• Реализовал ключевые задачи на позиции «{extracted_role}» с использованием {skills_str} "
            "[добавьте 2-3 конкретных результата в цифрах по формуле XYZ]."
        ]

    contacts_block = (
        "\n".join(f"• {c}" for c in contact_lines)
        if contact_lines
        else "• Telegram: @username | Email: name@example.com | GitHub/Portfolio: ссылка"
    )

    education_block = (
        "\n".join(f"• {e.lstrip('•-* ')}" for e in education_lines)
        if education_lines
        else "• Высшее / профильное образование и специализированные курсы повышения квалификации"
    )

    sections_output: List[str] = [
        f"# {candidate_name} — {extracted_role}",
        f"_Адаптировано по стандарту: «{standards.get('title', 'Стандарт рынка')}»_",
        "",
        f"## 1. {required_sections[1] if len(required_sections) > 1 else 'Контакты'}",
        contacts_block,
        "",
        f"## 2. {required_sections[2] if len(required_sections) > 2 else 'Профессиональное резюме (Summary)'}",
        summary_block,
        "",
        f"## 3. {required_sections[3] if len(required_sections) > 3 else 'Ключевые навыки (ATS Keywords)'}",
        f"• **Основной стек и компетенции:** {skills_str}",
    ]
    if recommended_kw:
        sections_output.append(
            f"• **Рекомендуемые маркеры стандарта рынка (при наличии опыта):** {', '.join(recommended_kw)}"
        )

    sections_output.extend(
        [
            "",
            f"## 4. {required_sections[4] if len(required_sections) > 4 else 'Опыт работы и достижения (STAR / XYZ)'}",
            "\n".join(formatted_exp),
            "",
            f"## 5. {required_sections[5] if len(required_sections) > 5 else 'Образование и сертификация'}",
            education_block,
            "",
            "---",
            "### Применённые требования стандарта рынка:",
            standards.get("standards_text", ""),
        ]
    )

    return "\n".join(sections_output).strip()


async def _rewrite_resume_via_free_llm(
    raw_text: str,
    extracted_role: str,
    extracted_skills: List[str],
    standards: Dict[str, Any],
) -> Optional[str]:
    """Если в .env задан бесплатный ключ LLM_API_KEY (например Groq / OpenRouter Free / Ollama),
    выполняет интеллектуальную переработку резюме строго по заданным стандартам рынка.
    В случае отсутствия ключа или ошибки сети возвращает None для перехода на встроенный бесплатный движок.
    """
    if not config.llm_api_key:
        return None

    system_prompt = (
        "Ты — экспертный карьерный консультант и ATS-оптимизатор резюме.\n"
        "Твоя задача — адаптировать резюме кандидата СТРОГО под следующие стандарты рынка, "
        "заданные внутри бота:\n\n"
        f"Название стандарта: {standards.get('title')}\n"
        f"Обязательные разделы: {', '.join(standards.get('required_sections', []))}\n"
        f"Правила стандарта:\n{standards.get('standards_text')}\n\n"
        "Сохраняй правдивые факты из резюме кандидата, но переформулируй опыт через глаголы действия "
        "(STAR / XYZ), выдели ключевые навыки для ATS и структурируй документ на русском языке."
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
        "temperature": 0.3,
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
    """Отдельная функция адаптации резюме под стандарты рынка.

    1. Загружает исходное резюме пользователя из БД.
    2. Получает активные стандарты рынка (заданные отдельной функцией внутри бота).
    3. Выполняет аудит соответствия (оценка ATS 0-100%, сильные стороны, точки роста).
    4. Формирует адаптированное резюме (через бесплатный LLM API при наличии ключа или встроенный локальный движок).
    5. Сохраняет адаптированное резюме в БД и возвращает полный отчёт + DOCX-документ.
    """
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

    # Пробуем бесплатный LLM API (если настроен), иначе используем встроенный бесплатный алгоритмический движок
    adapted_text = await _rewrite_resume_via_free_llm(
        raw_text=raw_text,
        extracted_role=extracted_role,
        extracted_skills=extracted_skills,
        standards=standards,
    )
    engine_used = "LLM API (OpenAI-совместимый)" if adapted_text else "Встроенный бесплатный ATS/STAR-оптимизатор"

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
    """Генерирует готовый файл .docx из адаптированного резюме для отправки пользователю в Telegram."""
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(11)

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
