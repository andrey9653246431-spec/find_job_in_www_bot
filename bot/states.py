"""Состояния конечного автомата (FSM) для диалогов Telegram-бота."""
from aiogram.fsm.state import State, StatesGroup


class ResumeStates(StatesGroup):
    """Состояние ожидания загрузки резюме (файлом или текстом)."""
    waiting_for_resume = State()


class MarketStandardsStates(StatesGroup):
    """Состояние ожидания ввода пользовательских стандартов рынка внутри бота."""
    waiting_for_custom_standards = State()


class SourceStates(StatesGroup):
    """Состояние ожидания ссылки на новый источник (сайт или ТГ-канал)."""
    waiting_for_source_url = State()


class ResourceSearchStates(StatesGroup):
    """Состояние ожидания запроса для поиска каналов, агрегаторов или компаний."""
    waiting_for_query = State()
