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
    {
        "canonical_url": "https://t.me/ru_python_jobs",
        "parse_url": "https://t.me/s/ru_python_jobs",
        "source_type": "tg_channel",
        "title": "TG: Python Jobs RU (@ru_python_jobs)",
    },
    {
        "canonical_url": "https://t.me/devjobs",
        "parse_url": "https://t.me/s/devjobs",
        "source_type": "tg_channel",
        "title": "TG: DevJobs — Вакансии в IT (@devjobs)",
    },
    {
        "canonical_url": "https://t.me/remote_it_jobs",
        "parse_url": "https://t.me/s/remote_it_jobs",
        "source_type": "tg_channel",
        "title": "TG: Remote IT Jobs (@remote_it_jobs)",
    },
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
