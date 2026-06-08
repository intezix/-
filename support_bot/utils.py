import logging
from datetime import datetime
from typing import Any
from aiogram import Bot
from aiogram.types import Message
from config import ADMIN_CHAT_IDS, SUPPORT_FALLBACK_ADMIN_CHAT_IDS, SUPPORT_GROUP_ID
import db
logger = logging.getLogger(__name__)
_recent_submitters: set[int] = set()

def mark_recent_submitter(user_id: int) -> None:
    _recent_submitters.add(user_id)

def is_recent_submitter(user_id: int) -> bool:
    return user_id in _recent_submitters

def clear_recent_submitter(user_id: int) -> None:
    _recent_submitters.discard(user_id)
MESSAGE_HINT = 'Пожалуйста, напишите всё одним сообщением 🙏\nОпишите подробно:\n— что именно произошло\n— на каком шаге (какая кнопка/экран)\n— что ожидали увидеть\n— что получилось по факту\nЕсли есть скрин — прикрепите сюда в этом же сообщении.'
ALREADY_ACCEPTED = 'Спасибо! Ваше сообщение уже принято 🤍\nЕсли хотите добавить детали — нажмите кнопку нужного раздела ещё раз и отправьте одним сообщением.'
TOPIC_LABELS = {'CANCEL': 'Отмена подписки', 'FEEDBACK': 'Пожелания', 'ISSUE_PAYMENT': 'Проблема с оплатой', 'ISSUE_BOT': 'Проблема с ботом', 'OTHER': 'Другое'}

def _fallback_chats() -> list[int]:
    return SUPPORT_FALLBACK_ADMIN_CHAT_IDS or ADMIN_CHAT_IDS

def format_user_info(message: Message) -> str:
    user = message.from_user
    if not user:
        return 'Unknown'
    name = (user.first_name or '') + (' ' + (user.last_name or '')).strip()
    username = f'@{user.username}' if user.username else '—'
    return f'{name} ({username})'

async def safe_send(bot: Bot, chat_id: int, text: str, **kwargs: Any) -> bool:
    try:
        await bot.send_message(chat_id, text, **kwargs)
        return True
    except Exception as e:
        logger.exception('safe_send to %s: %s', chat_id, e)
        return False

async def notify_admins_fallback(bot: Bot, text: str) -> None:
    for cid in _fallback_chats():
        await safe_send(bot, cid, text)

async def _ensure_user_topic(bot: Bot, message: Message) -> tuple[int | None, bool]:
    user = message.from_user
    if not user or not SUPPORT_GROUP_ID:
        return (None, False)
    uid_str = str(user.id)
    existing = db.get_user_topic(uid_str)
    if existing:
        return (existing, False)
    title_parts = [user.first_name or '']
    if user.username:
        title_parts.append(f'(@{user.username})')
    title_parts.append(f'| {user.id}')
    title = ' '.join((p for p in title_parts if p)).strip() or str(user.id)
    try:
        topic = await bot.create_forum_topic(chat_id=SUPPORT_GROUP_ID, name=title)
        thread_id = topic.message_thread_id
        db.save_user_topic(uid_str, thread_id)
        return (thread_id, True)
    except Exception as e:
        logger.exception('Failed to create forum topic for user %s: %s', uid_str, e)
        return (None, False)

async def send_ticket_to_forum(bot: Bot, logical_topic: str, message: Message, body_text: str) -> None:
    thread_id, created_new = await _ensure_user_topic(bot, message)
    user = message.from_user
    if thread_id is None or not user:
        header = f"[PP SUPPORT]\n👤 UserID: {(user.id if user else '?')}\n👥 Username: @{user.username}" if user and user.username else '👥 Username: —'
        header = header + '\nText: ' + (body_text or '')
        await notify_admins_fallback(bot, header)
        return
    uid = user.id
    username = f'@{user.username}' if user.username else '—'
    name = (user.first_name or '') + (' ' + (user.last_name or '')).strip()
    if created_new:
        ts = datetime.utcnow().isoformat() + 'Z'
        header = f"[PP SUPPORT]\n👤 {name or '—'} {username}\n🆔 {uid}\n🕒 {ts}\n🎯 Тема: {TOPIC_LABELS.get(logical_topic, logical_topic)}"
        await safe_send(bot, SUPPORT_GROUP_ID, header, message_thread_id=thread_id)
    try:
        await bot.copy_message(SUPPORT_GROUP_ID, from_chat_id=message.chat.id, message_id=message.message_id, message_thread_id=thread_id)
    except Exception as e:
        logger.exception('Failed to copy user message to topic %s: %s', thread_id, e)

async def send_cancel_event_to_forum(bot: Bot, logical_topic: str, message: Message, text: str) -> None:
    thread_id, _ = await _ensure_user_topic(bot, message)
    if thread_id is None:
        await notify_admins_fallback(bot, text)
        return
    await safe_send(bot, SUPPORT_GROUP_ID, f'{text}\n\n[Topic: {logical_topic}]', message_thread_id=thread_id)