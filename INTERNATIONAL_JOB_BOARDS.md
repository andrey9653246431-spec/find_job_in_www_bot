# 🌍 Международные job-борды: проверка и подключение (18.11.2026)

## Результаты живой проверки (curl/aiohttp, User-Agent браузера)

| # | Площадка | HTTP | Что отдаёт | Решение |
|---|---|---|---|---|
| 1 | https://www.indeed.com/ | **403** | антибот-заглушка | 🔗 ручной поиск |
| 2 | https://www.glassdoor.com/ | **403** | страница «Security \| Glassdoor» | 🔗 ручной поиск |
| 3 | https://www.ziprecruiter.ie/ | **403** | Cloudflare «Just a moment…» | 🔗 ручной поиск |
| 4 | https://www.careerbuilder.com/ | **403** | заглушка | 🔗 ручной поиск |
| 5 | https://wantapply.com/ | **403** | Cloudflare «Just a moment…» | 🔗 ручной поиск |
| 6 | https://weworkremotely.com/ | **200** | RSS `remote-jobs.rss` (2.2 MB) | ✅ автопоиск |
| 7 | https://remoteok.com/ | **200** | JSON API (`/api`, 642 KB) | ✅ автопоиск |
| 8 | https://remote.co/ | **timeout** | недоступен с хостинга | 🔗 ручной поиск |
| 9 | https://jobspresso.co/ | **200** | RSS `?post_type=job_listing` | ✅ автопоиск |

## Что добавлено в код

- `bot/database.py` → 9 записей в `DEFAULT_SOURCES` с корректным `source_type`:
  `json_api` (RemoteOK), `website` + RSS (WWR, Jobspresso), `manual` (Indeed, Glassdoor, ZipRecruiter, CareerBuilder, WantApply, Remote.co).
- `bot/services/vacancy_parser.py`:
  - `parse_remoteok_api()` — парсит JSON API (позиция, компания, теги, зарплата, дата по `epoch`);
  - `MANUAL_BOARD_LINK_TEMPLATES` + `build_manual_board_link()` — ссылки под профиль;
  - `_format_manual_boards()` — отдельный блок в конце выдачи;
  - `format_vacancies_search_blocks()` → `(body, footer)`, чтобы дисклеймер не обрезался при длинном списке.
- `bot/services/resource_catalog.py` → 9 записей в `AGGREGATORS` (флаг `manual_search: True` у закрытых).
- `bot/handlers/search.py` → длинное сообщение режется **по границе карточки вакансии**, подвал (предупреждения + борды + дисклеймер) уходит отдельным сообщением.

## Живой прогон поиска (профиль «Project Manager», 7 дней)

```
источников в БД: 31 | ручных: 6 | найдено: 73 | issues: 1 (@fuck_the_frameworks)
 7  We Work Remotely (RSS)
 2  GeekJob
 1  RemoteOK (JSON API)
```

Отдельно за 30 дней: RemoteOK — 38 вакансий, We Work Remotely — 67, Jobspresso — 6.

## Ограничение, о котором честно предупреждаем

Indeed, Glassdoor, ZipRecruiter, CareerBuilder, WantApply, Remote.co **нельзя парсить без платных API/прокси** — они блокируют ботов (403/Cloudflare). Бот не выдумывает их вакансии: он даёт проверенную ссылку с подставленным периодом и должностью, а всё остальное — по вашему клику в браузере.
