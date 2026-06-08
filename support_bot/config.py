import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

def _get_env(key: str, default: str | None=None) -> str:
    val = os.environ.get(key)
    if val is not None:
        return val.strip()
    if default is not None:
        return default
    raise RuntimeError(f'Missing required env: {key}')
SUPPORT_BOT_TOKEN = _get_env('SUPPORT_BOT_TOKEN')
ADMIN_CHAT_IDS_STR = _get_env('ADMIN_CHAT_IDS')
ADMIN_CHAT_IDS = [x.strip() for x in ADMIN_CHAT_IDS_STR.split(',') if x.strip()]
ADMIN_CHAT_IDS = [int(cid) for cid in ADMIN_CHAT_IDS]
SUPPORT_GROUP_ID = int(_get_env('SUPPORT_GROUP_ID'))
_FALLBACK_STR = os.environ.get('SUPPORT_FALLBACK_ADMIN_CHAT_IDS', '') or ''
if _FALLBACK_STR.strip():
    SUPPORT_FALLBACK_ADMIN_CHAT_IDS = [int(x.strip()) for x in _FALLBACK_STR.split(',') if x.strip()]
else:
    SUPPORT_FALLBACK_ADMIN_CHAT_IDS: list[int] = []
YOOKASSA_SHOP_ID = _get_env('YOOKASSA_SHOP_ID')
YOOKASSA_SECRET_KEY = _get_env('YOOKASSA_SECRET_KEY')
YOOKASSA_RETURN_URL = _get_env('YOOKASSA_RETURN_URL', 'https://example.com/return')
TIMEZONE = _get_env('TIMEZONE', 'Europe/Europe/Amsterdam')
LOG_LEVEL = _get_env('LOG_LEVEL', 'INFO')
DB_PATH = BASE_DIR / 'support_bot.db'