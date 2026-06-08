from enum import Enum
from typing import Final
import os

from dotenv import load_dotenv


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env: {name}")
    return value


def _parse_int_set(raw: str) -> set[int]:
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    out: set[int] = set()
    for p in parts:
        try:
            out.add(int(p))
        except ValueError:
            continue
    return out


class UXMode(str, Enum):
    INLINE_WITH_FILTERS = "INLINE_WITH_FILTERS"
    REPLY_SIMPLE = "REPLY_SIMPLE"


load_dotenv()

BOT_TOKEN = _required_env("BOT_TOKEN")
DEV_ADMIN_IDS: Final[set[int]] = _parse_int_set(os.getenv("DEV_ADMIN_IDS", ""))
UX_MODE: Final[UXMode] = UXMode.INLINE_WITH_FILTERS
RECIPE_PHOTOS_MODE: Final[int] = 1
RECIPES_PER_PAGE: Final[int] = 3
TELEGRAPH_TOKEN: Final[str] = os.getenv("TELEGRAPH_TOKEN", "")
TELEGRAPH_AUTHOR: Final[str] = "Рецепты ПП"
TELEGRAPH_AUTHOR_URL: Final[str] = ""
RECIPES_HEADER_IMAGE_URL: Final[str] = "https://files.catbox.moe/ows59e.png"
GUIDE_IMAGE_URL: Final[str] = "https://files.catbox.moe/dcgp79.png"
GUIDE_RECIPES: Final[dict] = {"_омлет_с_помидорами": "omletspomidorami1.png", "_омлет_с_сыром": "2рецепт.png"}
FIRST_RECIPE_ID: Final[str] = "_омлет_с_помидорами"
PROTECT_CONTENT: Final[bool] = False
YOOKASSA_SHOP_ID: Final[str] = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY: Final[str] = os.getenv("YOOKASSA_SECRET_KEY", "")
SUBSCRIPTION_PRICE_RUB: Final[int] = 590
SUBSCRIPTION_PERIOD_DAYS: Final[int] = 30


class Texts:
    WELCOME_STEP1 = "<b>Привет</b> 🤍\nТы в закрытой базе рецептов от <b>katti eyes</b>.\n\n<b>Здесь ты получишь:</b>\n\n🥑 завтраки, обеды, ужины\n🧠 готовые рационы\n✨ рецепты с КБЖУ\n\n<b>Если ты хочешь питаться быстро, вкусно и без сложных рецептов — тебе сюда!</b>\n\n<i>Нажми на кнопку «Продолжить», чтобы открыть доступ.</i>"
    WELCOME_STEP1_NO_BUTTON = "<b>Привет</b> 🤍\nТы в закрытой базе рецептов от <b>katti eyes</b>.\n\n<b>Здесь ты получишь:</b>\n\n🥑 завтраки, обеды, ужины\n🧠 готовые рационы\n✨ рецепты с КБЖУ\n\n<b>Если ты хочешь питаться быстро, вкусно и без сложных рецептов — тебе сюда!</b>"
    WELCOME_STEP2 = "<b>Ты почти внутри</b> 🤍\n\nПосле оплаты тебе откроется полный доступ к базе рецептов:\n\n✓ 100+ ПП-блюд\n✓ КБЖУ каждого рецепта\n✓ новые рецепты каждый месяц\n✓ удобные фильтры и категории\n\n💎 Спеццена для новых пользователей:\n<b>590 ₽ вместо <s>890</s> ₽ / месяц.</b>\n\n<i>Далее — 590 ₽ ежемесячно.</i>\n<i>*Цена продления фиксируется за вами при покупке и сохраняется на весь период подписки</i>\n\n<i>Нажми на кнопку «Оплатить», чтобы открыть полный доступ.</i>"
    WELCOME_STEP3 = "<b>Готово</b> 🎉\nДоступ к <b>PP BOT</b> активирован!\n\n📖 Теперь тебе доступны все рецепты.\n\n<i>Выбирай категорию и начинай готовить вкусно и полезно 🤍</i>\n\nКнопка <i>«Перейти к категориям»</i>"
    CONTINUE = "Продолжить"
    PAY = "💳 Оплатить 590 ₽"
    GO_TO_CATEGORIES = "Перейти к категориям"
    WELCOME = WELCOME_STEP1
    WELCOME_NO_BUTTON = WELCOME_STEP1
    LETS_GO = CONTINUE
    CHOOSE_MEAL = "🍽 Выберите приём пищи:"
    MEAL_BREAKFAST = "🍳 Завтраки"
    MEAL_LUNCH = "🍲 Обеды"
    MEAL_DINNER = "🥗 Ужины"
    BACK = "⬅️ Назад"
    NEXT = "➡️ Далее"
    TO_MENU = "📋 В меню"
    TO_MEALS = "⬅️ К приёмам пищи"
    START_OVER = "НАЧАТЬ"
    FILTERS = "🔍 Фильтры"
    APPLY_FILTERS = "✅ Применить"
    CLEAR_FILTERS = "🗑 Сбросить"
    OPEN_RECIPE = "📖 Открыть рецепт"
    SUITABLE = "✅ Подходит"
    NOT_SUITABLE = "❌ Не подходит"
    CHOOSE_CATEGORY = "Выберите категорию:"
    RECIPES_LIST = "📋 Рецепты ({start}-{end} из {total}):"
    NO_RECIPES = "😔 Рецепты не найдены"
    RECIPE_CHOSEN = "✅ Отличный выбор!"
    FAVOURITES_HINT = "Нажми ⭐ рядом с рецептом — сохраню в избранное"
    FAVOURITES_EMPTY = "Ты пока ничего не добавил в избранное ⭐"
    FAVOURITES_ADDED = "Сохранил в избранное ⭐"
    FAVOURITES_ALREADY = "Этот рецепт уже в избранном ⭐"
    FAVOURITES_REMOVED = "Удалено из избранного"
    FAVOURITES_REMOVE_BTN = "🗑 Удалить из избранного"
    FAVOURITES_TITLE = "⭐ ИЗБРАННОЕ"
    FILTER_QUICK = "⚡️ До 10 минут"
    FILTER_SWEET = "🧁 Сладкие"
    FILTER_HEARTY = "🍳 Сытные"
    FILTER_NO_COOKING = "❄️ Без готовки"
    FILTER_NO_GLUTEN_LACTOSE = "🥛 Без глютена и лактозы"
    FILTER_OVEN = "💨 В духовке"
    FILTER_QUICK_25 = "⚡️ До 25 минут"
    FILTER_LIGHT = "🥗 Легкие"
    FILTER_PROTEIN = "🥚 Белковые"
    FILTER_BALANCED = "⚖️ Сбалансированные"


class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACKS = "snacks"
    DESSERTS = "desserts"
    SMOOTHIE = "smoothie"


class FilterTag(str, Enum):
    QUICK = "quick"
    SWEET = "sweet"
    HEARTY = "hearty"
    NO_COOKING = "no_cooking"
    NO_GLUTEN_LACTOSE = "no_gluten_lactose"
    OVEN = "oven"
    QUICK_25 = "quick_25"
    LIGHT = "light"
    PROTEIN = "protein"
    BALANCED = "balanced"


FILTER_TEXTS = {
    FilterTag.QUICK: Texts.FILTER_QUICK,
    FilterTag.SWEET: Texts.FILTER_SWEET,
    FilterTag.HEARTY: Texts.FILTER_HEARTY,
    FilterTag.NO_COOKING: Texts.FILTER_NO_COOKING,
    FilterTag.NO_GLUTEN_LACTOSE: Texts.FILTER_NO_GLUTEN_LACTOSE,
    FilterTag.OVEN: Texts.FILTER_OVEN,
    FilterTag.QUICK_25: Texts.FILTER_QUICK_25,
    FilterTag.LIGHT: Texts.FILTER_LIGHT,
    FilterTag.PROTEIN: Texts.FILTER_PROTEIN,
    FilterTag.BALANCED: Texts.FILTER_BALANCED,
}
FILTERS_ACTIVE = (FilterTag.QUICK, FilterTag.SWEET, FilterTag.HEARTY)
FILTERS_ACTIVE_LUNCH_DINNER = (FilterTag.OVEN, FilterTag.QUICK_25, FilterTag.HEARTY, FilterTag.LIGHT, FilterTag.PROTEIN, FilterTag.BALANCED)
MEAL_TEXTS = {MealType.BREAKFAST: Texts.MEAL_BREAKFAST, MealType.LUNCH: Texts.MEAL_LUNCH, MealType.DINNER: Texts.MEAL_DINNER}