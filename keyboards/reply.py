from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from typing import List
from config import Texts, MealType, MEAL_TEXTS
from services.recipe_service import Recipe, Category

class ReplyKeyboards:

    @staticmethod
    def welcome_step1() -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        builder.button(text=Texts.CONTINUE)
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def welcome_step2() -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        builder.button(text=Texts.PAY)
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def welcome_step3() -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        builder.button(text=Texts.GO_TO_CATEGORIES)
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def welcome() -> ReplyKeyboardMarkup:
        return ReplyKeyboards.welcome_step1()

    @staticmethod
    def meals() -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        active_meals = [MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER]
        for meal_type in active_meals:
            builder.button(text=MEAL_TEXTS[meal_type])
        builder.adjust(1)
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def categories(categories: List[Category]) -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        for cat in categories:
            builder.button(text=cat.name)
        builder.button(text=Texts.TO_MEALS)
        builder.adjust(1)
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def recipes_list(recipes: List[Recipe], has_prev: bool, has_next: bool) -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        for recipe in recipes:
            builder.button(text=recipe.name)
        nav_row = []
        if has_prev:
            nav_row.append(KeyboardButton(text=Texts.BACK))
        if has_next:
            nav_row.append(KeyboardButton(text=Texts.NEXT))
        builder.adjust(1)
        if nav_row:
            builder.row(*nav_row)
        builder.row(KeyboardButton(text=Texts.TO_MENU))
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def recipe_detail() -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        builder.row(KeyboardButton(text=Texts.SUITABLE), KeyboardButton(text=Texts.NOT_SUITABLE))
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def recipe_accepted() -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        builder.button(text=Texts.TO_MENU)
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def start_over() -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        builder.button(text=Texts.START_OVER)
        return builder.as_markup(resize_keyboard=True)