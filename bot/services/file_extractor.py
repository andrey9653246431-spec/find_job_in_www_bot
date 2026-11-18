"""Отдельный модуль загрузки резюме, извлечения текста из файлов (PDF, DOCX, TXT)
и первичного анализа профиля кандидата (целевая роль и ключевые навыки).
"""
import io
import re
from typing import Any, Dict, List, Tuple
from docx import Document
from pypdf import PdfReader
from bot.database import Database

# Словарь популярных навыков и ключевых слов для автоматического профилирования резюме
KNOWN_SKILLS_MAP: Dict[str, str] = {
    # Языки программирования и разработка
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "java": "Java",
    "golang": "Go",
    "c++": "C++",
    "c#": "C#",
    "php": "PHP",
    "rust": "Rust",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "sql": "SQL",
    # Фреймворки и библиотеки
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "aiogram": "aiogram",
    "asyncio": "asyncio",
    "react": "React",
    "vue": "Vue.js",
    "angular": "Angular",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "spring": "Spring",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scikit-learn": "Scikit-learn",
    # Базы данных и инфраструктура
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "clickhouse": "ClickHouse",
    "kafka": "Apache Kafka",
    "rabbitmq": "RabbitMQ",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "linux": "Linux",
    "git": "Git",
    "ci/cd": "CI/CD",
    "github actions": "GitHub Actions",
    "gitlab": "GitLab CI",
    "nginx": "Nginx",
    "aws": "AWS",
    # Аналитика, QA, Менеджмент, Дизайн, Маркетинг
    "power bi": "Power BI",
    "tableau": "Tableau",
    "excel": "Excel",
    "airflow": "Apache Airflow",
    "etl": "ETL",
    "pytest": "Pytest",
    "selenium": "Selenium",
    "playwright": "Playwright",
    "postman": "Postman",
    "jira": "Jira",
    "confluence": "Confluence",
    "scrum": "Scrum",
    "agile": "Agile",
    "kanban": "Kanban",
    "figma": "Figma",
    "seo": "SEO",
    "smm": "SMM",
    "google analytics": "Google Analytics",
    "яндекс.метрика": "Яндекс.Метрика",
    "b2b": "B2B",
    "crm": "CRM",
    "rest api": "REST API",
    "graphql": "GraphQL",
    "microservices": "Микросервисы",
    "микросервис": "Микросервисы",
    "парсинг": "Парсинг данных",
    "beautifulsoup": "BeautifulSoup",
    "aiohttp": "aiohttp",
    "llm": "LLM / AI",
    "nlp": "NLP",
}

ROLE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"(?:желаемая должность|должность|позиция|target role|position|role)\s*[:\-–]\s*(.+)", re.I), ""),
    (re.compile(r"\b(senior|middle|junior|lead|тимлид|ведущий|младший|старший)?\s*(python|backend|frontend|fullstack|full-stack|devops|data|ml|qa|тестировщик|аналитик|разработчик|программист|инженер|менеджер|маркетолог|дизайнер|product|project)\s*([a-zа-яё\-\s]{0,25})", re.I), ""),
]


def extract_text_from_file_bytes(file_bytes: bytes, file_name: str) -> str:
    """Извлекает чистый текст из загруженного файла резюме (.pdf, .docx, .txt, .md)."""
    lower_name = file_name.lower()

    if lower_name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text = []
        for page in reader.pages:
            page_txt = page.extract_text() or ""
            if page_txt.strip():
                pages_text.append(page_txt.strip())
        return "\n\n".join(pages_text).strip()

    if lower_name.endswith(".docx"):
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        # Дополнительно извлекаем текст из таблиц (часто используется в шаблонах резюме)
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text and c.text.strip()]
                if cells:
                    paragraphs.append(" | ".join(dict.fromkeys(cells)))
        return "\n".join(paragraphs).strip()

    if lower_name.endswith((".txt", ".md", ".rtf", ".csv")):
        for encoding in ("utf-8", "cp1251", "latin-1"):
            try:
                return file_bytes.decode(encoding).strip()
            except UnicodeDecodeError:
                continue
        return file_bytes.decode("utf-8", errors="ignore").strip()

    raise ValueError(
        f"Неподдерживаемый формат файла: {file_name}. "
        "Пожалуйста, загрузите резюме в формате PDF, DOCX, TXT или отправьте текстом."
    )


def extract_role_from_resume(resume_text: str) -> str:
    """Определяет целевую должность из текста резюме."""
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    if not lines:
        return "Специалист"

    # 1. Ищем явное указание "Должность: ..."
    explicit_pattern = ROLE_PATTERNS[0][0]
    for line in lines[:15]:
        match = explicit_pattern.search(line)
        if match:
            role_candidate = match.group(1).strip(" .,;-")
            if 2 <= len(role_candidate) <= 80:
                return role_candidate

    # 2. Ищем характерные названия профессий в первых строках
    role_regex = re.compile(
        r"((?:Junior|Middle|Senior|Lead|Team Lead|Главный|Ведущий|Старший|Младший)?\s*"
        r"(?:Python|Backend|Frontend|Fullstack|Java|Go|Data|ML|AI|DevOps|QA|System|Business|Product|Project|UX/UI|Digital|SMM|SEO)?\s*"
        r"(?:разработчик|программист|инженер|аналитик|тестировщик|менеджер|маркетолог|дизайнер|специалист|"
        r"Developer|Engineer|Analyst|Manager|Designer|Scientist|Architect))",
        re.IGNORECASE,
    )
    for line in lines[:12]:
        match = role_regex.search(line)
        if match:
            found = re.sub(r"\s+", " ", match.group(1)).strip()
            if len(found) >= 4:
                return found

    # 3. Если не нашли по шаблону, берём первую содержательную строку (кроме ФИО/контактов)
    for line in lines[:5]:
        if not any(tok in line.lower() for tok in ("@", "телефон", "phone", "резюме", "cv", "http")):
            if 4 <= len(line) <= 60:
                return line

    return "Специалист"


def extract_skills_from_resume(resume_text: str) -> List[str]:
    """Извлекает ключевые навыки и технологии из текста резюме для поиска вакансий."""
    text_lower = resume_text.lower()
    detected_skills: List[str] = []

    for key, canonical_name in KNOWN_SKILLS_MAP.items():
        # Проверяем вхождение как отдельного токена или словосочетания
        pattern = r"(?:^|[\s,;/()\[\•\-])" + re.escape(key) + r"(?:$|[\s,;/()\[\.!\?])"
        if re.search(pattern, text_lower):
            if canonical_name not in detected_skills:
                detected_skills.append(canonical_name)

    # Также ищем явный блок "Навыки: ..." / "Skills: ..."
    skills_line_match = re.search(
        r"(?:навыки|стек|технологии|ключевые навыки|skills|tech stack)\s*[:\-–]\s*([^\n]+)",
        resume_text,
        re.IGNORECASE,
    )
    if skills_line_match:
        raw_items = re.split(r"[,;|•·]+", skills_line_match.group(1))
        for item in raw_items:
            cleaned = item.strip(" .-–\t")
            if 2 <= len(cleaned) <= 30 and cleaned.lower() not in {s.lower() for s in detected_skills}:
                detected_skills.append(cleaned)

    # Если навыки не распознаны из словаря, извлекаем наиболее значимые существительные/термины из роли
    if not detected_skills:
        role = extract_role_from_resume(resume_text)
        words = [w.strip(",.()") for w in role.split() if len(w.strip(",.()")) >= 3]
        detected_skills.extend(words[:5])

    return detected_skills[:20]


async def upload_and_register_resume(
    db: Database,
    user_id: int,
    raw_text: str,
    file_name: str = "text_input",
    username: str = "",
) -> Dict[str, Any]:
    """Отдельная функция загрузки резюме в бота.

    1. Принимает извлечённый текст резюме.
    2. Определяет целевую должность и список ключевых навыков/тегов.
    3. Сохраняет резюме в базу данных SQLite.
    4. Возвращает профиль загруженного резюме.
    """
    cleaned_text = raw_text.strip()
    if len(cleaned_text) < 20:
        raise ValueError(
            "Текст резюме слишком короткий (менее 20 символов). "
            "Пожалуйста, отправьте полное резюме."
        )

    extracted_role = extract_role_from_resume(cleaned_text)
    extracted_skills = extract_skills_from_resume(cleaned_text)

    saved_record = await db.save_resume(
        user_id=user_id,
        raw_text=cleaned_text,
        extracted_role=extracted_role,
        extracted_skills=extracted_skills,
        file_name=file_name,
        username=username,
    )
    return saved_record
