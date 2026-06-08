from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
BTN_FEEDBACK = '📄 Ваши пожелания'
BTN_ISSUES = '❓ У меня проблемы'
BTN_ISSUE_PAYMENT = '💳 Проблема с оплатой'
BTN_ISSUE_BOT = '🤖 Проблема с ботом'
BTN_ISSUE_OTHER = '🧩 Другое'
BTN_BACK = '🔙 Назад'
BTN_BACK_MENU = '🔙 В меню'

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_FEEDBACK)], [KeyboardButton(text=BTN_ISSUES)]], resize_keyboard=True)

def back_to_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_BACK_MENU)]], resize_keyboard=True)

def issues_submenu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_ISSUE_PAYMENT)], [KeyboardButton(text=BTN_ISSUE_BOT)], [KeyboardButton(text=BTN_ISSUE_OTHER)], [KeyboardButton(text=BTN_BACK_MENU)]], resize_keyboard=True)