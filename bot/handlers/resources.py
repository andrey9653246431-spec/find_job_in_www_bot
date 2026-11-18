"""Обработчики алгоритма поиска информационных ресурсов (HR-ассистент).

Реализует требования ТЗ:
1. Определение типа поиска по запросу пользователя:
   - Telegram-каналы и чаты → ссылки `https://t.me/...` с тематикой;
   - агрегаторы и сайты с вакансиями → job-борды;
   - компании / ТОП-100 / карьерные страницы → структурированный список по отраслям;
   - профессия → deep-links агрегаторов с фильтрами.
2. Структурированный Markdown-ответ по блокам, прямая ссылка и описание у каждого пункта.
3. Автоматическое деление длинного ответа на несколько сообщений.
4. Обязательный дисклеймер о том, что ссылки могут меняться.
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import get_resource_search_keyboard
from bot.services.search_assistant import (
    SEARCH_TYPE_AGGREGATORS,
    SEARCH_TYPE_COMPANIES,
    SEARCH_TYPE_PROFESSION,
    SEARCH_TYPE_TELEGRAM,
    build_resources_answer,
    build_sources_catalog_summary,
)
from bot.states import ResourceSearchStates

router = Router(name="resources")

_SEARCH_TYPE_PROMPTS = {
    SEARCH_TYPE_TELEGRAM: (
        "📱 **Поиск Telegram-каналов**\n\n"
        "Ниже — проверенные каналы с вакансиями. Хотите подборку под свою специализацию? "
        "Введите запрос текстом, например: `HR`, `Python`, `маркетинг`, `удалёнка`."
    ),
    SEARCH_TYPE_AGGREGATORS: (
        "🌐 **Поиск сайтов-агрегаторов**\n\n"
        "Показываю базу job-бордов. Уточните запрос, если нужна конкретика, "
        "например: `IT`, `банки`, `регионы`."
    ),
    SEARCH_TYPE_COMPANIES: (
        "🏢 **Поиск компаний и карьерных страниц**\n\n"
        "Показываю компании по отраслям с ссылками на сайт и вакансии. "
        "Уточните отрасль: `ритейл`, `банки`, `IT`, `логистика`, `фарма` или `ТОП-100`."
    ),
    SEARCH_TYPE_PROFESSION: (
        "🎯 **Поиск вакансий по профессии**\n\n"
        "Введите профессию или ключевые слова — соберу прямые ссылки на поиск "
        "с фильтрами на агрегаторах и подскажу, как искать каналы в Telegram."
    ),
}


async def _send_search_answer(message: Message, query: str, search_type: str | None = None) -> None:
    """Формирует и отправляет ответ алгоритма поиска (с делением на части)."""
    answer = build_resources_answer(query=query, search_type=search_type)

    for warning in answer["warnings"]:
        await message.answer(warning)

    parts = answer["parts"]
    for index, part in enumerate(parts, start=1):
        suffix = f"\n\n_Часть {index} из {len(parts)}_" if len(parts) > 1 else ""
        await message.answer(part + suffix, parse_mode="Markdown", disable_web_page_preview=True)


@router.message(Command("find_resources"))
@router.message(Command("resources"))
@router.message(Command("channels"))
@router.message(Command("aggregators"))
@router.message(Command("companies"))
@router.message(F.text == "🧭 Найти каналы и сайты")
async def cmd_find_resources(message: Message, state: FSMContext) -> None:
    """Открывает меню поиска ресурсов: ТГ-каналы, агрегаторы, компании, профессия."""
    await state.clear()
    catalog = build_sources_catalog_summary()
    text = (
        "🧭 **Поиск каналов, сайтов и компаний для трудоустройства**\n\n"
        f"В базе бота: **{catalog['telegram_channels']}** Telegram-каналов, "
        f"**{catalog['aggregators']}** агрегаторов, "
        f"**{catalog['companies']}** компаний в {catalog['industries']} отраслях.\n\n"
        "Выберите тип поиска кнопкой ниже или просто напишите запрос текстом, например:\n"
        "• `Дай ссылки на ТГ-каналы и агрегаторы для поиска работы в HR`\n"
        "• `компании ритейла`\n"
        "• `ТОП-100 компаний`\n"
        "• `вакансии аналитик данных`"
    )
    await message.answer(
        text,
        reply_markup=get_resource_search_keyboard(),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


@router.callback_query(F.data.startswith("res_find:"))
async def cb_find_resources_by_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Быстрый выбор типа поиска inline-кнопкой."""
    search_type = (callback.data or "").split(":", 1)[1]
    await callback.answer("Подбираю ресурсы")
    if not callback.message:
        return

    if search_type in (SEARCH_TYPE_TELEGRAM, SEARCH_TYPE_AGGREGATORS, SEARCH_TYPE_COMPANIES):
        await _send_search_answer(callback.message, query="", search_type=search_type)
    else:
        await state.set_state(ResourceSearchStates.waiting_for_query)
        await callback.message.answer(
            _SEARCH_TYPE_PROMPTS[SEARCH_TYPE_PROFESSION], parse_mode="Markdown"
        )


@router.message(ResourceSearchStates.waiting_for_query, F.text)
async def handle_resource_query(message: Message, state: FSMContext) -> None:
    """Обрабатывает текстовый запрос пользователя и определяет тип поиска автоматически."""
    await state.clear()
    query = (message.text or "").strip()
    if not query:
        await message.answer(
            "⚠️ Введите запрос текстом, например: `компании банков` или `ТГ-каналы для дизайнеров`.",
            parse_mode="Markdown",
        )
        return
    await _send_search_answer(message, query=query)


_KEYWORD_HINTS = (
    "канал", "каналы", "тг", "telegram", "телеграм", "чат", "чаты",
    "агрегатор", "агрегаторы", "job-борд", "джоб-борд", "сайты с вакансиями",
    "карьерн", "карьера", "компани", "компании", "работодател", "топ-100", "топ 100",
)


@router.message(F.text)
async def handle_free_text_resource_query(message: Message) -> None:
    """Ловит свободный текстовый запрос про каналы/агрегаторы/компании
    (когда пользователь не открывал меню поиска ресурсов)."""
    query = (message.text or "").strip()
    query_low = query.lower()
    if not any(hint in query_low for hint in _KEYWORD_HINTS):
        return
    if query_low.startswith("/"):
        return
    await _send_search_answer(message, query=query)
