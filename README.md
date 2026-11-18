# 🤖 find_job_in_www_bot — Telegram-бот для формирования резюме и поиска работы

[![Unpack & Tests](https://github.com/andrey9653246431-spec/find_job_in_www_bot/actions/workflows/unpack_zip.yml/badge.svg)](https://github.com/andrey9653246431-spec/find_job_in_www_bot/actions)

Репозиторий проекта: **[andrey9653246431-spec/find_job_in_www_bot](https://github.com/andrey9653246431-spec/find_job_in_www_bot)**

Готовый проект асинхронного Telegram-бота, созданный **полностью на бесплатных и open-source инструментах** (`Python 3.11+`, `aiogram 3`, `SQLite / aiosqlite`, `aiohttp`, `BeautifulSoup4`, `python-docx`, `pypdf`).

---

## ✨ Реализованный функционал (по техническому заданию)

1. **📤 Отдельная функция загрузки резюме (`bot/services/file_extractor.py`, `bot/handlers/resume.py`)**
   - Принимает резюме файлом (`.pdf`, `.docx`, `.txt`, `.md`) или обычным текстовым сообщением в чате.
   - Автоматически извлекает текст, определяет **целевую должность** и формирует список **ключевых навыков (Hard/Soft skills)** для последующего поиска вакансий.
   - Сохраняет профиль резюме в локальную базу данных SQLite (`users_resumes`).

2. **📐 Отдельная функция задания стандартов рынка внутри бота (`bot/services/market_standards.py`, `bot/handlers/standards.py`)**
   - Функция `set_market_standards()` / меню **«📐 Стандарты рынка»** (`/standards`) позволяет прямо внутри Telegram-бота:
     - выбрать один из готовых отраслевых стандартов:
       - 🌐 *Универсальный ATS-стандарт (STAR / Google XYZ)*
       - 💻 *IT / Разработка ПО (Tech CV)*
       - 📊 *Data Science & Аналитика*
       - 📈 *Digital-маркетинг и Продажи*
     - 🏛 **«Золотой стандарт»: Executive CV (Framework 2026+)** — архитектура идеального executive-резюме (см. п. 2.1);
     - **или задать собственные стандарты рынка текстом прямо в боте** (указать обязательные разделы, целевые ключевые слова и правила оформления).
   - Стандарты сохраняются в таблице `market_standards` в БД.

### 2.1 🏛 Золотой стандарт: АРХИТЕКТУРА ИДЕАЛЬНОГО EXECUTIVE CV (Framework 2026+)

Отдельная функция `set_gold_standard_executive_cv_2026()` (кнопка **🏛 Золотой стандарт: Executive CV (2026+)** / команда `/gold_standard`) включает пресет `executive_cv_2026` — он выбран **стандартом по умолчанию**. Формирование текста резюме выполняет отдельная функция `build_ideal_executive_cv_2026()`.

Структура — максимум **2 страницы**, верхняя половина Page 1 должна продавать кандидата за **7–30 секунд**:

| № | Блок | Требования |
|---|---|---|
| 📌 1 | **HEADER (Шапка)** | ФИО крупно; целевая должность строго под ФИО с вектором (`Commercial Director \| Fashion Retail / Omnichannel`); локация + готовность к релокации/командировкам; контакты (телефон, email, LinkedIn/TG). **Правило:** никаких фото, дат рождения, возраста, семейного положения |
| 📌 2 | **ПРОФИЛЬ (Executive Summary)** | 3–5 строк по формуле `[Уровень + опыт] + [Масштаб бизнеса] + [Ключевая экспертиза: P&L, Omnichannel, CAP/OTB] + [Главный результат-визитка]`. Только бизнес-язык, без клише «ответственный и коммуникабельный» |
| 📌 3 | **КЛЮЧЕВАЯ ЭКСПЕРТИЗА (Core Expertise / ATS Keywords)** | Облако тегов через разделитель `\|`, сгруппированное в **Business & Strategy**, **Operations**, **Leadership & Tech**. Точная рыночная лексика (ATS vocabulary) |
| 📌 4 | **ОПЫТ РАБОТЫ (Professional Experience)** | Обратный хронологический порядок; шапка компании (название, сфера, масштаб); должность и период; контекст роли 1–2 предложения (P&L, бюджет, прямые подчинённые); **Scope** 3–4 пункта; **ключевые результаты 3–4 пункта (жёсткий максимум 4)** по формуле `Глагол действия + Метрика (цифра) + Механизм/Влияние` |
| 📌 5 | **ДОПОЛНИТЕЛЬНЫЕ БЛОКИ** | Образование и языки (с уровнем: `Английский — B2/Upper-Intermediate`); ключевые проекты 1–2 кейса в формате `Проблема -> Решение -> Результат в цифрах` |

**⚠️ Четыре фильтра упаковки**, которые применяет `build_ideal_executive_cv_2026()`:

1. **Evidence Map (Карта доказательств)** — CV содержит профиль и масштаб, детали уходят на интервью; лимит `max_bullets_per_role = 4` (лишние пункты выносятся в заметку «сокращено второстепенных пунктов для интервью»).
2. **Attribution (Атрибуция цифр)** — разделение личного вклада и общекомандного результата, формулировки с механизмом достижения.
3. **Борьба с Red Flags** — функция `strip_red_flags_and_demographics()` удаляет фото, дату рождения, возраст, семейное положение, штампы и пассивные клише.
4. **Один фокус — один экран** — сильнейшие достижения на Page 1; опыт 10-летней давности — не более 2–3 строк.

Группировку ATS-тегов выполняет отдельная функция `categorize_core_expertise_tags()` — она приводит навыки к точной рыночной лексике (`P&L` → `P&L Management`, `Omnichannel` → `Omnichannel Strategy`) и не допускает дублей между кластерами.

Дополнительно архитектор резюме:
- разбирает **несколько мест работы** (обратный хронологический порядок), беря должность и период из шапки компании;
- корректно снимает `Scope:` / `Зона ответственности:` и переносит пункты в блок Scope;
- сохраняет стаж (`12 лет опыта`) в профиле, при этом удаляя возраст (`41 год`);
- для каждой роли применяет лимит ≤ 4 буллитов, а «лишние» пункты отмечает как материал для интервью.

Готовый текст можно скачать как `Ideal_Executive_CV_2026.docx`; демонстрационный пример — в каталоге [`examples/`](examples/ideal_executive_cv_2026_example.md).

### 2.2 👁 Показ примера идеального резюме (`/example_cv`)

Отдельная функция `build_ideal_executive_cv_2026_example()` (команда `/example_cv`, кнопка **🏛 Пример идеального резюме** в главном меню и inline-кнопка **👁 Показать пример идеального резюме** в меню стандартов) показывает эталон без загрузки собственного резюме и без обращения к БД:

- пояснение и **карту архитектуры**: 5 блоков + 4 фильтра упаковки;
- `ATS Score` исходного «грязного» образца;
- готовый **текст эталонного Executive CV** (по частям, с учётом лимита Telegram 4096 символов);
- файл **`Ideal_Executive_CV_2026_Example.docx`** — шаблон структуры для своего резюме.

Встроенный образец (`EXECUTIVE_CV_2026_EXAMPLE_RAW`) специально содержит фото, дату рождения, возраст, семейное положение и клише — чтобы наглядно показать работу фильтра Red Flags.

3. **✨ Отдельная функция адаптации резюме под стандарты рынка (`adapt_resume_to_market_standards`)**
   - Запускается кнопкой **«✨ Адаптировать резюме»** (`/adapt_resume`).
   - Проводит аудит резюме по активным стандартам рынка и рассчитывает **ATS Compliance Score (0–100%)**.
   - Перестраивает структуру резюме строго по разделам заданного стандарта, заменяет пассивные глаголы («занимался», «писал код», «участвовал») на глаголы результата по методу **STAR / XYZ**, очищает текст от штампов и формирует готовый для скачивания файл **`Adapted_Resume_Market_Standard.docx`**.
   - **Два бесплатных режима работы:**
     - **Встроенный бесплатный алгоритмический движок** (работает «из коробки» вообще без API-ключей).
     - **Бесплатный LLM-режим (опционально)** — поддержка бесплатных ключей **Groq API** (`llama-3.3-70b-versatile`), **OpenRouter Free** или локальной **Ollama** через `.env`.

4. **🔍 Парсинг и поиск вакансий по резюме с выбором периода (`1 день`, `1 неделя`, `1 месяц`)**
   - Запускается кнопкой **«🔍 Поиск вакансий»** (`/search`).
   - Предлагает интерактивный выбор периода:
     - 🕐 **За 1 день** (`24 часа`)
     - 📅 **За 1 неделю** (`7 дней`)
     - 🗓 **За 1 месяц** (`30 дней`)
   - Асинхронно парсит все активные ресурсы из базы данных:
     - **Публичные Telegram-каналы** через веб-превью `https://t.me/s/<channel>` (полностью бесплатно, не требует SIM-карты или платного API).
     - **Сайты вакансий**: открытый бесплатный API `hh.ru` (`https://api.hh.ru/vacancies`), RSS/HTML `career.habr.com` и любые пользовательские сайты/RSS-ленты.
   - Фильтрует вакансии по дате публикации, сопоставляет с навыками и должностью из резюме, ранжирует по релевантности и выводит сообщение со списком подходящих вакансий.

5. **🌐 Добавление сайтов и ТГ-каналов в базу источников с проверкой на дубликаты (`bot/services/source_manager.py`, `bot/handlers/sources.py`)**
   - Поддерживает добавление ссылок в любом формате: `@channel_name`, `t.me/channel_name`, `https://t.me/s/channel_name`, `https://site.ru/jobs`.
   - Нормализует ссылку и проверяет наличие в таблице `sources` базы данных SQLite:
     - **Если источник уже есть в базе** — бот сообщает пользователю: *«⚠️ Этот источник уже есть в моей базе данных!»*.
     - **Если источник новый** — бот сохраняет его в базу данных и сообщает: *«✅ Новый источник успешно добавлен в базу данных!»*.

---

## 🧭 Алгоритм поиска каналов, сайтов и компаний (`/find_resources`)

Отдельный модуль `bot/services/search_assistant.py` + каталог `bot/services/resource_catalog.py` реализуют правила «экспертного HR-ассистента по России и СНГ».

**Определение типа поиска по запросу** (`detect_search_intent`):

| Запрос пользователя | Что выдаёт бот |
|---|---|
| «Telegram-каналы», «ТГ-каналы», «чаты» | ссылки `https://t.me/username` в формате `[Название](https://t.me/username)` + тематика канала (IT, HR, Маркетинг, GameDev, Remote) |
| «агрегаторы», «сайты с вакансиями», конкретные платформы | job-борды: hh.ru, Хабр Карьера, Работа.ру, Зарплата.ру, Город Работ, **hirify.me**, getmatch, GeekJob, Работа России, LinkedIn |
| «компании», «ТОП-100/500/1000», «карьерные страницы» | структурированный список компаний по отраслям: `[Сайт](...) | [Карьера / Вакансии](...) | описание` |
| «ТГ-каналы и агрегаторы» (смешанный запрос) | оба блока в одном ответе |
| профессия («вакансии HR-менеджер») | deep-links поиска с фильтрами: hh.ru, Хабр Карьера, hirify.me, getmatch + инструкция поиска каналов в Telegram |

**Правила вывода, зашитые в код:**
1. **Структура и блоки** — более 15–20 позиций разбиваются на смысловые блоки (отрасли: IT и Телеком, Банки и финансы, Ритейл и e-commerce, Промышленность, Логистика, FMCG, Фарма).
2. **Каждый пункт** — название, прямая ссылка, короткое описание в одну строку.
3. **Никаких выдуманных ссылок** — все URL берутся из проверенного каталога; карьерные страницы включаются только там, где адрес подтверждён, иначе используется документированный поиск hh.ru (`/search/vacancy?text=...`). Для непроверенных ресурсов выводится предупреждение *«Проверьте актуальность ссылки, точный адрес может быть изменён»*.
4. **Лимиты Telegram** — ответ автоматически делится на части (`split_long_message`, 3800 символов) с подписью «Часть N из M»; при запросе более 50 компаний выводится предупреждение.
5. **Дисклеймер в каждом ответе** — «Ссылки могут меняться. Актуальность вакансий проверяйте на официальных сайтах компаний, в Telegram-каналах или на агрегаторах (hh.ru, hirify.me).»
6. **Живая проверка при добавлении источника** — `verify_source_availability()` запрашивает `https://t.me/s/<channel>` и сообщает, отдаёт ли канал публичное превью (защита от приватных и несуществующих каналов).

**Примеры ответов:** [`examples/resources_search_examples.md`](examples/resources_search_examples.md). Каталог: 138 Telegram-каналов, 32 сайта-агрегатора, 30 компаний в 7 отраслях — полный реестр источников вакансий ниже, в разделе «📡 Источники вакансий».

---

## 📡 Источники вакансий: полный реестр (163 ресурса)

Реестр сгенерирован из кода (`bot/database.py` + `bot/services/resource_catalog.py`) скриптом `tools/regen_readme_registry.py` — он не может разойтись с базой.

### Сводка

| Что | Сколько | Как используется |
|---|---|---|
| Telegram-каналы | **135** | парсинг через веб-превью `t.me/s/<канал>` |
| Сайты, API и RSS | **28** | API/RSS/HTML-парсинг + ручные ссылки поиска |
| — из них автопарсинг | **9** | hh.ru API, «Работа России» API, RSS Хабр Карьеры/WWR/Jobspresso, HTML budu.jobs и remote-job.ru |
| — из них ручной поиск | **19** | бот формирует готовые ссылки под профиль (Cloudflare/403/JS) |
| **Итого** | **163** | один поиск = 163 параллельных запросов |

Каталог ресурсов `/find_resources`: **138** каналов, **31** сайта-агрегатора, 30 компаний с карьерными страницами.

Живой прогон (профиль «Директор по маркетингу», 7 дней): **163 источников → 410 вакансий**, 19 предупреждений об источниках с закрытым веб-превью (они остаются в базе, бот честно сообщает причину и даёт ссылку).

## 🌐 Сайты, RSS-ленты и API (28)

| Сайт | URL | Как читаем |
|---|---|---|
| RemoteOK | https://remoteok.com/ | JSON API |
| We Work Remotely | https://weworkremotely.com/ | RSS |
| Jobspresso | https://jobspresso.co/ | RSS |
| Indeed | https://www.indeed.com/ | 🔗 ручной поиск (403/JS/антибот) |
| Glassdoor | https://www.glassdoor.com/ | 🔗 ручной поиск (403/JS/антибот) |
| ZipRecruiter IE | https://www.ziprecruiter.ie/ | 🔗 ручной поиск (403/JS/антибот) |
| CareerBuilder | https://www.careerbuilder.com/ | 🔗 ручной поиск (403/JS/антибот) |
| WantApply | https://wantapply.com/ | 🔗 ручной поиск (403/JS/антибот) |
| Remote.co | https://remote.co/ | 🔗 ручной поиск (403/JS/антибот) |
| HeadHunter | https://hh.ru | API hh.ru |
| Хабр Карьера | https://career.habr.com | RSS |
| GeekJob | https://geekjob.ru | HTML-лента |
| Работа России | https://trudvsem.ru | открытые данные (JSON API) |
| Буду | https://budu.jobs/ | HTML-лента |
| Remote Job | https://remote-job.ru/ | HTML-лента |
| getmatch | https://getmatch.ru/vacancies | 🔗 ручной поиск (403/JS/антибот) |
| Facancy | https://facancy.ru/ | 🔗 ручной поиск (403/JS/антибот) |
| Changellenge | https://changellenge.com/ | 🔗 ручной поиск (403/JS/антибот) |
| InGame Job | https://ingamejob.com/ | 🔗 ручной поиск (403/JS/антибот) |
| Careerist | https://careerist.ru/ | 🔗 ручной поиск (403/JS/антибот) |
| LinkedIn Jobs | https://www.linkedin.com/jobs/ | 🔗 ручной поиск (403/JS/антибот) |
| Wellfound | https://wellfound.com/jobs | 🔗 ручной поиск (403/JS/антибот) |
| Jooble | https://ru.jooble.org/ | 🔗 ручной поиск (403/JS/антибот) |
| ГородРабот | https://gorodrabot.ru | 🔗 ручной поиск (403/JS/антибот) |
| Avito Работа | https://www.avito.ru/rossiya/vakansii | 🔗 ручной поиск (403/JS/антибот) |
| YouDo | https://youdo.com/ | 🔗 ручной поиск (403/JS/антибот) |
| Kwork | https://kwork.ru/ | 🔗 ручной поиск (403/JS/антибот) |
| FL.ru | https://www.fl.ru/ | 🔗 ручной поиск (403/JS/антибот) |

### 🌍 Почему часть площадок — только ручной поиск

- **Indeed, Glassdoor, ZipRecruiter, CareerBuilder, WantApply, Remote.co** — Cloudflare/403 с облачных IP: бот не обходит защиту и не выдумывает вакансии.
- **Avito (439), ГородРабот (423), Jooble, YouDo, Kwork, FL.ru, getmatch, Careerist, Facancy, Changellenge, InGame Job, Wellfound, LinkedIn** — либо антибот-ответ, либо выдача рендерится JavaScript-ом, поэтому в HTML нет вакансий.
- Для всех таких площадок бот показывает **ссылку поиска под ваш профиль** (`build_manual_board_link`) и прямо пишет, что это ручной режим.

## 📢 Telegram-каналы (138)

### Executive, топ-менеджмент и карьера руководителя (11)

- **Я Топ** — [@i_top_groups](https://t.me/i_top_groups) — Вакансии и резюме для топ-менеджеров, руководителей и управленцев.
- **КАРЬЕРА ЛИДЕРА \| Вакансии для руководителей** — [@work_for_top](https://t.me/work_for_top) — Вакансии для руководителей и топов: CEO, директора направлений.
- **Exec Select \| Топ вакансии для руководителей** — [@execselect](https://t.me/execselect) — Отборные executive-вакансии для руководителей высшего звена.
- **Вакансии от CRC** — [@vacancyCRC](https://t.me/vacancyCRC) — Career Review Center: вакансии для middle/top-менеджеров и HR-консалтинг.
- **Work For TOP Вакансии для руководителей** — [@workfortop](https://t.me/workfortop) — Вакансии для руководителей: топ-позиции и управленческие роли.
- **TOP LEVEL JOB [топ вакансии для руководителей]** — [@toplevel_job](https://t.me/toplevel_job) — Вакансии уровня CEO/CEO-1 с прямыми контактами работодателей.
- **Ловец вакансий 🙌🏻** — [@jobcatcher](https://t.me/jobcatcher) — 4.4K: агрегатор управленческих вакансий.
- **Job for Chiefs** — [@forchiefs](https://t.me/forchiefs) — CPO, CTO, directors, heads, C-level.
- **TOP Management** — [@vakansii_top_manager](https://t.me/vakansii_top_manager) — CEO, COO, коммерческие директора.
- **Executive Career** — [@ExecCareer](https://t.me/ExecCareer) — Executive search, карьера топов.
- **Executive & C Level** — [@executive_jobs](https://t.me/executive_jobs) — Международные executive позиции.

### HR, рекрутинг, кадры и HR-tech (37)

- **HR \| Вакансии 🦊** — [@vacancies_it](https://t.me/vacancies_it) — Вакансии в IT и подборка HR-позиций от кадровых агентств.
- **Ирена_Иванова_official** — [@irenaivanova_official](https://t.me/irenaivanova_official) — Авторский канал Ирены Ивановой: рынок труда, карьера, инсайды от хантера.
- **Наталья Ларина \| Карьера по своим правилам** — [@larina_career](https://t.me/larina_career) — Карьера по своим правилам: поиск работы, офферы, карьерные стратегии.
- **#ПерезагрузкаКарьеры** — [@hrexpert63](https://t.me/hrexpert63) — Эксперт по обе стороны найма: карьера, HR-практика, разборы.
- **Abrashitova Natalya \| Карьерное развитие** — [@hrhack_career](https://t.me/hrhack_career) — Наталья Абрашитова (HRD 15+ лет): вакансии, HR-советы, карьерные разборы.
- **Живое обучение** — [@prolearning](https://t.me/prolearning) — Елена Тихомирова о том, как учатся взрослые и как строить корпоративное обучение.
- **Talent Hunters** — [@talent_hunters](https://t.me/talent_hunters) — Лана Катаева (ex-AVRIO): тренды рынка труда, хантинг, HR-мероприятия.
- **IT HR тусовка от ХК** — [@ithr_tusovka](https://t.me/ithr_tusovka) — Хабр Карьера: найм в IT, тренды, исследования, мемы для эйчаров.
- **Рекомендательный рекрутинг** — [@recommend_recruit](https://t.me/recommend_recruit) — Рекрутинг по рекомендациям: заявки, кандидаты, вознаграждение за рекомендацию.
- **Смелый рекрутинг** — [@ithunterio](https://t.me/ithunterio) — Смелый рекрутинг: нестандартные подходы к найму и сорсингу.
- **TrendHR** — [@trend_hr](https://t.me/trend_hr) — HR-тренды, инструменты и практики найма.
- **БОЛЬШЕ чем HR** — [@more_than_hr](https://t.me/more_than_hr) — Галина Друбецкая: HR шире найма — культура, коммуникации, люди.
- **ВСЕМ МЕМ** — [@vsemmema](https://t.me/vsemmema) — Мемы про работу, найм и офисную жизнь.
- **Елена Шебашова \| ЗА КАДРОМ** — [@elena_shebashova](https://t.me/elena_shebashova) — Елена Шебашова: за кадром найма — карьера, HR, откровенные разборы.
- **HR-вакансии \| ЗА КАДРОМ** — [@zakadrom_hr](https://t.me/zakadrom_hr) — HR-вакансии и карьерные возможности в сфере управления персоналом.
- **hh.ru** — [@hh_ru_official](https://t.me/hh_ru_official) — Официальный канал hh.ru (89.7K): подборки вакансий, карьерные советы, продукты hh.
- **Обновите резюме!** — [@obn_rezume](https://t.me/obn_rezume) — 11.4K: вакансии и советы по построению карьеры.
- **HR-Tech.Карьера 🔥** — [@HRTech_Jobs](https://t.me/HRTech_Jobs) — 9.8K: ежедневные вакансии в сфере HR-Tech от компаний.
- **Вакансии в HR-Аналитике** — [@HR_Analytics_Jobs](https://t.me/HR_Analytics_Jobs) — 7.2K: вакансии для HR-аналитиков и people analytics.
- **Архитектор Карьеры** — [@architect_career](https://t.me/architect_career) — 1.3K: карьерный коучинг и HR-практика.
- **Карьера без паники с Дарьей Гречиной** — [@ne_titanik_DG](https://t.me/ne_titanik_DG) — 1.2K: честно о карьере и найме — без воды и «просто верь в себя».
- **JOBнулся. О работе и карьере. Как есть** — [@jobnulsya](https://t.me/jobnulsya) — 619: авторский канал Василия Паева о работе, карьере, HR и жизни.
- **МарЧар \| Маркетинг в HR** — [@marhrru](https://t.me/marhrru) — Маркетинг в HR: employer brand, коммуникации, кейсы подбора.
- **HR мама 🍋** — [@HRmother](https://t.me/HRmother) — HR-практика для мам и не только: подбор, адаптация, карьера в HR.
- **Кадровый голод** — [@kadrovik_krd](https://t.me/kadrovik_krd) — Кадровое делопроизводство, ТК РФ и практика кадровика.
- **Аптуми (up to me)** — [@uptume](https://t.me/uptume) — Карьерное развитие, самоопределение и поиск работы.
- **Русский HR** — [@rus_hr](https://t.me/rus_hr) — Новости и практика российского HR-рынка.
- **Всё, я увольняюсь!** — [@uvolnyaus](https://t.me/uvolnyaus) — Увольнение, смена работы и карьерные истории без прикрас.
- **АККСиомы Карьеры** — [@akks_career](https://t.me/akks_career) — Карьерные советы, разборы вакансий и резюме.
- **Вакансии от Хрипченко Ани** — [@rudakovahr](https://t.me/rudakovahr) — Подборка актуальных HR- и офисных вакансий от рекрутера.
- **Job for HR** — [@forhr](https://t.me/forhr) — Recruiter, HRBP, HRD.
- **HR вакансии** — [@job_in_hr](https://t.me/job_in_hr) — Recruitment, HR, кадровые роли.
- **HR Jobs** — [@hr_jobs_rabota](https://t.me/hr_jobs_rabota) — Recruiter, HRBP, HRD.
- **эйчарли** — [@hrorhr](https://t.me/hrorhr) — Профильный поток, senior и executive.
- **HR Хаб вакансии** — [@hrhubvacancy](https://t.me/hrhubvacancy) — Сильный источник HR вакансий.
- **HR Хаб 300+** — [@hrhubvacancy300](https://t.me/hrhubvacancy300) — Роли с высокой компенсацией (HRD, Head of HR).
- **HR Хаб Junior** — [@hrhubjunior](https://t.me/hrhubjunior) — Junior HR и начальные роли.

### Product, project и QA (4)

- **Hire ProProduct - Продуктовые вакансии** — [@hireproproduct](https://t.me/hireproproduct) — Вакансии для продакт- и проджект-менеджеров, аналитиков, дизайнеров.
- **Job for Products and Projects** — [@forproducts](https://t.me/forproducts) — Product, Project, CPO, Product Owner.
- **Product Jobs** — [@product_jobs](https://t.me/product_jobs) — Product и Project менеджеры.
- **Job for QA** — [@forallqa](https://t.me/forallqa) — Manual, Automation, QA Lead.

### IT, разработка, данные и GameDev (12)

- **Хабр Карьера** — [@habr_career](https://t.me/habr_career) — Вакансии и обсуждение карьеры в IT от редакции Хабра.
- **IT Job x IT Vacancies** — [@job_it_ru](https://t.me/job_it_ru) — Подборка IT-вакансий: разработка, аналитика, DevOps, удалёнка.
- **Remote IT Jobs** — [@remote_it_jobs](https://t.me/remote_it_jobs) — Только удалённые IT-вакансии — удобно для поиска из любого города.
- **Game Development Jobs** — [@devjobs](https://t.me/devjobs) — Вакансии в игровой индустрии: программисты, художники, геймдизайнеры.
- **Вакансии в IT** — [@data_jobs_ru](https://t.me/data_jobs_ru) — Свежие IT-вакансии, включая аналитику данных и инженерию.
- **Senior Помідор** — [@tomato1000](https://t.me/tomato1000) — IT-вакансии с зарплатой от $1000 (UA/remote). ⚠️ веб-превью закрыто — ручной просмотр.
- **Удаленка — IT и Digital** — [@theyseeku_it](https://t.me/theyseeku_it) — 9.7K: удалённая работа в IT и digital — разработка, аналитика, дизайн.
- **Analytics Jobs** — [@analytics_jobs](https://t.me/analytics_jobs) — Data Analyst, BI, Product Analyst.
- **Работа IT аналитикам** — [@jobs_for_it_analyst](https://t.me/jobs_for_it_analyst) — BA, SA, системная аналитика.
- **Data Science Jobs** — [@datasciencejobs](https://t.me/datasciencejobs) — ML, DS, AI, CV, Data Engineering.
- **DevOps Jobs** — [@devops_jobs](https://t.me/devops_jobs) — DevOps, SRE.
- **СЕТИ IT & Digital вакансии** — [@it_vakansii_jobs](https://t.me/it_vakansii_jobs) — Большой поток с прямыми контактами HR.

### Дизайн (7)

- **Точка входа** — [@bbe_jobs](https://t.me/bbe_jobs) — 25.6K: вакансии для дизайнеров и креативной индустрии (школа BBE).
- **Ищу работу \| Диджитал** — [@work_looking](https://t.me/work_looking) — 5.6K: вакансии для дизайнеров, SMM-специалистов и digital.
- **Job for Designers** — [@fordesigner](https://t.me/fordesigner) — UX, UI, Graphic, Art Direction.
- **UI/UX Jobs** — [@uiux_jobs](https://t.me/uiux_jobs) — Узкопрофильный UX/UI.
- **Вакансии для дизайнеров** — [@designer_vacancies](https://t.me/designer_vacancies) — Graphic, UX/UI, illustration, 3D.
- **UX/UI Designer Vacancies** — [@uxui_designer_vacancies](https://t.me/uxui_designer_vacancies) — Узкопрофильный UX/UI.
- **Design Jobs** — [@design_jobs_uxui](https://t.me/design_jobs_uxui) — UX/UI и Graphic.

### Маркетинг, PR, медиа и контент (12)

- **marketing jobs** — [@marketing_jobs](https://t.me/marketing_jobs) — Вакансии для маркетологов: performance, бренд, продуктовая аналитика.
- **Ждём резюме \| Лайфхакер** — [@zdemcv](https://t.me/zdemcv) — 80.4K: вакансии в диджитале и медиа от Лайфхакера.
- **Джобстер Digital \| Маркетинг \| Вакансии и резюме** — [@digital_jobster](https://t.me/digital_jobster) — 47.8K: вакансии и резюме в маркетинге, digital, PR, SMM.
- **CPA HUNTER \| Вакансии арбитража трафика** — [@hr_affiliate](https://t.me/hr_affiliate) — 35.7K: вакансии в IT, CPA, SEO, SMM и affiliate-маркетинге.
- **Работа GO** — [@rabota_go](https://t.me/rabota_go) — 22.4K: вакансии в маркетинге, медиа, продажах и SMM.
- **Job for Marketing** — [@forallmarketing](https://t.me/forallmarketing) — Digital, Growth, Performance, CRM, CMO.
- **DNative Job** — [@dnative_job](https://t.me/dnative_job) — SMM и Digital.
- **Work Hunter** — [@vakansii_0](https://t.me/vakansii_0) — Marketing, SMM, PR, Content, Design, Sales.
- **Вакансии Telegram Ads / закупщики** — [@vakansiitelegramm](https://t.me/vakansiitelegramm) — Таргетологи, Telegram Ads, посевы.
- **Job for Media & Content** — [@forallmedia](https://t.me/forallmedia) — Редакторы, журналисты, копирайтеры.
- **Мы вам перезвоним** — [@perezvonyu](https://t.me/perezvonyu) — Media и Digital.
- **Event Hunter** — [@mskeventjob](https://t.me/mskeventjob) — Media, events, creative, production.

### Продажи, клиентский сервис и Customer Success (7)

- **Job for Sales & BizDev** — [@forallsales](https://t.me/forallsales) — Sales, BDM, Account Management, CCO.
- **Sales Work** — [@sales_work](https://t.me/sales_work) — Общие продажи.
- **IT Sales Manager Jobs** — [@sales_manager_job](https://t.me/sales_manager_job) — Sales в IT, SaaS, fintech и digital.
- **Sales Talents** — [@salestalents](https://t.me/salestalents) — Sales, KAM, BDM.
- **Careerspace** — [@careerspace](https://t.me/careerspace) — Общий канал с подборками по продажам.
- **Вакансии в клиентском сервисе** — [@bizservisjob](https://t.me/bizservisjob) — Customer Support, CX.
- **Customer Success Talents** — [@cstalents](https://t.me/cstalents) — CS, account management.

### Финансы, финтех, юристы и комплаенс (7)

- **Fintech - Jobs** — [@fintech_jobs](https://t.me/fintech_jobs) — Вакансии в финтехе, банках, крипте и платёжных сервисах.
- **CFO / IFRS вакансии** — [@cfo_ifrs](https://t.me/cfo_ifrs) — CFO, Controller, IFRS, Finance.
- **CFO Search** — [@cfosearch](https://t.me/cfosearch) — Финансовые руководители.
- **Финансы, бухгалтерия, экономика** — [@working_in_finance](https://t.me/working_in_finance) — Бухгалтеры, экономисты, аналитики, 1С.
- **Work in Accounting** — [@work_in_accounting](https://t.me/work_in_accounting) — Бухгалтерия и finance operations.
- **Работа в финтехе** — [@fintech_work](https://t.me/fintech_work) — Fintech, stock market, crypto, startups.
- **FintechJob Cards & Payments** — [@paymentcardjobs](https://t.me/paymentcardjobs) — Payments, acquiring, cards, operations.

### Ассистенты и администрирование (4)

- **ИЩУ АССИСТЕНТА \| Размещение вакансий** — [@nanyatassistenta](https://t.me/nanyatassistenta) — Вакансии и поиск ассистентов: размещение запросов на подбор ассистента, executive/personal assistant.
- **GetAssistant вакансии** — [@getassistant_vacancy](https://t.me/getassistant_vacancy) — Business/Executive/Personal Assistant (150-200k+).
- **Ассистека** — [@assisteca_job](https://t.me/assisteca_job) — Ассистенты разного уровня.
- **Менеджер / Ассистент / Работа** — [@pomochnik_vakansii](https://t.me/pomochnik_vakansii) — Ассистенты, office management, операционка.

### Отрасли: фарма, медицина, стройка, HoReCa (12)

- **ПРОМЫШЛЕННЫЙ СОЮЗ [вакансии: B2B, FMCG, фарма, агро, стройка]** — [@psoyuz](https://t.me/psoyuz) — Вакансии в производстве, стройке, агро, фарме и FMCG (B2B).
- **ФАРМА. Вакансии** — [@JobinPharma](https://t.me/JobinPharma) — Фармкомпании, аптечные сети, дистрибьюторы.
- **Лапа в фарме** — [@lapainpharma](https://t.me/lapainpharma) — Нишевый источник, стажировки.
- **Pharma & Medical Recruitment** — [@pharmed_recruitment](https://t.me/pharmed_recruitment) — Фарма и medical.
- **Работа / Медицина / Вакансии** — [@superjob_medicina](https://t.me/superjob_medicina) — Врачи, клиники, медперсонал.
- **Работа в медицине** — [@job_in_med](https://t.me/job_in_med) — Медицина (общее).
- **Медицинские вакансии / сообщество** — [@job_in_zdrav](https://t.me/job_in_zdrav) — Врачи и медицинский персонал.
- **HoReCa HR** — [@HoReCa_HR](https://t.me/HoReCa_HR) — Рестораны, кафе, гостиницы.
- **Общепит работа есть** — [@rujobinfood](https://t.me/rujobinfood) — Общепит.
- **Express Waiter** — [@expresswaiter](https://t.me/expresswaiter) — Рестораны, официанты, кухня.
- **Express Waiter Vacancies** — [@expresswaiter_vacancy](https://t.me/expresswaiter_vacancy) — Отдельный поток вакансий.
- **Повара / HoReCa** — [@exwaiters](https://t.me/exwaiters) — Кухня (повара).

### Удалёнка, фриланс и релокация (8)

- **Remote Jobs \| Remote Work** — [@remote_work_jobs](https://t.me/remote_work_jobs) — Удалённые вакансии разных профессий, в том числе англоязычные.
- **Вакансии с релокацией** — [@relocation_vacancies](https://t.me/relocation_vacancies) — Релокация: зарубежные и релокационные вакансии с визовой поддержкой.
- **Удаленка. Вакансии и резюме** — [@rabota_freelancee](https://t.me/rabota_freelancee) — 33.3K: удалённые вакансии и резюме — маркетинг, SMM, digital.
- **Brocli: зарубежный фриланс \| лайфхаки** — [@digitalbroccoli](https://t.me/digitalbroccoli) — 23.8K: выход на зарубежный фриланс, оплаты, кейсы и лайфхаки.
- **Удаленка** — [@remote_w0rk](https://t.me/remote_w0rk) — 15.5K: канал для поиска работы и работников на удалёнке.
- **Уютный Фриланс 😸** — [@Uyut_frilans](https://t.me/Uyut_frilans) — 14.1K: фриланс-вакансии, проверенные заказчики. ⚠️ канал закрыл веб-превью — только ручной просмотр.
- **Фрилансер: вакансии на удаленке** — [@workfreelancer](https://t.me/workfreelancer) — 12.5K: площадка удалённой работы, размещение вакансий и резюме.
- **Easy Work \| Фриланс заказы \| Удаленная работа** — [@Easy_wrk](https://t.me/Easy_wrk) — 4.9K: удалённая работа и фриланс-заказы.

### Общие подборки вакансий, аналитика рынка и прочее (17)

- **Finder.work: работа и вакансии** — [@theyseeku](https://t.me/theyseeku) — 274K подписчиков: удалённые вакансии со всей России, размещение бесплатно (finder.work).
- **Янг Групп** — [@you_social](https://t.me/you_social) — Вакансии и карьерные возможности для молодых специалистов.
- **Лучшие вакансии** — [@vacanciesbest](https://t.me/vacanciesbest) — Отобранные вакансии по разным функциям и уровням.
- **Топовые вакансии \| Петр Липов** — [@jobinspb](https://t.me/jobinspb) — Вакансии Санкт-Петербурга и управление карьерой.
- **Неустойчивое развитие** — [@nongreta](https://t.me/nongreta) — Экология, ESG и устойчивое развитие — вакансии и повестка.
- **Юридические вакансии** — [@legal_jobs](https://t.me/legal_jobs) — In house, consulting, litigation, corporate, M&A.
- **HelloLawyer Jobs** — [@hellolawyer_jobs](https://t.me/hellolawyer_jobs) — Legal Counsel, Compliance, IP, Regulatory.
- **Вакансии строительство** — [@vacancii_construction](https://t.me/vacancii_construction) — РП, ПТО, архитекторы, инженеры, сметчики.
- **Мосинжпроект** — [@mosinzproekt](https://t.me/mosinzproekt) — Карьерный канал работодателя (ГИП, сметчики, IT).
- **JavaScript Jobs** — [@javascript_jobs](https://t.me/javascript_jobs) — Frontend, JS, TypeScript.
- **Python Jobs** — [@ru_pythonjobs](https://t.me/ru_pythonjobs) — Python.
- **Java Jobs** — [@java_jobs](https://t.me/java_jobs) — Java/Kotlin.
- **JavaDevJob** — [@javadevjob](https://t.me/javadevjob) — Ещё один поток Java.
- **Golang Jobs** — [@golangjob](https://t.me/golangjob) — Go (Golang).
- **Mobile Dev Jobs** — [@mobile_jobs](https://t.me/mobile_jobs) — iOS, Android.
- **MobileDevJob** — [@mobiledevjob](https://t.me/mobiledevjob) — Mobile (общее).
- **PR вакансии и стажировки** — [@prvacant](https://t.me/prvacant) — От стажёра до руководителя.


## ⚙️ Как это работает

| Механизм | Где | Что делает |
|---|---|---|
| `Database.ensure_default_sources()` | `main.py` при старте | досеивает новые источники **в уже существующую БД** без дублей (`canonical_url`), в логе: `Добавлено новых источников вакансий в БД: N` |
| `source_issues` | `vacancy_parser.py` | собирает нечитаемые источники (закрытое превью, 403, таймаут) и показывает их блоком — «пустая выдача» не выглядит как «вакансий нет» |
| `_pick_title_and_snippet()` | там же | заголовком вакансии становится первая строка с буквами/цифрами — эмодзи-строки (`🔥`, `🆕`) пропускаются |
| `parse_remoteok_api()` | там же | парсит JSON API RemoteOK (позиция, компания, теги, зарплата, дата по `epoch`) |
| `format_vacancies_search_blocks()` | там же | отдаёт сообщение двумя блоками (`body` + `footer`), чтобы предупреждения и дисклеймер не обрезались |
| Проверка дублей | тесты | `test_sources_total_and_uniqueness`, `test_tgstat_channels_no_duplicates` — уникальность `canonical_url` и `username` |

### Добавить свой источник

```
/add_source https://t.me/your_channel     # канал: проверка доступности превью
/add_source https://example.com/vacancies # сайт: проверка HTTP-ответа
```
Ответ — «✅ добавлен» либо «⚠️ этот источник уже есть в базе данных» (с названием, типом и проверкой ссылки). Список: `/sources`, удаление: `/remove_source <ссылка>`.

### Ограничения (честно)

- Один поиск = 163 параллельных HTTP-запросов → обычно 10–25 секунд.
- Часть площадок (Indeed, Glassdoor, ZipRecruiter, CareerBuilder, WantApply, Remote.co) закрыта антибот-защитой — без платных API их не обойти.
- Ряд каналов отключил публичное веб-превью (`@Uyut_frilans`, `@tomato1000`, `@devops_jobs`, `@java_jobs`, `@uiux_jobs`, `@job_in_hr`, `@HoReCa_HR` и др.) — бот показывает их в блоке «⚠️ Часть источников не удалось прочитать» со ссылкой, вакансии по ним смотрите вручную.
- `@fuck_the_frameworks` и `SuperJob` выведены из поиска (закрытое превью / нет совпадений с профилем): записи в базе погашены `is_active = 0`, предупреждения больше не показываются.
- Актуальность ссылок и состав каналов меняются. Дисклеймер: «Ссылки могут меняться. Актуальность вакансий проверяйте на официальных сайтах компаний, в Telegram-каналах или на агрегаторах (hh.ru, hirify.me).»

---

## 🧩 Профиль резюме: должность и навыки (`/set_role`, `/set_skills`, `/reset_profile`)

При загрузке резюме бот сам определяет **целевую должность** и **ключевые навыки** (`build_resume_profile()`), которые затем используются в поиске вакансий и в адаптации под стандарты.

Что гарантируется:

- **ФИО никогда не подставляется вместо должности или навыка** — имя определяется отдельной функцией `is_probable_person_name()` и хранится только как метаданные (`detect_candidate_name()`).
- Должность ищется в порядке: явное «Должность / Позиция / Целевая должность» → название профессии в первых строках → название профессии в блоке опыта. Поддерживаются `коммерческий директор`, `руководитель отдела продаж`, `HR-директор`, `Python-разработчик`, `начальник отдела логистики` и т.п.
- Навыки берутся из словаря (IT + бизнес/офис: `P&L`, `Excel`, `1C`, `CRM`, `OTB`, `KPI`, `Category Management` …), из многострочного блока «Навыки:» и из технологических токенов (`ERP`, `SAP`, `BI`).
- Если ничего не распознано — бот честно пишет «⚠️ не распознана/не найдены» и предлагает команды:

| Команда | Назначение |
|---|---|
| `/set_role Коммерческий директор` | задать целевую должность вручную |
| `/set_skills P&L, Excel, CRM, 1C` | задать ключевые навыки вручную |
| `/reset_profile` | пересобрать профиль из сохранённого текста резюме |

**Авто-починка старых записей:** при старте бот вызывает `repair_invalid_resume_profiles()` — если в базе сохранён профиль, где роль или навыки равны ФИО, они пересобираются автоматически (в логе: «Исправлено профилей резюме…»).

---

## 🛠 Стек бесплатных инструментов

| Компонент | Инструмент | Стоимость |
|---|---|---|
| Язык и фреймворк бота | Python 3.11+ / `aiogram 3.x` | Бесплатно (MIT) |
| База данных | `SQLite 3` + `aiosqlite` | Бесплатно (встроена, не нужен сервер БД) |
| Парсинг ТГ-каналов и сайтов | `aiohttp` + `BeautifulSoup4` + `t.me/s/...` + `api.hh.ru` | Бесплатно (без Userbot SIM и платных прокси) |
| Обработка и генерация документов | `pypdf` (PDF) + `python-docx` (DOCX) | Бесплатно (Open Source) |
| Адаптация резюме | Встроенный ATS/STAR-движок + опционально Groq Free Tier / Ollama | Бесплатно |
| CI/CD и автотесты | `pytest` + `GitHub Actions` (`.github/workflows/unpack_zip.yml`) | Бесплатно на GitHub |

---

## 📂 Структура репозитория

```text
├── README.md                        # Документация проекта (реестр источников — ниже)
├── requirements.txt                 # Зависимости Python
├── .env.example                     # Шаблон переменных окружения
├── .gitignore                       # Исключения Git
├── Dockerfile / docker-compose.yml  # Запуск в контейнере
├── check_bot_ready.py               # Предполётная проверка (18 модулей, getMe, роутеры)
├── unpack_and_setup.py              # Self-extracting установщик (со встроенным архивом)
├── unpack_windows.bat               # Распаковщик для Windows
├── unpack_linux_mac.sh              # Распаковщик для Linux/macOS
├── .github/workflows/
│   ├── run_bot.yml                  # Запуск бота на бесплатном GitHub Runner (+preflight)
│   └── unpack_zip.yml               # Распаковка zip, pytest и авто-коммит в ветку
├── main.py                          # Точка входа: БД, досев источников, авто-починка профилей
├── bot/
│   ├── config.py                    # Настройки из .env (BOT_TOKEN, LLM_*, таймауты)
│   ├── database.py                  # SQLite: резюме, стандарты, источники (DEFAULT_SOURCES — 53)
│   ├── keyboards.py                 # Кнопки меню и периодов (1 день / 1 неделя / 1 месяц)
│   ├── states.py                    # FSM-состояния диалогов
│   ├── handlers/
│   │   ├── common.py                # /start, /help, /cancel
│   │   ├── resume.py                # Загрузка резюме, /set_role, /set_skills, /reset_profile
│   │   ├── standards.py             # Стандарты рынка внутри бота (Framework 2026+)
│   │   ├── resources.py             # /find_resources, /channels, /aggregators, /companies
│   │   ├── sources.py               # Добавление источников с проверкой дублей и доступности
│   │   └── search.py                # Поиск вакансий за 1 день / 1 неделю / 1 месяц
│   └── services/
│       ├── file_extractor.py        # PDF/DOCX/TXT → текст, профиль (роль, навыки), self-repair
│       ├── market_standards.py      # Золотой стандарт, аудит, адаптация, DOCX, опциональный LLM
│       ├── resource_catalog.py      # Каталог: 43 канала, 20 агрегаторов, 30 компаний
│       ├── search_assistant.py      # Алгоритм поиска ресурсов + формат выдачи + дисклеймер
│       ├── source_manager.py        # Нормализация ссылок, проверка доступности и дублей
│       └── vacancy_parser.py        # Парсер TG/RSS/JSON API/HTML + source_issues
├── docs (в корне):
│   ├── SOURCES_FROM_TGSTAT.md       # Разбор 23 каналов из подборки TGStat (22 добавлено)
│   ├── ADDED_TELEGRAM_CHANNELS.md   # первая партия: 12 HR/карьерных каналов
│   ├── INTERNATIONAL_JOB_BOARDS.md  # 9 зарубежных бордов: проверка и стратегии
│   ├── UPDATE_2026-11-18.md         # Манифест обновления
│   └── LAUNCH_GITHUB_ACTIONS.md     # Гайд запуска и таблица типовых ошибок
├── examples/                        # Примеры: ideal_executive_cv_2026_example.md/.docx
└── tests/
    └── test_bot_services.py         # 20 тестов pytest
```

---

## 🔁 Обновление файлов через GitHub Actions

1. Скачайте `find_job_in_www_bot.zip` и загрузите его в корень репозитория (**Add file → Upload files**, коммит в `main`).
2. Workflow **«Unpack ZIP Archive & Run Tests (CI)»** автоматически: распакует архив → прогонит `pytest` → закоммитит файлы в `main` → удалит архив.
3. Проверить результат: вкладка **Actions** (последний запуск должен быть ✅) и корень репозитория (появились `bot/services/search_assistant.py`, `examples/` и т.д.).

**Если запуск упал на шаге «Commit and push»** — это гонка двух одновременных запусков (второй push отклоняется как *non-fast-forward*). В актуальной версии workflow это исправлено: добавлены `concurrency: unpack-<ref>` и повторный push с синхронизацией (`fetch` + `reset` + retry). Так как `GITHUB_TOKEN` не имеет права изменять файлы внутри `.github/workflows/`, обновить сам workflow нужно один раз вручную: **Actions → Unpack ZIP Archive & Run Tests (CI) → ⋯ → View file → ✏️ Edit** и вставить содержимое [`.github/workflows/unpack_zip.yml`](.github/workflows/unpack_zip.yml).

---

## 🚀 Запуск в Telegram через GitHub Actions

Полная пошаговая инструкция: **[LAUNCH_GITHUB_ACTIONS.md](LAUNCH_GITHUB_ACTIONS.md)**.

Кратко:
1. Токен от **@BotFather** → **Settings → Secrets and variables → Actions → New repository secret**: имя `BOT_TOKEN`.
2. Один раз вручную создать `.github/workflows/run_bot.yml` (содержимое — в файле `.github/workflows/run_bot.yml` проекта), т.к. `GITHUB_TOKEN` не может пушить workflow-файлы.
3. **Actions → Run Telegram Bot (GitHub Actions Free Runner) → Run workflow** → длительность сессии (до 350 мин).
4. В логах шаг **Preflight check** подтвердит `getMe` и отсутствие webhook; в Telegram отправьте боту `/start`.

Ограничение бесплатного раннера — 6 часов на один запуск; для 24/7 используйте Railway/Render/VPS (команда `python main.py`).

---

## 🩺 Проверка перед запуском в Telegram (`check_bot_ready.py`)

Перед первым запуском выполните одну команду — она проверит всё, что нужно боту:

```bash
python check_bot_ready.py --online
```

Скрипт проверяет:

| Проверка | Что ловит |
|---|---|
| Python 3.10+ и зависимости | отсутствующие `aiogram`, `aiosqlite`, `python-docx`, `pypdf` и др. |
| Файл `.env` и формат `BOT_TOKEN` | пустой/заглушечный токен, лишние пробелы и кавычки |
| `.gitignore` | не исключён `.env` (риск утечки токена в репозиторий) |
| SQLite | права на запись, создание схемы, 9 предзаполненных источников |
| Импорт всех 18 модулей | ошибки синтаксиса/циклических импортов |
| **Холодный старт** | БД + `Bot` + `Dispatcher` + 6 роутеров, 34 обработчика сообщений, 11 callback |
| `getMe` + `getWebhookInfo` | отклонённый токен и **установленный webhook** (он ломает polling) |
| LLM-ключ | напоминание, что бот работает и без него |

Выход `0` — можно запускать `python main.py`. Выход `1` — есть блокеры, скрипт перечислит их в конце.

---

## 🚀 Быстрый старт и запуск

### 1. Получите бесплатный токен бота в Telegram
1. Откройте [@BotFather](https://t.me/BotFather) в Telegram.
2. Отправьте команду `/newbot`, укажите имя и юзернейм бота.
3. Скопируйте полученный `BOT_TOKEN`.

### 2. Настройте окружение
```bash
cp .env.example .env
# Укажите ваш BOT_TOKEN внутри файла .env
```

### 3. Установите зависимости и запустите бота
```bash
python -m venv .venv
source .venv/bin/activate  # Для Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 4. Запуск автотестов
```bash
pytest -v
```

---

## 📦 Как опубликовать проект в репозиторий `find_job_in_www_bot`

Удалённый репозиторий `origin` уже настроен на `https://github.com/andrey9653246431-spec/find_job_in_www_bot.git`:

```bash
git clone https://github.com/andrey9653246431-spec/find_job_in_www_bot.git
# Или для отправки из текущей папки проекта:
git remote set-url origin https://github.com/andrey9653246431-spec/find_job_in_www_bot.git
git branch -M main
git push -u origin main
```

После пуша на вкладке **[Actions](https://github.com/andrey9653246431-spec/find_job_in_www_bot/actions)** в вашем репозитории GitHub автоматически запустится бесплатный workflow `Python CI`, который проверит все тесты бота.
