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
        "https://www.superjob.ru/vacancy/search/?keywords=",
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

    # Имитируем старую (сломанную) запись: ФИО и в роли, и в навыках
    await db.update_resume_profile(
        user_id=user_id,
        role="Кузнецов Дмитрий Сергеевич",
        skills=["Кузнецов", "Дмитрий", "Сергеевич"],
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
async def test_fuck_the_frameworks_channel_added(db: Database) -> None:
    """Тест 12: канал @fuck_the_frameworks добавлен в БД и каталог.

    Канал существует, но закрыл публичное веб-превью — поэтому поиск должен не
    «молчать», а сообщать причину (source_issues).
    """
    from bot.database import DEFAULT_SOURCES
    from bot.services.resource_catalog import TELEGRAM_CHANNELS

    src = next(
        (s for s in DEFAULT_SOURCES if s["canonical_url"] == "https://t.me/fuck_the_frameworks"),
        None,
    )
    assert src is not None
    assert src["parse_url"] == "https://t.me/s/fuck_the_frameworks"
    assert src["source_type"] == "tg_channel"

    sources = await db.list_sources(active_only=False)
    assert "https://t.me/fuck_the_frameworks" in {s["canonical_url"] for s in sources}

    assert "fuck_the_frameworks" in {c["username"] for c in TELEGRAM_CHANNELS}


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
                "title": "TG: fuck_the_frameworks (@fuck_the_frameworks)",
                "url": "https://t.me/fuck_the_frameworks",
                "reason": "канал не отдаёт публичное веб-превью",
            }
        ],
    }
    message = format_vacancies_search_message(result)
    assert "не удалось прочитать" in message
    assert "fuck_the_frameworks" in message
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
