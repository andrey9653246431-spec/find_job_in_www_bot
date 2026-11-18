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
    # --- Третья подборка: российские борды и фриланс-площадки (проверено 18.11.2026) ---
    {
        "name": "Буду",
        "url": "https://budu.jobs/",
        "description": "Джоб-борд с вакансиями компаний и стажировками; бот читает HTML-ленту.",
        "topics": ("any", "office", "it"),
        "verified": True,
    },
    {
        "name": "Remote Job",
        "url": "https://remote-job.ru/",
        "description": "Удалённые вакансии по России и СНГ; бот читает HTML-ленту.",
        "topics": ("remote", "any", "it", "marketing"),
        "verified": True,
    },
    {
        "name": "Facancy",
        "url": "https://facancy.ru/",
        "description": "Агрегатор вакансий с фильтрами по городу и профессии. Ручной поиск.",
        "topics": ("any", "office"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "Changellenge",
        "url": "https://changellenge.com/",
        "description": "Карьерная платформа для студентов и молодых специалистов (кейсы, стажировки). Ручной поиск.",
        "topics": ("any", "graduate", "office"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "InGame Job",
        "url": "https://ingamejob.com/",
        "description": "Вакансии в геймдеве: разработка, арт, геймдизайн, продакт. Ручной поиск.",
        "topics": ("it", "gamedev", "design", "any"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "Careerist",
        "url": "https://careerist.ru/",
        "description": "Карьерный сервис: вакансии и помощь с трудоустройством. Ручной поиск.",
        "topics": ("any", "office"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "Wellfound",
        "url": "https://wellfound.com/jobs",
        "description": "Вакансии стартапов (ex-AngelList), в том числе с релокацией. Ручной поиск.",
        "topics": ("international", "it", "relocation", "any"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "Jooble",
        "url": "https://ru.jooble.org/",
        "description": "Агрегатор вакансий из множества источников. Выдача рендерится JavaScript-ом — ручной поиск.",
        "topics": ("any", "office", "blue_collar"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "Avito Работа",
        "url": "https://www.avito.ru/rossiya/vakansii",
        "description": "Массовый рынок труда: от линейного персонала до офиса. Защита от ботов — ручной поиск.",
        "topics": ("any", "blue_collar", "office", "horeca"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "YouDo",
        "url": "https://youdo.com/",
        "description": "Площадка услуг и разовых задач (фриланс, подработка). Ручной поиск.",
        "topics": ("freelance", "any"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "Kwork",
        "url": "https://kwork.ru/",
        "description": "Фриланс-биржа кворков: услуги и заказы по фиксированной цене. Ручной поиск.",
        "topics": ("freelance", "design", "marketing", "it"),
        "verified": True,
        "manual_search": True,
    },
    {
        "name": "FL.ru",
        "url": "https://www.fl.ru/",
        "description": "Крупнейшая русскоязычная фриланс-биржа: проекты и заказы. Ручной поиск.",
        "topics": ("freelance", "it", "design", "marketing"),
        "verified": True,
        "manual_search": True,
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
    # --- Вторая подборка: HR-сообщества, executive-вакансии, обучение ---
    {
        "name": "Ирена_Иванова_official",
        "username": "irenaivanova_official",
        "topic": "Карьера / HR",
        "description": "Авторский канал Ирены Ивановой: рынок труда, карьера, инсайды от хантера.",
        "verified": True,
    },
    {
        "name": "Наталья Ларина | Карьера по своим правилам",
        "username": "larina_career",
        "topic": "Карьера",
        "description": "Карьера по своим правилам: поиск работы, офферы, карьерные стратегии.",
        "verified": True,
    },
    {
        "name": "Я Топ",
        "username": "i_top_groups",
        "topic": "Вакансии / Топ-менеджмент",
        "description": "Вакансии и резюме для топ-менеджеров, руководителей и управленцев.",
        "verified": True,
    },
    {
        "name": "#ПерезагрузкаКарьеры",
        "username": "hrexpert63",
        "topic": "Карьера / HR",
        "description": "Эксперт по обе стороны найма: карьера, HR-практика, разборы.",
        "verified": True,
    },
    {
        "name": "Abrashitova Natalya | Карьерное развитие",
        "username": "hrhack_career",
        "topic": "Карьера / HR",
        "description": "Наталья Абрашитова (HRD 15+ лет): вакансии, HR-советы, карьерные разборы.",
        "verified": True,
    },
    {
        "name": "Живое обучение",
        "username": "prolearning",
        "topic": "Обучение / L&D",
        "description": "Елена Тихомирова о том, как учатся взрослые и как строить корпоративное обучение.",
        "verified": True,
    },
    {
        "name": "КАРЬЕРА ЛИДЕРА | Вакансии для руководителей",
        "username": "work_for_top",
        "topic": "Вакансии / Топ-менеджмент",
        "description": "Вакансии для руководителей и топов: CEO, директора направлений.",
        "verified": True,
    },
    {
        "name": "Exec Select | Топ вакансии для руководителей",
        "username": "execselect",
        "topic": "Вакансии / Топ-менеджмент",
        "description": "Отборные executive-вакансии для руководителей высшего звена.",
        "verified": True,
    },
    {
        "name": "Вакансии от CRC",
        "username": "vacancyCRC",
        "topic": "Вакансии / Топ-менеджмент",
        "description": "Career Review Center: вакансии для middle/top-менеджеров и HR-консалтинг.",
        "verified": True,
    },
    {
        "name": "Вакансии с релокацией",
        "username": "relocation_vacancies",
        "topic": "Вакансии / Релокация",
        "description": "Релокация: зарубежные и релокационные вакансии с визовой поддержкой.",
        "verified": True,
    },
    {
        "name": "Hire ProProduct - Продуктовые вакансии",
        "username": "hireproproduct",
        "topic": "Вакансии / Продукт",
        "description": "Вакансии для продакт- и проджект-менеджеров, аналитиков, дизайнеров.",
        "verified": True,
    },
    {
        "name": "Work For TOP Вакансии для руководителей",
        "username": "workfortop",
        "topic": "Вакансии / Топ-менеджмент",
        "description": "Вакансии для руководителей: топ-позиции и управленческие роли.",
        "verified": True,
    },
    {
        "name": "Fintech - Jobs",
        "username": "fintech_jobs",
        "topic": "Вакансии / Финтех",
        "description": "Вакансии в финтехе, банках, крипте и платёжных сервисах.",
        "verified": True,
    },
    {
        "name": "Talent Hunters",
        "username": "talent_hunters",
        "topic": "HR / Рекрутинг",
        "description": "Лана Катаева (ex-AVRIO): тренды рынка труда, хантинг, HR-мероприятия.",
        "verified": True,
    },
    {
        "name": "IT HR тусовка от ХК",
        "username": "ithr_tusovka",
        "topic": "HR / IT",
        "description": "Хабр Карьера: найм в IT, тренды, исследования, мемы для эйчаров.",
        "verified": True,
    },
    {
        "name": "Рекомендательный рекрутинг",
        "username": "recommend_recruit",
        "topic": "HR / Рекрутинг",
        "description": "Рекрутинг по рекомендациям: заявки, кандидаты, вознаграждение за рекомендацию.",
        "verified": True,
    },
    {
        "name": "Смелый рекрутинг",
        "username": "ithunterio",
        "topic": "HR / Рекрутинг",
        "description": "Смелый рекрутинг: нестандартные подходы к найму и сорсингу.",
        "verified": True,
    },
    {
        "name": "TrendHR",
        "username": "trend_hr",
        "topic": "HR",
        "description": "HR-тренды, инструменты и практики найма.",
        "verified": True,
    },
    {
        "name": "БОЛЬШЕ чем HR",
        "username": "more_than_hr",
        "topic": "HR",
        "description": "Галина Друбецкая: HR шире найма — культура, коммуникации, люди.",
        "verified": True,
    },
    {
        "name": "TOP LEVEL JOB [топ вакансии для руководителей]",
        "username": "toplevel_job",
        "topic": "Вакансии / Топ-менеджмент",
        "description": "Вакансии уровня CEO/CEO-1 с прямыми контактами работодателей.",
        "verified": True,
    },
    {
        "name": "Senior Помідор",
        "username": "tomato1000",
        "topic": "Вакансии / IT",
        "description": "IT-вакансии с зарплатой от $1000 (UA/remote). ⚠️ веб-превью закрыто — ручной просмотр.",
        "verified": True,
    },
    {
        "name": "ПРОМЫШЛЕННЫЙ СОЮЗ [вакансии: B2B, FMCG, фарма, агро, стройка]",
        "username": "psoyuz",
        "topic": "Вакансии / Промышленность",
        "description": "Вакансии в производстве, стройке, агро, фарме и FMCG (B2B).",
        "verified": True,
    },
    {
        "name": "ВСЕМ МЕМ",
        "username": "vsemmema",
        "topic": "HR-мемы",
        "description": "Мемы про работу, найм и офисную жизнь.",
        "verified": True,
    },
    {
        "name": "Елена Шебашова | ЗА КАДРОМ",
        "username": "elena_shebashova",
        "topic": "HR / Карьера",
        "description": "Елена Шебашова: за кадром найма — карьера, HR, откровенные разборы.",
        "verified": True,
    },
    {
        "name": "HR-вакансии | ЗА КАДРОМ",
        "username": "zakadrom_hr",
        "topic": "HR / Вакансии",
        "description": "HR-вакансии и карьерные возможности в сфере управления персоналом.",
        "verified": True,
    },
    # --- Подборка TGStat: вакансии, фриланс и карьера ---
    {
        "name": "Finder.work: работа и вакансии",
        "username": "theyseeku",
        "topic": "Вакансии",
        "description": "274K подписчиков: удалённые вакансии со всей России, размещение бесплатно (finder.work).",
        "verified": True,
    },
    {
        "name": "hh.ru",
        "username": "hh_ru_official",
        "topic": "Вакансии / HR",
        "description": "Официальный канал hh.ru (89.7K): подборки вакансий, карьерные советы, продукты hh.",
        "verified": True,
    },
    {
        "name": "Ждём резюме | Лайфхакер",
        "username": "zdemcv",
        "topic": "Вакансии / Медиа",
        "description": "80.4K: вакансии в диджитале и медиа от Лайфхакера.",
        "verified": True,
    },
    {
        "name": "Джобстер Digital | Маркетинг | Вакансии и резюме",
        "username": "digital_jobster",
        "topic": "Вакансии / Маркетинг",
        "description": "47.8K: вакансии и резюме в маркетинге, digital, PR, SMM.",
        "verified": True,
    },
    {
        "name": "CPA HUNTER | Вакансии арбитража трафика",
        "username": "hr_affiliate",
        "topic": "Вакансии / Арбитраж",
        "description": "35.7K: вакансии в IT, CPA, SEO, SMM и affiliate-маркетинге.",
        "verified": True,
    },
    {
        "name": "Удаленка. Вакансии и резюме",
        "username": "rabota_freelancee",
        "topic": "Вакансии / Удалёнка",
        "description": "33.3K: удалённые вакансии и резюме — маркетинг, SMM, digital.",
        "verified": True,
    },
    {
        "name": "Точка входа",
        "username": "bbe_jobs",
        "topic": "Вакансии / Дизайн",
        "description": "25.6K: вакансии для дизайнеров и креативной индустрии (школа BBE).",
        "verified": True,
    },
    {
        "name": "Brocli: зарубежный фриланс | лайфхаки",
        "username": "digitalbroccoli",
        "topic": "Фриланс / Зарубежье",
        "description": "23.8K: выход на зарубежный фриланс, оплаты, кейсы и лайфхаки.",
        "verified": True,
    },
    {
        "name": "Работа GO",
        "username": "rabota_go",
        "topic": "Вакансии / Маркетинг",
        "description": "22.4K: вакансии в маркетинге, медиа, продажах и SMM.",
        "verified": True,
    },
    {
        "name": "Удаленка",
        "username": "remote_w0rk",
        "topic": "Вакансии / Удалёнка",
        "description": "15.5K: канал для поиска работы и работников на удалёнке.",
        "verified": True,
    },
    {
        "name": "Уютный Фриланс 😸",
        "username": "Uyut_frilans",
        "topic": "Фриланс",
        "description": "14.1K: фриланс-вакансии, проверенные заказчики. ⚠️ канал закрыл веб-превью — только ручной просмотр.",
        "verified": True,
    },
    {
        "name": "Фрилансер: вакансии на удаленке",
        "username": "workfreelancer",
        "topic": "Фриланс",
        "description": "12.5K: площадка удалённой работы, размещение вакансий и резюме.",
        "verified": True,
    },
    {
        "name": "Обновите резюме!",
        "username": "obn_rezume",
        "topic": "Карьера / Вакансии",
        "description": "11.4K: вакансии и советы по построению карьеры.",
        "verified": True,
    },
    {
        "name": "HR-Tech.Карьера 🔥",
        "username": "HRTech_Jobs",
        "topic": "HR / HR-Tech",
        "description": "9.8K: ежедневные вакансии в сфере HR-Tech от компаний.",
        "verified": True,
    },
    {
        "name": "Удаленка — IT и Digital",
        "username": "theyseeku_it",
        "topic": "Вакансии / IT",
        "description": "9.7K: удалённая работа в IT и digital — разработка, аналитика, дизайн.",
        "verified": True,
    },
    {
        "name": "Вакансии в HR-Аналитике",
        "username": "HR_Analytics_Jobs",
        "topic": "HR / Аналитика",
        "description": "7.2K: вакансии для HR-аналитиков и people analytics.",
        "verified": True,
    },
    {
        "name": "Ищу работу | Диджитал",
        "username": "work_looking",
        "topic": "Вакансии / Дизайн",
        "description": "5.6K: вакансии для дизайнеров, SMM-специалистов и digital.",
        "verified": True,
    },
    {
        "name": "Easy Work | Фриланс заказы | Удаленная работа",
        "username": "Easy_wrk",
        "topic": "Фриланс / Удалёнка",
        "description": "4.9K: удалённая работа и фриланс-заказы.",
        "verified": True,
    },
    {
        "name": "Ловец вакансий 🙌🏻",
        "username": "jobcatcher",
        "topic": "Вакансии / Менеджмент",
        "description": "4.4K: агрегатор управленческих вакансий.",
        "verified": True,
    },
    {
        "name": "Архитектор Карьеры",
        "username": "architect_career",
        "topic": "Карьера / HR",
        "description": "1.3K: карьерный коучинг и HR-практика.",
        "verified": True,
    },
    {
        "name": "Карьера без паники с Дарьей Гречиной",
        "username": "ne_titanik_DG",
        "topic": "Карьера / HR",
        "description": "1.2K: честно о карьере и найме — без воды и «просто верь в себя».",
        "verified": True,
    },
    {
        "name": "JOBнулся. О работе и карьере. Как есть",
        "username": "jobnulsya",
        "topic": "Карьера / HR",
        "description": "619: авторский канал Василия Паева о работе, карьере, HR и жизни.",
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
        "name": "Неустойчивое развитие",
        "username": "nongreta",
        "topic": "ESG / Устойчивое развитие",
        "description": "Экология, ESG и устойчивое развитие — вакансии и повестка.",
        "verified": True,
    },
    # =========================================================================
    # Третья подборка каналов (присланный список, проверено по t.me 18.11.2026)
    # =========================================================================
    # --- Третья подборка: ТОП-менеджмент и executive ---
    {
        "name": "Job for Chiefs",
        "username": "forchiefs",
        "topic": "ТОП-менеджмент и executive",
        "description": "CPO, CTO, directors, heads, C-level.",
        "verified": True,
    },
    {
        "name": "TOP Management",
        "username": "vakansii_top_manager",
        "topic": "ТОП-менеджмент и executive",
        "description": "CEO, COO, коммерческие директора.",
        "verified": True,
    },
    {
        "name": "Executive Career",
        "username": "ExecCareer",
        "topic": "ТОП-менеджмент и executive",
        "description": "Executive search, карьера топов.",
        "verified": True,
    },
    {
        "name": "Executive & C Level",
        "username": "executive_jobs",
        "topic": "ТОП-менеджмент и executive",
        "description": "Международные executive позиции.",
        "verified": True,
    },
    # --- Третья подборка: Product и project ---
    {
        "name": "Job for Products and Projects",
        "username": "forproducts",
        "topic": "Product и project",
        "description": "Product, Project, CPO, Product Owner.",
        "verified": True,
    },
    {
        "name": "Product Jobs",
        "username": "product_jobs",
        "topic": "Product и project",
        "description": "Product и Project менеджеры.",
        "verified": True,
    },
    # --- Третья подборка: Аналитика и Data Science ---
    {
        "name": "Analytics Jobs",
        "username": "analytics_jobs",
        "topic": "Аналитика и Data Science",
        "description": "Data Analyst, BI, Product Analyst.",
        "verified": True,
    },
    {
        "name": "Работа IT аналитикам",
        "username": "jobs_for_it_analyst",
        "topic": "Аналитика и Data Science",
        "description": "BA, SA, системная аналитика.",
        "verified": True,
    },
    {
        "name": "Data Science Jobs",
        "username": "datasciencejobs",
        "topic": "Аналитика и Data Science",
        "description": "ML, DS, AI, CV, Data Engineering.",
        "verified": True,
    },
    # --- Третья подборка: Разработка и DevOps ---
    {
        "name": "DevOps Jobs",
        "username": "devops_jobs",
        "topic": "Разработка и DevOps",
        "description": "DevOps, SRE.",
        "verified": True,
    },
    # --- Третья подборка: QA / тестирование ---
    {
        "name": "Job for QA",
        "username": "forallqa",
        "topic": "QA / тестирование",
        "description": "Manual, Automation, QA Lead.",
        "verified": True,
    },
    # --- Третья подборка: IT и digital (общий поток) ---
    {
        "name": "СЕТИ IT & Digital вакансии",
        "username": "it_vakansii_jobs",
        "topic": "IT и digital (общий поток)",
        "description": "Большой поток с прямыми контактами HR.",
        "verified": True,
    },
    # --- Третья подборка: Дизайн ---
    {
        "name": "Job for Designers",
        "username": "fordesigner",
        "topic": "Дизайн",
        "description": "UX, UI, Graphic, Art Direction.",
        "verified": True,
    },
    {
        "name": "UI/UX Jobs",
        "username": "uiux_jobs",
        "topic": "Дизайн",
        "description": "Узкопрофильный UX/UI.",
        "verified": True,
    },
    {
        "name": "Вакансии для дизайнеров",
        "username": "designer_vacancies",
        "topic": "Дизайн",
        "description": "Graphic, UX/UI, illustration, 3D.",
        "verified": True,
    },
    {
        "name": "UX/UI Designer Vacancies",
        "username": "uxui_designer_vacancies",
        "topic": "Дизайн",
        "description": "Узкопрофильный UX/UI.",
        "verified": True,
    },
    {
        "name": "Design Jobs",
        "username": "design_jobs_uxui",
        "topic": "Дизайн",
        "description": "UX/UI и Graphic.",
        "verified": True,
    },
    # --- Третья подборка: Маркетинг, SMM и PR ---
    {
        "name": "Job for Marketing",
        "username": "forallmarketing",
        "topic": "Маркетинг, SMM и PR",
        "description": "Digital, Growth, Performance, CRM, CMO.",
        "verified": True,
    },
    {
        "name": "DNative Job",
        "username": "dnative_job",
        "topic": "Маркетинг, SMM и PR",
        "description": "SMM и Digital.",
        "verified": True,
    },
    {
        "name": "Work Hunter",
        "username": "vakansii_0",
        "topic": "Маркетинг, SMM и PR",
        "description": "Marketing, SMM, PR, Content, Design, Sales.",
        "verified": True,
    },
    {
        "name": "Вакансии Telegram Ads / закупщики",
        "username": "vakansiitelegramm",
        "topic": "Маркетинг, SMM и PR",
        "description": "Таргетологи, Telegram Ads, посевы.",
        "verified": True,
    },
    # --- Третья подборка: Медиа, контент и события ---
    {
        "name": "Job for Media & Content",
        "username": "forallmedia",
        "topic": "Медиа, контент и события",
        "description": "Редакторы, журналисты, копирайтеры.",
        "verified": True,
    },
    {
        "name": "Мы вам перезвоним",
        "username": "perezvonyu",
        "topic": "Медиа, контент и события",
        "description": "Media и Digital.",
        "verified": True,
    },
    {
        "name": "Event Hunter",
        "username": "mskeventjob",
        "topic": "Медиа, контент и события",
        "description": "Media, events, creative, production.",
        "verified": True,
    },
    # --- Третья подборка: HR и рекрутинг ---
    {
        "name": "Job for HR",
        "username": "forhr",
        "topic": "HR и рекрутинг",
        "description": "Recruiter, HRBP, HRD.",
        "verified": True,
    },
    {
        "name": "HR вакансии",
        "username": "job_in_hr",
        "topic": "HR и рекрутинг",
        "description": "Recruitment, HR, кадровые роли.",
        "verified": True,
    },
    {
        "name": "HR Jobs",
        "username": "hr_jobs_rabota",
        "topic": "HR и рекрутинг",
        "description": "Recruiter, HRBP, HRD.",
        "verified": True,
    },
    {
        "name": "эйчарли",
        "username": "hrorhr",
        "topic": "HR и рекрутинг",
        "description": "Профильный поток, senior и executive.",
        "verified": True,
    },
    {
        "name": "HR Хаб вакансии",
        "username": "hrhubvacancy",
        "topic": "HR и рекрутинг",
        "description": "Сильный источник HR вакансий.",
        "verified": True,
    },
    {
        "name": "HR Хаб 300+",
        "username": "hrhubvacancy300",
        "topic": "HR и рекрутинг",
        "description": "Роли с высокой компенсацией (HRD, Head of HR).",
        "verified": True,
    },
    {
        "name": "HR Хаб Junior",
        "username": "hrhubjunior",
        "topic": "HR и рекрутинг",
        "description": "Junior HR и начальные роли.",
        "verified": True,
    },
    # --- Третья подборка: Юристы и право ---
    {
        "name": "Юридические вакансии",
        "username": "legal_jobs",
        "topic": "Юристы и право",
        "description": "In house, consulting, litigation, corporate, M&A.",
        "verified": True,
    },
    {
        "name": "HelloLawyer Jobs",
        "username": "hellolawyer_jobs",
        "topic": "Юристы и право",
        "description": "Legal Counsel, Compliance, IP, Regulatory.",
        "verified": True,
    },
    # --- Третья подборка: Финансы и бухгалтерия ---
    {
        "name": "CFO / IFRS вакансии",
        "username": "cfo_ifrs",
        "topic": "Финансы и бухгалтерия",
        "description": "CFO, Controller, IFRS, Finance.",
        "verified": True,
    },
    {
        "name": "CFO Search",
        "username": "cfosearch",
        "topic": "Финансы и бухгалтерия",
        "description": "Финансовые руководители.",
        "verified": True,
    },
    {
        "name": "Финансы, бухгалтерия, экономика",
        "username": "working_in_finance",
        "topic": "Финансы и бухгалтерия",
        "description": "Бухгалтеры, экономисты, аналитики, 1С.",
        "verified": True,
    },
    {
        "name": "Work in Accounting",
        "username": "work_in_accounting",
        "topic": "Финансы и бухгалтерия",
        "description": "Бухгалтерия и finance operations.",
        "verified": True,
    },
    # --- Третья подборка: Финтех и банки ---
    {
        "name": "Работа в финтехе",
        "username": "fintech_work",
        "topic": "Финтех и банки",
        "description": "Fintech, stock market, crypto, startups.",
        "verified": True,
    },
    {
        "name": "FintechJob Cards & Payments",
        "username": "paymentcardjobs",
        "topic": "Финтех и банки",
        "description": "Payments, acquiring, cards, operations.",
        "verified": True,
    },
    # --- Третья подборка: Продажи и bizdev ---
    {
        "name": "Job for Sales & BizDev",
        "username": "forallsales",
        "topic": "Продажи и bizdev",
        "description": "Sales, BDM, Account Management, CCO.",
        "verified": True,
    },
    {
        "name": "Sales Work",
        "username": "sales_work",
        "topic": "Продажи и bizdev",
        "description": "Общие продажи.",
        "verified": True,
    },
    {
        "name": "IT Sales Manager Jobs",
        "username": "sales_manager_job",
        "topic": "Продажи и bizdev",
        "description": "Sales в IT, SaaS, fintech и digital.",
        "verified": True,
    },
    {
        "name": "Sales Talents",
        "username": "salestalents",
        "topic": "Продажи и bizdev",
        "description": "Sales, KAM, BDM.",
        "verified": True,
    },
    {
        "name": "Careerspace",
        "username": "careerspace",
        "topic": "Продажи и bizdev",
        "description": "Общий канал с подборками по продажам.",
        "verified": True,
    },
    # --- Третья подборка: Клиентский сервис и Customer Success ---
    {
        "name": "Вакансии в клиентском сервисе",
        "username": "bizservisjob",
        "topic": "Клиентский сервис и Customer Success",
        "description": "Customer Support, CX.",
        "verified": True,
    },
    {
        "name": "Customer Success Talents",
        "username": "cstalents",
        "topic": "Клиентский сервис и Customer Success",
        "description": "CS, account management.",
        "verified": True,
    },
    # --- Третья подборка: Ассистенты и администрирование ---
    {
        "name": "ИЩУ АССИСТЕНТА | Размещение вакансий",
        "username": "nanyatassistenta",
        "topic": "Ассистенты и администрирование",
        "description": "Вакансии и поиск ассистентов: размещение запросов на подбор ассистента, executive/personal assistant.",
        "verified": True,
    },
    {
        "name": "GetAssistant вакансии",
        "username": "getassistant_vacancy",
        "topic": "Ассистенты и администрирование",
        "description": "Business/Executive/Personal Assistant (150-200k+).",
        "verified": True,
    },
    {
        "name": "Ассистека",
        "username": "assisteca_job",
        "topic": "Ассистенты и администрирование",
        "description": "Ассистенты разного уровня.",
        "verified": True,
    },
    {
        "name": "Менеджер / Ассистент / Работа",
        "username": "pomochnik_vakansii",
        "topic": "Ассистенты и администрирование",
        "description": "Ассистенты, office management, операционка.",
        "verified": True,
    },
    # --- Третья подборка: Строительство и инжиниринг ---
    {
        "name": "Вакансии строительство",
        "username": "vacancii_construction",
        "topic": "Строительство и инжиниринг",
        "description": "РП, ПТО, архитекторы, инженеры, сметчики.",
        "verified": True,
    },
    {
        "name": "Мосинжпроект",
        "username": "mosinzproekt",
        "topic": "Строительство и инжиниринг",
        "description": "Карьерный канал работодателя (ГИП, сметчики, IT).",
        "verified": True,
    },
    # --- Третья подборка: Фармацевтика и медицина ---
    {
        "name": "ФАРМА. Вакансии",
        "username": "JobinPharma",
        "topic": "Фармацевтика и медицина",
        "description": "Фармкомпании, аптечные сети, дистрибьюторы.",
        "verified": True,
    },
    {
        "name": "Лапа в фарме",
        "username": "lapainpharma",
        "topic": "Фармацевтика и медицина",
        "description": "Нишевый источник, стажировки.",
        "verified": True,
    },
    {
        "name": "Pharma & Medical Recruitment",
        "username": "pharmed_recruitment",
        "topic": "Фармацевтика и медицина",
        "description": "Фарма и medical.",
        "verified": True,
    },
    {
        "name": "Работа / Медицина / Вакансии",
        "username": "superjob_medicina",
        "topic": "Фармацевтика и медицина",
        "description": "Врачи, клиники, медперсонал.",
        "verified": True,
    },
    {
        "name": "Работа в медицине",
        "username": "job_in_med",
        "topic": "Фармацевтика и медицина",
        "description": "Медицина (общее).",
        "verified": True,
    },
    {
        "name": "Медицинские вакансии / сообщество",
        "username": "job_in_zdrav",
        "topic": "Фармацевтика и медицина",
        "description": "Врачи и медицинский персонал.",
        "verified": True,
    },
    # --- Третья подборка: HoReCa и общепит ---
    {
        "name": "HoReCa HR",
        "username": "HoReCa_HR",
        "topic": "HoReCa и общепит",
        "description": "Рестораны, кафе, гостиницы.",
        "verified": True,
    },
    {
        "name": "Общепит работа есть",
        "username": "rujobinfood",
        "topic": "HoReCa и общепит",
        "description": "Общепит.",
        "verified": True,
    },
    {
        "name": "Express Waiter",
        "username": "expresswaiter",
        "topic": "HoReCa и общепит",
        "description": "Рестораны, официанты, кухня.",
        "verified": True,
    },
    {
        "name": "Express Waiter Vacancies",
        "username": "expresswaiter_vacancy",
        "topic": "HoReCa и общепит",
        "description": "Отдельный поток вакансий.",
        "verified": True,
    },
    {
        "name": "Повара / HoReCa",
        "username": "exwaiters",
        "topic": "HoReCa и общепит",
        "description": "Кухня (повара).",
        "verified": True,
    },
    # --- Третья подборка: Прочие отрасли ---
    {
        "name": "JavaScript Jobs",
        "username": "javascript_jobs",
        "topic": "Прочие отрасли",
        "description": "Frontend, JS, TypeScript.",
        "verified": True,
    },
    {
        "name": "Python Jobs",
        "username": "ru_pythonjobs",
        "topic": "Прочие отрасли",
        "description": "Python.",
        "verified": True,
    },
    {
        "name": "Java Jobs",
        "username": "java_jobs",
        "topic": "Прочие отрасли",
        "description": "Java/Kotlin.",
        "verified": True,
    },
    {
        "name": "JavaDevJob",
        "username": "javadevjob",
        "topic": "Прочие отрасли",
        "description": "Ещё один поток Java.",
        "verified": True,
    },
    {
        "name": "Golang Jobs",
        "username": "golangjob",
        "topic": "Прочие отрасли",
        "description": "Go (Golang).",
        "verified": True,
    },
    {
        "name": "Mobile Dev Jobs",
        "username": "mobile_jobs",
        "topic": "Прочие отрасли",
        "description": "iOS, Android.",
        "verified": True,
    },
    {
        "name": "MobileDevJob",
        "username": "mobiledevjob",
        "topic": "Прочие отрасли",
        "description": "Mobile (общее).",
        "verified": True,
    },
    {
        "name": "PR вакансии и стажировки",
        "username": "prvacant",
        "topic": "Прочие отрасли",
        "description": "От стажёра до руководителя.",
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
