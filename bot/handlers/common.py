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
        "5️⃣ **🌐 Источники вакансий** — добавление новых сайтов и ссылок на ТГ-каналы с автоматической проверкой на дубликаты в БД.\n\n"
        "👇 Выберите нужное действие на клавиатуре ниже:"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Справка по командам бота."""
    text = (
        "📖 **Список команд и функций бота:**\n\n"
        "• `/upload_resume` или кнопка **📤 Загрузить резюме** — загрузить резюме (PDF, DOCX, TXT или текст).\n"
        "• `/standards` или кнопка **📐 Стандарты рынка** — задать/изменить стандарты рынка внутри бота.\n"
        "• `/adapt_resume` или кнопка **✨ Адаптировать резюме** — адаптировать загруженное резюме под активные стандарты рынка.\n"
        "• `/search` или кнопка **🔍 Поиск вакансий** — запустить парсинг вакансий по резюме за **1 день**, **1 неделю** или **1 месяц**.\n"
        "• `/sources` или кнопка **🌐 Источники вакансий** — управление базой сайтов и ТГ-каналов.\n"
        "• `/add_source <ссылка>` — быстро добавить сайт или ТГ-канал в базу данных.\n"
        "• `/my_resume` или кнопка **📄 Моё резюме** — посмотреть текущий профиль резюме.\n"
        "• `/cancel` — отменить текущий ввод."
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")


@router.message(Command("cancel"))
@router.message(F.text.casefold() == "отмена")
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Сброс любого активного состояния FSM."""
    await state.clear()
    await message.answer(
        "❎ Текущее действие отменено. Вы в главном меню.",
        reply_markup=get_main_menu_keyboard(),
    )
