"""Клавиатуры (Reply и Inline) для Telegram-бота."""
from typing import Optional

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню бота с отдельными кнопками под каждую функцию ТЗ."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📤 Загрузить резюме"),
                KeyboardButton(text="✨ Адаптировать резюме"),
            ],
            [
                KeyboardButton(text="📐 Стандарты рынка"),
                KeyboardButton(text="🔍 Поиск вакансий"),
            ],
            [
                KeyboardButton(text="🌐 Источники вакансий"),
                KeyboardButton(text="📄 Моё резюме"),
            ],
            [
                KeyboardButton(text="🏛 Пример идеального резюме"),
                KeyboardButton(text="🧭 Найти каналы и сайты"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие в меню...",
    )


def get_search_period_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора периода поиска вакансий: 1 день, 1 неделя, 1 месяц."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🕐 За 1 день", callback_data="search_period:1"
                ),
                InlineKeyboardButton(
                    text="📅 За 1 неделю", callback_data="search_period:7"
                ),
                InlineKeyboardButton(
                    text="🗓 За 1 месяц", callback_data="search_period:30"
                ),
            ]
        ]
    )


def get_standards_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура отдельной функции настройки стандартов рынка внутри бота."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏛 Золотой стандарт: Executive CV (2026+)",
                    callback_data="std_preset:executive_cv_2026",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👁 Показать пример идеального резюме",
                    callback_data="std_action:example",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌐 Универсальный ATS (STAR/XYZ)",
                    callback_data="std_preset:universal_ats",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💻 IT / Разработка ПО",
                    callback_data="std_preset:it_dev",
                ),
                InlineKeyboardButton(
                    text="📊 Data / Аналитика",
                    callback_data="std_preset:data_analytics",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📈 Маркетинг и Продажи",
                    callback_data="std_preset:marketing_sales",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Задать свои стандарты рынка текстом",
                    callback_data="std_action:custom_input",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Вернуть Золотой стандарт (2026+)",
                    callback_data="std_action:reset",
                )
            ],
        ]
    )


def get_sources_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления базой источников (ТГ-каналы и сайты вакансий)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить сайт или ТГ-канал",
                    callback_data="src_action:add",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Показать все источники в БД",
                    callback_data="src_action:list",
                )
            ],
        ]
    )


def get_profile_edit_keyboard(with_search: bool = True) -> InlineKeyboardMarkup:
    """Кнопки ручной корректировки профиля резюме перед поиском вакансий."""
    rows = [
        [
            InlineKeyboardButton(
                text="✏️ Изменить должность",
                callback_data="profile_edit:role",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🛠 Изменить навыки",
                callback_data="profile_edit:skills",
            ),
        ],
    ]
    if with_search:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔍 Искать вакансии (1 день / 1 нед / 1 мес)",
                    callback_data="quick_action:search",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_after_upload_keyboard() -> InlineKeyboardMarkup:
    """Быстрые действия сразу после загрузки резюме.

    Первым делом — правка должности и навыков: их распознаёт парсер, и ошибку
    лучше исправить до поиска вакансий, а не после.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить должность",
                    callback_data="profile_edit:role",
                ),
                InlineKeyboardButton(
                    text="🛠 Изменить навыки",
                    callback_data="profile_edit:skills",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✨ Адаптировать под стандарты рынка",
                    callback_data="quick_action:adapt",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📐 Настроить стандарты рынка",
                    callback_data="quick_action:standards",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔍 Искать вакансии (1 день / 1 нед / 1 мес)",
                    callback_data="quick_action:search",
                )
            ],
        ]
    )


def get_resource_search_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа поиска ресурсов: ТГ-каналы, агрегаторы, компании."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📱 Telegram-каналы",
                    callback_data="res_find:telegram_channels",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌐 Сайты-агрегаторы",
                    callback_data="res_find:aggregators",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏢 Компании и карьерные страницы",
                    callback_data="res_find:companies",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Вакансии по профессии",
                    callback_data="res_find:profession",
                )
            ],
        ]
    )


def get_search_results_keyboard(shown: int, total: int, page_size: int = 10) -> Optional[InlineKeyboardMarkup]:
    """Кнопки листания выдачи: «Показать ещё» и «Показать все», если вакансий больше страницы.

    ``shown`` — сколько вакансий пользователь уже видел (смещение следующей страницы).
    Возвращает None, когда показывать больше нечего.
    """
    remaining = max(0, total - shown)
    if remaining <= 0:
        return None

    rows = []
    if remaining > page_size:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📄 Показать ещё {page_size}",
                    callback_data=f"search_more:{shown}",
                ),
                InlineKeyboardButton(
                    text=f"⏬ Показать все ({remaining})",
                    callback_data=f"search_all:{shown}",
                ),
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📄 Показать ещё {remaining}",
                    callback_data=f"search_more:{shown}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
