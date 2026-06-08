import base64
import logging
from typing import Any
import requests
from config import YOOKASSA_SECRET_KEY, YOOKASSA_SHOP_ID
logger = logging.getLogger(__name__)
API_BASE = 'https://api.yookassa.ru/v3'
TIMEOUT = 15

def _auth_header() -> str:
    raw = f'{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}'
    return 'Basic ' + base64.b64encode(raw.encode()).decode()

def _headers() -> dict[str, str]:
    return {'Authorization': _auth_header(), 'Content-Type': 'application/json', 'Idempotence-Key': ''}

def cancel_subscription(subscription_id: str) -> dict[str, Any] | None:
    url = f'{API_BASE}/subscriptions/{subscription_id}/cancel'
    import uuid
    req_headers = {**_headers(), 'Idempotence-Key': str(uuid.uuid4())}
    try:
        r = requests.post(url, headers=req_headers, json={}, timeout=TIMEOUT)
    except requests.RequestException as e:
        logger.exception('YooKassa request failed: %s', e)
        return None
    if r.status_code == 200:
        return r.json()
    logger.warning('YooKassa cancel_subscription %s: %s %s', subscription_id, r.status_code, r.text)
    return None

def get_subscription(subscription_id: str) -> dict[str, Any] | None:
    url = f'{API_BASE}/subscriptions/{subscription_id}'
    try:
        r = requests.get(url, headers=_headers(), timeout=TIMEOUT)
    except requests.RequestException as e:
        logger.exception('YooKassa get_subscription failed: %s', e)
        return None
    if r.status_code == 200:
        return r.json()
    logger.warning('YooKassa get_subscription %s: %s %s', subscription_id, r.status_code, r.text)
    return None