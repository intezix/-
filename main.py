import asyncio
import logging
import warnings
warnings.filterwarnings('ignore', message='.*model_custom_emoji_id.*', category=UserWarning)
warnings.filterwarnings('ignore', module='pydantic._internal._fields')
from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import ExceptionTypeFilter
from aiogram.exceptions import TelegramNetworkError
from config import BOT_TOKEN, UX_MODE, UXMode, Texts
from middlewares.callback_debounce import CallbackDebounceMiddleware
from middlewares.activity_tracker import ActivityTrackerMiddleware
from middlewares.subscription_check import SubscriptionCheckMiddleware
from services.user_activity_service import UserActivityService
from keyboards import ReplyKeyboards
from services.ui_registry import register_ui_message
from handlers import start
from handlers import dev_admin
from handlers import inline_handlers
from handlers import reply_handlers
from handlers import favourites_handlers
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_bot() -> Bot:
    session = AiohttpSession(timeout=180)
    return Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

def create_dispatcher() -> Dispatcher:
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.update.middleware(SubscriptionCheckMiddleware())
    dp.update.middleware(CallbackDebounceMiddleware())
    dp.update.middleware(ActivityTrackerMiddleware())

    @dp.error(ExceptionTypeFilter(TelegramNetworkError))
    async def on_network_error(event: ErrorEvent, bot: Bot) -> None:
        logger.warning('TelegramNetworkError: %s (update_id=%s)', event.exception, event.update.update_id if event.update else None)
        chat_id = None
        if event.update and event.update.message:
            chat_id = event.update.message.chat.id
        elif event.update and event.update.callback_query and event.update.callback_query.message:
            chat_id = event.update.callback_query.message.chat.id
        if chat_id:
            try:
                await bot.send_message(chat_id, 'Сеть временно недоступна. Попробуйте через минуту или проверьте интернет/VPN.', protect_content=False)
            except Exception as e:
                logger.debug('Could not send network error message to user: %s', e)
    dp.include_router(start.router)
    dp.include_router(dev_admin.router)
    if UX_MODE == UXMode.INLINE_WITH_FILTERS:
        logger.info('🔘 UX Mode: INLINE_WITH_FILTERS')
        dp.include_router(inline_handlers.router)
        dp.include_router(favourites_handlers.router)
    else:
        logger.info('⌨️ UX Mode: REPLY_SIMPLE')
        dp.include_router(reply_handlers.router)
    return dp

async def main():
    logger.info('🚀 Starting Recipe Bot...')
    bot = create_bot()
    dp = create_dispatcher()
    for attempt in range(1, 4):
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            break
        except TelegramNetworkError as e:
            if attempt < 3:
                logger.warning('Сеть недоступна (попытка %s/3), повтор через 15 с: %s', attempt, e)
                await asyncio.sleep(15)
            else:
                logger.error('Не удалось подключиться к Telegram после 3 попыток. Проверьте интернет/VPN и запустите снова.')
                await bot.session.close()
                return
    logger.info('📡 Bot is running. Press Ctrl+C to stop.')

    async def inactivity_watcher() -> None:
        service = UserActivityService()
        hard_inactivity_seconds = 24 * 60 * 60    # через 24 часа – смс + кнопка НАЧАТЬ
        check_interval_seconds = 60
        while True:
            try:
                # Через 24 часа отправляем смс + кнопку НАЧАТЬ
                hard_users = service.get_users_for_inactivity_reminder(hard_inactivity_seconds)
                if hard_users:
                    logger.info(f'⏰ Inactivity watcher (hard): {len(hard_users)} users for reminder')
                for user_id, _ in hard_users:
                    try:
                        keyboard = ReplyKeyboards.start_over()
                        text = (
                            'Ты давно не заходил в бот 🤍\n\n'
                            'Нажми кнопку ниже, чтобы снова выбрать приём пищи и рецепты.'
                        )
                        msg = await bot.send_message(
                            chat_id=user_id,
                            text=text,
                            reply_markup=keyboard,
                            protect_content=False,
                        )
                        service.set_reminder(user_id, msg.message_id)
                        register_ui_message(
                            user_id=user_id,
                            chat_id=user_id,
                            message_id=msg.message_id,
                            kind='inactivity_start',
                            is_persistent=False,
                        )
                    except Exception as e:
                        logger.exception(f'Failed to send inactivity reminder to user {user_id}: {e}')
            except Exception as e:
                logger.exception(f'Error in inactivity watcher: {e}')
            await asyncio.sleep(check_interval_seconds)
    try:
        if UX_MODE == UXMode.INLINE_WITH_FILTERS:
            asyncio.create_task(inactivity_watcher())
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('👋 Bot stopped.')