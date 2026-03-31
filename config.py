"""
Конфигурация Telegram-бота рецептов питания.

UX_MODE определяет режим работы бота:
- "INLINE_WITH_FILTERS": Inline-кнопки + фильтры + Telegraph для рецептов
- "REPLY_SIMPLE": Reply-клавиатура + без фильтров + рецепты в сообщениях
"""

from enum import Enum
from typing import Final
import os


class UXMode(str, Enum):
    """Режимы UX бота."""
    INLINE_WITH_FILTERS = "INLINE_WITH_FILTERS"
    REPLY_SIMPLE = "REPLY_SIMPLE"


# === ОСНОВНЫЕ НАСТРОЙКИ ===

# Токен бота (получить у @BotFather)
BOT_TOKEN: Final[str] = os.getenv("BOT_TOKEN", "7748935995:AAGpcKMurNU2Lx25WCdJf4IgPXTuDrI_NXE")

# Режим UX (раскомментируй нужный, закомментируй другой)
UX_MODE: Final[UXMode] = UXMode.INLINE_WITH_FILTERS  # Inline-кнопки + фильтры + Telegraph
#UX_MODE: Final[UXMode] = UXMode.REPLY_SIMPLE        # Reply-клавиатура, без фильтров

# === НАСТРОЙКИ ПАГИНАЦИИ ===

# Количество рецептов на странице
RECIPES_PER_PAGE: Final[int] = 3

# === TELEGRAPH НАСТРОЙКИ (для UX-режима №1) ===

# Токен Telegraph (получить через Telegraph API)
TELEGRAPH_TOKEN: Final[str] = os.getenv("TELEGRAPH_TOKEN", "")

# Автор страниц Telegraph
TELEGRAPH_AUTHOR: Final[str] = "Рецепты ПП"
TELEGRAPH_AUTHOR_URL: Final[str] = ""

# === ТЕКСТЫ БОТА ===

class Texts:
    """Все тексты бота в одном месте."""
    
    # Приветственное сообщение
    WELCOME = (
        "👋 <b>Добро пожаловать в бот рецептов ПП!</b>\n\n"
        "🥗 Здесь собраны проверенные рецепты правильного питания "
        "для завтрака, обеда и ужина.\n\n"
        "✅ Простые ингредиенты\n"
        "✅ Пошаговые инструкции\n"
        "✅ КБЖУ для каждого блюда\n"
        "✅ Удобные фильтры по времени и типу\n\n"
        "Нажмите <b>«Поехали»</b>, чтобы начать!"
    )
    
    # Кнопка старта
    LETS_GO = "🚀 Поехали"
    
    # Выбор приёма пищи
    CHOOSE_MEAL = "🍽 Выберите приём пищи:"
    
    # Категории
    MEAL_BREAKFAST = "🍳 Завтраки"
    MEAL_LUNCH = "🍲 Обеды"
    MEAL_DINNER = "🥗 Ужины"
    MEAL_SNACKS = "🥪 Перекусы"
    MEAL_DESSERTS = "🍰 Десерты"
    MEAL_SMOOTHIE = "🥤 Смузи"
    
    # Навигация
    BACK = "⬅️ Назад"
    NEXT = "➡️ Далее"
    TO_MENU = "📋 В меню"
    TO_MEALS = "🏠 К приёмам пищи"
    
    # Фильтры
    FILTERS = "🔍 Фильтры"
    APPLY_FILTERS = "✅ Применить"
    CLEAR_FILTERS = "🗑 Сбросить"
    
    # Рецепт
    OPEN_RECIPE = "📖 Открыть рецепт"
    SUITABLE = "✅ Подходит"
    NOT_SUITABLE = "❌ Не подходит"
    
    # Категории
    CHOOSE_CATEGORY = "Выберите категорию:"
    
    # Рецепты
    RECIPES_LIST = "📋 Рецепты ({start}-{end} из {total}):"
    NO_RECIPES = "😔 Рецепты не найдены"
    RECIPE_CHOSEN = "✅ Отличный выбор!"  # Показывается под рецептом
    
    # Фильтры (названия)
    FILTER_QUICK = "⚡️ До 10 минут"
    FILTER_ON_THE_GO = "🥪 На бегу"
    FILTER_SWEET = "🧁 Сладкие"
    FILTER_HEARTY = "🍳 Сытные"
    FILTER_NO_COOKING = "❄️ Без готовки"
    FILTER_NO_GLUTEN_LACTOSE = "🥛 Без глютена и лактозы"


# === ИДЕНТИФИКАТОРЫ ===

class MealType(str, Enum):
    """Типы категорий."""
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACKS = "snacks"
    DESSERTS = "desserts"
    SMOOTHIE = "smoothie"


class FilterTag(str, Enum):
    """Теги фильтров."""
    QUICK = "quick"           # до 10 минут
    ON_THE_GO = "on_the_go"   # на бегу
    SWEET = "sweet"           # сладкие
    HEARTY = "hearty"         # сытные
    NO_COOKING = "no_cooking" # без готовки
    NO_GLUTEN_LACTOSE = "no_gluten_lactose"  # без глютена и лактозы


# Маппинг фильтров к текстам
FILTER_TEXTS = {
    FilterTag.QUICK: Texts.FILTER_QUICK,
    FilterTag.ON_THE_GO: Texts.FILTER_ON_THE_GO,
    FilterTag.SWEET: Texts.FILTER_SWEET,
    FilterTag.HEARTY: Texts.FILTER_HEARTY,
    FilterTag.NO_COOKING: Texts.FILTER_NO_COOKING,
    FilterTag.NO_GLUTEN_LACTOSE: Texts.FILTER_NO_GLUTEN_LACTOSE,
}

# Маппинг категорий к текстам
MEAL_TEXTS = {
    MealType.BREAKFAST: Texts.MEAL_BREAKFAST,
    MealType.LUNCH: Texts.MEAL_LUNCH,
    MealType.DINNER: Texts.MEAL_DINNER,
    MealType.SNACKS: Texts.MEAL_SNACKS,
    MealType.DESSERTS: Texts.MEAL_DESSERTS,
    MealType.SMOOTHIE: Texts.MEAL_SMOOTHIE,
}
