"""Автотесты (pytest) для проверки всех ключевых функций бота согласно ТЗ:
1. Отдельная функция загрузки резюме (текст и DOCX).
2. Отдельная функция задания стандартов рынка внутри бота.
3. Отдельная функция адаптации резюме под заданные стандарты рынка.
4. Добавление сайтов и ТГ-каналов в БД с проверкой дубликатов (существующий vs новый источник).
5. Парсинг и поиск вакансий по резюме с фильтрацией по периодам: 1 день, 1 неделя, 1 месяц.
"""
from datetime import datetime, timedelta, timezone
import io
from pathlib import Path
from docx import Document
import pytest
import pytest_asyncio
from bot.database import Database
from bot.services.file_extractor import (
    extract_text_from_file_bytes,
    upload_and_register_resume,
)
from bot.services.market_standards import (
    adapt_resume_to_market_standards,
    build_ideal_executive_cv_2026,
    get_market_standards,
    reset_market_standards,
    set_gold_standard_executive_cv_2026,
    set_market_standards,
)
from bot.services.source_manager import (
    normalize_source_input,
    register_source_in_db,
)
from bot.services.vacancy_parser import (
    format_vacancies_search_message,
    parse_rss_or_xml_feed,
    parse_telegram_channel_html,
)


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> Database:
    """Создаёт временную изолированную базу данных SQLite для каждого теста."""
    db_file = tmp_path / "test_bot.sqlite3"
    database = Database(str(db_file))
    await database.init_db()
    return database


@pytest.mark.asyncio
async def test_upload_resume_function(db: Database) -> None:
    """Тест 1: Отдельная функция загрузки резюме (текст и DOCX-файл)."""
    sample_resume = (
        "Иван Петров\n"
        "Желаемая должность: Python Backend Developer\n"
        "Контакты: @ivan_dev, ivan@example.com\n"
        "Навыки: Python, FastAPI, PostgreSQL, Docker, Redis, Git, SQL, Pytest\n"
        "Опыт работы:\n"
        "Занимался разработкой микросервисов на FastAPI и оптимизировал запросы в PostgreSQL на 35%.\n"
        "Образование: МГТУ, Прикладная информатика."
    )
    saved = await upload_and_register_resume(
        db=db,
        user_id=101,
        raw_text=sample_resume,
        file_name="resume.txt",
        username="ivan_dev",
    )
    assert saved is not None
    assert "Python" in saved["extracted_role"]
    assert "Python" in saved["extracted_skills"]
    assert "FastAPI" in saved["extracted_skills"]
    assert "PostgreSQL" in saved["extracted_skills"]

    # Проверим извлечение из DOCX
    doc = Document()
    doc.add_paragraph("Анна Смирнова")
    doc.add_paragraph("Должность: Data Analyst")
    doc.add_paragraph("Навыки: SQL, Python, Power BI, Pandas")
    buf = io.BytesIO()
    doc.save(buf)

    extracted_docx_text = extract_text_from_file_bytes(buf.getvalue(), "anna_cv.docx")
    assert "Data Analyst" in extracted_docx_text
    assert "Power BI" in extracted_docx_text


@pytest.mark.asyncio
async def test_market_standards_and_resume_adaptation(db: Database) -> None:
    """Тест 2 и 3: Отдельная функция задания стандартов рынка внутри бота
    и отдельная функция адаптации резюме под эти стандарты.
    """
    user_id = 202
    sample_resume = (
        "Алексей Соколов\n"
        "Должность: Middle Python Разработчик\n"
        "Telegram: @alex_py\n"
        "Навыки: Python, Django, FastAPI, PostgreSQL, Docker\n"
        "Опыт работы:\n"
        "- Занимался разработкой REST API для финтех-сервиса.\n"
        "- Участвовал в разработке системы очередей и ускорил отклик на 40%.\n"
        "О себе: стрессоустойчивый, коммуникабельный, легко обучаюсь."
    )
    await upload_and_register_resume(db=db, user_id=user_id, raw_text=sample_resume)

    # Задаём пользовательские стандарты рынка отдельной функцией внутри бота
    custom_std_text = (
        "Разделы: Контакты, Tech Summary, Стек технологий, Инженерные достижения, Образование\n"
        "Ключевые слова: Python, FastAPI, Docker, CI/CD, Kubernetes\n"
        "Правила: Формула XYZ, сильные глаголы, без клише."
    )
    updated_std = await set_market_standards(
        db=db,
        user_id=user_id,
        custom_standards_text=custom_std_text,
        custom_title="Мой корпоративный IT-стандарт 2026",
    )
    assert updated_std["preset_key"] == "custom"
    assert updated_std["title"] == "Мой корпоративный IT-стандарт 2026"
    assert "Tech Summary" in updated_std["required_sections"]
    assert "Kubernetes" in updated_std["rules"]["focus_keywords"]

    # Запускаем отдельную функцию адаптации резюме под заданные стандарты рынка
    adaptation = await adapt_resume_to_market_standards(db=db, user_id=user_id)
    adapted_text = adaptation["adapted_text"]

    # Проверяем, что применён наш стандарт, слабые глаголы усилены, а клише удалены
    assert "Мой корпоративный IT-стандарт 2026" in adapted_text
    assert "Разработал и внедрил REST API" in adapted_text
    assert "стрессоустойчивый" not in adapted_text.lower()
    assert len(adaptation["docx_bytes"]) > 1000

    # Проверяем сброс стандартов к Золотому стандарту Executive CV (Framework 2026+)
    reset_std = await reset_market_standards(db=db, user_id=user_id)
    assert reset_std["preset_key"] == "executive_cv_2026"


@pytest.mark.asyncio
async def test_gold_standard_executive_cv_2026_framework(db: Database) -> None:
    """Тест 2.1: Отдельная функция формирования идеального резюме по
    «Золотому стандарту» — АРХИТЕКТУРА ИДЕАЛЬНОГО EXECUTIVE CV (Framework 2026+).
    """
    user_id = 205
    raw_executive_resume = (
        "Сергей Волков\n"
        "Должность: Commercial Director\n"
        "Дата рождения: 12.05.1985, 41 год, женат, есть дети, фото приложено\n"
        "Город: Москва\n"
        "Контакты: +7 (999) 123-45-67, s.volkov@example.com, linkedin.com/in/svolkov\n"
        "Навыки: P&L, B2B, CRM, BI, Agile, SQL, Excel\n"
        "О себе: 14+ лет опыта в ритейле. Ответственный и коммуникабельный руководитель.\n"
        "Опыт работы:\n"
        "ООО Фэшн Ритейл Групп (2020 - 2026)\n"
        "- Занимался развитием маркетплейсов: продажи выросли х3 (до 20% оборота 9+ млрд руб.).\n"
        "- Занимался управлением категорией и OTB бюджетом.\n"
        "- Участвовал в разработке новой ценовой стратегии (+15% маржинальности).\n"
        "- Принимал участие в запуске BI-аналитики.\n"
        "- Занимался настройкой складской логистики.\n"
        "- Работал над обучением персонала.\n"
        "Образование: ВШЭ, Стратегический менеджмент, 2008. Английский — B2."
    )
    await upload_and_register_resume(db=db, user_id=user_id, raw_text=raw_executive_resume)

    # Устанавливаем Золотой стандарт отдельной функцией
    gold_std = await set_gold_standard_executive_cv_2026(db=db, user_id=user_id)
    assert gold_std["preset_key"] == "executive_cv_2026"
    assert "Framework 2026+" in gold_std["title"]

    # Адаптируем резюме по Золотому стандарту
    result = await adapt_resume_to_market_standards(db=db, user_id=user_id)
    cv_text = result["adapted_text"]

    # 1. Проверяем наличие всех 5 архитектурных блоков Framework 2026+
    assert "ПРОФИЛЬ (Executive Summary)" in cv_text
    assert "КЛЮЧЕВАЯ ЭКСПЕРТИЗА (Core Expertise / ATS Keywords)" in cv_text
    assert "Business & Strategy:" in cv_text
    assert "Operations:" in cv_text
    assert "Leadership & Tech:" in cv_text
    assert " | " in cv_text  # Облако тегов через разделитель |
    assert "ОПЫТ РАБОТЫ (Professional Experience)" in cv_text
    assert "ДОПОЛНИТЕЛЬНЫЕ БЛОКИ" in cv_text

    # 2. Проверяем фильтр «Борьба с Red Flags» (удалены дата рождения, женат, ответственный и коммуникабельный)
    assert "12.05.1985" not in cv_text
    assert "женат" not in cv_text.lower()
    assert "ответственный и коммуникабельный" not in cv_text.lower()

    # 3. Проверяем фильтр «Evidence Map» (не более 4 буллитов ключевых результатов на роль)
    assert "сокращено второстепенных пунктов для интервью: 2" in cv_text


@pytest.mark.asyncio
async def test_sources_duplicate_and_new_detection(db: Database) -> None:
    """Тест 4: Добавление сайтов и ссылок на ТГ-каналы с проверкой на дубликаты в БД."""
    # 1. Пытаемся добавить ТГ-канал, который уже есть в предзаполненной БД (в другом формате ссылки)
    is_new_1, rec_1, msg_1 = await register_source_in_db(
        db=db,
        raw_input="@habr_career",
        user_id=303,
    )
    assert is_new_1 is False
    assert rec_1["canonical_url"] == "https://t.me/habr_career"
    assert "уже есть в моей базе данных" in msg_1

    # 2. Добавляем совершенно НОВЫЙ Telegram-канал
    is_new_2, rec_2, msg_2 = await register_source_in_db(
        db=db,
        raw_input="https://t.me/fastapi_jobs_ru",
        user_id=303,
    )
    assert is_new_2 is True
    assert rec_2["canonical_url"] == "https://t.me/fastapi_jobs_ru"
    assert rec_2["parse_url"] == "https://t.me/s/fastapi_jobs_ru"
    assert rec_2["source_type"] == "tg_channel"
    assert "Новый источник успешно добавлен в базу данных" in msg_2

    # 3. Повторно добавляем этот же ТГ-канал через t.me/s/... — должен распознать как существующий!
    is_new_3, _, msg_3 = await register_source_in_db(
        db=db,
        raw_input="https://t.me/s/fastapi_jobs_ru",
        user_id=303,
    )
    assert is_new_3 is False
    assert "уже есть в моей базе данных" in msg_3

    # 4. Добавляем НОВЫЙ веб-сайт вакансий
    is_new_4, rec_4, msg_4 = await register_source_in_db(
        db=db,
        raw_input="https://python.org/jobs/",
        user_id=303,
    )
    assert is_new_4 is True
    assert rec_4["canonical_url"] == "https://python.org/jobs"
    assert rec_4["source_type"] == "website"
    assert "Новый источник успешно добавлен в базу данных" in msg_4


def test_vacancy_parsing_and_period_filtering() -> None:
    """Тест 5: Парсинг ТГ-каналов и сайтов с фильтрацией за 1 день, 1 неделю, 1 месяц."""
    now = datetime.now(timezone.utc)
    dt_6_hours_ago = (now - timedelta(hours=6)).isoformat()
    dt_4_days_ago = (now - timedelta(days=4)).isoformat()
    dt_20_days_ago = (now - timedelta(days=20)).isoformat()
    dt_45_days_ago = (now - timedelta(days=45)).isoformat()

    sample_tg_html = f"""
    <div class="tgme_widget_message">
      <div class="tgme_widget_message_text">
        Senior Python Developer (FastAPI / PostgreSQL) — 350 000 руб.
        Ищем разработчика со знанием Python, FastAPI, Docker и SQL.
      </div>
      <a class="tgme_widget_message_date" href="https://t.me/ru_python_jobs/1001">
        <time datetime="{dt_6_hours_ago}"></time>
      </a>
    </div>
    <div class="tgme_widget_message">
      <div class="tgme_widget_message_text">
        Middle Python Backend Engineer (Django / Redis)
        Требуется опыт коммерческой разработки на Python и PostgreSQL.
      </div>
      <a class="tgme_widget_message_date" href="https://t.me/ru_python_jobs/1002">
        <time datetime="{dt_4_days_ago}"></time>
      </a>
    </div>
    <div class="tgme_widget_message">
      <div class="tgme_widget_message_text">
        Junior/Middle Python Developer (aiogram, asyncio, SQLite)
        Разработка Telegram-ботов и микросервисов.
      </div>
      <a class="tgme_widget_message_date" href="https://t.me/ru_python_jobs/1003">
        <time datetime="{dt_20_days_ago}"></time>
      </a>
    </div>
    <div class="tgme_widget_message">
      <div class="tgme_widget_message_text">
        Архивная вакансия Python Developer (2 месяца назад)
      </div>
      <a class="tgme_widget_message_date" href="https://t.me/ru_python_jobs/999">
        <time datetime="{dt_45_days_ago}"></time>
      </a>
    </div>
    """

    source = {
        "canonical_url": "https://t.me/ru_python_jobs",
        "parse_url": "https://t.me/s/ru_python_jobs",
        "source_type": "tg_channel",
        "title": "TG: @ru_python_jobs",
    }
    role = "Python Developer"
    skills = ["Python", "FastAPI", "PostgreSQL", "Docker", "aiogram"]

    # 1. Период: 1 ДЕНЬ (должна попасть только вакансия 6 часов назад)
    vacs_1d = parse_telegram_channel_html(
        html=sample_tg_html,
        source=source,
        role=role,
        skills=skills,
        cutoff_dt=now - timedelta(days=1),
    )
    assert len(vacs_1d) == 1
    assert "1001" in vacs_1d[0]["url"]

    # 2. Период: 1 НЕДЕЛЯ (должны попасть вакансии 6 часов назад и 4 дня назад)
    vacs_7d = parse_telegram_channel_html(
        html=sample_tg_html,
        source=source,
        role=role,
        skills=skills,
        cutoff_dt=now - timedelta(days=7),
    )
    assert len(vacs_7d) == 2

    # 3. Период: 1 МЕСЯЦ (должны попасть 3 вакансии за 30 дней, но не 45-дневная)
    vacs_30d = parse_telegram_channel_html(
        html=sample_tg_html,
        source=source,
        role=role,
        skills=skills,
        cutoff_dt=now - timedelta(days=30),
    )
    assert len(vacs_30d) == 3

    # Проверяем форматирование итогового сообщения со списком вакансий
    msg = format_vacancies_search_message(
        {
            "period_days": 30,
            "period_label": "1 месяц",
            "role": role,
            "skills": skills,
            "sources_checked": 5,
            "total_found": len(vacs_30d),
            "vacancies": vacs_30d,
        }
    )
    assert "Результаты поиска вакансий за 1 месяц" in msg
    assert "Senior Python Developer" in msg
    assert "https://t.me/ru_python_jobs/1001" in msg


@pytest.mark.asyncio
async def test_gold_standard_multi_role_and_clean_ats_keywords(db: Database) -> None:
    """Тест 2.2: Золотой стандарт — несколько ролей, чистые ATS-теги без дублей,
    корректный период из шапки компании и Scope без служебных ярлыков.
    """
    user_id = 207
    raw_resume = (
        "Иван Петров\n"
        "Должность: COO\n"
        "Локация: Санкт-Петербург\n"
        "Контакты: +7 999 000-11-22, ivan@example.com\n"
        "Навыки: Логистика, WMS, P&L, Управление командой\n"
        "О себе: 12 лет опыта в логистике. Управлял контуром с оборотом 5 млрд руб.\n"
        "Опыт работы:\n"
        "ООО Логистик Плюс, транспортная компания, 900 сотрудников (2022 - 2026)\n"
        "Scope: операционная модель, P&L, сеть хабов\n"
        "- Сократил издержки на 18% за счет перестройки маршрутизации.\n"
        "ПАО ТрансСервис, логистика (2015 - 2022)\n"
        "- Увеличил пропускную способность склада на 25%.\n"
        "Образование: МГТУ, Логистика, 2012"
    )
    await upload_and_register_resume(db=db, user_id=user_id, raw_text=raw_resume)
    await set_gold_standard_executive_cv_2026(db=db, user_id=user_id)
    cv_text = (await adapt_resume_to_market_standards(db=db, user_id=user_id))["adapted_text"]

    # 1. Стаж сохраняется в профиле (не вырезается фильтром возраста)
    assert "с опытом 12+ лет" in cv_text
    assert "Senior-level руководитель (COO)" in cv_text

    # 2. Обратный хронологический порядок: две роли с периодами из шапки компании
    assert "**Период:** 2022 — 2026" in cv_text
    assert "**Период:** 2015 — 2022" in cv_text
    assert cv_text.index("2022 — 2026") < cv_text.index("2015 — 2022")

    # 3. Scope без служебного ярлыка «Scope:»
    assert "**Scope (Область охвата):** операционная модель, P&L, сеть хабов" in cv_text

    # 4. ATS-облако: каноничная лексика вместо сырых дублей («P&L» -> «P&L Management»)
    assert "P&L Management" in cv_text
    assert " | P&L | " not in cv_text
    assert "Логистика |" not in cv_text  # русский дубль Supply Chain & Logistics не добавляется


def test_ideal_executive_cv_example_function() -> None:
    """Тест 2.3: Отдельная функция показа примера идеального резюме
    (`build_ideal_executive_cv_2026_example`) — работает без загруженного резюме и БД.
    """
    from bot.services.market_standards import build_ideal_executive_cv_2026_example

    example = build_ideal_executive_cv_2026_example()

    # 1. Возвращается полный набор данных для показа в чате + файл .docx
    assert example["example_text"]
    assert example["docx_bytes"][:2] == b"PK"  # корректный OOXML-архив
    assert 0 <= example["audit"]["score"] <= 100
    assert len(example["structure"]) == 6

    # 2. Пример содержит все 5 блоков архитектуры Framework 2026+
    assert "СЕРГЕЙ ВОЛКОВ" in example["example_text"]
    assert "ПРОФИЛЬ (Executive Summary)" in example["example_text"]
    assert "КЛЮЧЕВАЯ ЭКСПЕРТИЗА (Core Expertise / ATS Keywords)" in example["example_text"]
    assert "ОПЫТ РАБОТЫ (Professional Experience)" in example["example_text"]
    assert "ДОПОЛНИТЕЛЬНЫЕ БЛОКИ" in example["example_text"]

    # 3. Red Flags отсутствуют в эталонном примере
    assert "12.05.1985" not in example["example_text"]
    assert "женат" not in example["example_text"].lower()
    assert "коммуникабельный" not in example["example_text"].lower()


def test_search_assistant_intent_and_formats() -> None:
    """Тест 6: Алгоритм поиска ресурсов (HR-ассистент) — определение типа поиска,
    Markdown-формат, дисклеймер, деление длинных ответов и предупреждения.
    """
    from bot.services.resource_catalog import (
        AGGREGATORS,
        COMPANIES,
        LINKS_DISCLAIMER,
        TELEGRAM_CHANNELS,
        _company_vacancies_url,
        _verified_tg_url,
    )
    from bot.services.search_assistant import (
        SEARCH_TYPE_AGGREGATORS,
        SEARCH_TYPE_COMPANIES,
        SEARCH_TYPE_PROFESSION,
        SEARCH_TYPE_TELEGRAM,
        build_resources_answer,
        detect_industry,
        detect_search_intent,
        split_long_message,
    )

    # 1. Определение типа поиска по правилам ТЗ
    assert detect_search_intent("Дай ссылки на ТГ-каналы и чаты для HR") == SEARCH_TYPE_TELEGRAM
    assert detect_search_intent("покажи агрегаторы и сайты с вакансиями") == SEARCH_TYPE_AGGREGATORS
    assert detect_search_intent("ТОП-100 компаний с карьерными страницами") == SEARCH_TYPE_COMPANIES
    assert detect_search_intent("найди вакансии HR-менеджер") == SEARCH_TYPE_PROFESSION
    assert detect_search_intent("Дай ссылки на ТГ-каналы и агрегаторы для поиска работы в HR") == "mixed"
    assert detect_industry("компании ритейла и e-commerce") == "Ритейл и e-commerce"
    assert detect_industry("IT компании") == "IT и Телеком"

    # 2. Telegram-каналы: формат Markdown [Название](https://t.me/username) + тематика
    tg_answer = build_resources_answer("Дай ссылки на ТГ-каналы")
    assert tg_answer["search_type"] == SEARCH_TYPE_TELEGRAM
    for channel in TELEGRAM_CHANNELS[:3]:
        assert f"[{channel['name']}]({_verified_tg_url(channel['username'])})" in tg_answer["text"]
    assert "https://t.me/" in tg_answer["text"]
    assert LINKS_DISCLAIMER in tg_answer["text"]

    # 3. Агрегаторы: обязательные ресурсы из требований присутствуют
    agg_answer = build_resources_answer("агрегаторы вакансий")
    for mandatory in ("https://hh.ru", "career.habr.com", "https://hirify.me", "getmatch.ru"):
        assert mandatory in agg_answer["text"]
    assert LINKS_DISCLAIMER in agg_answer["text"]

    # 4. Компании: группировка по отраслям, сайт + ссылка на вакансии
    companies_answer = build_resources_answer("компании ритейла")
    assert "### 🛒 Ритейл и e-commerce" in companies_answer["text"]
    first_retail = next(c for c in COMPANIES if c["industry"] == "Ритейл и e-commerce")
    assert f"[{first_retail['site']}]({first_retail['site']})" in companies_answer["text"]
    assert f"]({_company_vacancies_url(first_retail)})" in companies_answer["text"]

    # 5. Предупреждение при запросе более 50 компаний
    big_answer = build_resources_answer("дай ТОП-500 компаний")
    assert big_answer["warnings"], "Ожидалось предупреждение о делении ответа на части"
    assert "50" in " ".join(big_answer["warnings"])

    # 6. Деление длинных ответов под лимит Telegram
    long_text = "\n".join(f"Строка номер {i} с описанием ресурса" for i in range(600))
    parts = split_long_message(long_text, limit=1000)
    assert len(parts) > 1
    assert all(len(part) <= 1000 for part in parts)

    # 7. Профессия: deep-links агрегаторов и инструкция по поиску в Telegram
    prof_answer = build_resources_answer("вакансии HR-менеджер")
    assert prof_answer["search_type"] == SEARCH_TYPE_PROFESSION
    assert "hh.ru/search/vacancy?text=" in prof_answer["text"]
    assert "поиск по ключевым словам внутри самого Telegram" in prof_answer["text"]
    assert LINKS_DISCLAIMER in prof_answer["text"]

    # 8. Запрет галлюцинаций: все ссылки собраны только из проверенного каталога
    import re as _re

    allowed_urls = {aggregator["url"] for aggregator in AGGREGATORS}
    allowed_urls |= {f"https://t.me/{c['username']}" for c in TELEGRAM_CHANNELS}
    for company in COMPANIES:
        allowed_urls.add(company["site"])
        allowed_urls.add(_company_vacancies_url(company))
    # плюс документированные шаблоны поиска по запросу (deep-links с параметрами)
    allowed_prefixes = (
        "https://hh.ru/search/vacancy?text=",
        "https://career.habr.com/vacancies?q=",
    )
    for answer in (tg_answer, agg_answer, companies_answer, prof_answer):
        for url in _re.findall(r"https?://[^\s\)\|\]\[]+", answer["text"]):
            assert url in allowed_urls or url.startswith(allowed_prefixes), (
                f"Ссылка не из каталога: {url}"
            )


@pytest.mark.asyncio
async def test_resume_profile_never_uses_name_as_role_or_skills(db: Database) -> None:
    """Тест 7 (регресс бага из продакшена): ФИО из резюме не должно попадать
    ни в целевую должность, ни в ключевые навыки.
    """
    from bot.services.file_extractor import build_resume_profile

    user_id = 401
    # Резюме без строки «Должность:» и без блока «Навыки:» — ровно тот случай,
    # когда бот раньше подставлял ФИО и как должность, и как навыки.
    raw_resume = (
        "Смирнов Алексей\n"
        "Москва\n"
        "Телефон: +7 900 000-00-00, smirnov@example.com\n"
        "О себе: работал в компании X, занимался продажами и отчётностью.\n"
    )
    await upload_and_register_resume(db=db, user_id=user_id, raw_text=raw_resume)
    record = await db.get_resume(user_id)

    assert record["extracted_role"] == "", "ФИО не должно становиться целевой должностью"
    assert record["extracted_skills"] == [], "ФИО не должно становиться ключевым навыком"
    # ФИО хранится только в исходном тексте, но не в профиле поиска
    assert "Смирнов" not in (record["extracted_role"] or "")
    assert all("Смирнов" not in skill for skill in record["extracted_skills"])

    # Профиль определяется отдельной функцией и не содержит имени
    profile = build_resume_profile(raw_resume)
    assert profile["candidate_name"] == "Смирнов Алексей"
    assert profile["role"] == ""
    assert profile["skills"] == []


@pytest.mark.asyncio
async def test_resume_profile_extraction_and_manual_override(db: Database) -> None:
    """Тест 8: корректное извлечение должности/навыков (включая многострочный блок
    «Навыки») и ручная корректировка через update_resume_profile (/set_role, /set_skills).
    """
    from bot.services.file_extractor import build_resume_profile

    user_id = 402
    raw_resume = (
        "Иванов Иван Иванович\n"
        "Москва, +7 999 123-45-67, ivanov@example.com\n"
        "Навыки:\n"
        "Excel, 1С\n"
        "CRM, KPI\n"
        "Опыт работы:\n"
        "ООО Ромашка — коммерческий директор (2018-2026)\n"
        "- Увеличил выручку на 30%.\n"
    )
    await upload_and_register_resume(db=db, user_id=user_id, raw_text=raw_resume)
    record = await db.get_resume(user_id)

    assert record["extracted_role"].lower() == "коммерческий директор"
    skills_lower = [s.lower() for s in record["extracted_skills"]]
    assert "excel" in skills_lower and "crm" in skills_lower and "1c" in skills_lower
    assert all("иван" not in s for s in skills_lower)

    profile = build_resume_profile(raw_resume)
    assert profile["candidate_name"] == "Иванов Иван Иванович"

    # Ручное уточнение профиля (аналог команд /set_role и /set_skills)
    updated = await db.update_resume_profile(
        user_id=user_id, role="Директор по развитию", skills=["P&L", "Excel", "CRM"]
    )
    assert updated["extracted_role"] == "Директор по развитию"
    assert updated["extracted_skills"] == ["P&L", "Excel", "CRM"]

    # Резюме и текст при этом не теряются
    assert "Ромашка" in updated["raw_text"]


@pytest.mark.asyncio
async def test_repair_legacy_broken_profile(db: Database) -> None:
    """Тест 9: авто-починка ранее сохранённого «сломанного» профиля,
    где вместо должности и навыков было записано ФИО (случай из продакшена).
    """
    from bot.services.file_extractor import (
        repair_invalid_resume_profiles,
        repair_profile_values,
    )

    user_id = 403
    raw_resume = (
        "Кузнецов Дмитрий Сергеевич\n"
        "Москва, +7 900 111-22-33\n"
        "Опыт работы:\n"
        "ООО Вектор — руководитель отдела продаж (2019-2026)\n"
        "- Выстроил отдел с нуля, выполнение плана 112%.\n"
    )
    await upload_and_register_resume(db=db, user_id=user_id, raw_text=raw_resume)

    # Имитируем старую (сломанную) запись: ФИО и в роли, и в навыках.
    # manual=False — это «данные из прошлой версии», а не правка человеком.
    await db.update_resume_profile(
        user_id=user_id,
        role="Кузнецов Дмитрий Сергеевич",
        skills=["Кузнецов", "Дмитрий", "Сергеевич"],
        manual=False,
    )

    role, skills, repaired = repair_profile_values(
        role="Кузнецов Дмитрий Сергеевич",
        skills=["Кузнецов", "Дмитрий", "Сергеевич"],
        raw_text=raw_resume,
    )
    assert repaired is True
    assert role.lower() == "руководитель отдела продаж"
    assert all("кузнецов" not in s.lower() for s in skills)

    # Авто-починка по всей базе при старте бота
    fixed = await repair_invalid_resume_profiles(db)
    assert fixed >= 1
    record = await db.get_resume(user_id)
    assert record["extracted_role"].lower() == "руководитель отдела продаж"
    assert all("кузнецов" not in s.lower() for s in record["extracted_skills"])


@pytest.mark.asyncio
async def test_user_added_hr_channels_in_database(db: Database) -> None:
    """Тест 10: добавленные пользователем HR/карьерные ТГ-каналы присутствуют в БД
    (и досеиваются в уже существующую базу через ensure_default_sources).
    """
    from bot.database import DEFAULT_SOURCES

    expected = {
        "https://t.me/marhrru",
        "https://t.me/HRmother",
        "https://t.me/kadrovik_krd",
        "https://t.me/uptume",
        "https://t.me/rus_hr",
        "https://t.me/uvolnyaus",
        "https://t.me/akks_career",
        "https://t.me/rudakovahr",
        "https://t.me/you_social",
        "https://t.me/vacanciesbest",
        "https://t.me/jobinspb",
        "https://t.me/nongreta",
    }
    defaults_urls = {src["canonical_url"] for src in DEFAULT_SOURCES}
    assert expected.issubset(defaults_urls)

    sources = await db.list_sources(active_only=False)
    stored_urls = {src["canonical_url"] for src in sources}
    assert expected.issubset(stored_urls), f"Не хватает: {expected - stored_urls}"

    # Каждый канал парсится через веб-превью t.me/s/<channel>
    for src in sources:
        if src["canonical_url"] in expected:
            assert src["parse_url"] == src["canonical_url"].replace("https://t.me/", "https://t.me/s/")
            assert src["source_type"] == "tg_channel"

    # Повторный вызов ничего не дублирует
    assert await db.ensure_default_sources() == 0


def test_user_added_hr_channels_in_resource_catalog() -> None:
    """Тест 11: те же каналы доступны в каталоге ресурсов (/find_resources)."""
    from bot.services.resource_catalog import TELEGRAM_CHANNELS

    catalog_usernames = {channel["username"] for channel in TELEGRAM_CHANNELS}
    for username in (
        "marhrru", "HRmother", "kadrovik_krd", "uptume", "rus_hr", "uvolnyaus",
        "akks_career", "rudakovahr", "you_social", "vacanciesbest", "jobinspb", "nongreta",
    ):
        assert username in catalog_usernames, f"Канал {username} отсутствует в каталоге"


@pytest.mark.asyncio
async def test_retired_sources_excluded_from_search(db: Database) -> None:
    """Тест 12: @fuck_the_frameworks и SuperJob выведены из поиска.

    Их больше нет ни в DEFAULT_SOURCES, ни в каталоге; в уже созданной базе они
    гасятся (is_active = 0), поэтому не парсятся и не дают предупреждений.
    """
    from bot.database import DEFAULT_SOURCES, RETIRED_SOURCES
    from bot.services.resource_catalog import AGGREGATORS, TELEGRAM_CHANNELS

    urls = {s["canonical_url"] for s in DEFAULT_SOURCES}
    assert "https://t.me/fuck_the_frameworks" not in urls
    assert "https://www.superjob.ru" not in urls
    assert set(RETIRED_SOURCES) == {
        "https://t.me/fuck_the_frameworks",
        "https://www.superjob.ru",
    }

    assert "fuck_the_frameworks" not in {c["username"] for c in TELEGRAM_CHANNELS}
    assert "https://www.superjob.ru" not in {a["url"] for a in AGGREGATORS}

    # в старой базе записи остаются, но выключены
    await db.add_source(
        canonical_url="https://t.me/fuck_the_frameworks",
        parse_url="https://t.me/s/fuck_the_frameworks",
        source_type="tg_channel",
        title="TG: fuck_the_frameworks (@fuck_the_frameworks)",
    )
    await db.add_source(
        canonical_url="https://www.superjob.ru",
        parse_url="https://www.superjob.ru/rss/job/",
        source_type="website",
        title="Сайт: SuperJob (superjob.ru)",
    )
    await db.ensure_default_sources()
    active = {s["canonical_url"] for s in await db.list_sources(active_only=True)}
    assert "https://t.me/fuck_the_frameworks" not in active
    assert "https://www.superjob.ru" not in active


def test_source_issues_are_reported_in_message() -> None:
    """Тест 13: закрытое веб-превью попадает в отчёт, а не теряется молча."""
    from datetime import datetime, timezone

    from bot.services.vacancy_parser import format_vacancies_search_message

    result = {
        "period_days": 7,
        "period_label": "1 неделя",
        "role": "Директор по продажам",
        "skills": ["Excel"],
        "sources_checked": 22,
        "total_found": 0,
        "vacancies": [],
        "source_issues": [
            {
                "title": "TG: DevOps Jobs - работа и аналитика (@devops_jobs)",
                "url": "https://t.me/devops_jobs",
                "reason": "канал не отдаёт публичное веб-превью",
            }
        ],
    }
    message = format_vacancies_search_message(result)
    # ники и URL экранируются (`devops\_jobs`), поэтому сравниваем без слешей
    plain = message.replace("\\", "")
    assert "не удалось прочитать" in message
    assert "devops_jobs" in plain
    assert "веб-превью" in message


INTL_SITES = {
    "https://www.indeed.com/": "manual",
    "https://www.glassdoor.com/": "manual",
    "https://www.ziprecruiter.ie/": "manual",
    "https://www.careerbuilder.com/": "manual",
    "https://wantapply.com/": "manual",
    "https://remote.co/": "manual",
    "https://weworkremotely.com/": "website",
    "https://remoteok.com/": "json_api",
    "https://jobspresso.co/": "website",
}


@pytest.mark.asyncio
async def test_international_sites_added(db: Database) -> None:
    """Тест 14: 9 международных job-бордов добавлены в БД с правильной стратегией парсинга."""
    from bot.database import DEFAULT_SOURCES

    defaults = {s["canonical_url"]: s for s in DEFAULT_SOURCES}
    for url, expected_type in INTL_SITES.items():
        assert url in defaults, f"Нет в DEFAULT_SOURCES: {url}"
        assert defaults[url]["source_type"] == expected_type, f"Неверный тип для {url}"

    stored = {s["canonical_url"]: s for s in await db.list_sources(active_only=False)}
    for url in INTL_SITES:
        assert url in stored, f"Нет в БД: {url}"

    # Автоматически парсимые борды используют RSS/API, а не обычную HTML-страницу
    assert stored["https://remoteok.com/"]["parse_url"].endswith("/api")
    assert stored["https://weworkremotely.com/"]["parse_url"].endswith(".rss")
    assert "feed" in stored["https://jobspresso.co/"]["parse_url"]


def test_international_sites_in_catalog() -> None:
    """Тест 15: те же площадки доступны в каталоге /find_resources."""
    from bot.services.resource_catalog import AGGREGATORS

    urls = {a["url"] for a in AGGREGATORS}
    for url in INTL_SITES:
        assert url in urls, f"Нет в AGGREGATORS: {url}"


def test_manual_board_links_built_from_resume_role() -> None:
    """Тест 16: ссылки «ручных» бордов строятся под должность, без угадывания путей."""
    from bot.services.resource_catalog import LINKS_DISCLAIMER
    from bot.services.vacancy_parser import (
        build_manual_board_link,
        format_vacancies_search_blocks,
    )

    indeed_url, has_query = build_manual_board_link(
        "https://www.indeed.com/", "Директор по продажам", 7
    )
    assert has_query is True
    assert indeed_url.startswith("https://www.indeed.com/jobs?q=")
    assert "fromage=7" in indeed_url

    # Glassdoor: шаблона нет → открываем главную, честно помечаем
    glassdoor_url, has_query = build_manual_board_link("https://www.glassdoor.com/", "CEO", 7)
    assert has_query is False
    assert glassdoor_url == "https://www.glassdoor.com/"

    result = {
        "period_days": 7,
        "period_label": "1 неделя",
        "role": "Директор по продажам",
        "skills": ["Excel"],
        "sources_checked": 31,
        "total_found": 0,
        "vacancies": [],
        "source_issues": [],
        "manual_sources": [
            {"title": "Сайт: Indeed (indeed.com)", "url": "https://www.indeed.com/"},
            {"title": "Сайт: Glassdoor (glassdoor.com)", "url": "https://www.glassdoor.com/"},
        ],
    }
    body, footer = format_vacancies_search_blocks(result)
    assert "Международные job-борды" in footer
    assert "https://www.indeed.com/jobs?q=" in footer
    assert "введите должность" in footer          # подсказка для Glassdoor
    assert LINKS_DISCLAIMER in footer              # дисклеймер всегда в конце
    assert "ручной поиск: 2" in body


TGSTAT_CHANNELS = {
    "theyseeku": "Finder.work: работа и вакансии",
    "hh_ru_official": "hh.ru",
    "zdemcv": "Ждём резюме | Лайфхакер",
    "digital_jobster": "Джобстер Digital",
    "hr_affiliate": "CPA HUNTER",
    "rabota_freelancee": "Удаленка. Вакансии и резюме",
    "bbe_jobs": "Точка входа",
    "digitalbroccoli": "Brocli",
    "rabota_go": "Работа GO",
    "remote_w0rk": "Удаленка",
    "Uyut_frilans": "Уютный Фриланс",
    "workfreelancer": "Фрилансер: вакансии на удаленке",
    "obn_rezume": "Обновите резюме!",
    "HRTech_Jobs": "HR-Tech.Карьера",
    "theyseeku_it": "Удаленка — IT и Digital",
    "HR_Analytics_Jobs": "Вакансии в HR-Аналитике",
    "work_looking": "Ищу работу | Диджитал",
    "Easy_wrk": "Easy Work",
    "jobcatcher": "Ловец вакансий",
    "architect_career": "Архитектор Карьеры",
    "ne_titanik_DG": "Карьера без паники",
    "jobnulsya": "JOBнулся",
}


def test_tgstat_channels_no_duplicates() -> None:
    """Тест 17: в базе и каталоге нет дублей (проверка перед добавлением подборки TGStat)."""
    from bot.database import DEFAULT_SOURCES
    from bot.services.resource_catalog import AGGREGATORS, TELEGRAM_CHANNELS

    urls = [s["canonical_url"] for s in DEFAULT_SOURCES]
    assert len(urls) == len(set(urls)), f"Дубли источников: {[u for u in set(urls) if urls.count(u) > 1]}"

    usernames = [c["username"] for c in TELEGRAM_CHANNELS]
    assert len(usernames) == len(set(usernames)), (
        f"Дубли каналов: {[u for u in set(usernames) if usernames.count(u) > 1]}"
    )

    agg_urls = [a["url"] for a in AGGREGATORS]
    assert len(agg_urls) == len(set(agg_urls)), "Дубли агрегаторов"

    # Новые каналы не должны пересекаться с уже существовавшими
    assert not (set(TGSTAT_CHANNELS) & {"marhrru", "rudakovahr", "habr_career", "job_it_ru"})


@pytest.mark.asyncio
async def test_tgstat_channels_added(db: Database) -> None:
    """Тест 18: 22 канала из подборки TGStat есть в БД с корректными parse_url."""
    from bot.database import DEFAULT_SOURCES
    from bot.services.resource_catalog import TELEGRAM_CHANNELS

    defaults = {s["canonical_url"]: s for s in DEFAULT_SOURCES}
    stored = {s["canonical_url"] for s in await db.list_sources(active_only=False)}
    catalog = {c["username"]: c for c in TELEGRAM_CHANNELS}

    for username, name_part in TGSTAT_CHANNELS.items():
        url = f"https://t.me/{username}"
        assert url in defaults, f"Нет в DEFAULT_SOURCES: {url}"
        assert defaults[url]["parse_url"] == f"https://t.me/s/{username}"
        assert defaults[url]["source_type"] == "tg_channel"
        assert url in stored, f"Нет в БД: {url}"

        assert username in catalog, f"Нет в каталоге: {username}"
        assert name_part.lower()[:10] in catalog[username]["name"].lower()

    # Всего источников: 9 базовых + 13 + 9 международных + 22 из TGStat
    # + 24 из второй подборки + 70 каналов и 16 сайтов третьей подборки
    assert len(DEFAULT_SOURCES) == 163
    # Повторный досев ничего не дублирует
    assert await db.ensure_default_sources() == 0


SECOND_BATCH = {
    "irenaivanova_official": "Ирена_Иванова_official",
    "larina_career": "Наталья Ларина",
    "i_top_groups": "Я Топ",
    "hrexpert63": "#ПерезагрузкаКарьеры",
    "hrhack_career": "Abrashitova Natalya",
    "prolearning": "Живое обучение",
    "work_for_top": "КАРЬЕРА ЛИДЕРА",
    "execselect": "Exec Select",
    "vacancyCRC": "Вакансии от CRC",
    "relocation_vacancies": "Вакансии с релокацией",
    "hireproproduct": "Hire ProProduct",
    "workfortop": "Work For TOP",
    "fintech_jobs": "Fintech",
    "talent_hunters": "Talent Hunters",
    "ithr_tusovka": "IT HR тусовка",
    "recommend_recruit": "Рекомендательный рекрутинг",
    "ithunterio": "Смелый рекрутинг",
    "trend_hr": "TrendHR",
    "more_than_hr": "БОЛЬШЕ чем HR",
    "toplevel_job": "TOP LEVEL JOB",
    "tomato1000": "Senior Помідор",
    "vsemmema": "ВСЕМ МЕМ",
    "psoyuz": "ПРОМЫШЛЕННЫЙ СОЮЗ",
    "elena_shebashova": "Елена Шебашова",
    "zakadrom_hr": "HR-вакансии | ЗА КАДРОМ",
}


THIRD_BATCH = {
    "forchiefs": "Job for Chiefs",
    "vakansii_top_manager": "TOP Management",
    "execcareer": "Executive Career",
    "forproducts": "Job for Products",
    "product_jobs": "Product Jobs",
    "analytics_jobs": "Analytics Jobs",
    "datasciencejobs": "Data Science Jobs",
    "ru_pythonjobs": "Python Jobs",
    "javadevjob": "JavaDevJob",
    "golangjob": "Golang Jobs",
    "mobiledevjob": "MobileDevJob",
    "forallqa": "Job for QA",
    "it_vakansii_jobs": "СЕТИ IT & Digital",
    "fordesigner": "Job for Designers",
    "designer_vacancies": "Вакансии для дизайнеров",
    "forallmarketing": "Job for Marketing",
    "dnative_job": "DNative Job",
    "prvacant": "PR вакансии",
    "vakansii_0": "Work Hunter",
    "forallmedia": "Job for Media",
    "perezvonyu": "Мы вам перезвоним",
    "mskeventjob": "Event Hunter",
    "forhr": "Job for HR",
    "hr_jobs_rabota": "HR Jobs",
    "hrorhr": "эйчарли",
    "hrhubvacancy": "HR Хаб вакансии",
    "hrhubvacancy300": "HR Хаб 300+",
    "hrhubjunior": "HR Хаб Junior",
    "legal_jobs": "Юридические вакансии",
    "hellolawyer_jobs": "HelloLawyer Jobs",
    "cfo_ifrs": "CFO / IFRS",
    "cfosearch": "CFO Search",
    "fintech_work": "Работа в финтехе",
    "paymentcardjobs": "FintechJob",
    "forallsales": "Job for Sales",
    "sales_work": "Sales Work",
    "sales_manager_job": "IT Sales Manager Jobs",
    "salestalents": "Sales Talents",
    "careerspace": "Careerspace",
    "bizservisjob": "Вакансии в клиентском сервисе",
    "cstalents": "Customer Success Talents",
    "getassistant_vacancy": "GetAssistant",
    "assisteca_job": "Ассистека",
    "nanyatassistenta": "ИЩУ АССИСТЕНТА",
    "pomochnik_vakansii": "Менеджер / Ассистент / Работа",
    "mosinzproekt": "Мосинжпроект",
    "jobinpharma": "ФАРМА. Вакансии",
    "lapainpharma": "Лапа в фарме",
    "pharmed_recruitment": "Pharma & Medical Recruitment",
    "superjob_medicina": "Работа / Медицина / Вакансии",
    "rujobinfood": "Общепит работа есть",
    "expresswaiter": "Express Waiter",
}

# Каналы третьей подборки, которые существуют, но закрыли публичное веб-превью:
# бот оставляет их в базе и честно сообщает причину в блоке source_issues.
THIRD_BATCH_CLOSED_PREVIEW = (
    "executive_jobs", "jobs_for_it_analyst", "devops_jobs", "javascript_jobs",
    "java_jobs", "mobile_jobs", "uiux_jobs", "job_in_hr", "working_in_finance",
    "work_in_accounting", "vacancii_construction", "job_in_med", "job_in_zdrav",
    "horeca_hr", "expresswaiter_vacancy", "exwaiters",
)


@pytest.mark.asyncio
async def test_second_batch_channels_added(db: Database) -> None:
    """Тест 19: 24 канала из второй подборки добавлены, дубли с прежними исключены."""
    from bot.database import DEFAULT_SOURCES
    from bot.services.resource_catalog import TELEGRAM_CHANNELS

    defaults = {s["canonical_url"]: s for s in DEFAULT_SOURCES}
    stored = {s["canonical_url"] for s in await db.list_sources(active_only=False)}
    catalog = {c["username"]: c for c in TELEGRAM_CHANNELS}

    for username, name_part in SECOND_BATCH.items():
        url = f"https://t.me/{username}"
        assert url in defaults, f"Нет в DEFAULT_SOURCES: {url}"
        assert defaults[url]["parse_url"] == f"https://t.me/s/{username}"
        assert url in stored, f"Нет в БД: {url}"
        assert username in catalog, f"Нет в каталоге: {username}"
        assert name_part.lower()[:8] in catalog[username]["name"].lower()

    # уже добавленные ранее каналы не должны дублироваться под другими именами
    for old in ("akks_career", "jobinspb", "theyseeku", "vacanciesbest", "rus_hr", "you_social", "uptume"):
        assert old in {u.replace("https://t.me/", "") for u in defaults}


def test_sources_total_and_uniqueness() -> None:
    """Тест 20: 163 источника, все уникальны; 135 каналов и 28 сайтов."""
    from bot.database import DEFAULT_SOURCES
    from bot.services.resource_catalog import TELEGRAM_CHANNELS

    tg = [s for s in DEFAULT_SOURCES if s["source_type"] == "tg_channel"]
    sites = [s for s in DEFAULT_SOURCES if s["source_type"] != "tg_channel"]
    assert (len(tg), len(sites), len(DEFAULT_SOURCES)) == (135, 28, 163)
    assert len({s["canonical_url"] for s in DEFAULT_SOURCES}) == 163
    assert len({c["username"] for c in TELEGRAM_CHANNELS}) == len(TELEGRAM_CHANNELS)


@pytest.mark.asyncio
async def test_third_batch_channels_and_sites_added(db: Database) -> None:
    """Тест 21: третья подборка — 70 каналов и 16 сайтов добавлены, дубли отсеяны."""
    from bot.database import DEFAULT_SOURCES
    from bot.services.resource_catalog import AGGREGATORS, TELEGRAM_CHANNELS

    defaults = {s["canonical_url"].lower(): s for s in DEFAULT_SOURCES}
    stored = {s["canonical_url"].lower() for s in await db.list_sources(active_only=False)}
    catalog = {c["username"].lower(): c for c in TELEGRAM_CHANNELS}

    # Telegram-никие регистронезависимы: дублей «ExecCareer»/«execcareer» быть не должно
    assert len(defaults) == len(DEFAULT_SOURCES)

    for username, name_part in THIRD_BATCH.items():
        url = f"https://t.me/{username}"
        assert url.lower() in defaults, f"Нет в DEFAULT_SOURCES: {url}"
        assert defaults[url.lower()]["parse_url"].lower() == f"https://t.me/s/{username}".lower()
        assert url.lower() in stored, f"Нет в БД: {url}"
        assert username.lower() in catalog, f"Нет в каталоге: {username}"
        assert name_part.lower()[:8] in catalog[username.lower()]["name"].lower()

    # каналы с закрытым веб-превью остаются в базе (бот сообщит причину, а не промолчит)
    for username in THIRD_BATCH_CLOSED_PREVIEW:
        assert f"https://t.me/{username}".lower() in defaults, f"Нет в DEFAULT_SOURCES: {username}"

    # дубли из присланного списка не добавились повторно
    for dup in ("vacancyCRC", "vacanciesbest", "rabota_freelancee"):
        assert f"https://t.me/{dup}".lower() in defaults

    # новые сайты: API «Работа России», две HTML-ленты и ручные площадки
    assert defaults["https://trudvsem.ru"]["parse_url"] == "https://opendata.trudvsem.ru/api/v1/vacancies"
    assert defaults["https://budu.jobs/"]["source_type"] == "website"
    assert defaults["https://remote-job.ru/"]["source_type"] == "website"
    for manual in (
        "https://facancy.ru/", "https://kwork.ru/", "https://www.fl.ru/",
        "https://youdo.com/", "https://ru.jooble.org/", "https://wellfound.com/jobs",
    ):
        assert defaults[manual]["source_type"] == "manual"

    agg_urls = {a["url"] for a in AGGREGATORS}
    for site in ("https://budu.jobs/", "https://remote-job.ru/", "https://kwork.ru/", "https://www.fl.ru/"):
        assert site in agg_urls, f"Нет в каталоге агрегаторов: {site}"


def test_trudvsem_api_parser() -> None:
    """Тест 22: открытые данные «Работа России» разбираются в вакансии."""
    from datetime import datetime, timedelta, timezone

    from bot.services.vacancy_parser import parse_trudvsem_api

    payload = {
        "status": "200",
        "meta": {"total": 1, "limit": 1},
        "results": {
            "vacancies": [
                {
                    "vacancy": {
                        "id": "abc",
                        "job-name": "Директор по маркетингу",
                        "company": {"name": "ООО Тест"},
                        "region": {"name": "Москва"},
                        "date_modify": "2026-11-17T09:51:54+0300",
                        "salary_min": "150000",
                        "salary_max": "200000",
                        "duty": "Управление маркетингом, бюджет, команда",
                        "requirements": "Опыт 5 лет, CRM",
                        "employment": "Полная занятость",
                        "vac_url": "https://trudvsem.ru/vacancy/card/1/abc",
                    }
                }
            ]
        },
    }

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    result = parse_trudvsem_api(
        json_text=__import__("json").dumps(payload, ensure_ascii=False),
        source={"canonical_url": "https://trudvsem.ru", "title": "Сайт: Работа России (trudvsem.ru API)"},
        role="Директор по маркетингу",
        skills=["маркетинг", "бюджет"],
        cutoff_dt=cutoff,
    )
    assert len(result) == 1
    vacancy = result[0]
    assert "Директор по маркетингу" in vacancy["title"]
    assert vacancy["url"] == "https://trudvsem.ru/vacancy/card/1/abc"
    assert vacancy["relevance_score"] > 0
    assert vacancy["published_at"] >= cutoff

    # пустой ответ и битый JSON не ломают поиск
    assert parse_trudvsem_api("{}", {"canonical_url": "https://trudvsem.ru"}, "роль", [], cutoff) == []
    assert parse_trudvsem_api("не json", {"canonical_url": "https://trudvsem.ru"}, "роль", [], cutoff) == []


# =============================================================================
# Длинные сообщения и Markdown-сущности (ошибка «can't find end of the entity»)
# =============================================================================

def test_split_message_never_breaks_entities() -> None:
    """Тест 23: длинный текст режется по строкам — сущности остаются целыми."""
    from bot.services.message_utils import has_broken_entities, split_message

    text = "\n".join(
        f"**{i}. Директор по маркетингу** — [открыть](https://t.me/x/{i}) — описание вакансии"
        for i in range(1, 200)
    )
    chunks = split_message(text, limit=1000)

    assert len(chunks) > 1
    assert all(len(chunk) <= 1000 for chunk in chunks)
    assert all(not has_broken_entities(chunk) for chunk in chunks)
    # ни одна строка не потерялась и порядок сохранён
    restored = "\n".join(chunks).split("\n")
    assert len(restored) == len(text.split("\n"))
    assert restored[0].startswith("**1.")


def test_split_message_handles_overlong_line() -> None:
    """Тест 24: строка длиннее лимита режется с потерей разметки, но без «половинок»."""
    from bot.services.message_utils import has_broken_entities, split_message

    long_line = "**важно** " + "текст " * 300
    chunks = split_message(long_line, limit=500)

    assert all(len(chunk) <= 500 for chunk in chunks)
    assert all(not has_broken_entities(chunk) for chunk in chunks)
    assert "важно" in chunks[0]


def test_vacancy_title_and_source_are_markdown_escaped() -> None:
    """Тест 25: названия с `[`, `]`, `*`, `_` не ломают разметку выдачи."""
    from datetime import datetime, timezone

    from bot.services.message_utils import has_broken_entities
    from bot.services.vacancy_parser import format_vacancies_search_blocks

    result = {
        "period_days": 7,
        "period_label": "1 неделя",
        "role": "Директор [по маркетингу]",
        "skills": ["бренд_менеджмент", "CRM*"],
        "sources_checked": 10,
        "total_found": 1,
        "vacancies": [
            {
                "title": "Вакансия [топ] *срочно*",
                "url": "https://t.me/toplevel_job/1",
                "source_title": "TG: TOP LEVEL JOB [топ вакансии] (@toplevel_job)",
                "source_type": "tg_channel",
                "published_at": datetime.now(timezone.utc),
                "matched_skills": ["бренд_менеджмент"],
                "relevance_score": 30,
                "snippet": "описание с подчёркиванием job_in_hr и [скобкой]",
            }
        ],
        "source_issues": [],
        "manual_sources": [],
    }
    body, footer = format_vacancies_search_blocks(result)

    assert not has_broken_entities(body), body
    assert not has_broken_entities(footer), footer
    plain_body = body.replace("\\", "")
    assert "TOP LEVEL JOB [топ вакансии]" in plain_body


def test_prepare_text_disables_markup_for_broken_text() -> None:
    """Тест 26: при незакрытой сущности текст уходит без parse_mode (без ошибки 400)."""
    from bot.handlers.messaging import prepare_text

    text, mode = prepare_text("**жирный** и /find_resources", "Markdown")
    assert mode is None
    assert "**" not in text

    text, mode = prepare_text("**жирный** и `код`", "Markdown")
    assert mode == "Markdown"
    assert text == "**жирный** и `код`"


@pytest.mark.asyncio
async def test_long_search_result_is_sent_in_safe_chunks() -> None:
    """Тест 27: длинная выдача отправляется частями ≤ лимита и без «половинок» сущностей."""
    from datetime import datetime, timezone

    from bot.handlers.messaging import send_long_message
    from bot.services.message_utils import has_broken_entities
    from bot.services.vacancy_parser import format_vacancies_search_blocks

    vacancies = [
        {
            "title": f"Вакансия {i} — компания",
            "url": f"https://t.me/toplevel_job/{i}",
            "source_title": "TG: TOP LEVEL JOB [топ вакансии] (@toplevel_job)",
            "source_type": "tg_channel",
            "published_at": datetime.now(timezone.utc),
            "matched_skills": ["маркетинг"],
            "relevance_score": 30,
            "snippet": "описание вакансии",
        }
        for i in range(1, 60)
    ]
    body, footer = format_vacancies_search_blocks(
        {
            "period_days": 7,
            "period_label": "1 неделя",
            "role": "Директор по маркетингу",
            "skills": ["маркетинг"],
            "sources_checked": 100,
            "total_found": len(vacancies),
            "all_vacancies": vacancies,
            "page_size": len(vacancies),
            "vacancies": vacancies,
            "source_issues": [],
            "manual_sources": [],
        }
    )
    assert len(body) > 3900, "для теста нужна выдача длиннее лимита Telegram"

    class FakeMessage:
        """Минимальная заглушка aiogram.Message: только edit_text/answer."""

        def __init__(self) -> None:
            self.sent: list = []

        async def edit_text(self, text, **kwargs):
            self.sent.append(("edit", text, kwargs))
            return self

        async def answer(self, text, **kwargs):
            self.sent.append(("answer", text, kwargs))
            return self

    fake = FakeMessage()
    await send_long_message(body, fake, parse_mode="Markdown")

    assert len(fake.sent) > 1, "длинная выдача должна уйти несколькими сообщениями"
    for _, text, kwargs in fake.sent:
        assert len(text) <= 3900
        assert not has_broken_entities(text)
        if kwargs.get("parse_mode") == "Markdown":
            assert has_broken_entities(text) is False


# =============================================================================
# Извлечение должности из резюме (полное название, а не первое слово)
# =============================================================================

def test_role_extraction_keeps_full_title() -> None:
    """Тест 28: «Руководитель продукта» не обрезается до «Руководитель»."""
    from bot.services.file_extractor import extract_role_from_resume

    cases = {
        "Руководитель продукта": "Руководитель продукта",
        "Менеджер проектов": "Менеджер проектов",
        "Начальник цеха": "Начальник цеха",
        "Главный инженер проекта": "Главный инженер проекта",
        "Старший аналитик данных": "Старший аналитик данных",
        "Руководитель отдела продаж": "Руководитель отдела продаж",
        "Директор по маркетингу": "Директор по маркетингу",
        "Руководитель направления логистики": "Руководитель направления логистики",
        "Инженер-программист отдела АСУ": "Инженер-программист отдела АСУ",
        "Ведущий специалист по работе с клиентами": "Ведущий специалист по работе с клиентами",
        "Руководитель продукта в Яндексе": "Руководитель продукта",
        "Аналитик данных, финансы": "Аналитик данных",
        "Специалист с опытом работы 5 лет": "Специалист",
    }
    for resume_line, expected in cases.items():
        actual = extract_role_from_resume(resume_line)
        assert actual == expected, f"{resume_line!r} → {actual!r}, ожидалось {expected!r}"


def test_role_extraction_abbreviations_and_english_titles() -> None:
    """Тест 29: C-level аббревиатуры и англоязычные должности распознаются."""
    from bot.services.file_extractor import extract_role_from_resume, is_probable_person_name

    assert extract_role_from_resume("CTO").startswith("CTO")
    assert extract_role_from_resume("CFO").startswith("CFO")
    assert extract_role_from_resume("Product Owner") == "Product Owner"
    assert extract_role_from_resume("Scrum Master") == "Scrum Master"
    assert extract_role_from_resume("Head of Marketing") == "Head of Marketing"

    # и при этом они не считаются ФИО
    for title in ("Product Owner", "Scrum Master", "Product Management", "Unit Economics"):
        assert not is_probable_person_name(title), title
    for name in ("Иванов Иван Иванович", "Анна Смирнова", "Peter Parker"):
        assert is_probable_person_name(name), name


def test_names_are_never_roles_and_skills() -> None:
    """Тест 30: ФИО не попадает ни в должность, ни в навыки."""
    from bot.services.file_extractor import (
        extract_role_from_resume,
        extract_skills_from_resume,
        build_resume_profile,
    )

    resume = (
        "Иванов Иван Иванович\n"
        "Москва\n\n"
        "Навыки\n"
        "Product Management, Unit Economics, P&L, SQL, Jira\n"
    )
    profile = build_resume_profile(resume)
    assert profile["role"] == ""
    assert profile["candidate_name"] == "Иванов Иван Иванович"
    assert "Иванов" not in " ".join(profile["skills"])
    assert "Product Management" in profile["skills"]
    assert extract_role_from_resume("Руководитель продукта\n" + resume) == "Руководитель продукта"


@pytest.mark.asyncio
async def test_uploaded_docx_resume_role_is_full(db: Database) -> None:
    """Тест 31: при загрузке DOCX-резюме в профиль попадает полная должность."""
    import io

    from docx import Document

    from bot.services.file_extractor import extract_text_from_file_bytes, upload_and_register_resume

    text = (
        "Иванов Иван Иванович\n"
        "Руководитель продукта\n"
        "Москва, готов к релокации\n\n"
        "О себе\n8 лет в продуктовой разработке, управлял P&L продукта.\n\n"
        "Навыки\nProduct Management, Unit Economics, P&L, SQL, Jira, Roadmap\n"
    )
    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)

    extracted = extract_text_from_file_bytes(buffer.getvalue(), "resume.docx")
    profile = await upload_and_register_resume(
        db=db, user_id=501, raw_text=extracted, file_name="resume.docx"
    )

    assert profile["extracted_role"] == "Руководитель продукта"
    assert "Product Management" in profile["extracted_skills"]

    stored = await db.get_resume(501)
    assert stored is not None
    assert stored["extracted_role"] == "Руководитель продукта"


@pytest.mark.asyncio
async def test_truncated_role_is_repaired_on_startup(db: Database) -> None:
    """Тест 32: сохранённая обрезанная должность «Руководитель» чинится при старте бота."""
    from bot.services.file_extractor import is_truncated_role, repair_invalid_resume_profiles

    raw = (
        "Иванов Иван Иванович\n"
        "Руководитель продукта\n"
        "Москва\n\n"
        "Навыки\nProduct Management, SQL\n"
    )
    await db.save_resume(
        user_id=888,
        raw_text=raw,
        extracted_role="Руководитель",
        extracted_skills=["SQL"],
    )
    assert is_truncated_role("Руководитель") is True
    assert is_truncated_role("Руководитель продукта") is False

    repaired = await repair_invalid_resume_profiles(db)
    assert repaired >= 1

    record = await db.get_resume(888)
    assert record is not None
    assert record["extracted_role"] == "Руководитель продукта"


@pytest.mark.asyncio
async def test_hh_api_block_is_reported_not_silent() -> None:
    """Тест 33: блокировка API hh.ru (403) попадает в предупреждения, а не теряется."""
    from datetime import datetime, timezone

    from bot.services.vacancy_parser import _fetch_hh_api_vacancies

    class _Resp:
        status = 403

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def json(self):
            return {"errors": [{"type": "forbidden"}]}

        async def text(self, errors="ignore"):
            return ""

    class _Session:
        def get(self, *args, **kwargs):
            return _Resp()

    issues: list = []
    result = await _fetch_hh_api_vacancies(
        session=_Session(),  # type: ignore[arg-type]
        source={"canonical_url": "https://hh.ru", "title": "Сайт: HeadHunter (hh.ru API)"},
        role="Руководитель продукта",
        skills=["SQL"],
        period_days=7,
        cutoff_dt=datetime.now(timezone.utc),
        issues=issues,
    )
    assert result == []
    assert len(issues) == 1
    assert "403" in issues[0]["reason"]


# =============================================================================
# Фильтр «Рекомендуем кандидата …» и листание выдачи (больше 10 вакансий)
# =============================================================================

def _fake_vacancy(idx: int, title: str = None, source: str = "TG: Вакансии от CRC (@vacancyCRC)") -> dict:
    from datetime import datetime, timezone

    return {
        "title": title or f"Руководитель продукта {idx}",
        "url": f"https://t.me/vacancyCRC/{idx}",
        "source_title": source,
        "source_type": "tg_channel",
        "published_at": datetime.now(timezone.utc),
        "matched_skills": ["Product Management"],
        "relevance_score": 50,
        "snippet": "описание вакансии",
    }


def test_recommend_candidate_posts_are_excluded() -> None:
    """Тест 34: объявления «Рекомендуем кандидата …» считаются резюме и в вакансии не попадают."""
    from bot.services.vacancy_parser import is_excluded_vacancy

    excluded_titles = [
        "РЕКОМЕНДУЕМ КАНДИДАТА НА ПОЗИЦИЮ:",
        "Рекомендуем кандидата на позиции: Финансовый директор / CFO",
        "🔥 рекомендуем кандидатов на вакансию",
        "Рекомендуем специалиста: Операционный директор",
    ]
    for title in excluded_titles:
        vacancy = _fake_vacancy(1, title=title)
        assert is_excluded_vacancy(vacancy), title

    # обычные вакансии с этим словом внутри не отбрасываются
    for title in (
        "Руководитель продукта в рекомендательном сервисе",
        "Директор по маркетингу (рекомендуем к отклику)",  # фраза не в начале
        "Product Owner",
    ):
        assert not is_excluded_vacancy(_fake_vacancy(2, title=title)), title


def test_search_page_shows_more_than_ten_with_continuous_numbering() -> None:
    """Тест 35: по кнопке «Показать ещё» видны вакансии 11–20, нумерация сквозная."""
    from bot.services.vacancy_parser import format_vacancies_search_blocks

    vacancies = [_fake_vacancy(i) for i in range(1, 26)]
    result = {
        "period_days": 7,
        "period_label": "1 неделя",
        "role": "Руководитель продукта",
        "skills": ["Product Management"],
        "sources_checked": 163,
        "total_found": len(vacancies),
        "all_vacancies": vacancies,
        "page_size": 10,
        "vacancies": vacancies[:10],
        "excluded_count": 13,
        "source_issues": [],
        "manual_sources": [],
    }

    first_body, first_footer = format_vacancies_search_blocks(result, offset=0, limit=10)
    assert "показаны 1–10 из 25" in first_body
    assert "**1. Руководитель продукта 1**" in first_body
    assert "**11. Руководитель продукта 11**" not in first_body
    assert "Отфильтровано" in first_body and "13" in first_body
    assert "Рекомендуем кандидата" in first_body
    assert first_footer, "на первой странице должен быть подвал с предупреждениями и дисклеймером"

    second_body, second_footer = format_vacancies_search_blocks(result, offset=10, limit=10)
    assert "показаны 11–20 из 25" in second_body
    assert "**11. Руководитель продукта 11**" in second_body
    assert "**20. Руководитель продукта 20**" in second_body
    assert second_footer == "", "подвал не дублируется на средней странице"

    last_body, last_footer = format_vacancies_search_blocks(result, offset=20, limit=10)
    assert "**21. Руководитель продукта 21**" in last_body
    assert "**25. Руководитель продукта 25**" in last_body
    assert last_footer, "на последней странице подвал (дисклеймер) возвращается"


def test_search_results_keyboard_offers_next_pages() -> None:
    """Тест 36: клавиатура выдачи предлагает «ещё 10» и «показать все», а в конце исчезает."""
    from bot.keyboards import get_search_results_keyboard

    keyboard = get_search_results_keyboard(shown=10, total=371, page_size=10)
    assert keyboard is not None
    buttons = [b for row in keyboard.inline_keyboard for b in row]
    texts = [b.text for b in buttons]
    assert any("Показать ещё 10" in t for t in texts)
    assert any("Показать все (361)" in t for t in texts)
    assert [b.callback_data for b in buttons] == ["search_more:10", "search_all:10"]

    tail = get_search_results_keyboard(shown=365, total=371, page_size=10)
    assert tail is not None
    assert "Показать ещё 6" in tail.inline_keyboard[0][0].text

    assert get_search_results_keyboard(shown=371, total=371, page_size=10) is None


def test_search_sessions_cache_lets_users_browse_without_new_parsing() -> None:
    """Тест 37: результат поиска кэшируется, страницы листаются без повторного парсинга."""
    from bot.services.search_sessions import (
        clear_search_result,
        get_search_result,
        store_search_result,
        total_items,
    )

    result = {"all_vacancies": [_fake_vacancy(i) for i in range(1, 16)], "total_found": 15}
    store_search_result(4242, result)
    assert get_search_result(4242) is result
    assert total_items(result) == 15

    clear_search_result(4242)
    assert get_search_result(4242) is None


@pytest.mark.asyncio
async def test_render_search_page_sends_all_pages_with_keyboard() -> None:
    """Тест 38: экран выдачи листается — каждая страница уходит с кнопками, последняя без них."""
    from bot.handlers.search import _render_search_page
    from bot.services.search_sessions import store_search_result

    class FakeMessage:
        def __init__(self) -> None:
            self.sent: list = []

        async def edit_text(self, text, **kwargs):
            self.sent.append(("edit", text, kwargs))
            return self

        async def answer(self, text, **kwargs):
            self.sent.append(("answer", text, kwargs))
            return self

    vacancies = [_fake_vacancy(i) for i in range(1, 26)]
    result = {
        "period_days": 7,
        "period_label": "1 неделя",
        "role": "Руководитель продукта",
        "skills": ["Product Management"],
        "sources_checked": 163,
        "total_found": 25,
        "all_vacancies": vacancies,
        "page_size": 10,
        "vacancies": vacancies[:10],
        "source_issues": [],
        "manual_sources": [],
    }
    store_search_result(5151, result)

    message = FakeMessage()
    await _render_search_page(message=message, result=result, offset=10)

    assert message.sent, "страница должна быть отправлена"
    last_kind, last_text, last_kwargs = message.sent[-1]
    assert "**11. Руководитель продукта 11**" in last_text
    assert last_kwargs.get("reply_markup") is not None, "на странице 11–20 кнопки ещё нужны"

    final_message = FakeMessage()
    await _render_search_page(message=final_message, result=result, offset=20)
    assert "**25. Руководитель продукта 25**" in final_message.sent[-1][1]
    assert final_message.sent[-1][2].get("reply_markup") is None, "после последней страницы кнопок нет"


@pytest.mark.asyncio
async def test_search_excludes_candidates_end_to_end(monkeypatch) -> None:
    """Тест 39: фильтр «Рекомендуем кандидата» работает на уровне всего поиска."""
    from bot.services import vacancy_parser

    vacancies = [
        _fake_vacancy(1),
        _fake_vacancy(2, title="РЕКОМЕНДУЕМ КАНДИДАТА НА ПОЗИЦИЮ: CFO"),
        _fake_vacancy(3),
    ]

    async def fake_parse_single_source(**kwargs):
        return list(vacancies)

    monkeypatch.setattr(vacancy_parser, "_parse_single_source", fake_parse_single_source)

    class FakeDB:
        async def get_resume(self, user_id):
            return {"extracted_role": "Руководитель продукта", "extracted_skills": ["SQL"]}

        async def list_sources(self, active_only=True):
            return [
                {
                    "title": "TG: Вакансии от CRC (@vacancyCRC)",
                    "canonical_url": "https://t.me/vacancyCRC",
                    "parse_url": "https://t.me/s/vacancyCRC",
                    "source_type": "tg_channel",
                    "is_active": 1,
                }
            ]

    result = await vacancy_parser.search_vacancies_by_resume(
        db=FakeDB(), user_id=1, period_days=7
    )
    titles = [v["title"] for v in result["all_vacancies"]]
    assert "РЕКОМЕНДУЕМ КАНДИДАТА НА ПОЗИЦИЮ: CFO" not in titles
    assert result["excluded_count"] == 1
    assert result["total_found"] == 2


# =============================================================================
# Правка профиля резюме кнопками + фильтр постов «Резюме» в Telegram-каналах
# =============================================================================

def _fsm_context(user_id: int = 700):
    """Готовый FSMContext на MemoryStorage — как в реальном диспетчере."""
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.fsm.storage.memory import MemoryStorage

    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=user_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


class _ProfileMessage:
    """Заглушка aiogram.Message для правки профиля: text + answer + from_user."""

    def __init__(self, text: str, user_id: int = 700) -> None:
        self.text = text
        self.sent: list = []

        class _User:
            id = user_id
            username = "tester"

        self.from_user = _User()

    async def answer(self, text, **kwargs):
        self.sent.append((text, kwargs))
        return self

    async def edit_text(self, text, **kwargs):
        self.sent.append((text, kwargs))
        return self


class _ProfileCallback:
    """Заглушка CallbackQuery: data + message + from_user."""

    def __init__(self, data: str, message, user_id: int = 700) -> None:
        self.data = data
        self.message = message
        self.answered = 0

        class _User:
            id = user_id

        self.from_user = _User()

    async def answer(self, *args, **kwargs):
        self.answered += 1


@pytest.mark.asyncio
async def test_profile_edit_buttons_are_offered_after_upload() -> None:
    """Тест 40: сразу после загрузки резюме есть кнопки правки должности и навыков."""
    from bot.keyboards import get_after_upload_keyboard, get_profile_edit_keyboard

    upload_kb = get_after_upload_keyboard()
    buttons = {b.callback_data: b.text for row in upload_kb.inline_keyboard for b in row}
    assert "profile_edit:role" in buttons and "должность" in buttons["profile_edit:role"].lower()
    assert "profile_edit:skills" in buttons and "навык" in buttons["profile_edit:skills"].lower()
    assert "quick_action:search" in buttons
    # кнопки правки стоят выше поиска — их и надо нажимать до поиска
    flat = [b.callback_data for row in upload_kb.inline_keyboard for b in row]
    assert flat.index("profile_edit:role") < flat.index("quick_action:search")
    assert flat.index("profile_edit:skills") < flat.index("quick_action:search")

    edit_kb = get_profile_edit_keyboard()
    edit_codes = [b.callback_data for row in edit_kb.inline_keyboard for b in row]
    assert edit_codes == ["profile_edit:role", "profile_edit:skills", "quick_action:search"]


@pytest.mark.asyncio
async def test_edit_role_flow_updates_profile(db: Database) -> None:
    """Тест 41: кнопка «Изменить должность» → ввод текста → должность сохранена в БД."""
    from bot.handlers.resume import cb_edit_profile_role, handle_profile_role_input

    await db.save_resume(
        user_id=700,
        raw_text="Иванов Иван\nМенеджер\nМосква\n\nНавыки\nExcel, CRM\n",
        extracted_role="Менеджер",
        extracted_skills=["Excel", "CRM"],
    )
    state = _fsm_context(700)
    message = _ProfileMessage("", user_id=700)
    callback = _ProfileCallback("profile_edit:role", message, user_id=700)

    await cb_edit_profile_role(callback, state, db)
    assert callback.answered == 1
    assert await state.get_state() == "ResumeStates:waiting_for_role"
    assert "Изменение целевой должности" in message.sent[-1][0]

    typed = _ProfileMessage("«Руководитель продукта»", user_id=700)
    await handle_profile_role_input(typed, state, db)

    assert await state.get_state() is None, "после сохранения состояние должно сбрасываться"
    record = await db.get_resume(700)
    assert record["extracted_role"] == "Руководитель продукта"
    assert "Руководитель продукта" in typed.sent[-1][0]
    assert typed.sent[-1][1].get("reply_markup") is not None


@pytest.mark.asyncio
async def test_edit_skills_flow_parses_and_replaces(db: Database) -> None:
    """Тест 42: навыки заменяются списком из текста, дубликаты убираются, «очистить» работает."""
    from bot.handlers.resume import (
        cb_edit_profile_skills,
        handle_profile_skills_input,
        _parse_skills_input,
    )

    assert _parse_skills_input("P&L, Excel; CRM | 1C") == ["P&L", "Excel", "CRM", "1C"]
    assert _parse_skills_input("Excel, excel, EXCEL") == ["Excel"]

    await db.save_resume(
        user_id=701,
        raw_text="Иванов Иван\nРуководитель продукта\nНавыки\nExcel\n",
        extracted_role="Руководитель продукта",
        extracted_skills=["Excel"],
    )
    state = _fsm_context(701)
    message = _ProfileMessage("", user_id=701)
    callback = _ProfileCallback("profile_edit:skills", message, user_id=701)

    await cb_edit_profile_skills(callback, state, db)
    assert await state.get_state() == "ResumeStates:waiting_for_skills"

    typed = _ProfileMessage(
        "Product Management, Unit Economics\nSQL, Product Management", user_id=701
    )
    await handle_profile_skills_input(typed, state, db)

    record = await db.get_resume(701)
    assert record["extracted_skills"] == ["Product Management", "Unit Economics", "SQL"]
    assert await state.get_state() is None

    # «очистить» освобождает список
    await cb_edit_profile_skills(_ProfileCallback("profile_edit:skills", message, user_id=701), state, db)
    await handle_profile_skills_input(_ProfileMessage("очистить", user_id=701), state, db)
    assert (await db.get_resume(701))["extracted_skills"] == []


@pytest.mark.asyncio
async def test_edit_role_can_be_cancelled(db: Database) -> None:
    """Тест 43: правку профиля можно отменить — прежние значения остаются."""
    from bot.handlers.resume import handle_profile_role_input

    await db.save_resume(
        user_id=702,
        raw_text="Иванов Иван\nДиректор по маркетингу\n",
        extracted_role="Директор по маркетингу",
        extracted_skills=["Excel"],
    )
    state = _fsm_context(702)
    await state.set_state("ResumeStates:waiting_for_role")

    cancelled = _ProfileMessage("/cancel", user_id=702)
    await handle_profile_role_input(cancelled, state, db)

    assert await state.get_state() is None
    assert (await db.get_resume(702))["extracted_role"] == "Директор по маркетингу"
    assert "отменено" in cancelled.sent[-1][0].lower()

    # нажатие кнопки главного меню тоже выходит из режима правки
    await state.set_state("ResumeStates:waiting_for_role")
    menu_click = _ProfileMessage("🔍 Поиск вакансий", user_id=702)
    await handle_profile_role_input(menu_click, state, db)
    assert await state.get_state() is None
    assert (await db.get_resume(702))["extracted_role"] == "Директор по маркетингу"


def test_resume_posts_excluded_only_in_telegram_channels() -> None:
    """Тест 44: посты, начинающиеся с «Резюме», отбрасываются в TG-каналах, но не на сайтах."""
    from bot.services.vacancy_parser import (
        REASON_CANDIDATE_RECOMMENDATION,
        REASON_RESUME_POST,
        vacancy_exclusion_reason,
    )

    tg_resume = {"title": "Резюме: Иван Иванов, финансовый директор", "snippet": "", "source_type": "tg_channel"}
    assert vacancy_exclusion_reason(tg_resume) == REASON_RESUME_POST

    emoji_resume = {"title": "📄 РЕЗЮМЕ — директор по продажам", "snippet": "", "source_type": "tg_channel"}
    assert vacancy_exclusion_reason(emoji_resume) == REASON_RESUME_POST

    cv_post = {"title": "CV: Product manager", "snippet": "", "source_type": "tg_channel"}
    assert vacancy_exclusion_reason(cv_post) == REASON_RESUME_POST

    # на сайте вакансий «Резюме …» может быть статьёй — не отбрасываем
    site_resume = {"title": "Резюме: как составить правильно", "snippet": "", "source_type": "website"}
    assert vacancy_exclusion_reason(site_resume) == ""

    # «Резюме не требуется» — это вакансия
    no_resume_needed = {"title": "Резюме не требуется — продавец", "snippet": "", "source_type": "tg_channel"}
    assert vacancy_exclusion_reason(no_resume_needed) == ""

    # обычная вакансия и рекомендация кандидата
    vacancy = {"title": "Руководитель продукта", "snippet": "", "source_type": "tg_channel"}
    assert vacancy_exclusion_reason(vacancy) == ""
    recommendation = {
        "title": "РЕКОМЕНДУЕМ КАНДИДАТА НА ПОЗИЦИЮ: CFO",
        "snippet": "",
        "source_type": "tg_channel",
    }
    assert vacancy_exclusion_reason(recommendation) == REASON_CANDIDATE_RECOMMENDATION


@pytest.mark.asyncio
async def test_search_reports_resume_posts_filtered() -> None:
    """Тест 45: в шапке выдачи видно, сколько постов-резюме отфильтровано и почему."""
    from bot.services import vacancy_parser

    vacancies = [
        {"title": "Руководитель продукта", "url": "https://t.me/x/1", "source_title": "TG: x",
         "source_type": "tg_channel", "published_at": __import__("datetime").datetime.now(
             __import__("datetime").timezone.utc), "matched_skills": [], "relevance_score": 10,
         "snippet": ""},
        {"title": "Резюме: Иван Иванов, CFO", "url": "https://t.me/x/2", "source_title": "TG: x",
         "source_type": "tg_channel", "published_at": __import__("datetime").datetime.now(
             __import__("datetime").timezone.utc), "matched_skills": [], "relevance_score": 10,
         "snippet": ""},
        {"title": "РЕКОМЕНДУЕМ КАНДИДАТА НА ПОЗИЦИЮ: COO", "url": "https://t.me/x/3",
         "source_title": "TG: x", "source_type": "tg_channel",
         "published_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
         "matched_skills": [], "relevance_score": 10, "snippet": ""},
    ]

    async def fake_parse_single_source(**kwargs):
        return list(vacancies)

    monkeypatch_target = "_parse_single_source"
    original = getattr(vacancy_parser, monkeypatch_target)
    setattr(vacancy_parser, monkeypatch_target, fake_parse_single_source)
    try:
        class FakeDB:
            async def get_resume(self, user_id):
                return {"extracted_role": "Руководитель продукта", "extracted_skills": []}

            async def list_sources(self, active_only=True):
                return [{"title": "TG: x", "canonical_url": "https://t.me/x",
                         "parse_url": "https://t.me/s/x", "source_type": "tg_channel", "is_active": 1}]

        result = await vacancy_parser.search_vacancies_by_resume(db=FakeDB(), user_id=1, period_days=7)
    finally:
        setattr(vacancy_parser, monkeypatch_target, original)

    assert result["total_found"] == 1
    assert result["excluded_count"] == 2
    assert result["excluded_breakdown"]["пост-резюме кандидата («Резюме …»)"] == 1
    assert result["excluded_breakdown"]["рекомендация кандидата («Рекомендуем кандидата …»)"] == 1

    body, _footer = vacancy_parser.format_vacancies_search_blocks(result)
    assert "Отфильтровано постов-резюме" in body
    assert "Резюме …" in body


@pytest.mark.asyncio
async def test_manual_profile_edit_survives_auto_repair(db: Database) -> None:
    """Тест 46: ручную правку профиля авто-починка при старте бота не перезаписывает."""
    from bot.services.file_extractor import repair_invalid_resume_profiles

    # 1. Ручная правка: пользователь сам выбрал короткую должность «Руководитель»
    await db.save_resume(
        user_id=710,
        raw_text="Иванов Иван\nРуководитель продукта\nМосква\n",
        extracted_role="Руководитель продукта",
        extracted_skills=["SQL"],
    )
    await db.update_resume_profile(user_id=710, role="Руководитель")
    assert (await db.get_resume(710))["profile_edited_manually"] == 1

    # 2. Профиль из старой версии (без отметки о ручной правке)
    await db.save_resume(
        user_id=711,
        raw_text="Петров Пётр\nРуководитель продукта\nМосква\n",
        extracted_role="Руководитель",
        extracted_skills=["SQL"],
    )

    await repair_invalid_resume_profiles(db)

    assert (await db.get_resume(710))["extracted_role"] == "Руководитель", "ручную правку не трогаем"
    assert (await db.get_resume(711))["extracted_role"] == "Руководитель продукта", "старый профиль чинится"


@pytest.mark.asyncio
async def test_profile_edit_marks_manual_and_survives_restart_flow(db: Database) -> None:
    """Тест 47: правка кнопками помечает профиль как ручной и переживает перезапуск бота."""
    from bot.handlers.resume import handle_profile_role_input, handle_profile_skills_input
    from bot.services.file_extractor import repair_invalid_resume_profiles

    await db.save_resume(
        user_id=712,
        raw_text="Иванов Иван\nМенеджер\nМосква\n",
        extracted_role="Менеджер",
        extracted_skills=["Excel"],
    )
    state = _fsm_context(712)
    await state.set_state("ResumeStates:waiting_for_role")
    await handle_profile_role_input(_ProfileMessage("Директор", user_id=712), state, db)
    await state.set_state("ResumeStates:waiting_for_skills")
    await handle_profile_skills_input(_ProfileMessage("Excel, P&L", user_id=712), state, db)

    await repair_invalid_resume_profiles(db)

    record = await db.get_resume(712)
    assert record["extracted_role"] == "Директор"
    assert record["extracted_skills"] == ["Excel", "P&L"]
    assert record["profile_edited_manually"] == 1


# =============================================================================
# Подключение бесплатной LLM (Gemini / Groq / Cerebras / Mistral / OpenRouter / Ollama)
# =============================================================================

_GOOD_ANSWER = "## ПРОФЕССИОНАЛЬНЫЙ ОПЫТ\n" + ("- Вывел продукт на рынок, +38% выручки. " * 12)


class _FakeLLMResponse:
    def __init__(self, status: int, payload) -> None:
        self.status = status
        self._payload = payload

    async def text(self, *args, **kwargs):
        return self._payload if isinstance(self._payload, str) else "{}"

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeLLMSession:
    """Подменяет aiohttp.ClientSession: отдаёт заранее заданные ответы по URL."""

    calls: list = []

    def __init__(self, handler, **kwargs) -> None:
        self.handler = handler
        self.__class__.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def post(self, url, json=None, headers=None):
        type(self).calls.append({"url": url, "json": json, "headers": headers})
        status, payload = self.handler(url, json, headers)
        return _FakeLLMResponse(status, payload)


def _openai_answer(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def _gemini_answer(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def _install_fake_session(monkeypatch, handler) -> None:
    from bot.services import llm_client

    monkeypatch.setattr(
        llm_client.aiohttp, "ClientSession", lambda **kwargs: _FakeLLMSession(handler)
    )


def test_llm_providers_are_built_from_env(monkeypatch) -> None:
    """Тест 48: провайдеры собираются из переменных окружения, порядок задаётся LLM_ORDER."""
    from bot.services import llm_client

    for name in ("LLM_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY",
                 "CEREBRAS_API_KEY", "MISTRAL_API_KEY", "OPENROUTER_API_KEY",
                 "LLM_PROVIDER", "LLM_ORDER"):
        monkeypatch.delenv(name, raising=False)

    assert llm_client.build_providers() == [], "без ключей провайдеров нет"

    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test-key-123456")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test-key-123456")
    keys = [p.key for p in llm_client.build_providers()]
    assert keys == ["gemini", "groq"]

    monkeypatch.setenv("LLM_ORDER", "groq,gemini")
    assert [p.key for p in llm_client.build_providers()] == ["groq", "gemini"]

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert [p.key for p in llm_client.build_providers()] == ["gemini"]
    monkeypatch.delenv("LLM_PROVIDER")

    # ключ в чате показывается замаскированным
    masked = llm_client.build_providers()[0].masked_key()
    assert masked.startswith("gsk") and "…" in masked and "test-key" not in masked


@pytest.mark.asyncio
async def test_llm_falls_back_to_second_provider_on_quota(monkeypatch) -> None:
    """Тест 49: если у провайдера кончилась квота (429), запрос уходит следующему."""
    from bot.services import llm_client

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("LLM_ORDER", "gemini,groq")

    def handler(url, payload, headers):
        if "generativelanguage" in url:
            return 429, "quota exceeded"
        return 200, _openai_answer(_GOOD_ANSWER)

    _install_fake_session(monkeypatch, handler)
    result = await llm_client.generate_text("system", "user")

    assert result is not None
    assert "Groq" in result.provider_label
    assert result.text.startswith("## ПРОФЕССИОНАЛЬНЫЙ ОПЫТ")
    assert any("HTTP 429" in a for a in result.attempts)
    assert llm_client.LAST_RESULT is result


@pytest.mark.asyncio
async def test_llm_gemini_request_shape(monkeypatch) -> None:
    """Тест 50: для Gemini используется нативный эндпоинт с system_instruction."""
    from bot.services import llm_client

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    monkeypatch.setenv("LLM_ORDER", "gemini")

    def handler(url, payload, headers):
        return 200, _gemini_answer(_GOOD_ANSWER)

    _install_fake_session(monkeypatch, handler)
    result = await llm_client.generate_text("Ты коуч", "Резюме")

    assert result is not None and "Gemini" in result.provider_label
    call = _FakeLLMSession.calls[0]
    assert call["url"].endswith(":generateContent")
    assert "/models/gemini-2.5-flash" in call["url"]
    assert call["headers"]["x-goog-api-key"] == "AIza-test"
    assert call["json"]["system_instruction"]["parts"][0]["text"] == "Ты коуч"
    assert call["json"]["contents"][0]["parts"][0]["text"] == "Резюме"


@pytest.mark.asyncio
async def test_llm_skips_refusals_and_short_answers(monkeypatch) -> None:
    """Тест 51: вежливый отказ и слишком короткий ответ считаются неудачей провайдера."""
    from bot.services import llm_client

    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("LLM_ORDER", "gemini,groq")

    def handler(url, payload, headers):
        if "generativelanguage" in url:
            return 200, _gemini_answer("Извините, не могу помочь с этим запросом.")
        return 200, _openai_answer(_GOOD_ANSWER)

    _install_fake_session(monkeypatch, handler)
    result = await llm_client.generate_text("system", "user")

    assert result is not None and "Groq" in result.provider_label
    assert any("короткий" in a for a in result.attempts)


@pytest.mark.asyncio
async def test_llm_returns_none_when_all_providers_fail(monkeypatch) -> None:
    """Тест 52: если не ответил никто, возвращается None (бот уходит на локальный движок)."""
    from bot.services import llm_client

    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("LLM_PROVIDER", "groq")

    def handler(url, payload, headers):
        return 401, "invalid api key"

    _install_fake_session(monkeypatch, handler)
    assert await llm_client.generate_text("system", "user") is None
    assert llm_client.LAST_RESULT is None
    assert any("HTTP 401" in a for a in llm_client.LAST_ATTEMPTS)


@pytest.mark.asyncio
async def test_adaptation_reports_llm_model(monkeypatch, db: Database) -> None:
    """Тест 53: в отчёте об адаптации видно, какой бесплатной моделью сделана переработка."""
    from bot.services import llm_client, market_standards

    async def fake_generate(system_prompt, user_prompt, **kwargs):
        return llm_client.LLMResult(
            text=_GOOD_ANSWER,
            provider_label="Groq (free tier)",
            model="llama-3.3-70b-versatile",
            attempts=["Groq (free tier): OK"],
        )

    monkeypatch.setattr(market_standards, "generate_text", fake_generate)

    await db.save_resume(
        user_id=720,
        raw_text="Иванов Иван\nРуководитель продукта\nВывел 3 продукта, выручка +38%.\n",
        extracted_role="Руководитель продукта",
        extracted_skills=["Product Management", "SQL"],
    )
    result = await market_standards.adapt_resume_to_market_standards(db=db, user_id=720)

    assert result["adapted_text"] == _GOOD_ANSWER
    assert "Бесплатная LLM" in result["engine_used"]
    assert "llama-3.3-70b-versatile" in result["engine_used"]
    assert result["docx_bytes"][:2] == b"PK", "должен собраться .docx"


@pytest.mark.asyncio
async def test_llm_command_explains_how_to_connect(monkeypatch) -> None:
    """Тест 54: команда /llm без ключей объясняет, как подключить бесплатную модель."""
    from bot.handlers.common import cmd_llm_status

    for name in ("LLM_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY",
                 "CEREBRAS_API_KEY", "MISTRAL_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    class FakeMessage:
        def __init__(self):
            self.sent = []

        async def answer(self, text, **kwargs):
            self.sent.append((text, kwargs))
            return self

    message = FakeMessage()
    await cmd_llm_status(message)

    text = message.sent[-1][0]
    assert "LLM не подключена" in text
    assert "aistudio.google.com/apikey" in text and "console.groq.com/keys" in text
    assert "GEMINI_API_KEY" in text and "Secrets" in text
    assert message.sent[-1][1].get("parse_mode") == "Markdown"
