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
        "canonical_url": "https://t.me/nongreta",
        "parse_url": "https://t.me/s/nongreta",
        "source_type": "tg_channel",
        "title": "TG: Неустойчивое развитие (@nongreta)",
    },
    # --- Подборка TGStat: каналы с вакансиями и карьерой (проверено 18.11.2026 по t.me) ---
    {
        "canonical_url": "https://t.me/theyseeku",
        "parse_url": "https://t.me/s/theyseeku",
        "source_type": "tg_channel",
        "title": "TG: Finder.work: работа и вакансии (@theyseeku)",
    },
    {
        "canonical_url": "https://t.me/hh_ru_official",
        "parse_url": "https://t.me/s/hh_ru_official",
        "source_type": "tg_channel",
        "title": "TG: hh.ru (@hh_ru_official)",
    },
    {
        "canonical_url": "https://t.me/zdemcv",
        "parse_url": "https://t.me/s/zdemcv",
        "source_type": "tg_channel",
        "title": "TG: Ждём резюме | Лайфхакер (@zdemcv)",
    },
    {
        "canonical_url": "https://t.me/digital_jobster",
        "parse_url": "https://t.me/s/digital_jobster",
        "source_type": "tg_channel",
        "title": "TG: Джобстер Digital | Маркетинг | Вакансии и резюме (@digital_jobster)",
    },
    {
        "canonical_url": "https://t.me/hr_affiliate",
        "parse_url": "https://t.me/s/hr_affiliate",
        "source_type": "tg_channel",
        "title": "TG: CPA HUNTER | Вакансии арбитража трафика (@hr_affiliate)",
    },
    {
        "canonical_url": "https://t.me/rabota_freelancee",
        "parse_url": "https://t.me/s/rabota_freelancee",
        "source_type": "tg_channel",
        "title": "TG: Удаленка. Вакансии и резюме (@rabota_freelancee)",
    },
    {
        "canonical_url": "https://t.me/bbe_jobs",
        "parse_url": "https://t.me/s/bbe_jobs",
        "source_type": "tg_channel",
        "title": "TG: Точка входа (@bbe_jobs)",
    },
    {
        "canonical_url": "https://t.me/digitalbroccoli",
        "parse_url": "https://t.me/s/digitalbroccoli",
        "source_type": "tg_channel",
        "title": "TG: Brocli: зарубежный фриланс | лайфхаки (@digitalbroccoli)",
    },
    {
        "canonical_url": "https://t.me/rabota_go",
        "parse_url": "https://t.me/s/rabota_go",
        "source_type": "tg_channel",
        "title": "TG: Работа GO (@rabota_go)",
    },
    {
        "canonical_url": "https://t.me/remote_w0rk",
        "parse_url": "https://t.me/s/remote_w0rk",
        "source_type": "tg_channel",
        "title": "TG: Удаленка (@remote_w0rk)",
    },
    {
        "canonical_url": "https://t.me/Uyut_frilans",
        "parse_url": "https://t.me/s/Uyut_frilans",
        "source_type": "tg_channel",
        "title": "TG: Уютный Фриланс 😸 (@Uyut_frilans)",
    },
    {
        "canonical_url": "https://t.me/workfreelancer",
        "parse_url": "https://t.me/s/workfreelancer",
        "source_type": "tg_channel",
        "title": "TG: Фрилансер: вакансии на удаленке (@workfreelancer)",
    },
    {
        "canonical_url": "https://t.me/obn_rezume",
        "parse_url": "https://t.me/s/obn_rezume",
        "source_type": "tg_channel",
        "title": "TG: Обновите резюме! (@obn_rezume)",
    },
    {
        "canonical_url": "https://t.me/HRTech_Jobs",
        "parse_url": "https://t.me/s/HRTech_Jobs",
        "source_type": "tg_channel",
        "title": "TG: HR-Tech.Карьера 🔥 (@HRTech_Jobs)",
    },
    {
        "canonical_url": "https://t.me/theyseeku_it",
        "parse_url": "https://t.me/s/theyseeku_it",
        "source_type": "tg_channel",
        "title": "TG: Удаленка — IT и Digital (@theyseeku_it)",
    },
    {
        "canonical_url": "https://t.me/HR_Analytics_Jobs",
        "parse_url": "https://t.me/s/HR_Analytics_Jobs",
        "source_type": "tg_channel",
        "title": "TG: Вакансии в HR-Аналитике (@HR_Analytics_Jobs)",
    },
    {
        "canonical_url": "https://t.me/work_looking",
        "parse_url": "https://t.me/s/work_looking",
        "source_type": "tg_channel",
        "title": "TG: Ищу работу | Диджитал (@work_looking)",
    },
    {
        "canonical_url": "https://t.me/Easy_wrk",
        "parse_url": "https://t.me/s/Easy_wrk",
        "source_type": "tg_channel",
        "title": "TG: Easy Work | Фриланс заказы | Удаленная работа (@Easy_wrk)",
    },
    {
        "canonical_url": "https://t.me/jobcatcher",
        "parse_url": "https://t.me/s/jobcatcher",
        "source_type": "tg_channel",
        "title": "TG: Ловец вакансий 🙌🏻 (@jobcatcher)",
    },
    {
        "canonical_url": "https://t.me/architect_career",
        "parse_url": "https://t.me/s/architect_career",
        "source_type": "tg_channel",
        "title": "TG: Архитектор Карьеры (@architect_career)",
    },
    {
        "canonical_url": "https://t.me/ne_titanik_DG",
        "parse_url": "https://t.me/s/ne_titanik_DG",
        "source_type": "tg_channel",
        "title": "TG: Карьера без паники с Дарьей Гречиной (@ne_titanik_DG)",
    },
    {
        "canonical_url": "https://t.me/jobnulsya",
        "parse_url": "https://t.me/s/jobnulsya",
        "source_type": "tg_channel",
        "title": "TG: JOBнулся. О работе и карьере. Как есть (@jobnulsya)",
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
    # --- Вторая подборка каналов (проверено по t.me 18.11.2026) ---
    {
        "canonical_url": "https://t.me/irenaivanova_official",
        "parse_url": "https://t.me/s/irenaivanova_official",
        "source_type": "tg_channel",
        "title": "TG: Ирена_Иванова_official (@irenaivanova_official)",
    },
    {
        "canonical_url": "https://t.me/larina_career",
        "parse_url": "https://t.me/s/larina_career",
        "source_type": "tg_channel",
        "title": "TG: Наталья Ларина | Карьера по своим правилам (@larina_career)",
    },
    {
        "canonical_url": "https://t.me/i_top_groups",
        "parse_url": "https://t.me/s/i_top_groups",
        "source_type": "tg_channel",
        "title": "TG: Я Топ (@i_top_groups)",
    },
    {
        "canonical_url": "https://t.me/hrexpert63",
        "parse_url": "https://t.me/s/hrexpert63",
        "source_type": "tg_channel",
        "title": "TG: #ПерезагрузкаКарьеры (@hrexpert63)",
    },
    {
        "canonical_url": "https://t.me/hrhack_career",
        "parse_url": "https://t.me/s/hrhack_career",
        "source_type": "tg_channel",
        "title": "TG: Abrashitova Natalya | Карьерное развитие (@hrhack_career)",
    },
    {
        "canonical_url": "https://t.me/prolearning",
        "parse_url": "https://t.me/s/prolearning",
        "source_type": "tg_channel",
        "title": "TG: Живое обучение (@prolearning)",
    },
    {
        "canonical_url": "https://t.me/work_for_top",
        "parse_url": "https://t.me/s/work_for_top",
        "source_type": "tg_channel",
        "title": "TG: КАРЬЕРА ЛИДЕРА | Вакансии для руководителей (@work_for_top)",
    },
    {
        "canonical_url": "https://t.me/execselect",
        "parse_url": "https://t.me/s/execselect",
        "source_type": "tg_channel",
        "title": "TG: Exec Select | Топ вакансии для руководителей (@execselect)",
    },
    {
        "canonical_url": "https://t.me/vacancyCRC",
        "parse_url": "https://t.me/s/vacancyCRC",
        "source_type": "tg_channel",
        "title": "TG: Вакансии от CRC (@vacancyCRC)",
    },
    {
        "canonical_url": "https://t.me/relocation_vacancies",
        "parse_url": "https://t.me/s/relocation_vacancies",
        "source_type": "tg_channel",
        "title": "TG: Вакансии с релокацией (@relocation_vacancies)",
    },
    {
        "canonical_url": "https://t.me/hireproproduct",
        "parse_url": "https://t.me/s/hireproproduct",
        "source_type": "tg_channel",
        "title": "TG: Hire ProProduct - Продуктовые вакансии (@hireproproduct)",
    },
    {
        "canonical_url": "https://t.me/workfortop",
        "parse_url": "https://t.me/s/workfortop",
        "source_type": "tg_channel",
        "title": "TG: Work For TOP Вакансии для руководителей (@workfortop)",
    },
    {
        "canonical_url": "https://t.me/fintech_jobs",
        "parse_url": "https://t.me/s/fintech_jobs",
        "source_type": "tg_channel",
        "title": "TG: Fintech - Jobs (@fintech_jobs)",
    },
    {
        "canonical_url": "https://t.me/talent_hunters",
        "parse_url": "https://t.me/s/talent_hunters",
        "source_type": "tg_channel",
        "title": "TG: Talent Hunters (@talent_hunters)",
    },
    {
        "canonical_url": "https://t.me/ithr_tusovka",
        "parse_url": "https://t.me/s/ithr_tusovka",
        "source_type": "tg_channel",
        "title": "TG: IT HR тусовка от ХК (@ithr_tusovka)",
    },
    {
        "canonical_url": "https://t.me/recommend_recruit",
        "parse_url": "https://t.me/s/recommend_recruit",
        "source_type": "tg_channel",
        "title": "TG: Рекомендательный рекрутинг (@recommend_recruit)",
    },
    {
        "canonical_url": "https://t.me/ithunterio",
        "parse_url": "https://t.me/s/ithunterio",
        "source_type": "tg_channel",
        "title": "TG: Смелый рекрутинг (@ithunterio)",
    },
    {
        "canonical_url": "https://t.me/trend_hr",
        "parse_url": "https://t.me/s/trend_hr",
        "source_type": "tg_channel",
        "title": "TG: TrendHR (@trend_hr)",
    },
    {
        "canonical_url": "https://t.me/more_than_hr",
        "parse_url": "https://t.me/s/more_than_hr",
        "source_type": "tg_channel",
        "title": "TG: БОЛЬШЕ чем HR (@more_than_hr)",
    },
    {
        "canonical_url": "https://t.me/toplevel_job",
        "parse_url": "https://t.me/s/toplevel_job",
        "source_type": "tg_channel",
        "title": "TG: TOP LEVEL JOB [топ вакансии для руководителей] (@toplevel_job)",
    },
    {
        "canonical_url": "https://t.me/tomato1000",
        "parse_url": "https://t.me/s/tomato1000",
        "source_type": "tg_channel",
        "title": "TG: Senior Помідор (@tomato1000)",
    },
    {
        "canonical_url": "https://t.me/psoyuz",
        "parse_url": "https://t.me/s/psoyuz",
        "source_type": "tg_channel",
        "title": "TG: ПРОМЫШЛЕННЫЙ СОЮЗ [вакансии: B2B, FMCG, фарма, агро, стройка] (@psoyuz)",
    },
    {
        "canonical_url": "https://t.me/vsemmema",
        "parse_url": "https://t.me/s/vsemmema",
        "source_type": "tg_channel",
        "title": "TG: ВСЕМ МЕМ (@vsemmema)",
    },
    {
        "canonical_url": "https://t.me/elena_shebashova",
        "parse_url": "https://t.me/s/elena_shebashova",
        "source_type": "tg_channel",
        "title": "TG: Елена Шебашова | ЗА КАДРОМ (@elena_shebashova)",
    },
    {
        "canonical_url": "https://t.me/zakadrom_hr",
        "parse_url": "https://t.me/s/zakadrom_hr",
        "source_type": "tg_channel",
        "title": "TG: HR-вакансии | ЗА КАДРОМ (@zakadrom_hr)",
    },
    # =========================================================================
    # Третья подборка — присланный список (проверено по t.me 18.11.2026)
    # 70 каналов по профессиям и отраслям: executive, product, аналитика, dev/QA,
    # дизайн, маркетинг/PR, контент, HR, legal, финансы, продажи, клиентский сервис,
    # ассистенты, стройка, фарма, медицина, HoReCa. Дубли с прежними подборками
    # (vacancyCRC, vacanciesbest, rabota_freelancee) исключены проверкой canonical_url.
    # Каналы, закрывшие веб-превью, остаются в списке (бот честно сообщает в source_issues).
    # =========================================================================
    # --- ТОП-менеджмент и executive ---
    {
        "canonical_url": "https://t.me/forchiefs",
        "parse_url": "https://t.me/s/forchiefs",
        "source_type": "tg_channel",
        "title": "TG: Job for Chiefs (TOP vacancies) (@forchiefs)",
    },
    {
        "canonical_url": "https://t.me/vakansii_top_manager",
        "parse_url": "https://t.me/s/vakansii_top_manager",
        "source_type": "tg_channel",
        "title": "TG: TOP Management - вакансии руководителей и директоров (@vakansii_top_manager)",
    },
    {
        "canonical_url": "https://t.me/ExecCareer",
        "parse_url": "https://t.me/s/ExecCareer",
        "source_type": "tg_channel",
        "title": "TG: Карьера ТОП и Executive Search (@ExecCareer)",
    },
    {
        "canonical_url": "https://t.me/executive_jobs",
        "parse_url": "https://t.me/s/executive_jobs",
        "source_type": "tg_channel",
        "title": "TG: Executive & C-Level вакансії (@executive_jobs)",
    },
    # --- Product и project ---
    {
        "canonical_url": "https://t.me/forproducts",
        "parse_url": "https://t.me/s/forproducts",
        "source_type": "tg_channel",
        "title": "TG: Job for Products and Projects (@forproducts)",
    },
    {
        "canonical_url": "https://t.me/product_jobs",
        "parse_url": "https://t.me/s/product_jobs",
        "source_type": "tg_channel",
        "title": "TG: Вакансии для продактов и проджектов (@product_jobs)",
    },
    # --- Аналитика и Data Science ---
    {
        "canonical_url": "https://t.me/analytics_jobs",
        "parse_url": "https://t.me/s/analytics_jobs",
        "source_type": "tg_channel",
        "title": "TG: BA & SA Jobs | Работа для бизнес и системных аналитиков (@analytics_jobs)",
    },
    {
        "canonical_url": "https://t.me/jobs_for_it_analyst",
        "parse_url": "https://t.me/s/jobs_for_it_analyst",
        "source_type": "tg_channel",
        "title": "TG: Работа ИТ аналитикам (системные и бизнес аналитики) (@jobs_for_it_analyst)",
    },
    {
        "canonical_url": "https://t.me/datasciencejobs",
        "parse_url": "https://t.me/s/datasciencejobs",
        "source_type": "tg_channel",
        "title": "TG: Data Science Jobs (@datasciencejobs)",
    },
    # --- Разработка и DevOps ---
    {
        "canonical_url": "https://t.me/devops_jobs",
        "parse_url": "https://t.me/s/devops_jobs",
        "source_type": "tg_channel",
        "title": "TG: DevOps Jobs - работа и аналитика (@devops_jobs)",
    },
    # --- QA / тестирование ---
    {
        "canonical_url": "https://t.me/forallqa",
        "parse_url": "https://t.me/s/forallqa",
        "source_type": "tg_channel",
        "title": "TG: Job for QA (@forallqa)",
    },
    # --- IT и digital (общий поток) ---
    {
        "canonical_url": "https://t.me/it_vakansii_jobs",
        "parse_url": "https://t.me/s/it_vakansii_jobs",
        "source_type": "tg_channel",
        "title": "TG: СЕТИ — IT & Digital вакансии (@it_vakansii_jobs)",
    },
    # --- Дизайн ---
    {
        "canonical_url": "https://t.me/fordesigner",
        "parse_url": "https://t.me/s/fordesigner",
        "source_type": "tg_channel",
        "title": "TG: Job for Designers (@fordesigner)",
    },
    {
        "canonical_url": "https://t.me/uiux_jobs",
        "parse_url": "https://t.me/s/uiux_jobs",
        "source_type": "tg_channel",
        "title": "TG: UI/UX Jobs — вакансии и аналитика (@uiux_jobs)",
    },
    {
        "canonical_url": "https://t.me/designer_vacancies",
        "parse_url": "https://t.me/s/designer_vacancies",
        "source_type": "tg_channel",
        "title": "TG: Вакансии для дизайнеров (@designer_vacancies)",
    },
    {
        "canonical_url": "https://t.me/uxui_designer_vacancies",
        "parse_url": "https://t.me/s/uxui_designer_vacancies",
        "source_type": "tg_channel",
        "title": "TG: Вакансии UX UI дизайнеров (@uxui_designer_vacancies)",
    },
    {
        "canonical_url": "https://t.me/design_jobs_uxui",
        "parse_url": "https://t.me/s/design_jobs_uxui",
        "source_type": "tg_channel",
        "title": "TG: Вакансии для Дизайнеров (@design_jobs_uxui)",
    },
    # --- Маркетинг, SMM и PR ---
    {
        "canonical_url": "https://t.me/forallmarketing",
        "parse_url": "https://t.me/s/forallmarketing",
        "source_type": "tg_channel",
        "title": "TG: Job for Marketing (@forallmarketing)",
    },
    {
        "canonical_url": "https://t.me/dnative_job",
        "parse_url": "https://t.me/s/dnative_job",
        "source_type": "tg_channel",
        "title": "TG: Вакансии SMM и Digital (@dnative_job)",
    },
    {
        "canonical_url": "https://t.me/vakansii_0",
        "parse_url": "https://t.me/s/vakansii_0",
        "source_type": "tg_channel",
        "title": "TG: Work Hunter – удаленная работа. Вакансии: маркетинг, SMM, PR, Digital (@vakansii_0)",
    },
    {
        "canonical_url": "https://t.me/vakansiitelegramm",
        "parse_url": "https://t.me/s/vakansiitelegramm",
        "source_type": "tg_channel",
        "title": "TG: Вакансии Закупщик Telegram / TG ADS (@vakansiitelegramm)",
    },
    # --- Медиа, контент и события ---
    {
        "canonical_url": "https://t.me/forallmedia",
        "parse_url": "https://t.me/s/forallmedia",
        "source_type": "tg_channel",
        "title": "TG: Job for Media & Content (@forallmedia)",
    },
    {
        "canonical_url": "https://t.me/perezvonyu",
        "parse_url": "https://t.me/s/perezvonyu",
        "source_type": "tg_channel",
        "title": "TG: Мы вам перезвоним (@perezvonyu)",
    },
    {
        "canonical_url": "https://t.me/mskeventjob",
        "parse_url": "https://t.me/s/mskeventjob",
        "source_type": "tg_channel",
        "title": "TG: Event hunter - вся творческая работа Москва (@mskeventjob)",
    },
    # --- HR и рекрутинг ---
    {
        "canonical_url": "https://t.me/forhr",
        "parse_url": "https://t.me/s/forhr",
        "source_type": "tg_channel",
        "title": "TG: Job for HR (IT & Digital) (@forhr)",
    },
    {
        "canonical_url": "https://t.me/job_in_hr",
        "parse_url": "https://t.me/s/job_in_hr",
        "source_type": "tg_channel",
        "title": "TG: HR Вакансии и работа кадровиком, HR рекрутером (@job_in_hr)",
    },
    {
        "canonical_url": "https://t.me/hr_jobs_rabota",
        "parse_url": "https://t.me/s/hr_jobs_rabota",
        "source_type": "tg_channel",
        "title": "TG: Вакансии для HR / IT рекрутеров (@hr_jobs_rabota)",
    },
    {
        "canonical_url": "https://t.me/hrorhr",
        "parse_url": "https://t.me/s/hrorhr",
        "source_type": "tg_channel",
        "title": "TG: эйчарли | HR вакансии (@hrorhr)",
    },
    {
        "canonical_url": "https://t.me/hrhubvacancy",
        "parse_url": "https://t.me/s/hrhubvacancy",
        "source_type": "tg_channel",
        "title": "TG: HR[хаб]вакансии (@hrhubvacancy)",
    },
    {
        "canonical_url": "https://t.me/hrhubvacancy300",
        "parse_url": "https://t.me/s/hrhubvacancy300",
        "source_type": "tg_channel",
        "title": "TG: 300HR[хаб]вакансии (@hrhubvacancy300)",
    },
    {
        "canonical_url": "https://t.me/hrhubjunior",
        "parse_url": "https://t.me/s/hrhubjunior",
        "source_type": "tg_channel",
        "title": "TG: HR[хаб]junior (@hrhubjunior)",
    },
    # --- Юристы и право ---
    {
        "canonical_url": "https://t.me/legal_jobs",
        "parse_url": "https://t.me/s/legal_jobs",
        "source_type": "tg_channel",
        "title": "TG: Юридические вакансии (@legal_jobs)",
    },
    {
        "canonical_url": "https://t.me/hellolawyer_jobs",
        "parse_url": "https://t.me/s/hellolawyer_jobs",
        "source_type": "tg_channel",
        "title": "TG: hellolawyer | вакансии для юристов (@hellolawyer_jobs)",
    },
    # --- Финансы и бухгалтерия ---
    {
        "canonical_url": "https://t.me/cfo_ifrs",
        "parse_url": "https://t.me/s/cfo_ifrs",
        "source_type": "tg_channel",
        "title": "TG: Вакансии в CFO/IFRS (@cfo_ifrs)",
    },
    {
        "canonical_url": "https://t.me/cfosearch",
        "parse_url": "https://t.me/s/cfosearch",
        "source_type": "tg_channel",
        "title": "TG: CFO GO | Онлайн-агрегатор вакансий для финансистов (@cfosearch)",
    },
    {
        "canonical_url": "https://t.me/working_in_finance",
        "parse_url": "https://t.me/s/working_in_finance",
        "source_type": "tg_channel",
        "title": "TG: Вакансии бухгалтерам, экономистам, аналитикам, работа 1С. (@working_in_finance)",
    },
    {
        "canonical_url": "https://t.me/work_in_accounting",
        "parse_url": "https://t.me/s/work_in_accounting",
        "source_type": "tg_channel",
        "title": "TG: Работа бухгалтерам, аналитикам и по 1С. Финансовые вакансии. (@work_in_accounting)",
    },
    # --- Финтех и банки ---
    {
        "canonical_url": "https://t.me/fintech_work",
        "parse_url": "https://t.me/s/fintech_work",
        "source_type": "tg_channel",
        "title": "TG: Работа в финтехе | Fintech, Crypto, Blockchain вакансии (@fintech_work)",
    },
    {
        "canonical_url": "https://t.me/paymentcardjobs",
        "parse_url": "https://t.me/s/paymentcardjobs",
        "source_type": "tg_channel",
        "title": "TG: FintechJob: Сards & Payments (@paymentcardjobs)",
    },
    # --- Продажи и bizdev ---
    {
        "canonical_url": "https://t.me/forallsales",
        "parse_url": "https://t.me/s/forallsales",
        "source_type": "tg_channel",
        "title": "TG: Job for Sales & BizDev (@forallsales)",
    },
    {
        "canonical_url": "https://t.me/sales_work",
        "parse_url": "https://t.me/s/sales_work",
        "source_type": "tg_channel",
        "title": "TG: Sales Work | вакансии в продажи (@sales_work)",
    },
    {
        "canonical_url": "https://t.me/sales_manager_job",
        "parse_url": "https://t.me/s/sales_manager_job",
        "source_type": "tg_channel",
        "title": "TG: Менеджер по продажам в IT - вакансии (@sales_manager_job)",
    },
    {
        "canonical_url": "https://t.me/salestalents",
        "parse_url": "https://t.me/s/salestalents",
        "source_type": "tg_channel",
        "title": "TG: Таланты продаж (@salestalents)",
    },
    {
        "canonical_url": "https://t.me/careerspace",
        "parse_url": "https://t.me/s/careerspace",
        "source_type": "tg_channel",
        "title": "TG: careerspace (@careerspace)",
    },
    # --- Клиентский сервис и Customer Success ---
    {
        "canonical_url": "https://t.me/bizservisjob",
        "parse_url": "https://t.me/s/bizservisjob",
        "source_type": "tg_channel",
        "title": "TG: Вакансии и резюме в клиентском сервисе (@bizservisjob)",
    },
    {
        "canonical_url": "https://t.me/cstalents",
        "parse_url": "https://t.me/s/cstalents",
        "source_type": "tg_channel",
        "title": "TG: Таланты Customer Success (@cstalents)",
    },
    # --- Ассистенты и администрирование ---
    {
        "canonical_url": "https://t.me/nanyatassistenta",
        "parse_url": "https://t.me/s/nanyatassistenta",
        "source_type": "tg_channel",
        "title": "TG: ИЩУ АССИСТЕНТА | Размещение вакансий (@nanyatassistenta)",
    },
    {
        "canonical_url": "https://t.me/getassistant_vacancy",
        "parse_url": "https://t.me/s/getassistant_vacancy",
        "source_type": "tg_channel",
        "title": "TG: Вакансии: ассистенты, бизнес-ассистенты, личные помощники - GetAssista (@getassistant_vacancy)",
    },
    {
        "canonical_url": "https://t.me/assisteca_job",
        "parse_url": "https://t.me/s/assisteca_job",
        "source_type": "tg_channel",
        "title": "TG: Ассистека: вакансии для ассистентов (@assisteca_job)",
    },
    {
        "canonical_url": "https://t.me/pomochnik_vakansii",
        "parse_url": "https://t.me/s/pomochnik_vakansii",
        "source_type": "tg_channel",
        "title": "TG: Менеджер | Ассистент | Работа (@pomochnik_vakansii)",
    },
    # --- Строительство и инжиниринг ---
    {
        "canonical_url": "https://t.me/vacancii_construction",
        "parse_url": "https://t.me/s/vacancii_construction",
        "source_type": "tg_channel",
        "title": "TG: Работа, Вакансии, строительство: Руководитель проектов, начальник учас (@vacancii_construction)",
    },
    {
        "canonical_url": "https://t.me/mosinzproekt",
        "parse_url": "https://t.me/s/mosinzproekt",
        "source_type": "tg_channel",
        "title": "TG: МОСИНЖПРОЕКТ (@mosinzproekt)",
    },
    # --- Фармацевтика и медицина ---
    {
        "canonical_url": "https://t.me/JobinPharma",
        "parse_url": "https://t.me/s/JobinPharma",
        "source_type": "tg_channel",
        "title": "TG: ФАРМА. Вакансии (@JobinPharma)",
    },
    {
        "canonical_url": "https://t.me/lapainpharma",
        "parse_url": "https://t.me/s/lapainpharma",
        "source_type": "tg_channel",
        "title": "TG: Лапа в фарме | Вакансии, резюме в фармацевтической сфере (@lapainpharma)",
    },
    {
        "canonical_url": "https://t.me/pharmed_recruitment",
        "parse_url": "https://t.me/s/pharmed_recruitment",
        "source_type": "tg_channel",
        "title": "TG: 💉Фарма&Медикал Рекрутмент / Вакансии в Фарме, Работа в Фарме (@pharmed_recruitment)",
    },
    {
        "canonical_url": "https://t.me/superjob_medicina",
        "parse_url": "https://t.me/s/superjob_medicina",
        "source_type": "tg_channel",
        "title": "TG: Работа / Медицина / Вакансии (@superjob_medicina)",
    },
    {
        "canonical_url": "https://t.me/job_in_med",
        "parse_url": "https://t.me/s/job_in_med",
        "source_type": "tg_channel",
        "title": "TG: Медицинские вакансии. Работа врачам (@job_in_med)",
    },
    {
        "canonical_url": "https://t.me/job_in_zdrav",
        "parse_url": "https://t.me/s/job_in_zdrav",
        "source_type": "tg_channel",
        "title": "TG: Медицина, врачи. Вакансии и работа для врачей, докторов, в больницах,  (@job_in_zdrav)",
    },
    # --- HoReCa и общепит ---
    {
        "canonical_url": "https://t.me/HoReCa_HR",
        "parse_url": "https://t.me/s/HoReCa_HR",
        "source_type": "tg_channel",
        "title": "TG: Общепит работа | HoReCa Вакансии (@HoReCa_HR)",
    },
    {
        "canonical_url": "https://t.me/rujobinfood",
        "parse_url": "https://t.me/s/rujobinfood",
        "source_type": "tg_channel",
        "title": "TG: Общепит - работа есть! (@rujobinfood)",
    },
    {
        "canonical_url": "https://t.me/expresswaiter",
        "parse_url": "https://t.me/s/expresswaiter",
        "source_type": "tg_channel",
        "title": "TG: ♨️ EW ♨️ - Вакансии, Работа, Общепит, Ресторан, Повар, Официант (@expresswaiter)",
    },
    {
        "canonical_url": "https://t.me/expresswaiter_vacancy",
        "parse_url": "https://t.me/s/expresswaiter_vacancy",
        "source_type": "tg_channel",
        "title": "TG: EW - Работа, Общепит, Ресторан, Вакансии, Повар, Официант, HoReCa, Мос (@expresswaiter_vacancy)",
    },
    {
        "canonical_url": "https://t.me/exwaiters",
        "parse_url": "https://t.me/s/exwaiters",
        "source_type": "tg_channel",
        "title": "TG: EW - Повар, Общепит, Ресторан, Вакансии, Общепит, Работа, HoReCa (@exwaiters)",
    },
    # --- Прочие отрасли ---
    {
        "canonical_url": "https://t.me/javascript_jobs",
        "parse_url": "https://t.me/s/javascript_jobs",
        "source_type": "tg_channel",
        "title": "TG: JavaScript Jobs — чат (@javascript_jobs)",
    },
    {
        "canonical_url": "https://t.me/ru_pythonjobs",
        "parse_url": "https://t.me/s/ru_pythonjobs",
        "source_type": "tg_channel",
        "title": "TG: Вакансии для Python-разработчиков / Python Jobs (@ru_pythonjobs)",
    },
    {
        "canonical_url": "https://t.me/java_jobs",
        "parse_url": "https://t.me/s/java_jobs",
        "source_type": "tg_channel",
        "title": "TG: Java Jobs (@java_jobs)",
    },
    {
        "canonical_url": "https://t.me/javadevjob",
        "parse_url": "https://t.me/s/javadevjob",
        "source_type": "tg_channel",
        "title": "TG: Java jobs — вакансии для java-разработчиков (@javadevjob)",
    },
    {
        "canonical_url": "https://t.me/golangjob",
        "parse_url": "https://t.me/s/golangjob",
        "source_type": "tg_channel",
        "title": "TG: Golang Jobs (@golangjob)",
    },
    {
        "canonical_url": "https://t.me/mobile_jobs",
        "parse_url": "https://t.me/s/mobile_jobs",
        "source_type": "tg_channel",
        "title": "TG: Mobile Dev Jobs — вакансии и резюме (@mobile_jobs)",
    },
    {
        "canonical_url": "https://t.me/mobiledevjob",
        "parse_url": "https://t.me/s/mobiledevjob",
        "source_type": "tg_channel",
        "title": "TG: Mobile jobs — вакансии для мобильных разработчиков (@mobiledevjob)",
    },
    {
        "canonical_url": "https://t.me/prvacant",
        "parse_url": "https://t.me/s/prvacant",
        "source_type": "tg_channel",
        "title": "TG: PR Вакансии и стажировки (@prvacant)",
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
        "canonical_url": "https://geekjob.ru",
        "parse_url": "https://geekjob.ru/vacancies",
        "source_type": "website",
        "title": "Сайт: GeekJob (geekjob.ru)",
    },
    # --- Третья подборка: российские сайты и job-борды (проверено 18.11.2026) ---
    # Автопарсинг: открытые данные «Работа России» (JSON API) и две площадки,
    # отдающие вакансии в HTML без JavaScript.
    {
        "canonical_url": "https://trudvsem.ru",
        "parse_url": "https://opendata.trudvsem.ru/api/v1/vacancies",
        "source_type": "website",
        "title": "Сайт: Работа России (trudvsem.ru, открытые данные API)",
    },
    {
        "canonical_url": "https://budu.jobs/",
        "parse_url": "https://budu.jobs/",
        "source_type": "website",
        "title": "Сайт: Буду (budu.jobs)",
    },
    {
        "canonical_url": "https://remote-job.ru/",
        "parse_url": "https://remote-job.ru/",
        "source_type": "website",
        "title": "Сайт: Remote Job (remote-job.ru)",
    },
    # Карьерные страницы компаний (source_type="career"): вакансии самих работодателей.
    # Отдают вакансии в HTML — их читает parse_career_page_html (JSON-LD + ссылки).
    {
        "canonical_url": "https://team.vk.company/vacancy/",
        "parse_url": "https://team.vk.company/vacancy/",
        "source_type": "career",
        "title": "Карьера: VK (team.vk.company)",
    },
    {
        "canonical_url": "https://career.avito.com/vacancies",
        "parse_url": "https://career.avito.com/vacancies",
        "source_type": "career",
        "title": "Карьера: Avito (career.avito.com)",
    },
    {
        "canonical_url": "https://job.2gis.ru/vacancies",
        "parse_url": "https://job.2gis.ru/vacancies",
        "source_type": "career",
        "title": "Карьера: 2ГИС (job.2gis.ru)",
    },
    {
        "canonical_url": "https://job.mts.ru/vacancies",
        "parse_url": "https://job.mts.ru/vacancies",
        "source_type": "career",
        "title": "Карьера: МТС (job.mts.ru)",
    },
    {
        "canonical_url": "https://yandex.ru/jobs/vacancies",
        "parse_url": "https://yandex.ru/jobs/vacancies",
        "source_type": "career",
        "title": "Карьера: Яндекс (yandex.ru/jobs)",
    },
    {
        "canonical_url": "https://x5.ru/career/",
        "parse_url": "https://x5.ru/career/",
        "source_type": "career",
        "title": "Карьера: X5 Group (x5.ru/career)",
    },
    # Ручной поиск: 423/439 (антибот), SPA без вакансий в HTML или закрытая выдача.
    {
        "canonical_url": "https://getmatch.ru/vacancies",
        "parse_url": "https://getmatch.ru/vacancies",
        "source_type": "manual",
        "title": "Сайт: getmatch (getmatch.ru)",
    },
    {
        "canonical_url": "https://facancy.ru/",
        "parse_url": "https://facancy.ru/",
        "source_type": "manual",
        "title": "Сайт: Facancy (facancy.ru)",
    },
    {
        "canonical_url": "https://changellenge.com/",
        "parse_url": "https://changellenge.com/",
        "source_type": "manual",
        "title": "Сайт: Changellenge (changellenge.com)",
    },
    {
        "canonical_url": "https://ingamejob.com/",
        "parse_url": "https://ingamejob.com/",
        "source_type": "manual",
        "title": "Сайт: InGame Job (ingamejob.com)",
    },
    {
        "canonical_url": "https://careerist.ru/",
        "parse_url": "https://careerist.ru/",
        "source_type": "manual",
        "title": "Сайт: Careerist (careerist.ru)",
    },
    {
        "canonical_url": "https://www.linkedin.com/jobs/",
        "parse_url": "https://www.linkedin.com/jobs/",
        "source_type": "manual",
        "title": "Сайт: LinkedIn Jobs (linkedin.com/jobs)",
    },
    {
        "canonical_url": "https://wellfound.com/jobs",
        "parse_url": "https://wellfound.com/jobs",
        "source_type": "manual",
        "title": "Сайт: Wellfound (wellfound.com/jobs)",
    },
    {
        "canonical_url": "https://ru.jooble.org/",
        "parse_url": "https://ru.jooble.org/",
        "source_type": "manual",
        "title": "Сайт: Jooble (ru.jooble.org)",
    },
    {
        "canonical_url": "https://gorodrabot.ru",
        "parse_url": "https://gorodrabot.ru",
        "source_type": "manual",
        "title": "Сайт: ГородРабот (gorodrabot.ru)",
    },
    {
        "canonical_url": "https://www.avito.ru/rossiya/vakansii",
        "parse_url": "https://www.avito.ru/rossiya/vakansii",
        "source_type": "manual",
        "title": "Сайт: Avito Работа (avito.ru)",
    },
    {
        "canonical_url": "https://youdo.com/",
        "parse_url": "https://youdo.com/",
        "source_type": "manual",
        "title": "Сайт: YouDo (youdo.com)",
    },
    {
        "canonical_url": "https://kwork.ru/",
        "parse_url": "https://kwork.ru/",
        "source_type": "manual",
        "title": "Сайт: Kwork (kwork.ru)",
    },
    {
        "canonical_url": "https://www.fl.ru/",
        "parse_url": "https://www.fl.ru/",
        "source_type": "manual",
        "title": "Сайт: FL.ru (fl.ru)",
    },
]


# =============================================================================
# Источники, выведенные из поиска (остаются в таблице, но помечаются is_active = 0)
# =============================================================================
# Так уже созданные базы (в том числе рабочая база бота) перестают их парсить при
# старте — без ручного удаления. Вернуть источник можно через /add_source.
RETIRED_SOURCES: Dict[str, str] = {
    "https://t.me/fuck_the_frameworks": (
        "канал закрыл публичное веб-превью: вакансии прочитать невозможно, "
        "каждый поиск давал предупреждение"
    ),
    "https://www.superjob.ru": (
        "RSS-лента отдаётся, но вакансии не сопоставляются с профилем резюме — "
        "источник выведен из поиска"
    ),
}


class Database:
    """Асинхронный менеджер базы данных SQLite."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    async def _ensure_column(db: Any, table: str, column: str, ddl: str) -> None:
        """Добавляет колонку в существующую таблицу (SQLite не умеет IF NOT EXISTS).

        Нужно для уже работающих баз: бот обновляется поверх старого файла БД,
        поэтому схему приходится догонять вручную.
        """
        async with db.execute(f"PRAGMA table_info({table})") as cursor:
            columns = {row[1] for row in await cursor.fetchall()}
        if column not in columns:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

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
                    updated_at TEXT NOT NULL,
                    profile_edited_manually INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            # Базы, созданные до появления ручной правки профиля
            await self._ensure_column(
                db, "users_resumes", "profile_edited_manually", "INTEGER NOT NULL DEFAULT 0"
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
            # Выведенные из поиска источники гасим и в уже существующих базах
            for url in RETIRED_SOURCES:
                await db.execute(
                    "UPDATE sources SET is_active = 0 WHERE canonical_url = ?", (url,)
                )
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
        manual: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Обновляет целевую должность и/или ключевые навыки в профиле резюме.

        Нужен, когда автоматическое извлечение не справилось (например, в резюме
        не было ни названия должности, ни блока навыков).

        ``manual=True`` помечает профиль как отредактированный человеком: авто-починка
        при старте бота такие профили не трогает (иначе она «переисправит» выбор).
        """
        record = await self.get_resume(user_id)
        if not record:
            return None

        new_role = role if role is not None else record.get("extracted_role") or ""
        new_skills = skills if skills is not None else record.get("extracted_skills") or []

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users_resumes SET extracted_role = ?, extracted_skills = ?, updated_at = ?, "
                "profile_edited_manually = CASE WHEN ? THEN 1 ELSE profile_edited_manually END "
                "WHERE user_id = ?",
                (
                    new_role,
                    json.dumps(new_skills, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                    1 if manual else 0,
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
