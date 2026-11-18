# 🚀 Запуск бота в Telegram через GitHub Actions (бесплатно)

Пошагово, 10–15 минут. Всё, кроме токена, уже проверено и работает (8 тестов ✅, холодный старт ✅).

---

## Шаг 0. Что понадобится

| Что | Где взять | Стоимость |
|---|---|---|
| Токен бота | Telegram → **@BotFather** → `/newbot` (или `/mybots` → API Token) | бесплатно |
| Репозиторий | `andrey9653246431-spec/find_job_in_www_bot` | уже есть |
| GitHub Actions | вкладка **Actions** в репозитории | бесплатно для публичных репозиториев |

> ⚠️ GitHub Actions останавливает любой job через **6 часов** (у нас лимит 355 минут). Бот будет жить в течение одной сессии; для круглосуточной работы нужен хостинг (Railway / Render / VPS) — см. последний раздел.

---

## Шаг 1. Получить токен и проверить его формат

1. В Telegram откройте **@BotFather** → `/newbot` → имя → username (должен заканчиваться на `bot`).
2. Скопируйте строку вида `1234567890:AAH...` (после двоеточия — ~35 символов).
3. Проверить, что токен живой, можно прямо в браузере:
   `https://api.telegram.org/bot<ВАШ_ТОКЕН>/getMe`
   Должен вернуться JSON `{"ok":true,"result":{"username":"..."}}`.
   Если `{"ok":false,"error_code":401}` — токен скопирован с ошибкой или отозван.

---

## Шаг 2. Добавить секрет `BOT_TOKEN`

1. Откройте: **Settings → Secrets and variables → Actions**
   `https://github.com/andrey9653246431-spec/find_job_in_www_bot/settings/secrets/actions`
2. **New repository secret**
3. **Name:** `BOT_TOKEN` (ровно так, без пробелов)
4. **Secret:** вставьте токен (без кавычек и переводов строки)
5. **Add secret**

Опционально (не обязательно — бот работает и без них):

| Секрет | Значение |
|---|---|
| `LLM_API_KEY` | ключ бесплатного Groq (`console.groq.com/keys`) или OpenRouter Free |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` (по умолчанию уже так) |
| `LLM_MODEL` | `llama-3.3-70b-versatile` |

---

## Шаг 3. Добавить workflow запуска (один раз, вручную)

GitHub-токен Actions не имеет права создавать файлы в `.github/workflows/`, поэтому этот файл добавляется руками:

1. Откройте `https://github.com/andrey9653246431-spec/find_job_in_www_bot/new/main/.github/workflows`
   (либо **Add file → Create new file** и введите путь `.github/workflows/run_bot.yml`)
2. **Имя файла:** `.github/workflows/run_bot.yml`
3. Вставьте содержимое файла `.github/workflows/run_bot.yml` из проекта (он открыт в просмотрщике справа).
4. **Commit changes** → коммит в ветку `main`.

Что делает этот workflow:
- восстанавливает SQLite-базу из кэша;
- ставит зависимости;
- **делает предполётную проверку** `check_bot_ready.py --online` (формат токена, `getMe`, отсутствие webhook, БД, роутеры);
- запускает `python -u main.py` на N минут (по умолчанию 60, максимум 350);
- сохраняет базу обратно в кэш;
- отличает штатное завершение по таймауту от падения (в логах будет код).

---

## Шаг 4. Запустить бота

1. Вкладка **Actions** → слева **Run Telegram Bot (GitHub Actions Free Runner)**
2. Справа **Run workflow** → ветка `main` → `run_duration_minutes` = `60` (или сколько нужно, максимум 350)
3. **Run workflow**
4. Через 30–60 секунд откройте запуск → job `run-bot` → шаг **Preflight** должен показать:
   ```
   ✅ Telegram принял токен (getMe)   @ваш_бот · id 1234567890
   ✅ Webhook не установлен — long polling будет работать
   ✅ Холодный старт проходит без ошибок
   ```
5. В Telegram отправьте боту **/start** — должно прийти главное меню с кнопками.

> Бот живёт, пока идёт job (вверху страницы будет «in progress»). Логи обновляются в реальном времени: шаг **Run Telegram Bot with GitHub Secrets**.

---

## Шаг 5. Проверка функций (2 минуты)

| Действие в боте | Что должно произойти |
|---|---|
| `/start` | меню с 7 кнопками |
| `/example_cv` | эталонный Executive CV (текст + `.docx`) |
| `/find_resources` | ТГ-каналы / агрегаторы / компании по отраслям |
| `/upload_resume` → пришлите PDF/DOCX/TXT | «Резюме загружено», извлечена должность и навыки (ФИО в профиль не попадает) |
| `/my_resume` | профиль: ФИО, целевая должность, навыки; если что-то не распознано — подсказка с `/set_role` |
| `/set_role`, `/set_skills`, `/reset_profile` | ручное уточнение профиля и пересборка из текста |
| `/adapt_resume` | адаптация по Золотому стандарту + файл `Ideal_Executive_CV_2026.docx` |
| `/search` → «1 неделя» | список вакансий из ТГ-каналов и hh.ru |

---

## 🧯 Если не запускается — таблица ошибок

| Симптом в логах Actions | Причина | Что делать |
|---|---|---|
| `❌ BOT_TOKEN не задан` | секрет не добавлен или назван иначе | Settings → Secrets → имя ровно `BOT_TOKEN`, затем **перезапустить** workflow |
| Шаг Preflight упал с **exit code 2** | `python` не нашёл файл `check_bot_ready.py` (его нет в репозитории) | загрузите `find_job_in_www_bot.zip` в корень репозитория **или** используйте обновлённый workflow — в нём есть резервная проверка через `getMe` (`curl`) |
| `Telegram отклонил токен: Unauthorized` | токен отозван / вставлен не полностью | `/revoke` в @BotFather → новый токен → обновить секрет |
| `У бота установлен webhook — polling не заработает` | ранее ставили webhook | `https://api.telegram.org/bot<TOKEN>/deleteWebhook?drop_pending_updates=true` |
| Вкладка Actions пустая / нет кнопки Run workflow | workflow лежит не в `.github/workflows/` или не в `main` | Проверьте путь файла: `.github/workflows/run_bot.yml`, ветка по умолчанию `main` |
| `Error: This request has been automatically failed because it uses a deprecated...` | устаревшая версия action | Обновите `actions/checkout@v4`, `setup-python@v5` (уже стоит в файле) |
| Джоб «убит» через 6 часов | лимит GitHub Actions | Запустите новый ран или используйте хостинг |
| Бот молчит, но job зелёный | другой экземпляр бота уже работает с этим токеном (два polling конфликтуют) | Остановите второй запуск: Actions → предыдущий run → **Cancel workflow** |
| `sqlite3.OperationalError: unable to open database file` | нет каталога `data/` | В проекте он создаётся автоматически; проверьте, что `DB_PATH=data/bot_database.sqlite3` |
| `409 Conflict: terminated by other getUpdates request` | запущены 2 копии бота | Оставьте одну: у workflow уже есть `concurrency: telegram-bot-runner` |

---

## 🔁 Как продлить работу бота

- **Вариант A (вручную):** каждые ~5,5 часов запускать workflow снова (Run workflow).
- **Вариант B (по расписанию):** в `.github/workflows/run_bot.yml` раскомментируйте блок
  ```yaml
  schedule:
    - cron: "0 */6 * * *"
  ```
  ⚠️ GitHub может задерживать cron-запуски на 5–20 минут; бот будет простаивать между сессиями.
- **Вариант C (24/7, бесплатный тариф):** Railway / Render / Fly.io — команда запуска `python main.py`,
  переменные `BOT_TOKEN` и `DB_PATH=data/bot_database.sqlite3`, диск — постоянный volume на `data/`.

---

## ✅ Что уже проверено в проекте

- `pytest -q` → **8 passed** (Executive CV 2026+, пример резюме, алгоритм поиска, источники, парсинг).
- `python check_bot_ready.py` → 18 модулей импортируются, холодный старт: 6 роутеров, 34 обработчика, 11 callback, SQLite с 9 источниками.
- `api.telegram.org` доступен, токен валидируется через `getMe`, webhook-конфликт детектируется.

**Единственное, чего не хватает для старта, — секрет `BOT_TOKEN` (Шаг 2) и файл workflow в `.github/workflows/` (Шаг 3).**
