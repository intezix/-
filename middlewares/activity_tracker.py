from typing import Callable, Dict, Any, Awaitable, Optional
from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery
from config import Texts
from services.inactivity_flow import is_inactivity_start_callback, is_start_over_text
from services.user_activity_service import UserActivityService
from services.ui_registry import remove_inactivity_prompt
from events_writer import log_event

class ActivityTrackerMiddleware(BaseMiddleware):

    def __init__(self) -> None:
        self._service = UserActivityService()

    async def __call__(self, handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]], event: Update, data: Dict[str, Any]) -> Any:
        message: Optional[Message] = event.message or event.edited_message
        callback: Optional[CallbackQuery] = event.callback_query
        user_id: Optional[int] = None
        user_text: Optional[str] = None
        if message and message.from_user:
            user_id = message.from_user.id
            user_text = message.text or message.caption
        elif callback and callback.from_user:
            user_id = callback.from_user.id
        if user_id is None:
            return await handler(event, data)

        # Unified event log (best-effort)
        try:
            if callback:
                await log_event(
                    source_bot="main_bot",
                    telegram_user_id=user_id,
                    event_type="UI_CALLBACK",
                    action="нажатие кнопки",
                    screen=None,
                    status="ok",
                    payload_json={"update_id": event.update_id},
                    callback_data=callback.data,
                    username=callback.from_user.username if callback.from_user else None,
                )
            elif message:
                await log_event(
                    source_bot="main_bot",
                    telegram_user_id=user_id,
                    event_type="UI_MESSAGE",
                    action="сообщение",
                    screen=None,
                    status="ok",
                    payload_json={"update_id": event.update_id},
                    message_text=user_text,
                    username=message.from_user.username if message.from_user else None,
                )
        except Exception:
            pass

        self._service.update_activity(user_id)
        reminder_message_id = self._service.get_reminder_message_id(user_id)
        if reminder_message_id is not None:
            skip_removal = (message and is_start_over_text(user_text)) or (
                callback and is_inactivity_start_callback(callback.data)
            )
            if not skip_removal:
                bot = None
                msg_id_for_log = None
                cb_data = None
                if callback:
                    bot = callback.message.bot
                    msg_id_for_log = callback.message.message_id
                    cb_data = callback.data
                elif message:
                    bot = message.bot
                    msg_id_for_log = message.message_id

                if callback:
                    # Reminder exists, user clicked ANY other UI element.
                    import logging

                    logging.getLogger(__name__).info(
                        "[UI_REGISTRY] regular callback with active inactivity prompt user=%s msg=%s data=%s",
                        user_id,
                        msg_id_for_log,
                        cb_data,
                    )

                try:
                    # Remove prompt from persistent registry first.
                    await remove_inactivity_prompt(user_id=user_id, bot=bot)
                except Exception:
                    pass

                # Fallback: delete by known reminder message id (idempotent).
                try:
                    if bot is not None:
                        await bot.delete_message(chat_id=user_id, message_id=reminder_message_id)
                except Exception:
                    try:
                        if bot is not None:
                            await bot.edit_message_reply_markup(
                                chat_id=user_id,
                                message_id=reminder_message_id,
                                reply_markup=None,
                            )
                    except Exception:
                        pass

                # Always clear scheduling record.
                self._service.clear_reminder(user_id)

                import logging

                logging.getLogger(__name__).info(
                    "[UI_REGISTRY] inactivity prompt removed user=%s",
                    user_id,
                )
        return await handler(event, data)