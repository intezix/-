"""
Telegram-бот рецептов питания.

Точка входа. Настраивает бота и запускает polling.

Два UX-режима:
- INLINE_WITH_FILTERS: Inline-кнопки + фильтры + Telegraph
- REPLY_SIMPLE: Reply-клавиатура + без фильтров + рецепты в сообщениях

Переключение режима: config.py → UX_MODE
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, UX_MODE, UXMode

# Импорт роутеров
from handlers import start
from handlers import inline_handlers
from handlers import reply_handlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_bot() -> Bot:
    """Создаёт экземпляр бота."""
    return Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )


def create_dispatcher() -> Dispatcher:
    """
    Создаёт диспетчер и регистрирует роутеры.
    
    В зависимости от UX_MODE регистрируются разные хендлеры.
    """
    # Используем MemoryStorage для FSM
    # Для продакшена можно заменить на Redis:
    # from aiogram.fsm.storage.redis import RedisStorage
    # storage = RedisStorage.from_url("redis://localhost:6379")
    storage = MemoryStorage()
    
    dp = Dispatcher(storage=storage)
    
    # Всегда регистрируем /start
    dp.include_router(start.router)
    
    # Регистрируем хендлеры в зависимости от режима
    if UX_MODE == UXMode.INLINE_WITH_FILTERS:
        logger.info("🔘 UX Mode: INLINE_WITH_FILTERS")
        dp.include_router(inline_handlers.router)
    else:
        logger.info("⌨️ UX Mode: REPLY_SIMPLE")
        dp.include_router(reply_handlers.router)
    
    return dp


async def main():
    """Главная функция запуска бота."""
    logger.info("🚀 Starting Recipe Bot...")
    
    bot = create_bot()
    dp = create_dispatcher()
    
    # Удаляем webhook если был установлен
    await bot.delete_webhook(drop_pending_updates=True)
    
    logger.info("📡 Bot is running. Press Ctrl+C to stop.")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped.")
