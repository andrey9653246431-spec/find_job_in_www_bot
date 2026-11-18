"""Отдельный модуль загрузки резюме, извлечения текста из файлов (PDF, DOCX, TXT)
и первичного анализа профиля кандидата (целевая роль и ключевые навыки).
"""
import io
import re
from typing import Any, Dict, List, Optional, Tuple
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
    # Бизнес, менеджмент, офис, ритейл (executive/office профили)
    "p&l": "P&L",
    "unit economics": "Unit Economics",
    "юнит-экономик": "Unit Economics",
    "бюджетир": "Бюджетирование",
    "бюджет": "Бюджетирование",
    "управление командой": "Управление командой",
    "управление проект": "Управление проектами",
    "проектное управление": "Управление проектами",
    "стратегическ": "Стратегическое планирование",
    "бизнес-план": "Бизнес-планирование",
    "ценообраз": "Ценообразование",
    "ассортимент": "Управление ассортиментом",
    "категор": "Категорийный менеджмент",
    "category management": "Category Management",
    "otb": "OTB",
    "cap/otb": "CAP/OTB",
    "закупк": "Закупки",
    "procurement": "Procurement",
    "логистик": "Логистика",
    "supply chain": "Supply Chain",
    "склад": "Складская логистика",
    "продаж": "Продажи",
    "b2c": "B2C",
    "маркетплейс": "Маркетплейсы",
    "маркетинг": "Маркетинг",
    "бренд": "Бренд-менеджмент",
    "digital": "Digital",
    "e-commerce": "E-commerce",
    "ритейл": "Retail",
    "retail": "Retail",
    "мерчандайзинг": "Мерчандайзинг",
    "kpi": "KPI",
    "okr": "OKR",
    "bi-": "BI",
    "bi ": "BI",
    "power query": "Power Query",
    "1с": "1C",
    "1c": "1C",
    "sap": "SAP",
    "erp": "ERP",
    "bitrix": "Bitrix24",
    "битрикс": "Bitrix24",
    "amocrm": "amoCRM",
    "salesforce": "Salesforce",
    "google ads": "Google Ads",
    "яндекс директ": "Яндекс.Директ",
    "яндекс.директ": "Яндекс.Директ",
    "таргет": "Таргетированная реклама",
    "email-маркетинг": "Email-маркетинг",
    "smm": "SMM",
    "seo": "SEO",
    "hr": "HR",
    "рекрутинг": "Рекрутинг",
    "подбор персонала": "Подбор персонала",
    "кадров": "Кадровое администрирование",
    "охрана труда": "Охрана труда",
    "делопроизводств": "Делопроизводство",
    "документооборот": "Документооборот",
    "ms project": "MS Project",
    "powerpoint": "PowerPoint",
    "word": "Word",
    "excel": "Excel",
    "python": "Python",
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


# Служебные заголовки разделов резюме — их нельзя принимать за должность
SECTION_HEADINGS = {
    "резюме", "curriculum vitae", "cv", "профиль", "о себе", "обо мне", "summary",
    "опыт работы", "опыт", "профессиональный опыт", "work experience", "experience",
    "образование", "education", "навыки", "ключевые навыки", "skills", "технологии",
    "стек", "tech stack", "языки", "languages", "контакты", "contacts", "проекты",
    "projects", "достижения", "achievements", "курсы", "сертификаты", "дополнительно",
    "личные качества", "рекомендации", "публикации", "цель", "цель резюме",
}

CONTACT_TOKENS = (
    "@", "http", "www.", "tel", "phone", "телефон", "e-mail", "email", "почта",
    "telegram", "whatsapp", "linkedin", "github", "skype", "адрес", "город", "москва",
    "санкт-петербург", "россия", "russia", "moscow", "born", "дата рождения",
)

# Расширенный словарь должностей: латиница + кириллица, включая директоров и руководителей.
# Собираем регулярку из трёх частей без вложенных групп, чтобы не ошибиться со скобками.
_ROLE_LEVEL_PREFIX = (
    r"(?:(?:Junior|Middle|Senior|Lead|Chief|Head|Deputy|General|Executive)\s+)?"
)
_ROLE_DOMAIN_PREFIX = (
    r"(?:(?:Python|Backend|Frontend|Fullstack|Full-stack|Java|Go|Data|ML|AI|DevOps|QA|"
    r"System|Business|Product|Project|UX/UI|Digital|SMM|SEO|HR|Sales|Marketing|Finance|IT|PR)"
    r"(?:\s+|-)?)?"
)
_ROLE_ADJ_PREFIX = (
    r"(?:(?:Генеральный|Коммерческий|Финансовый|Технический|Исполнительный|"
    r"Операционный|Главный|Ведущий|Старший|Младший|Директор по|Начальник)\s+)?"
)
_ROLE_TITLES = (
    r"(?:инженер-программист|инженер-конструктор|инженер-технолог|инженер-проектировщик|"
    r"инженер-энергетик|инженер-сметчик|инженер-электроник|инженер-механик|"
    r"инженер-испытатель|инженер-наладчик|врач-специалист|"
    r"разработчик|программист|инженер|аналитик|тестировщик|менеджер|маркетолог|дизайнер|"
    r"специалист|директор|руководитель|начальник|заместитель|бухгалтер|юрист|экономист|"
    r"логист|закупщик|кадровик|рекрутер|секретарь|администратор|координатор|супервайзер|"
    r"мерчандайзер|товаровед|Developer|Engineer|Analyst|Manager|Designer|Scientist|"
    r"Architect|Director|Officer|Specialist|Consultant|Coordinator|Supervisor|"
    r"Administrator|Head)\b"
)
# Хвост должности: «… по продажам», «… отдела продаж», «… продукта», «… цеха».
# Раньше хвост начинался только с «по/отдела/направления», из-за чего
# «Руководитель продукта» превращался в «Руководитель», а «Менеджер проектов» — в
# «Менеджер». Теперь допускается ещё и существительное в родительном падеже.
_ROLE_TAIL_STOP = {
    # служебные слова и обрывающие фразы
    "с", "со", "в", "во", "на", "и", "или", "для", "от", "до", "о", "об", "при", "без",
    "из", "к", "ко", "у", "через", "после", "опыт", "опыта", "опытом", "работы", "работа",
    "работает", "стаж", "лет", "года", "год", "месяцев", "месяца",
    # города, компании, служебные блоки резюме
    "город", "москва", "москве", "санкт-петербург", "спб", "россия", "рф", "резюме",
    "вакансия", "компания", "компании", "ооо", "ао", "пао", "зао", "оао", "ип", "group",
    "llc", "ltd", "inc", "and", "with", "for", "of", "in", "at", "the", "experience",
    "years", "полная", "занятость", "зарплата", "ожидания", "требования", "обязанности",
    "цель", "ключевые", "навыки", "образование",
}
_ROLE_TAIL_WORD = (
    r"(?!(?:" + "|".join(sorted(_ROLE_TAIL_STOP, key=len, reverse=True)) + r")\b)"
    r"[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z\-]+"
    r"|"
    # «с клиентами», «с поставщиками», но не «с опытом» и не «с целью»
    r"с(?!\s+(?:опыт|цел|знан|использован|учёт|учет|обязанн|требован|зарплат|город|компан))"
)
# Оборачиваем в группу: иначе альтернатива «с» теряет обязательный пробел
_ROLE_TAIL_UNIT = "(?:" + _ROLE_TAIL_WORD + ")"
_ROLE_TAIL = (
    r"(?:"
    # «по продажам», «отдела продаж», «направления логистики», «по работе с клиентами»
    r"\s+(?:по|отдела|отделом|департамента|направления|группы|службы|филиала|подразделения)"
    r"(?:\s+" + _ROLE_TAIL_UNIT + r"){1,4}"
    r"|"
    # «продукта», «проектов», «цеха», «данных» — существительное после должности
    r"(?:\s+" + _ROLE_TAIL_UNIT + r"){1,2}"
    r")?"
)

# Аббревиатуры и англоязычные названия, которые словарь должностей не ловит
ROLE_ABBREVIATIONS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bCEO\b"), "CEO (Chief Executive Officer)"),
    (re.compile(r"\bCTO\b"), "CTO (Chief Technology Officer)"),
    (re.compile(r"\bCFO\b"), "CFO (Chief Financial Officer)"),
    (re.compile(r"\bCOO\b"), "COO (Chief Operating Officer)"),
    (re.compile(r"\bCMO\b"), "CMO (Chief Marketing Officer)"),
    (re.compile(r"\bCPO\b"), "CPO (Chief Product Officer)"),
    (re.compile(r"\bCIO\b"), "CIO (Chief Information Officer)"),
    (re.compile(r"\bCISO\b"), "CISO (Chief Information Security Officer)"),
    (re.compile(r"\bCHRO\b"), "CHRO (Chief HR Officer)"),
    (re.compile(r"\bCCO\b"), "CCO (Chief Commercial Officer)"),
    (re.compile(r"\bProduct Owner\b", re.I), "Product Owner"),
    (re.compile(r"\bProduct Manager\b", re.I), "Product Manager"),
    (re.compile(r"\bProject Manager\b", re.I), "Project Manager"),
    (re.compile(r"\bProgram Manager\b", re.I), "Program Manager"),
    (re.compile(r"\bScrum Master\b", re.I), "Scrum Master"),
    (re.compile(r"\bBusiness Analyst\b", re.I), "Business Analyst"),
    (re.compile(r"\bSystem Analyst\b", re.I), "System Analyst"),
    (re.compile(r"\bData Scientist\b", re.I), "Data Scientist"),
    (re.compile(r"\bData Engineer\b", re.I), "Data Engineer"),
    (re.compile(r"\bSolution Architect\b", re.I), "Solution Architect"),
    (re.compile(r"\bHead of\s+([A-Za-z][A-Za-z\s\-]{2,30})", re.I), "Head of"),
]


def _find_abbreviation(line: str) -> Optional[Tuple[int, str]]:
    """Ищет C-level аббревиатуру или англоязычную должность: (позиция, название)."""
    for pattern, title in ROLE_ABBREVIATIONS:
        match = pattern.search(line)
        if not match:
            continue
        if title == "Head of":
            tail = re.sub(r"\s+", " ", match.group(1)).strip(" .,;:-–—")
            return match.start(), f"Head of {tail}"[:80]
        return match.start(), title
    return None


def _match_abbreviation(line: str) -> str:
    """Распознаёт C-level аббревиатуры и англоязычные названия должностей."""
    hit = _find_abbreviation(line)
    return hit[1] if hit else ""


ROLE_TITLE_REGEX = re.compile(
    "("
    + _ROLE_ADJ_PREFIX
    + _ROLE_LEVEL_PREFIX
    + _ROLE_DOMAIN_PREFIX
    + _ROLE_TITLES
    + _ROLE_TAIL
    + ")",
    re.IGNORECASE,
)


# Слова, которые встречаются в должностях и навыках, но не в ФИО.
# Нужны, чтобы «Product Management», «Scrum Master», «Unit Economics» не принимались
# за имя человека и не выпадали из профиля резюме.
_NOT_A_NAME_TOKENS = {
    "manager", "management", "owner", "master", "analyst", "analytics", "engineer", "engineering",
    "developer", "designer", "director", "officer", "lead", "head", "specialist", "consultant",
    "consulting", "economist", "economics", "marketing", "sales", "product", "project", "program",
    "scrum", "data", "science", "scientist", "finance", "financial", "accounting", "audit",
    "hr", "qa", "devops", "python", "java", "sql", "crm", "erp", "sap", "tableau", "jira",
    "confluence", "roadmap", "unit", "growth", "digital", "brand", "marketplace", "logistics",
    "procurement", "customer", "success", "operations", "strategy", "business", "support",
}


def is_probable_person_name(line: str) -> bool:
    """Понимает, является ли строка ФИО (чтобы никогда не подставлять имя как должность/навык)."""
    raw = line.strip().strip(",.;:")
    if not raw or len(raw) > 60:
        return False

    low = raw.lower()
    # Явные маркеры ФИО
    if re.match(r"^(фио|ф\.и\.о\.?|имя|name)\s*[:\-–]", low):
        return True

    # Контакты, город, ссылки — не имя
    if any(token in low for token in CONTACT_TOKENS) or re.search(r"\d", raw):
        return False

    words = re.split(r"\s+", raw)
    if not 2 <= len(words) <= 4:
        return False
    if re.search(r"[.!?]", raw):
        return False

    # Каждое слово — с заглавной буквы и только буквами/дефисом
    title_words = 0
    for word in words:
        if not re.fullmatch(r"[A-ZА-ЯЁ][a-zа-яё]+(?:-[A-ZА-ЯЁ][a-zа-яё]+)?", word):
            return False
        title_words += 1
    if title_words < 2:
        return False

    # Должности латиницей («Product Owner», «Scrum Master») — не ФИО
    if _match_abbreviation(raw):
        return False

    # Имя не должно состоять из слов-должностей/разделов/навыков
    word_lows = {w.lower() for w in words}
    if word_lows & _NOT_A_NAME_TOKENS:
        return False
    if raw.lower() in KNOWN_SKILLS_MAP:
        return False
    if word_lows & SECTION_HEADINGS:
        return False
    if ROLE_TITLE_REGEX.search(raw):
        return False

    return True


def detect_candidate_name(resume_text: str) -> str:
    """Извлекает ФИО кандидата из начала резюме (для отображения в профиле)."""
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    for line in lines[:6]:
        if is_probable_person_name(line):
            return re.sub(r"\s+", " ", line.strip(" ,.;:"))
    # Заглавные ФИО отдельной строкой (ИВАНОВ ИВАН ИВАНОВИЧ)
    for line in lines[:6]:
        if re.fullmatch(r"[А-ЯЁ\s]{6,50}", line) and 2 <= len(line.split()) <= 4:
            return line.title()
    return ""


def _clean_role(raw: str) -> str:
    """Нормализует найденное название должности."""
    role = re.sub(r"\s+", " ", raw).strip(" .,;:-–—")
    role = re.sub(r"^(?:желаемая\s+)?(?:должность|позиция|вакансия|role|position)\s*[:\-–]\s*", "", role, flags=re.I)
    return role


def _pick_title_candidate(line: str) -> str:
    """Выбирает из строки самое раннее совпадение: словарь должностей или аббревиатуру.

    Нужно, чтобы «Senior Product Manager» не превращался в «Product Manager»,
    а «Технический директор (CTO)» — в «CTO».
    """
    candidates: List[Tuple[int, str]] = []
    abbreviation = _find_abbreviation(line)
    if abbreviation:
        candidates.append(abbreviation)
    match = ROLE_TITLE_REGEX.search(line)
    if match:
        found = _clean_role(match.group(1))
        if len(found) >= 4:
            candidates.append((match.start(), found))
    if not candidates:
        return ""
    return min(candidates, key=lambda item: item[0])[1]


def extract_role_from_resume(resume_text: str) -> str:
    """Определяет целевую должность из текста резюме.

    Порядок поиска:
    1. Явное указание «Должность / Желаемая должность / Позиция».
    2. Название профессии в первых строках (расширенный словарь: директор, руководитель, ...).
    3. Название профессии в заголовках блоков опыта работы.
    ФИО, контакты и служебные заголовки никогда не принимаются за должность.
    Возвращает пустую строку, если должность не найдена, — тогда бот попросит указать её вручную.
    """
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    if not lines:
        return ""

    explicit_pattern = ROLE_PATTERNS[0][0]

    # 1. Явное указание должности
    for line in lines[:20]:
        match = explicit_pattern.search(line)
        if match:
            role_candidate = _clean_role(match.group(1))
            if 2 <= len(role_candidate) <= 80 and not is_probable_person_name(role_candidate):
                return role_candidate

    # 2. Название профессии в начале резюме
    for line in lines[:15]:
        if is_probable_person_name(line):
            continue
        if line.lower().strip(" :") in SECTION_HEADINGS:
            continue
        best = _pick_title_candidate(line)
        if best:
            return best

    # 3. Название профессии в блоке опыта (например, «Директор по продажам»)
    for line in lines[:60]:
        if len(line) > 90 or is_probable_person_name(line):
            continue
        best = _pick_title_candidate(line)
        if best:
            return best

    return ""


def extract_skills_from_resume(resume_text: str) -> List[str]:
    """Извлекает ключевые навыки и технологии из текста резюме для поиска вакансий.

    1. Словарь известных навыков (IT + бизнес/менеджмент/офис).
    2. Блок «Навыки / Skills / Стек» — как в строку, так и многострочный список.
    3. Технологические токены (ERP, OTB, P&L, SAP, 1C и т.п.).
    ФИО кандидата в навыки никогда не попадает.
    """
    detected_skills: List[str] = []
    candidate_name = detect_candidate_name(resume_text)
    name_tokens = {tok.lower() for tok in re.split(r"\s+", candidate_name) if tok}

    def _add(value: str) -> None:
        cleaned = value.strip(" .,;:•-–—|\t")
        if not 2 <= len(cleaned) <= 40:
            return
        # «1С» (кириллица) и «1C» (латиница) — один и тот же навык
        if re.fullmatch(r"1[сc]", cleaned, re.I):
            cleaned = "1C"
        low = cleaned.lower()
        if low in name_tokens or is_probable_person_name(cleaned):
            return
        if low in {s.lower() for s in detected_skills}:
            return
        detected_skills.append(cleaned)

    text_lower = resume_text.lower()

    # 1. Словарь навыков
    for key, canonical_name in KNOWN_SKILLS_MAP.items():
        pattern = r"(?:^|[\s,;/()\[\•\-])" + re.escape(key) + r"(?:$|[\s,;/()\[\.!\?])"
        if re.search(pattern, text_lower):
            _add(canonical_name)

    # 2. Блок навыков: строка «Навыки: Python, SQL» и/или многострочный список
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    heading_re = re.compile(
        r"^(навыки|ключевые навыки|профессиональные навыки|компетенции|стек|технологии|"
        r"skills|tech stack|competencies)\s*[:\-–]?\s*(.*)$",
        re.I,
    )
    for idx, line in enumerate(lines):
        match = heading_re.match(line)
        if not match:
            continue
        inline = match.group(2).strip()
        if inline:
            for item in re.split(r"[,;|•·]+", inline):
                if item.strip():
                    _add(item)
        # Продолжение списка в следующих строках (до пустой строки/нового заголовка)
        for follow in lines[idx + 1: idx + 12]:
            follow_low = follow.lower().strip(" :")
            if follow_low in SECTION_HEADINGS:
                break
            if re.match(r"^(опыт|образование|проекты|работа|experience|education)\b", follow_low):
                break
            items = re.split(r"[,;|•·]+", follow.lstrip("•-–—\t "))
            for item in items:
                if item.strip():
                    _add(item)

    # 3. Технологические токены в верхнем регистре (ERP, OTB, P&L, BI, SAP, 1C, KPI)
    for token in re.findall(r"\b(?:[A-Z]{2,6}(?:/[A-Z]{2,6})?|P&L|1C|1С)\b", resume_text):
        _add(token)

    return detected_skills[:20]


def build_resume_profile(resume_text: str) -> Dict[str, Any]:
    """Собирает профиль кандидата: ФИО, целевая должность и ключевые навыки.

    Используется при загрузке резюме и при ручной корректировке профиля.
    """
    return {
        "candidate_name": detect_candidate_name(resume_text),
        "role": extract_role_from_resume(resume_text),
        "skills": extract_skills_from_resume(resume_text),
    }


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

    # ФИО никогда не подставляется вместо должности: если должность не найдена,
    # сохраняем пустую строку и просим пользователя указать её вручную (/set_role).
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


# «Обрезанные» должности: сохранилось только общее слово без уточнения.
GENERIC_ROLE_WORDS = {
    "руководитель", "менеджер", "директор", "специалист", "инженер", "аналитик",
    "начальник", "заместитель", "разработчик", "программист", "консультант",
    "администратор", "координатор", "бухгалтер", "маркетолог", "дизайнер", "логист",
}


def is_truncated_role(value: str) -> bool:
    """Проверяет, что должность сохранилась обрезанной («Руководитель» вместо «Руководитель продукта»)."""
    return (value or "").strip().lower() in GENERIC_ROLE_WORDS


def repair_profile_values(
    role: str, skills: List[str], raw_text: str
) -> Tuple[str, List[str], bool]:
    """Чинит «испорченный» профиль, где вместо должности/навыков сохранилось ФИО.

    Возвращает (role, skills, was_repaired). Если значения похожи на ФИО
    кандидата, они заменяются на результат повторного извлечения из текста резюме.
    """
    name = detect_candidate_name(raw_text)
    name_tokens = {tok.lower() for tok in re.split(r"\s+", name) if tok}

    def _is_bad_role(value: str) -> bool:
        value = (value or "").strip()
        if not value:
            return False
        low = value.lower()
        return bool(
            is_probable_person_name(value)
            or (name and low == name.lower())
            or (len(name_tokens) >= 2 and set(re.split(r"\s+", low)) == name_tokens)
        )

    def _is_bad_skill(value: str) -> bool:
        low = (value or "").strip().lower()
        if not low:
            return True
        if low in name_tokens:
            return True
        return is_probable_person_name(value)

    bad_role = _is_bad_role(role)
    bad_skills = bool(skills) and all(_is_bad_skill(skill) for skill in skills)

    # Должность вида «Руководитель» без уточнения — перечитываем резюме целиком
    if not bad_role and is_truncated_role(role):
        fuller_role = extract_role_from_resume(raw_text)
        if len(fuller_role) > len(role):
            return fuller_role, skills, True

    if not bad_role and not bad_skills:
        return role, skills, False

    repaired_role = "" if bad_role else role
    repaired_skills = [] if bad_skills else [s for s in skills if not _is_bad_skill(s)]

    if bad_role:
        repaired_role = extract_role_from_resume(raw_text)
    if bad_skills:
        repaired_skills = extract_skills_from_resume(raw_text)

    return repaired_role, repaired_skills, True


async def repair_invalid_resume_profiles(db: Database) -> int:
    """Проходит по всем резюме в БД и исправляет профили, где вместо данных сохранилось ФИО.

    Вызывается при старте бота, поэтому «сломанные» профили чинятся автоматически
    (пользователю достаточно перезапустить бота или отправить /reset_profile).
    """
    repaired_count = 0
    try:
        resumes = await db.list_all_resumes()
    except Exception:  # noqa: BLE001
        return 0

    for record in resumes:
        # Профиль, который человек поправил кнопками «Изменить должность/навыки»,
        # автоматика не перезаписывает — иначе правка «слетит» после рестарта.
        if record.get("profile_edited_manually"):
            continue

        role = record.get("extracted_role") or ""
        skills = record.get("extracted_skills") or []
        new_role, new_skills, was_repaired = repair_profile_values(
            role=role, skills=skills, raw_text=record.get("raw_text") or ""
        )
        if was_repaired:
            await db.update_resume_profile(
                user_id=record["user_id"], role=new_role, skills=new_skills
            )
            repaired_count += 1
    return repaired_count
