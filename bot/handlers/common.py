"""Общие команды бота: /start, /help, /cancel."""
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from bot.keyboards import get_main_menu_keyboard

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Приветственное сообщение и вывод главного меню."""
    await state.clear()
    text = (
        "👋 **Добро пожаловать в бот формирования резюме и умного поиска работы!**\n\n"
        "Я работаю на базе бесплатных open-source инструментов и умею:\n\n"
        "1️⃣ **📤 Загрузить резюме** — принимаю резюме файлом (`PDF`, `DOCX`, `TXT`) или обычным текстом, "
        "автоматически выделяю целевую должность и ключевые навыки.\n"
        "2️⃣ **📐 Стандарты рынка** — отдельная функция внутри бота, где вы можете выбрать отраслевой стандарт "
        "(ATS, IT, Data, Маркетинг) или задать свои собственные стандарты рынка.\n"
        "3️⃣ **✨ Адаптировать резюме** — отдельная функция переработки вашего резюме под заданные стандарты рынка "
        "(с оценкой ATS 0–100% и выдачей готового файла `.docx`).\n"
        "4️⃣ **🔍 Поиск вакансий по резюме** — парсинг Telegram-каналов и сайтов из базы данных за выбранный период: "
        "**1 день**, **1 неделя** или **1 месяц**.\n"
        "5️⃣ **🌐 Источники вакансий** — добавление новых сайтов и ссылок на ТГ-каналы с автоматической проверкой на дубликаты в БД.\n"
        "🏛 **Пример идеального резюме** (`/example_cv`) — эталонный Executive CV по Золотому стандарту Framework 2026+ "
        "(текст + файл `.docx`).\n"
        "🧭 **Найти каналы и сайты** (`/find_resources`) — проверенные ТГ-каналы с вакансиями, "
        "агрегаторы и карьерные страницы компаний с фильтром по отрасли.\n\n"
        "👇 Выберите нужное действие на клавиатуре ниже:"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Справка по командам бота."""
    text = (
        "📖 **Список команд и функций бота:**\n\n"
        "• `/upload_resume` или кнопка **📤 Загрузить резюме** — загрузить резюме (PDF, DOCX, TXT или текст).\n"
        "• `/gold_standard` — активировать «Золотой стандарт»: **🏛 Архитектура идеального Executive CV (Framework 2026+)**.\n"
        "• `/example_cv` или кнопка **🏛 Пример идеального резюме** — показать эталонный пример Executive CV 2026+ (текст + файл `.docx`).\n"
        "• `/standards` или кнопка **📐 Стандарты рынка** — задать/изменить стандарты рынка внутри бота.\n"
        "• `/adapt_resume` или кнопка **✨ Адаптировать резюме** — адаптировать загруженное резюме под активные стандарты рынка.\n"
        "• `/search` или кнопка **🔍 Поиск вакансий** — запустить парсинг вакансий по резюме за **1 день**, **1 неделю** или **1 месяц**.\n"
        "• `/set_role <должность>`, `/set_skills <навыки через запятую>`, `/reset_profile` — "
        "уточнить или пересобрать профиль (должность и навыки) для поиска вакансий.\n"
        "• `/find_resources` или кнопка **🧭 Найти каналы и сайты** — подборка ТГ-каналов с вакансиями, "
        "сайтов-агрегаторов и карьерных страниц компаний (с делением длинных списков на блоки).\n"
        "• `/sources` или кнопка **🌐 Источники вакансий** — управление базой сайтов и ТГ-каналов.\n"
        "• `/add_source <ссылка>` — быстро добавить сайт или ТГ-канал в базу данных.\n"
        "• `/my_resume` или кнопка **📄 Моё резюме** — посмотреть текущий профиль резюме.\n"
        "• `/llm` — показать, какая бесплатная LLM подключена для адаптации резюме "
        "(и что ответил провайдер при последнем вызове).\n"
        "• `/cancel` — отменить текущий ввод."
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")


@router.message(Command("llm"))
async def cmd_llm_status(message: Message) -> None:
    """Показывает, какая бесплатная LLM подключена и что случилось при последнем вызове."""
    from bot.services.llm_client import LAST_ATTEMPTS, build_providers

    providers = build_providers()
    if not providers:
        text = (
            "🤖 **LLM не подключена** — адаптация резюме идёт встроенным локальным архитектором.\n\n"
            "**Как включить бесплатную модель (5 минут):**\n"
            "1. Возьмите бесплатный ключ у одного из провайдеров:\n"
            "   • **Google Gemini** — https://aistudio.google.com/apikey (без карты)\n"
            "   • **Groq** — https://console.groq.com/keys (без карты, быстрый Llama 3.3 70B)\n"
            "   • **Cerebras** — https://cloud.cerebras.ai (1 млн токенов/день)\n"
            "   • **Mistral** — https://console.mistral.ai (Experiment tier)\n"
            "   • **OpenRouter** — https://openrouter.ai/keys (модели с суффиксом `:free`)\n"
            "2. Добавьте ключ в GitHub: **Settings → Secrets and variables → Actions → New repository secret**:\n"
            "   имя `GEMINI_API_KEY` (или `GROQ_API_KEY`), значение — сам ключ.\n"
            "3. Перезапустите **Actions → run_bot → Run workflow**.\n\n"
            "_Можно задать несколько ключей — бот будет пробовать их по очереди._"
        )
        await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)
        return

    lines = ["🤖 **Подключённые бесплатные LLM (порядок перебора):**"]
    for index, provider in enumerate(providers, start=1):
        lines.append(
            f"{index}. {provider.label} — модель `{provider.model}`"
        )
    lines.append("")
    if LAST_ATTEMPTS:
        lines.append("**Последний вызов:**")
        for attempt in LAST_ATTEMPTS:
            lines.append(f"• {attempt}")
    else:
        lines.append("_С момента запуска бота LLM ещё не вызывалась._")
    lines.append("")
    lines.append(
        "Поменять порядок: секрет `LLM_ORDER` (например `groq,gemini`). "
        "Выбрать единственного провайдера: `LLM_PROVIDER`. "
        "Другая модель: `GEMINI_MODEL`, `GROQ_MODEL`, `CEREBRAS_MODEL`, `OPENROUTER_MODEL`."
    )
    await message.answer("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)


@router.message(Command("cancel"))
@router.message(F.text.casefold() == "отмена")
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Сброс любого активного состояния FSM."""
    await state.clear()
    await message.answer(
        "❎ Текущее действие отменено. Вы в главном меню.",
        reply_markup=get_main_menu_keyboard(),
    )
