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
    get_market_standards,
    reset_market_standards,
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

    # Проверяем сброс стандартов к базовым
    reset_std = await reset_market_standards(db=db, user_id=user_id)
    assert reset_std["preset_key"] == "universal_ats"


@pytest.mark.asyncio
async def test_sources_duplicate_and_new_detection(db: Database) -> None:
    """Тест 4: Добавление сайтов и ссылок на ТГ-каналы с проверкой на дубликаты в БД."""
    # 1. Пытаемся добавить ТГ-канал, который уже есть в предзаполненной БД (в другом формате ссылки)
    is_new_1, rec_1, msg_1 = await register_source_in_db(
        db=db,
        raw_input="@ru_python_jobs",
        user_id=303,
    )
    assert is_new_1 is False
    assert rec_1["canonical_url"] == "https://t.me/ru_python_jobs"
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
