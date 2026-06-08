from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Set
from config import Texts, MealType, FilterTag, FILTER_TEXTS, MEAL_TEXTS, FILTERS_ACTIVE, FILTERS_ACTIVE_LUNCH_DINNER, FIRST_RECIPE_ID, GUIDE_RECIPES
from services.recipe_service import Recipe, Category, RecipeService


class CallbackData:
    LETS_GO = "lets_go"
    WELCOME_CONTINUE = "welcome:continue"
    WELCOME_PAY = "welcome:pay"
    WELCOME_GO_TO_CATEGORIES = "welcome:go_to_categories"
    MEAL = "meal"
    CATEGORY = "cat"
    FILTER = "filter"
    APPLY_FILTERS = "apply_filters"
    CLEAR_FILTERS = "clear_filters"
    SHOW_FILTERS = "show_filters"
    RECIPE = "recipe"
    RECIPE_SUITABLE = "suitable"
    RECIPE_NOT_SUITABLE = "not_suitable"
    RECIPE_BACK = "recipe:back"
    RECIPE_PHOTOS_BACK = "recipe_photos_back"
    RECIPE_PHOTO_FAV = "recipe_photo_fav"
    RECIPE_PHOTO_FAV_REMOVE = "recipe_photo_fav_remove"
    RECIPE_GUIDE = "recipe:guide"
    PAGE_PREV = "page_prev"
    PAGE_NEXT = "page_next"
    TO_MENU = "to_menu"
    TO_MEALS = "to_meals"
    OPEN_RECIPE = "open_recipe"
    FAV_REMOVE = "fav_remove"
    FAVOURITES = "favourites"
    FAV_PAGE_PREV = "fav_page_prev"
    FAV_PAGE_NEXT = "fav_page_next"
    FAV_ENTER = "fav:enter"
    FAV_TOGGLE = "fav:toggle"
    FAV_COMMIT = "fav:commit"
    FAV_CANCEL = "fav:cancel"
    FAV_DELETE_ENTER = "fav:delete_enter"
    FAV_DELETE_COMMIT = "fav:delete_commit"
    FAV_DELETE_CANCEL = "fav:delete_cancel"
    SUBSCRIPTION_CHECK = "subscription_check"
    INACTIVITY_START = "inactivity:start"


class InlineKeyboards:
    @staticmethod
    def welcome_step1() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text=Texts.CONTINUE, callback_data=CallbackData.WELCOME_CONTINUE)
        return builder.as_markup()

    @staticmethod
    def welcome_step2() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text=Texts.PAY, callback_data=CallbackData.WELCOME_PAY)
        return builder.as_markup()

    @staticmethod
    def welcome_step3() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text=Texts.GO_TO_CATEGORIES, callback_data=CallbackData.WELCOME_GO_TO_CATEGORIES)
        return builder.as_markup()

    @staticmethod
    def welcome() -> InlineKeyboardMarkup:
        return InlineKeyboards.welcome_step1()

    @staticmethod
    def inactivity_prompt() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text=Texts.START_OVER, callback_data=CallbackData.INACTIVITY_START)
        return builder.as_markup()

    @staticmethod
    def meals() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        active_meals = [MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER]
        for meal_type in active_meals:
            builder.button(text=MEAL_TEXTS[meal_type], callback_data=f"{CallbackData.MEAL}:{meal_type.value}")
        builder.button(text="⭐ Избранное", callback_data=CallbackData.FAVOURITES)
        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def categories(categories: List[Category], show_filters_button: bool = True) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for cat in categories:
            builder.button(text=cat.name, callback_data=f"{CallbackData.CATEGORY}:{cat.id}")
        builder.adjust(1)
        if show_filters_button:
            builder.row(InlineKeyboardButton(text=Texts.FILTERS, callback_data=CallbackData.SHOW_FILTERS))
        builder.row(InlineKeyboardButton(text=Texts.TO_MEALS, callback_data=CallbackData.TO_MEALS))
        return builder.as_markup()

    @staticmethod
    def filters(selected_filters: Set[str], meal_type: str = None, recipe_service: RecipeService = None) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        if meal_type in ("lunch", "dinner"):
            if meal_type == "lunch":
                active_filters = tuple((ft for ft in FILTERS_ACTIVE_LUNCH_DINNER if ft is not FilterTag.LIGHT))
            else:
                active_filters = FILTERS_ACTIVE_LUNCH_DINNER
        else:
            active_filters = FILTERS_ACTIVE
        for filter_tag in active_filters:
            is_selected = filter_tag.value in selected_filters
            if is_selected:
                text = f"{FILTER_TEXTS[filter_tag]}  ✓"
            else:
                text = FILTER_TEXTS[filter_tag]
            is_disabled = False
            if meal_type in ("lunch", "dinner") and recipe_service is not None:
                is_available = recipe_service.is_filter_available(meal_type, selected_filters, filter_tag.value)
                is_disabled = not is_available
            builder.button(text=text, callback_data=f"{CallbackData.FILTER}:{filter_tag.value}", disabled=is_disabled)
        builder.adjust(1)
        builder.row(
            InlineKeyboardButton(text=Texts.APPLY_FILTERS, callback_data=CallbackData.APPLY_FILTERS),
            InlineKeyboardButton(text=Texts.CLEAR_FILTERS, callback_data=CallbackData.CLEAR_FILTERS),
        )
        builder.row(InlineKeyboardButton(text=Texts.TO_MENU, callback_data=CallbackData.TO_MENU))
        return builder.as_markup()

    @staticmethod
    def recipes_list(
        recipes: List[Recipe],
        has_prev: bool,
        has_next: bool,
        telegraph_urls: dict = None,
        user_favourites: Set[str] = None,
        selection_mode: bool = False,
        selected_recipe_ids: Set[str] = None,
        selection_context: str = None,
        page_offset: int = 0,
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        if selected_recipe_ids is None:
            selected_recipe_ids = set()
        if selection_mode:
            for i, recipe in enumerate(recipes):
                is_selected = recipe.id in selected_recipe_ids
                text = f"{recipe.name}  ✓" if is_selected else recipe.name
                builder.button(text=text, callback_data=f"{CallbackData.FAV_TOGGLE}:{i}")
            builder.adjust(1)
            builder.row(
                InlineKeyboardButton(text="✅ Добавить", callback_data=CallbackData.FAV_COMMIT),
                InlineKeyboardButton(text="❌ Отмена", callback_data=CallbackData.FAV_CANCEL),
            )
            nav_buttons = []
            if has_prev:
                nav_buttons.append(InlineKeyboardButton(text=Texts.BACK, callback_data=CallbackData.PAGE_PREV))
            if has_next:
                nav_buttons.append(InlineKeyboardButton(text=Texts.NEXT, callback_data=CallbackData.PAGE_NEXT))
            if nav_buttons:
                builder.row(*nav_buttons)
            builder.row(InlineKeyboardButton(text=Texts.TO_MENU, callback_data=CallbackData.TO_MENU))
        else:
            for i, recipe in enumerate(recipes):
                builder.button(text=recipe.name, callback_data=f"{CallbackData.RECIPE}:{i}")
            builder.adjust(1)
            nav_buttons = []
            if has_prev:
                nav_buttons.append(InlineKeyboardButton(text=Texts.BACK, callback_data=CallbackData.PAGE_PREV))
            if has_next:
                nav_buttons.append(InlineKeyboardButton(text=Texts.NEXT, callback_data=CallbackData.PAGE_NEXT))
            if nav_buttons:
                builder.row(*nav_buttons)
            builder.row(InlineKeyboardButton(text=Texts.TO_MENU, callback_data=CallbackData.TO_MENU))
        return builder.as_markup()

    @staticmethod
    def recipe_detail(recipe_id: str, telegraph_url: str = None, show_guide_button: bool = False) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text=Texts.SUITABLE, callback_data=CallbackData.RECIPE_SUITABLE),
            InlineKeyboardButton(text=Texts.NOT_SUITABLE, callback_data=CallbackData.RECIPE_NOT_SUITABLE),
        )
        return builder.as_markup()

    @staticmethod
    def guide_back() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text="◀️ Назад", callback_data=CallbackData.RECIPE_BACK)
        return builder.as_markup()

    @staticmethod
    def recipe_accepted() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text=Texts.TO_MENU, callback_data=CallbackData.TO_MENU)
        return builder.as_markup()

    @staticmethod
    def recipe_accepted_with_url(telegraph_url: str) -> InlineKeyboardMarkup:
        return InlineKeyboards.recipe_accepted()

    @staticmethod
    def recipe_photos_controls(recipe_id: str, in_favourites: bool = False, show_favourites: bool = True) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        if show_favourites:
            if in_favourites:
                builder.button(text=Texts.FAVOURITES_REMOVE_BTN, callback_data=CallbackData.RECIPE_PHOTO_FAV_REMOVE)
            else:
                builder.button(text="⭐ Добавить в избранное", callback_data=CallbackData.RECIPE_PHOTO_FAV)
        builder.button(text=Texts.BACK, callback_data=CallbackData.RECIPE_PHOTOS_BACK)
        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def favourites_list(
        recipes: List[Recipe],
        has_prev: bool,
        has_next: bool,
        telegraph_urls: dict = None,
        delete_mode: bool = False,
        selected_recipe_ids: Set[str] = None,
        page_offset: int = 0,
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        if selected_recipe_ids is None:
            selected_recipe_ids = set()
        if delete_mode:
            for i, recipe in enumerate(recipes):
                is_selected = recipe.id in selected_recipe_ids
                text = f"{recipe.name}  ✓" if is_selected else recipe.name
                builder.button(text=text, callback_data=f"{CallbackData.FAV_TOGGLE}:{i}")
            builder.adjust(1)
            builder.row(
                InlineKeyboardButton(text="🗑 Удалить", callback_data=CallbackData.FAV_DELETE_COMMIT),
                InlineKeyboardButton(text="❌ Отмена", callback_data=CallbackData.FAV_DELETE_CANCEL),
            )
            nav_buttons = []
            if has_prev:
                nav_buttons.append(InlineKeyboardButton(text=Texts.BACK, callback_data=CallbackData.FAV_PAGE_PREV))
            if has_next:
                nav_buttons.append(InlineKeyboardButton(text=Texts.NEXT, callback_data=CallbackData.FAV_PAGE_NEXT))
            if nav_buttons:
                builder.row(*nav_buttons)
            builder.row(InlineKeyboardButton(text=Texts.TO_MENU, callback_data=CallbackData.TO_MENU))
        else:
            for i, recipe in enumerate(recipes):
                builder.button(text=recipe.name, callback_data=f"{CallbackData.RECIPE}:{i}")
            builder.adjust(1)
            nav_buttons = []
            if has_prev:
                nav_buttons.append(InlineKeyboardButton(text=Texts.BACK, callback_data=CallbackData.FAV_PAGE_PREV))
            if has_next:
                nav_buttons.append(InlineKeyboardButton(text=Texts.NEXT, callback_data=CallbackData.FAV_PAGE_NEXT))
            if nav_buttons:
                builder.row(*nav_buttons)
            builder.row(InlineKeyboardButton(text=Texts.TO_MENU, callback_data=CallbackData.TO_MENU))
        return builder.as_markup()

    @staticmethod
    def subscription_payment(confirmation_url: str, payment_id: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="Перейти к оплате", url=confirmation_url))
        builder.row(InlineKeyboardButton(text="✅ Я оплатил — проверить", callback_data=f"{CallbackData.SUBSCRIPTION_CHECK}:{payment_id}"))
        return builder.as_markup()