# Третья подборка источников: разбор присланного списка (18.11.2026)

Присланный файл: `Qwen_csv_20261118_2st22n8r9.txt` — **95 строк**, разделитель `;`, колонки `ID;Название;URL;Категория;Специфика/Комментарий`.

| Что было в списке | Сколько |
|---|---|
| Сайты и job-борды (ID 7–27) | 21 |
| Telegram-каналы по профессиям и отраслям (ID 28–105) | 74 |
| **Всего** | **95** |

## 1. Как проверялось (и почему именно так)

1. **Дубли** — сверка `canonical_url` с `DEFAULT_SOURCES` без учёта регистра (ники в Telegram регистронезависимы) и сверка ников с каталогом `/find_resources`.
2. **Telegram** — каждый ник запрошен через публичное веб-превью `https://t.me/s/<ник>`: берутся `og:title` (реальное название канала) и число сообщений в ленте. Совпадение названия с присланным списком проверялось обязательно.
3. **Сайты** — HTTP-запрос с браузерным User-Agent: статус, тип ответа (HTML/JSON/RSS), затем прогон страницы через парсер бота, чтобы понять, есть ли вакансии в HTML.
4. **Ничего не выдумывается:** неподтверждённый ник не добавляется, а попадает в раздел «Не добавлено».

## 2. Сайты (21)

| ID | Название | URL | HTTP | Статус |
|---|---|---|---|---|
| 7 | Getmatch | https://getmatch.ru/ | 200 | 🔗 добавлен: ручной поиск (выдача рендерится JS) |
| 8 | Буду | https://budu.jobs/ | 200 | ✅ добавлен: HTML-лента, бот находит вакансии |
| 9 | Facancy | https://facancy.ru/ | 200 | 🔗 добавлен: ручной поиск (в HTML нет вакансий) |
| 10 | Changellenge | https://changellenge.com/ | 200 | 🔗 добавлен: ручной поиск (карьерная платформа, JS) |
| 11 | InGame Job | https://ingamejob.com/ | 200 | 🔗 добавлен: ручной поиск (JS-выдача) |
| 12 | Remote Job | https://remote-job.ru/ | 200 | ✅ добавлен: HTML-лента, бот находит вакансии |
| 13 | Careerist | https://careerist.ru/ | 200 | 🔗 добавлен: ручной поиск (JS-выдача) |
| 14 | LinkedIn Jobs | https://www.linkedin.com/jobs/ | 200 | 🔗 добавлен: ручной поиск (LinkedIn закрыт для парсинга) |
| 15 | Indeed | https://www.indeed.com/ | 403 | ♻️ уже был в базе (ручной поиск, 403 Cloudflare) |
| 16 | Glassdoor | https://www.glassdoor.com/ | 403 | ♻️ уже был в базе (ручной поиск, 403 Cloudflare) |
| 17 | Wellfound | https://wellfound.com/jobs | 200 | 🔗 добавлен: ручной поиск (JS-выдача) |
| 18 | Remote OK | https://remoteok.com/ | 200 | ♻️ уже был в базе (JSON API RemoteOK) |
| 19 | We Work Remotely | https://weworkremotely.com/ | 200 | ♻️ уже был в базе (RSS We Work Remotely) |
| 20 | Jooble | https://ru.jooble.org/ | 200 | 🔗 добавлен: ручной поиск (200 OK, но вакансии подгружаются JS) |
| 21 | ГородРабот | https://gorodrabot.ru/ | 423 | 🔗 добавлен: ручной поиск (HTTP 423 — антибот) |
| 22 | Работа России | https://trudvsem.ru/ | 460 | ✅ добавлен: открытые данные API `opendata.trudvsem.ru` (JSON, ≈486 тыс. вакансий) |
| 23 | Avito Работа | https://www.avito.ru/rossiya/vakansii | 439 | 🔗 добавлен: ручной поиск (HTTP 439 — антибот) |
| 24 | YouDo | https://youdo.com/ | 200 | 🔗 добавлен: ручной поиск (JS-приложение) |
| 25 | Kwork | https://kwork.ru/ | 200 | 🔗 добавлен: ручной поиск (JS-приложение) |
| 26 | FL.ru | https://www.fl.ru/ | 200 | 🔗 добавлен: ручной поиск (JS-выдача) |
| 27 | ccwork | https://ccwork.io/ | ERR | ❌ не добавлен: домен `ccwork.io` не отвечает (DNS/соединение) |

Итог: **16 добавлено** (1 — открытые данные API «Работа России», 2 — HTML-ленты, 13 — площадки ручного поиска), **4 уже были в базе** (Indeed, Glassdoor, RemoteOK, We Work Remotely), **1 недоступен** (`ccwork.io` — домен не отвечает, поэтому ссылку не добавлял: «Проверьте актуальность ссылки»).

## 3. Telegram-каналы (74)

### 3.1 Добавлено: 55 канала с открытой лентой

| @ник | Название в Telegram (`og:title`) | Сообщений в превью |
|---|---|---|
| [@forchiefs](https://t.me/forchiefs) | Job for Chiefs (TOP vacancies) | 20 |
| [@vakansii_top_manager](https://t.me/vakansii_top_manager) | TOP Management - вакансии руководителей и директоров | 20 |
| [@ExecCareer](https://t.me/ExecCareer) | Карьера ТОП и Executive Search | 20 |
| [@forproducts](https://t.me/forproducts) | Job for Products and Projects | 20 |
| [@product_jobs](https://t.me/product_jobs) | Вакансии для продактов и проджектов | 20 |
| [@analytics_jobs](https://t.me/analytics_jobs) | BA & SA Jobs | Работа для бизнес и системных аналитиков | 20 |
| [@datasciencejobs](https://t.me/datasciencejobs) | Data Science Jobs | 20 |
| [@ru_pythonjobs](https://t.me/ru_pythonjobs) | Вакансии для Python-разработчиков / Python Jobs | 3 |
| [@javadevjob](https://t.me/javadevjob) | Java jobs — вакансии для java-разработчиков | 20 |
| [@golangjob](https://t.me/golangjob) | Golang Jobs | 20 |
| [@mobiledevjob](https://t.me/mobiledevjob) | Mobile jobs — вакансии для мобильных разработчиков | 20 |
| [@forallqa](https://t.me/forallqa) | Job for QA | 20 |
| [@it_vakansii_jobs](https://t.me/it_vakansii_jobs) | СЕТИ — IT & Digital вакансии | 20 |
| [@fordesigner](https://t.me/fordesigner) | Job for Designers | 20 |
| [@designer_vacancies](https://t.me/designer_vacancies) | Вакансии для дизайнеров | 20 |
| [@uxui_designer_vacancies](https://t.me/uxui_designer_vacancies) | Вакансии UX UI дизайнеров | 20 |
| [@design_jobs_uxui](https://t.me/design_jobs_uxui) | Вакансии для Дизайнеров | 20 |
| [@forallmarketing](https://t.me/forallmarketing) | Job for Marketing | 20 |
| [@dnative_job](https://t.me/dnative_job) | Вакансии SMM и Digital | 20 |
| [@prvacant](https://t.me/prvacant) | PR Вакансии и стажировки | 20 |
| [@vakansii_0](https://t.me/vakansii_0) | Work Hunter – удаленная работа. Вакансии: маркетинг, SMM, PR, Digital | 20 |
| [@vakansiitelegramm](https://t.me/vakansiitelegramm) | Вакансии Закупщик Telegram / TG ADS | 20 |
| [@forallmedia](https://t.me/forallmedia) | Job for Media & Content | 20 |
| [@perezvonyu](https://t.me/perezvonyu) | Мы вам перезвоним | 20 |
| [@mskeventjob](https://t.me/mskeventjob) | Event hunter - вся творческая работа Москва | 19 |
| [@forhr](https://t.me/forhr) | Job for HR (IT & Digital) | 20 |
| [@hr_jobs_rabota](https://t.me/hr_jobs_rabota) | Вакансии для HR / IT рекрутеров | 20 |
| [@hrorhr](https://t.me/hrorhr) | эйчарли | HR вакансии | 20 |
| [@hrhubvacancy](https://t.me/hrhubvacancy) | HR[хаб]вакансии | 20 |
| [@hrhubvacancy300](https://t.me/hrhubvacancy300) | 300HR[хаб]вакансии | 20 |
| [@hrhubjunior](https://t.me/hrhubjunior) | HR[хаб]junior | 20 |
| [@legal_jobs](https://t.me/legal_jobs) | Юридические вакансии | 20 |
| [@hellolawyer_jobs](https://t.me/hellolawyer_jobs) | hellolawyer | вакансии для юристов | 16 |
| [@cfo_ifrs](https://t.me/cfo_ifrs) | Вакансии в CFO/IFRS | 20 |
| [@cfosearch](https://t.me/cfosearch) | CFO GO | Онлайн-агрегатор вакансий для финансистов | 20 |
| [@fintech_work](https://t.me/fintech_work) | Работа в финтехе | Fintech, Crypto, Blockchain вакансии | 20 |
| [@paymentcardjobs](https://t.me/paymentcardjobs) | FintechJob: Сards & Payments | 20 |
| [@forallsales](https://t.me/forallsales) | Job for Sales & BizDev | 20 |
| [@sales_work](https://t.me/sales_work) | Sales Work | вакансии в продажи | 20 |
| [@sales_manager_job](https://t.me/sales_manager_job) | Менеджер по продажам в IT - вакансии | 20 |
| [@salestalents](https://t.me/salestalents) | Таланты продаж | 4 |
| [@careerspace](https://t.me/careerspace) | careerspace | 14 |
| [@bizservisjob](https://t.me/bizservisjob) | Вакансии и резюме в клиентском сервисе | 20 |
| [@cstalents](https://t.me/cstalents) | Таланты Customer Success | 20 |
| [@getassistant_vacancy](https://t.me/getassistant_vacancy) | Вакансии: ассистенты, бизнес-ассистенты, личные помощники - GetAssista | 20 |
| [@assisteca_job](https://t.me/assisteca_job) | Ассистека: вакансии для ассистентов | 20 |
| [@pomochnik_vakansii](https://t.me/pomochnik_vakansii) | Менеджер | Ассистент | Работа | 20 |
| [@mosinzproekt](https://t.me/mosinzproekt) | МОСИНЖПРОЕКТ | 13 |
| [@JobinPharma](https://t.me/JobinPharma) | ФАРМА. Вакансии | 19 |
| [@lapainpharma](https://t.me/lapainpharma) | Лапа в фарме | Вакансии, резюме в фармацевтической сфере | 20 |
| [@pharmed_recruitment](https://t.me/pharmed_recruitment) | 💉Фарма&Медикал Рекрутмент / Вакансии в Фарме, Работа в Фарме | 20 |
| [@superjob_medicina](https://t.me/superjob_medicina) | Работа / Медицина / Вакансии | 20 |
| [@rujobinfood](https://t.me/rujobinfood) | Общепит - работа есть! | 20 |
| [@expresswaiter](https://t.me/expresswaiter) | ♨️ EW ♨️ - Вакансии, Работа, Общепит, Ресторан, Повар, Официант | 20 |
| [@nanyatassistenta](https://t.me/nanyatassistenta) | ИЩУ АССИСТЕНТА \| Размещение вакансий | 20 |

> **Исправление в присланном нике.** ID 91 был указан как `@nanyatassistentа` — в конце стояла **кириллическая «а»**, такого канала не существует. Проверка похожих ников дала реальный `@nanyatassistenta` («ИЩУ АССИСТЕНТА | Размещение вакансий», лента открыта, 20 сообщений) — он и добавлен. Ровно тот случай, когда ник нельзя копировать вслепую.

### 3.2 Дубли — исключены (3)

| @ник | Название в списке | Почему дубль |
|---|---|---|
| [@vacancyCRC](https://t.me/vacancyCRC) | Вакансии CRC | добавлен во второй подборке |
| [@vacanciesbest](https://t.me/vacanciesbest) | Facancy / лучшие вакансии | добавлен в первой партии HR-каналов |
| [@rabota_freelancee](https://t.me/rabota_freelancee) | Marketing / SMM / Digital Remote | добавлен в подборке TGStat |

### 3.3 Каналы с закрытым веб-превью (16): в базе, но без автопоиска

Каналы существуют (подтверждено по `og:title`), но владельцы отключили публичную ленту `t.me/s/`. Бот **оставляет их в источниках** и честно пишет в блоке «⚠️ Часть источников не удалось прочитать» с ссылкой — вместо тихого пропуска.

| @ник | Название в Telegram (`og:title`) |
|---|---|
| [@executive_jobs](https://t.me/executive_jobs) | Executive & C-Level вакансії |
| [@jobs_for_it_analyst](https://t.me/jobs_for_it_analyst) | Работа ИТ аналитикам (системные и бизнес аналитики) |
| [@devops_jobs](https://t.me/devops_jobs) | DevOps Jobs - работа и аналитика |
| [@javascript_jobs](https://t.me/javascript_jobs) | JavaScript Jobs — чат |
| [@java_jobs](https://t.me/java_jobs) | Java Jobs |
| [@mobile_jobs](https://t.me/mobile_jobs) | Mobile Dev Jobs — вакансии и резюме |
| [@uiux_jobs](https://t.me/uiux_jobs) | UI/UX Jobs — вакансии и аналитика |
| [@job_in_hr](https://t.me/job_in_hr) | HR Вакансии и работа кадровиком, HR рекрутером |
| [@working_in_finance](https://t.me/working_in_finance) | Вакансии бухгалтерам, экономистам, аналитикам, работа 1С. |
| [@work_in_accounting](https://t.me/work_in_accounting) | Работа бухгалтерам, аналитикам и по 1С. Финансовые вакансии. |
| [@vacancii_construction](https://t.me/vacancii_construction) | Работа, Вакансии, строительство: Руководитель проектов, начальник учас |
| [@job_in_med](https://t.me/job_in_med) | Медицинские вакансии. Работа врачам |
| [@job_in_zdrav](https://t.me/job_in_zdrav) | Медицина, врачи. Вакансии и работа для врачей, докторов, в больницах,  |
| [@HoReCa_HR](https://t.me/HoReCa_HR) | Общепит работа | HoReCa Вакансии |
| [@expresswaiter_vacancy](https://t.me/expresswaiter_vacancy) | EW - Работа, Общепит, Ресторан, Вакансии, Повар, Официант, HoReCa, Мос |
| [@exwaiters](https://t.me/exwaiters) | EW - Повар, Общепит, Ресторан, Вакансии, Общепит, Работа, HoReCa |

## 4. Что изменилось в проекте

| Показатель | Было | Стало |
|---|---|---|
| Источников в `DEFAULT_SOURCES` | 78 | **165** (136 Telegram + 29 сайтов) |
| Каналов в каталоге `/find_resources` | 68 | **139** |
| Сайтов-агрегаторов в каталоге | 20 | **32** |
| Тестов | 22 | **24** |
| Живой прогон (7 дней, «Директор по маркетингу») | 271 вакансия | **410 вакансий** |
| Предупреждений о закрытых превью | 3 | 19 (16 новых + 3 прежних) |

Новое в коде:

- `parse_trudvsem_api()` + `_fetch_trudvsem_api_vacancies()` в `bot/services/vacancy_parser.py` — чтение открытых данных портала «Работа России» (`opendata.trudvsem.ru/api/v1/vacancies`), ссылка на первоисточник берётся из поля `vac_url`, которое отдаёт сам API.
- Запросы к hh.ru и «Работе России» теперь строятся **по должности**, навыки используются только для ранжирования: прежний запрос «должность + 3 навыка» отдавал 0 вакансий.
- Блок ручного поиска расширен: до 12 площадок + «…и ещё N — полный список в /find_resources».
- `tools/regen_readme_registry.py` — реестр README теперь **генерируется из кода** и не может разойтись с базой.
- Тесты: `test_third_batch_channels_and_sites_added` (21) и `test_trudvsem_api_parser` (22).

## 5. Честные ограничения

- 16 каналов из списка закрыли веб-превью: их вакансии бот прочитать не может — только показать ссылку и предупреждение. Это ограничение Telegram, а не бота.
- 13 сайтов из списка отдают вакансии только через JavaScript или антибот — они добавлены как «ручной поиск», бот формирует ссылку под профиль.
- `ccwork.io` не отвечает — не добавлен. Если сайт переедет на новый домен, пришлите ссылку, и источник будет добавлен.
- Часть каналов-«потоков» (например, `@ru_pythonjobs` — 3 сообщения в превью) публикует мало постов; выдача по ним невелика, но каналы живые.
- Свежесть вакансий ограничена периодом 1/7/30 дней и датой в самом сообщении — если канал не указывает дату в тексте, используется дата публикации сообщения.

## 6. Проверочные команды

```bash
PYTHONPATH=/home/user python -c "from bot.database import DEFAULT_SOURCES; print(len(DEFAULT_SOURCES))"   # 165
python -m pytest -q                                                                                      # 24 passed
python check_bot_ready.py                                                                              # 165 источников по умолчанию
PYTHONPATH=/home/user python tools/regen_readme_registry.py                                             # реестр README
```
