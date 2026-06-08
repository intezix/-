import time
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update
from keyboards.inline import CallbackData
DEBOUNCE_SEC = 0.7
CLEANUP_AFTER_SEC = 10.0

class CallbackDebounceMiddleware(BaseMiddleware):

    def __init__(self, debounce_sec: float=DEBOUNCE_SEC):
        self.debounce_sec = debounce_sec
        self._last: Dict[tuple, float] = {}
        # Глобальная "занятость" по пользователю: пока обрабатывается один callback,
        # остальные просто игнорируются, чтобы не было гонок и дублей UI.
        self._busy_users: Dict[int, bool] = {}

    async def __call__(self, handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]], event: Update, data: Dict[str, Any]) -> Any:
        callback = event.callback_query
        if not callback:
            return await handler(event, data)
        user_id = callback.from_user.id if callback.from_user else 0
        # Глобальный антиспам: не даём обрабатывать несколько callback'ов параллельно для одного пользователя.
        if self._busy_users.get(user_id):
            await callback.answer()
            return
        self._busy_users[user_id] = True
        try:
            cb_data = callback.data or ''
            # Для категорий и выбора рецептов считаем любой клик одной "операцией".
            # Можно задать разные интервалы антиспама по типам кнопок.
            if cb_data.startswith(f'{CallbackData.CATEGORY}:'):
                key = (user_id, 'category')
                limit = self.debounce_sec  # ~0.7 c
            elif cb_data.startswith(f'{CallbackData.RECIPE}:'):
                key = (user_id, 'recipe')
                limit = max(self.debounce_sec, 1.8)  # более жёсткий антиспам для открытия рецептов
            else:
                key = (user_id, cb_data)
                limit = self.debounce_sec
            now = time.time()
            for k, t in list(self._last.items()):
                if now - t > CLEANUP_AFTER_SEC:
                    del self._last[k]
            if key in self._last and now - self._last[key] < limit:
                await callback.answer()
                return
            self._last[key] = now
            return await handler(event, data)
        finally:
            self._busy_users[user_id] = False