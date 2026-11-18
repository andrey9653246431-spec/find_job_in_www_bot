"""Каталог проверенных ресурсов для поиска работы в России и СНГ.

Модуль хранит «белый список» источников, которые бот показывает пользователю:
1. Telegram-каналы с вакансиями (`TELEGRAM_CHANNELS`).
2. Сайты-агрегаторы и job-борды (`AGGREGATORS`).
3. Компании с группировкой по отраслям (`COMPANIES`) — официальный сайт + ссылка
   на вакансии (официальная карьерная страница, если она подтверждена, иначе —
   поиск вакансий компании на hh.ru).

Принцип «не выдумывать ссылки»:
- у каждой записи есть флаг `verified` (проверено автоматической проверкой доступности);
- для компаний без подтверждённой карьерной страницы ссылка на вакансии строится
  по документированному шаблону поиска hh.ru, а не угадывается;
- ко всем ответам добавляется дисклеймер `LINKS_DISCLAIMER`.
"""
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote


# Дисклеймер, который обязан присутствовать в каждом ответе бота (по требованиям ТЗ)
LINKS_DISCLAIMER = (
    "Ссылки могут меняться. Актуальность вакансий проверяйте на официальных сайтах компаний, "
    "в Telegram-каналах или на агрегаторах (hh.ru, hirify.me)."
)

# Предупреждение о непроверенной ссылке
LINK_WARNING = "Проверьте актуальность ссылки: точный адрес может быть изменён."

# Инструкция по поиску узких специализаций в Telegram
TELEGRAM_SEARCH_HINT = (
    "Ищете узкую специализацию (например, «вакансии для 1С-аналитиков» или «работа в конкретном городе»)? "
    "Используйте поиск по ключевым словам внутри самого Telegram: строка поиска → «Вакансии <профессия>» "
    "или «<профессия> <город>» → вкладка «Каналы». Так вы найдёте живые нишевые каналы, "
    "которых нет ни в одном каталоге."
)

# Лимиты формирования ответа
MAX_ITEMS_PER_BLOCK = 20          # больше 15–20 позиций — разбиваем на смысловые блоки
MAX_COMPANIES_PER_REQUEST = 50    # при запросе > 50 компаний предупреждаем о нескольких сообщениях
MESSAGE_CHUNK_SIZE = 3800         # безопасный размер сообщения Telegram


def hh_search_url(query: str) -> str:
    """Ссылка на поиск вакансий hh.ru по произвольному запросу (документированный параметр `text`)."""
    return f"https://hh.ru/search/vacancy?text={quote(query, safe='')}"


def hh_company_vacancies_url(company_name: str) -> str:
    """Ссылка на вакансии компании в поиске hh.ru (используется, если карьерная страница не подтверждена)."""
    return f"https://hh.ru/search/vacancy?text={quote(company_name, safe='')}"


# =============================================================================
# 1. САЙТЫ-АГРЕГАТОРЫ И JOB-БОРДЫ
# =============================================================================
AGGREGATORS: List[Dict[str, Any]] = [
    # --- Международные и remote-борды ---
    {
        "name": "Indeed",
        "url": "https://www.indeed.com/",
        "description": "Крупнейший мировой агрегатор вакансий (США, ЕС, Азия). Закрыт для автопарсинга — открывайте по ссылке.",
        "topics": ("international", "remote", "it", "finance", "office", "any"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "Glassdoor",
        "url": "https://www.glassdoor.com/",
        "description": "Вакансии + отзывы сотрудников и зарплаты компаний (США/ЕС). Ручной поиск.",
        "topics": ("international", "remote", "finance", "office", "any"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "ZipRecruiter (IE)",
        "url": "https://www.ziprecruiter.ie/",
        "description": "Ирландский/европейский рынок: вакансии с визовой поддержкой и релокацией. Ручной поиск.",
        "topics": ("international", "relocation", "it", "any"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "CareerBuilder",
        "url": "https://www.careerbuilder.com/",
        "description": "Американский job-борд, много менеджерских и корпоративных позиций. Ручной поиск.",
        "topics": ("international", "finance", "office", "any"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "WantApply",
        "url": "https://wantapply.com/",
        "description": "Агрегатор зарубежных вакансий с релокацией и визовой поддержкой. Ручной поиск.",
        "topics": ("international", "relocation", "any"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "We Work Remotely",
        "url": "https://weworkremotely.com/",
        "description": "Крупнейший remote-борд: IT, продукт, дизайн, маркетинг. Бот читает RSS-ленту автоматически.",
        "topics": ("international", "remote", "it", "product", "design"),
        "verified": True,
    },
    {
        "name": "RemoteOK",
        "url": "https://remoteok.com/",
        "description": "Биржа удалённых вакансий с открытым JSON API — бот забирает вакансии автоматически.",
        "topics": ("international", "remote", "it", "product"),
        "verified": True,
    },
    {
        "name": "Remote.co",
        "url": "https://remote.co/",
        "description": "Удалённые вакансии по категориям (поддержка, продажи, разработка). Ручной поиск.",
        "topics": ("international", "remote", "any"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "Jobspresso",
        "url": "https://jobspresso.co/",
        "description": "Курируемые remote-вакансии; бот читает RSS-ленту автоматически.",
        "topics": ("international", "remote", "it", "any"),
        "verified": True,
    },
    {
        "name": "hh.ru (HeadHunter)",
        "url": "https://hh.ru",
        "description": "Крупнейшая база вакансий в РФ: фильтры по отрасли, зарплате и опыту, открытый API для бота.",
        "topics": ("it", "finance", "retail", "office", "any"),
        "verified": True,
    },
    {
        "name": "Хабр Карьера",
        "url": "https://career.habr.com",
        "description": "Вакансии для IT- и диджитал-специалистов с прозрачными зарплатными вилками.",
        "topics": ("it", "product", "design"),
        "verified": True,
    },
    {
        "name": "Работа.ру",
        "url": "https://www.rabota.ru",
        "description": "Вакансии по всей России: много позиций в ритейле, сервисе и на производстве.",
        "topics": ("retail", "service", "any"),
        "verified": True,
    },
    {
        "name": "Зарплата.ру",
        "url": "https://www.zarplata.ru",
        "description": "Региональные вакансии с удобным поиском по городу и уровню дохода.",
        "topics": ("any", "regions"),
        "verified": True,
    },
    {
        "name": "Город Работ",
        "url": "https://gorodrabot.ru",
        "description": "Агрегатор, который собирает вакансии с job-сайтов и центров занятости в одном поиске.",
        "topics": ("any", "regions"),
        "verified": False,
    },
    {
        "name": "SuperJob",
        "url": "https://www.superjob.ru",
        "description": "Крупный job-борд с сильными фильтрами по отраслям и подписками на вакансии.",
        "topics": ("any", "office"),
        "verified": True,
    },
    {
        "name": "hirify.me",
        "url": "https://hirify.me",
        "description": "Нишевый агрегатор вакансий IT и диджитал с акцентом на продуктовые команды.",
        "topics": ("it", "digital"),
        "verified": True,
    },
    {
        "name": "getmatch",
        "url": "https://getmatch.ru/vacancies",
        "description": "IT-вакансии с указанными вилками; есть бот для персонального мэтчинга.",
        "topics": ("it",),
        "verified": True,
    },
    {
        "name": "GeekJob",
        "url": "https://geekjob.ru",
        "description": "IT-вакансии, включая удалёнку и релокацию, с фильтром по стеку.",
        "topics": ("it", "remote"),
        "verified": True,
    },
    {
        "name": "Работа России (Трудвсем)",
        "url": "https://trudvsem.ru",
        "description": "Государственный портал вакансий и центров занятости — полезен для регионов и льготных категорий.",
        "topics": ("any", "regions", "state"),
        "verified": False,
    },
    {
        "name": "LinkedIn Jobs",
        "url": "https://www.linkedin.com/jobs",
        "description": "Международный рынок и вакансии зарубежных компаний (доступ из РФ ограничен).",
        "topics": ("international",),
        "verified": True,
    },
]


# =============================================================================
# 2. TELEGRAM-КАНАЛЫ С ВАКАНСИЯМИ (проверены на публичное превью)
# =============================================================================
TELEGRAM_CHANNELS: List[Dict[str, Any]] = [
    {
        "name": "Хабр Карьера",
        "username": "habr_career",
        "topic": "IT",
        "description": "Вакансии и обсуждение карьеры в IT от редакции Хабра.",
        "verified": True,
    },
    {
        "name": "IT Job x IT Vacancies",
        "username": "job_it_ru",
        "topic": "IT",
        "description": "Подборка IT-вакансий: разработка, аналитика, DevOps, удалёнка.",
        "verified": True,
    },
    {
        "name": "HR | Вакансии 🦊",
        "username": "vacancies_it",
        "topic": "IT / HR",
        "description": "Вакансии в IT и подборка HR-позиций от кадровых агентств.",
        "verified": True,
    },
    {
        "name": "Remote Jobs | Remote Work",
        "username": "remote_work_jobs",
        "topic": "Удалённая работа",
        "description": "Удалённые вакансии разных профессий, в том числе англоязычные.",
        "verified": True,
    },
    {
        "name": "Remote IT Jobs",
        "username": "remote_it_jobs",
        "topic": "IT / Remote",
        "description": "Только удалённые IT-вакансии — удобно для поиска из любого города.",
        "verified": True,
    },
    {
        "name": "Game Development Jobs",
        "username": "devjobs",
        "topic": "GameDev",
        "description": "Вакансии в игровой индустрии: программисты, художники, геймдизайнеры.",
        "verified": True,
    },
    {
        "name": "Вакансии в IT",
        "username": "data_jobs_ru",
        "topic": "IT / Данные",
        "description": "Свежие IT-вакансии, включая аналитику данных и инженерию.",
        "verified": True,
    },
    {
        "name": "marketing jobs",
        "username": "marketing_jobs",
        "topic": "Маркетинг",
        "description": "Вакансии для маркетологов: performance, бренд, продуктовая аналитика.",
        "verified": True,
    },
    # --- HR, карьера и подбор (проверено на публичное превью) ---
    {
        "name": "МарЧар | Маркетинг в HR",
        "username": "marhrru",
        "topic": "HR / Маркетинг",
        "description": "Маркетинг в HR: employer brand, коммуникации, кейсы подбора.",
        "verified": True,
    },
    {
        "name": "HR мама 🍋",
        "username": "HRmother",
        "topic": "HR",
        "description": "HR-практика для мам и не только: подбор, адаптация, карьера в HR.",
        "verified": True,
    },
    {
        "name": "Кадровый голод",
        "username": "kadrovik_krd",
        "topic": "HR / Кадры",
        "description": "Кадровое делопроизводство, ТК РФ и практика кадровика.",
        "verified": True,
    },
    {
        "name": "Аптуми (up to me)",
        "username": "uptume",
        "topic": "Карьера",
        "description": "Карьерное развитие, самоопределение и поиск работы.",
        "verified": True,
    },
    {
        "name": "Русский HR",
        "username": "rus_hr",
        "topic": "HR",
        "description": "Новости и практика российского HR-рынка.",
        "verified": True,
    },
    {
        "name": "Всё, я увольняюсь!",
        "username": "uvolnyaus",
        "topic": "Карьера",
        "description": "Увольнение, смена работы и карьерные истории без прикрас.",
        "verified": True,
    },
    {
        "name": "АККСиомы Карьеры",
        "username": "akks_career",
        "topic": "Карьера",
        "description": "Карьерные советы, разборы вакансий и резюме.",
        "verified": True,
    },
    {
        "name": "Вакансии от Хрипченко Ани",
        "username": "rudakovahr",
        "topic": "HR / Вакансии",
        "description": "Подборка актуальных HR- и офисных вакансий от рекрутера.",
        "verified": True,
    },
    {
        "name": "Янг Групп",
        "username": "you_social",
        "topic": "Вакансии",
        "description": "Вакансии и карьерные возможности для молодых специалистов.",
        "verified": True,
    },
    {
        "name": "Лучшие вакансии",
        "username": "vacanciesbest",
        "topic": "Вакансии",
        "description": "Отобранные вакансии по разным функциям и уровням.",
        "verified": True,
    },
    {
        "name": "Топовые вакансии | Петр Липов",
        "username": "jobinspb",
        "topic": "Вакансии / Санкт-Петербург",
        "description": "Вакансии Санкт-Петербурга и управление карьерой.",
        "verified": True,
    },
    {
        "name": "fuck_the_frameworks",
        "username": "fuck_the_frameworks",
        "topic": "Карьера / Рынок труда",
        "description": (
            "Неудобная правда про рынок труда в России: поиск работы, HR, вакансии, "
            "автоотказы. Авторский канал Александра Устинова."
        ),
        "verified": True,
    },
    {
        "name": "Неустойчивое развитие",
        "username": "nongreta",
        "topic": "ESG / Устойчивое развитие",
        "description": "Экология, ESG и устойчивое развитие — вакансии и повестка.",
        "verified": True,
    },
]


# =============================================================================
# 3. КОМПАНИИ ПО ОТРАСЛЯМ (официальный сайт + вакансии)
#    `career_url` указывается только там, где карьерная страница подтверждена;
#    иначе вакансии ищутся на hh.ru по названию компании.
# =============================================================================
COMPANIES: List[Dict[str, Any]] = [
    # --- IT и Телеком ---
    {"name": "Яндекс", "industry": "IT и Телеком", "site": "https://ya.ru", "career_url": "https://yandex.ru/jobs",
     "description": "Поиск, карты, реклама, облако — вакансии для инженеров, аналитиков и продактов."},
    {"name": "VK", "industry": "IT и Телеком", "site": "https://vk.com", "career_url": "https://team.vk.company",
     "description": "Соцсети и сервисы экосистемы VK; отдельный карьерный портал с офисами по РФ."},
    {"name": "МТС", "industry": "IT и Телеком", "site": "https://www.mts.ru", "career_url": "https://job.mts.ru",
     "description": "Телеком и digital-экосистема: от сети и IT до медиа и финтеха."},
    {"name": "МегаФон", "industry": "IT и Телеком", "site": "https://www.megafon.ru", "career_url": "https://job.megafon.ru",
     "description": "Телеком-оператор с сильными направлениями по данным и цифровым продуктам."},
    {"name": "Авито", "industry": "IT и Телеком", "site": "https://www.avito.ru", "career_url": None,
     "description": "Классифайд-платформа: продуктовые, инженерные и коммерческие роли."},
    {"name": "Ростелеком", "industry": "IT и Телеком", "site": "https://www.rt.ru", "career_url": None,
     "description": "Национальный оператор связи и ИТ-инфраструктуры, вакансии по всей стране."},

    # --- Банки и финансы ---
    {"name": "Сбер", "industry": "Банки и финансы", "site": "https://www.sber.ru", "career_url": None,
     "description": "Крупнейший банк РФ с огромным блоком технологических и рисковых ролей."},
    {"name": "ВТБ", "industry": "Банки и финансы", "site": "https://www.vtb.ru", "career_url": None,
     "description": "Госбанк с широкой сетью и корпоративным, розничным и инвестиционным блоками."},
    {"name": "Альфа-Банк", "industry": "Банки и финансы", "site": "https://alfabank.ru", "career_url": None,
     "description": "Частный банк с сильной продуктовой и digital-командой."},
    {"name": "Т-Банк (Тинькофф)", "industry": "Банки и финансы", "site": "https://www.tbank.ru", "career_url": None,
     "description": "Онлайн-банк и экосистема: инженерия, аналитика, продуктовый маркетинг."},
    {"name": "Газпромбанк", "industry": "Банки и финансы", "site": "https://www.gazprombank.ru", "career_url": None,
     "description": "Универсальный банк с корпоративным и инвестиционным направлениями."},

    # --- Ритейл и e-commerce ---
    {"name": "X5 Group (Пятёрочка, Перекрёсток)", "industry": "Ритейл и e-commerce", "site": "https://www.x5.ru",
     "career_url": "https://www.x5.ru/career",
     "description": "Крупнейший продуктовый ритейлер: магазины, логистика, офисные функции."},
    {"name": "Магнит", "industry": "Ритейл и e-commerce", "site": "https://magnit.ru", "career_url": None,
     "description": "Сеть магазинов и распределительных центров по всей России."},
    {"name": "Ozon", "industry": "Ритейл и e-commerce", "site": "https://www.ozon.ru", "career_url": "https://job.ozon.ru",
     "description": "Маркетплейс: логистика, категорийный менеджмент, IT и аналитика."},
    {"name": "Wildberries", "industry": "Ритейл и e-commerce", "site": "https://www.wildberries.ru", "career_url": None,
     "description": "Маркетплейс с большим объёмом вакансий в логистике и операциях."},
    {"name": "Лента", "industry": "Ритейл и e-commerce", "site": "https://lenta.com", "career_url": None,
     "description": "Сеть гипермаркетов: коммерческие, операционные и логистические роли."},
    {"name": "М.Видео-Эльдорадо", "industry": "Ритейл и e-commerce", "site": "https://www.mvideo.ru", "career_url": None,
     "description": "Техноритейл с развитым e-commerce и контакт-центрами."},

    # --- Промышленность, энергетика, добыча ---
    {"name": "Газпром", "industry": "Промышленность и энергетика", "site": "https://www.gazprom.ru", "career_url": None,
     "description": "Газовая монополия: производство, транспорт газа, инженерные и офисные функции."},
    {"name": "Роснефть", "industry": "Промышленность и энергетика", "site": "https://www.rosneft.ru", "career_url": None,
     "description": "Нефтегазовая компания с вакансиями в добыче, переработке и сбыте."},
    {"name": "Лукойл", "industry": "Промышленность и энергетика", "site": "https://lukoil.ru", "career_url": None,
     "description": "Вертикально интегрированная нефтяная компания, включая розничную сеть АЗС."},
    {"name": "Норникель", "industry": "Промышленность и энергетика", "site": "https://www.nornickel.ru", "career_url": None,
     "description": "Горно-металлургическая компания: производство, инженерия, экология."},
    {"name": "Росатом", "industry": "Промышленность и энергетика", "site": "https://www.rosatom.ru", "career_url": None,
     "description": "Госкорпорация с вакансиями в энергетике, машиностроении и ИТ."},
    {"name": "Северсталь", "industry": "Промышленность и энергетика", "site": "https://severstal.com", "career_url": None,
     "description": "Металлургия и горнодобыча, программы для инженеров и молодых специалистов."},

    # --- Логистика и транспорт ---
    {"name": "РЖД", "industry": "Логистика и транспорт", "site": "https://www.rzd.ru", "career_url": None,
     "description": "Железнодорожный холдинг: эксплуатация, инженерия, управление перевозками."},
    {"name": "Почта России", "industry": "Логистика и транспорт", "site": "https://www.pochta.ru", "career_url": None,
     "description": "Почтово-логистическая сеть с вакансиями по всей стране."},
    {"name": "СДЭК", "industry": "Логистика и транспорт", "site": "https://www.cdek.ru", "career_url": None,
     "description": "Логистический оператор e-commerce: сортировка, курьерская доставка, офис."},

    # --- FMCG, фарма, HoReCa ---
    {"name": "Балтика", "industry": "FMCG и производство", "site": "https://baltika.ru", "career_url": None,
     "description": "Пивоваренная компания: производство, supply chain, коммерция."},
    {"name": "Черкизово", "industry": "FMCG и производство", "site": "https://www.cherkizovo.com", "career_url": None,
     "description": "Агропромышленный холдинг: производство, качество, логистика."},
    {"name": "Р-Фарм", "industry": "Фарма и медицина", "site": "https://r-pharm.com", "career_url": None,
     "description": "Фармацевтическая группа: R&D, производство, клинические исследования."},
    {"name": "ИНВИТРО", "industry": "Фарма и медицина", "site": "https://www.invitro.ru", "career_url": None,
     "description": "Сеть медицинских лабораторий: врачи, лаборанты, менеджмент клиник."},
]


def _verified_tg_url(username: str) -> str:
    """Канонический адрес Telegram-канала по его username."""
    return f"https://t.me/{username}"


def _company_vacancies_url(company: Dict[str, Any]) -> str:
    """Ссылка на вакансии компании: подтверждённая карьерная страница или поиск на hh.ru."""
    return company.get("career_url") or hh_company_vacancies_url(company["name"])


def get_telegram_channels(topics: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Возвращает Telegram-каналы с вакансиями (опционально — отфильтрованные по тематике)."""
    if not topics:
        return list(TELEGRAM_CHANNELS)
    lowered = [t.lower() for t in topics]
    selected = [
        channel
        for channel in TELEGRAM_CHANNELS
        if any(topic in channel["topic"].lower() for topic in lowered)
    ]
    return selected or list(TELEGRAM_CHANNELS)


def get_aggregators(topics: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Возвращает job-борды и агрегаторы (опционально — отфильтрованные по тематике)."""
    if not topics:
        return list(AGGREGATORS)
    lowered = [t.lower() for t in topics]
    selected = [
        aggregator
        for aggregator in AGGREGATORS
        if any(
            topic in (t.lower() for t in aggregator["topics"]) for topic in lowered
        )
        or "any" in aggregator["topics"]
    ]
    return selected or list(AGGREGATORS)


def get_companies(industry: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Возвращает компании (опционально — по отрасли и с ограничением количества)."""
    selected = list(COMPANIES)
    if industry:
        industry_low = industry.lower()
        tokens = [t for t in re.split(r"[^0-9a-zа-яё-]+", industry_low) if len(t) > 2]
        selected = [
            company
            for company in selected
            if industry_low in company["industry"].lower()
            or (tokens and all(token in company["industry"].lower() for token in tokens))
        ] or list(COMPANIES)
    if limit:
        selected = selected[:limit]
    return selected


def get_industries() -> List[str]:
    """Список отраслей в порядке появления (для группировки ответа по блокам)."""
    ordered: List[str] = []
    for company in COMPANIES:
        if company["industry"] not in ordered:
            ordered.append(company["industry"])
    return ordered
