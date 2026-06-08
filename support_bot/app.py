import asyncio
import logging
import sys
import warnings
from pathlib import Path
warnings.filterwarnings('ignore', message='.*protected namespace.*')
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / '.env')
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from config import LOG_LEVEL, SUPPORT_BOT_TOKEN
import db
from handlers import router
logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO), format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

async def main() -> None:
    db.run_migrations()
    bot = Bot(token=SUPPORT_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('Support bot stopped.')