"""Модуль работы с базой данных SQLite (aiosqlite).

Хранит:
1. Загруженные и адаптированные резюме пользователей (`users_resumes`).
2. Заданные стандарты рынка (`market_standards`).
3. Базу информационных ресурсов: ТГ-каналы и сайты вакансий (`sources`).
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import aiosqlite

DEFAULT_SOURCES: List[Dict[str, str]] = [
    # Проверенные Telegram-каналы с вакансиями (публичное веб-превью доступно)
    {
        "canonical_url": "https://t.me/habr_career",
        "parse_url": "https://t.me/s/habr_career",
        "source_type": "tg_channel",
        "title": "TG: Хабр Карьера (@habr_career)",
    },
    {
        "canonical_url": "https://t.me/job_it_ru",
        "parse_url": "https://t.me/s/job_it_ru",
        "source_type": "tg_channel",
        "title": "TG: IT Job x IT Vacancies (@job_it_ru)",
    },
    {
        "canonical_url": "https://t.me/vacancies_it",
        "parse_url": "https://t.me/s/vacancies_it",
        "source_type": "tg_channel",
        "title": "TG: HR | Вакансии (@vacancies_it)",
    },
    {
        "canonical_url": "https://t.me/remote_work_jobs",
        "parse_url": "https://t.me/s/remote_work_jobs",
        "source_type": "tg_channel",
        "title": "TG: Remote Jobs | Remote Work (@remote_work_jobs)",
    },
    {
        "canonical_url": "https://t.me/marketing_jobs",
        "parse_url": "https://t.me/s/marketing_jobs",
        "source_type": "tg_channel",
        "title": "TG: marketing jobs (@marketing_jobs)",
    },
    # --- HR, карьера и вакансии (добавлено по запросу пользователя, проверено 18.11.2026) ---
    {
        "canonical_url": "https://t.me/marhrru",
        "parse_url": "https://t.me/s/marhrru",
        "source_type": "tg_channel",
        "title": "TG: МарЧар | Маркетинг в HR (@marhrru)",
    },
    {
        "canonical_url": "https://t.me/HRmother",
        "parse_url": "https://t.me/s/HRmother",
        "source_type": "tg_channel",
        "title": "TG: HR мама 🍋 (@HRmother)",
    },
    {
        "canonical_url": "https://t.me/kadrovik_krd",
        "parse_url": "https://t.me/s/kadrovik_krd",
        "source_type": "tg_channel",
        "title": "TG: Кадровый голод (@kadrovik_krd)",
    },
    {
        "canonical_url": "https://t.me/uptume",
        "parse_url": "https://t.me/s/uptume",
        "source_type": "tg_channel",
        "title": "TG: Аптуми (up to me) (@uptume)",
    },
    {
        "canonical_url": "https://t.me/rus_hr",
        "parse_url": "https://t.me/s/rus_hr",
        "source_type": "tg_channel",
        "title": "TG: Русский HR (@rus_hr)",
    },
    {
        "canonical_url": "https://t.me/uvolnyaus",
        "parse_url": "https://t.me/s/uvolnyaus",
        "source_type": "tg_channel",
        "title": "TG: Всё, я увольняюсь! (@uvolnyaus)",
    },
    {
        "canonical_url": "https://t.me/akks_career",
        "parse_url": "https://t.me/s/akks_career",
        "source_type": "tg_channel",
        "title": "TG: АККСиомы Карьеры (@akks_career)",
    },
    {
        "canonical_url": "https://t.me/rudakovahr",
        "parse_url": "https://t.me/s/rudakovahr",
        "source_type": "tg_channel",
        "title": "TG: Вакансии от Хрипченко Ани (@rudakovahr)",
    },
    {
        "canonical_url": "https://t.me/you_social",
        "parse_url": "https://t.me/s/you_social",
        "source_type": "tg_channel",
        "title": "TG: Янг Групп (@you_social)",
    },
    {
        "canonical_url": "https://t.me/vacanciesbest",
        "parse_url": "https://t.me/s/vacanciesbest",
        "source_type": "tg_channel",
        "title": "TG: Лучшие вакансии (@vacanciesbest)",
    },
    {
        "canonical_url": "https://t.me/jobinspb",
        "parse_url": "https://t.me/s/jobinspb",
        "source_type": "tg_channel",
        "title": "TG: Топовые вакансии | Петр Липов (@jobinspb)",
    },
    {
        "canonical_url": "https://t.me/fuck_the_frameworks",
        "parse_url": "https://t.me/s/fuck_the_frameworks",
        "source_type": "tg_channel",
        "title": "TG: fuck_the_frameworks (@fuck_the_frameworks)",
    },
    {
        "canonical_url": "https://t.me/nongreta",
        "parse_url": "https://t.me/s/nongreta",
        "source_type": "tg_channel",
        "title": "TG: Неустойчивое развитие (@nongreta)",
    },
    # --- Международные job-борды (проверено 18.11.2026) ---
    # Автопарсинг возможен: RemoteOK (JSON API), We Work Remotely и Jobspresso (RSS)
    {
        "canonical_url": "https://remoteok.com/",
        "parse_url": "https://remoteok.com/api",
        "source_type": "json_api",
        "title": "Сайт: RemoteOK (remoteok.com, JSON API)",
    },
    {
        "canonical_url": "https://weworkremotely.com/",
        "parse_url": "https://weworkremotely.com/remote-jobs.rss",
        "source_type": "website",
        "title": "Сайт: We Work Remotely (weworkremotely.com, RSS)",
    },
    {
        "canonical_url": "https://jobspresso.co/",
        "parse_url": "https://jobspresso.co/feed/?post_type=job_listing",
        "source_type": "website",
        "title": "Сайт: Jobspresso (jobspresso.co, RSS)",
    },
    # Ручной поиск: площадки отвечают 403 (Cloudflare) или недоступны с хостинга —
    # бот не парсит их, но показывает готовые ссылки поиска под профиль.
    {
        "canonical_url": "https://www.indeed.com/",
        "parse_url": "https://www.indeed.com/",
        "source_type": "manual",
        "title": "Сайт: Indeed (indeed.com)",
    },
    {
        "canonical_url": "https://www.glassdoor.com/",
        "parse_url": "https://www.glassdoor.com/",
        "source_type": "manual",
        "title": "Сайт: Glassdoor (glassdoor.com)",
    },
    {
        "canonical_url": "https://www.ziprecruiter.ie/",
        "parse_url": "https://www.ziprecruiter.ie/",
        "source_type": "manual",
        "title": "Сайт: ZipRecruiter IE (ziprecruiter.ie)",
    },
    {
        "canonical_url": "https://www.careerbuilder.com/",
        "parse_url": "https://www.careerbuilder.com/",
        "source_type": "manual",
        "title": "Сайт: CareerBuilder (careerbuilder.com)",
    },
    {
        "canonical_url": "https://wantapply.com/",
        "parse_url": "https://wantapply.com/",
        "source_type": "manual",
        "title": "Сайт: WantApply (wantapply.com)",
    },
    {
        "canonical_url": "https://remote.co/",
        "parse_url": "https://remote.co/",
        "source_type": "manual",
        "title": "Сайт: Remote.co (remote.co)",
    },
    # Сайты и агрегаторы вакансий
    {
        "canonical_url": "https://hh.ru",
        "parse_url": "https://api.hh.ru/vacancies",
        "source_type": "website",
        "title": "Сайт: HeadHunter (hh.ru API)",
    },
    {
        "canonical_url": "https://career.habr.com",
        "parse_url": "https://career.habr.com/vacancies/rss",
        "source_type": "website",
        "title": "Сайт: Хабр Карьера (career.habr.com)",
    },
    {
        "canonical_url": "https://www.superjob.ru",
        "parse_url": "https://www.superjob.ru/rss/job/",
        "source_type": "website",
        "title": "Сайт: SuperJob (superjob.ru)",
    },
    {
        "canonical_url": "https://geekjob.ru",
        "parse_url": "https://geekjob.ru/vacancies",
        "source_type": "website",
        "title": "Сайт: GeekJob (geekjob.ru)",
    },
]


class Database:
    """Асинхронный менеджер базы данных SQLite."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self) -> None:
        """Создаёт таблицы и предзаполняет базовые источники, если база пустая."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users_resumes (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    raw_text TEXT NOT NULL,
                    adapted_text TEXT,
                    extracted_role TEXT,
                    extracted_skills TEXT,
                    file_name TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS market_standards (
                    user_id INTEGER PRIMARY KEY,
                    preset_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    standards_text TEXT NOT NULL,
                    required_sections TEXT NOT NULL,
                    rules_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_url TEXT UNIQUE NOT NULL,
                    parse_url TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    added_by_user_id INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.commit()

            # Предзаполняем стартовые источники, если таблица пуста
            cursor = await db.execute("SELECT COUNT(*) FROM sources")
            row = await cursor.fetchone()
            count = row[0] if row else 0
            if count == 0:
                now_iso = datetime.now(timezone.utc).isoformat()
                for src in DEFAULT_SOURCES:
                    await db.execute(
                        """
                        INSERT OR IGNORE INTO sources
                        (canonical_url, parse_url, source_type, title, added_by_user_id, is_active, created_at)
                        VALUES (?, ?, ?, ?, 0, 1, ?)
                        """,
                        (
                            src["canonical_url"],
                            src["parse_url"],
                            src["source_type"],
                            src["title"],
                            now_iso,
                        ),
                    )
                await db.commit()

    async def ensure_default_sources(self) -> int:
        """Добавляет отсутствующие источники по умолчанию в уже существующую базу.

        Нужен, чтобы новые ТГ-каналы и сайты из DEFAULT_SOURCES появлялись и у тех
        пользователей, у которых база была создана раньше (иначе предзаполнение
        срабатывает только на пустой таблице `sources`).

        Возвращает количество добавленных источников.
        """
        added = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            for src in DEFAULT_SOURCES:
                cursor = await db.execute(
                    "SELECT 1 FROM sources WHERE canonical_url = ?",
                    (src["canonical_url"],),
                )
                if await cursor.fetchone():
                    continue
                await db.execute(
                    """
                    INSERT OR IGNORE INTO sources
                    (canonical_url, parse_url, source_type, title, added_by_user_id, is_active, created_at)
                    VALUES (?, ?, ?, ?, 0, 1, ?)
                    """,
                    (
                        src["canonical_url"],
                        src["parse_url"],
                        src["source_type"],
                        src["title"],
                        now_iso,
                    ),
                )
                added += 1
            await db.commit()
        return added

    # =========================================================================
    # Работа с резюме (Отдельная функция сохранения и чтения резюме в БД)
    # =========================================================================

    async def save_resume(
        self,
        user_id: int,
        raw_text: str,
        extracted_role: str,
        extracted_skills: List[str],
        file_name: str = "text_input",
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Сохраняет или обновляет резюме пользователя в БД."""
        now_iso = datetime.now(timezone.utc).isoformat()
        skills_json = json.dumps(extracted_skills, ensure_ascii=False)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO users_resumes
                (user_id, username, raw_text, adapted_text, extracted_role, extracted_skills, file_name, updated_at)
                VALUES (?, ?, ?, NULL, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    raw_text = excluded.raw_text,
                    adapted_text = NULL,
                    extracted_role = excluded.extracted_role,
                    extracted_skills = excluded.extracted_skills,
                    file_name = excluded.file_name,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    username or "",
                    raw_text,
                    extracted_role,
                    skills_json,
                    file_name,
                    now_iso,
                ),
            )
            await db.commit()
        return await self.get_resume(user_id)  # type: ignore

    async def save_adapted_resume(self, user_id: int, adapted_text: str) -> None:
        """Сохраняет адаптированную под стандарты рынка версию резюме."""
        now_iso = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE users_resumes
                SET adapted_text = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (adapted_text, now_iso, user_id),
            )
            await db.commit()

    async def list_all_resumes(self) -> List[Dict[str, Any]]:
        """Возвращает все сохранённые резюме (используется для авто-починки профилей)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users_resumes") as cursor:
                rows = await cursor.fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            try:
                data["extracted_skills"] = json.loads(data.get("extracted_skills") or "[]")
            except json.JSONDecodeError:
                data["extracted_skills"] = []
            results.append(data)
        return results

    async def update_resume_profile(
        self,
        user_id: int,
        role: Optional[str] = None,
        skills: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Обновляет целевую должность и/или ключевые навыки в профиле резюме.

        Нужен, когда автоматическое извлечение не справилось (например, в резюме
        не было ни названия должности, ни блока навыков).
        """
        record = await self.get_resume(user_id)
        if not record:
            return None

        new_role = role if role is not None else record.get("extracted_role") or ""
        new_skills = skills if skills is not None else record.get("extracted_skills") or []

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users_resumes SET extracted_role = ?, extracted_skills = ?, updated_at = ? WHERE user_id = ?",
                (
                    new_role,
                    json.dumps(new_skills, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                    user_id,
                ),
            )
            await db.commit()
        return await self.get_resume(user_id)

    async def get_resume(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает сохранённое резюме пользователя."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users_resumes WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            try:
                data["extracted_skills"] = json.loads(data.get("extracted_skills") or "[]")
            except json.JSONDecodeError:
                data["extracted_skills"] = []
            return data

    # =========================================================================
    # Работа со стандартами рынка (Отдельная функция хранения стандартов)
    # =========================================================================

    async def save_user_market_standards(
        self,
        user_id: int,
        preset_key: str,
        title: str,
        standards_text: str,
        required_sections: List[str],
        rules_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Сохраняет заданные пользователем стандарты рынка в БД."""
        now_iso = datetime.now(timezone.utc).isoformat()
        sections_json = json.dumps(required_sections, ensure_ascii=False)
        rules_json = json.dumps(rules_dict, ensure_ascii=False)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO market_standards
                (user_id, preset_key, title, standards_text, required_sections, rules_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    preset_key = excluded.preset_key,
                    title = excluded.title,
                    standards_text = excluded.standards_text,
                    required_sections = excluded.required_sections,
                    rules_json = excluded.rules_json,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    preset_key,
                    title,
                    standards_text,
                    sections_json,
                    rules_json,
                    now_iso,
                ),
            )
            await db.commit()
        return await self.get_user_market_standards(user_id)  # type: ignore

    async def get_user_market_standards(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получает установленные стандарты рынка для пользователя."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM market_standards WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            try:
                data["required_sections"] = json.loads(data.get("required_sections") or "[]")
            except json.JSONDecodeError:
                data["required_sections"] = []
            try:
                data["rules"] = json.loads(data.get("rules_json") or "{}")
            except json.JSONDecodeError:
                data["rules"] = {}
            return data

    async def delete_user_market_standards(self, user_id: int) -> None:
        """Сбрасывает пользовательские стандарты к стандартам по умолчанию."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM market_standards WHERE user_id = ?", (user_id,))
            await db.commit()

    # =========================================================================
    # Работа с источниками вакансий (Сайты и ТГ-каналы + проверка дубликатов)
    # =========================================================================

    async def get_source_by_canonical_url(
        self, canonical_url: str
    ) -> Optional[Dict[str, Any]]:
        """Проверяет, есть ли уже такой источник в базе данных."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM sources WHERE LOWER(canonical_url) = LOWER(?)",
                (canonical_url,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def add_source(
        self,
        canonical_url: str,
        parse_url: str,
        source_type: str,
        title: str,
        added_by_user_id: int = 0,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Добавляет источник вакансий (ТГ-канал или сайт) в БД.

        Возвращает кортеж (is_new, source_record):
        - is_new = False, если источник уже существует в базе данных.
        - is_new = True, если источник был новым и успешно добавлен в базу данных.
        """
        existing = await self.get_source_by_canonical_url(canonical_url)
        if existing:
            return False, existing

        now_iso = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO sources
                (canonical_url, parse_url, source_type, title, added_by_user_id, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    canonical_url,
                    parse_url,
                    source_type,
                    title,
                    added_by_user_id,
                    now_iso,
                ),
            )
            await db.commit()

        created = await self.get_source_by_canonical_url(canonical_url)
        return True, created or {
            "canonical_url": canonical_url,
            "parse_url": parse_url,
            "source_type": source_type,
            "title": title,
            "added_by_user_id": added_by_user_id,
            "is_active": 1,
            "created_at": now_iso,
        }

    async def list_sources(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Возвращает список всех источников вакансий из БД."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM sources"
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY id ASC"
            cursor = await db.execute(query)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
