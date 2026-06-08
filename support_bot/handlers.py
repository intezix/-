import logging
from datetime import datetime
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from config import SUPPORT_GROUP_ID
import db
import keyboards as kb
from states import SupportStates
from utils import ALREADY_ACCEPTED, mark_recent_submitter, is_recent_submitter, clear_recent_submitter, notify_admins_fallback, safe_send, send_ticket_to_forum
logger = logging.getLogger(__name__)
router = Router()
START_TEXT = 'Служба поддержки <b>PP BOT</b> на связи 🤍\nПожалуйста, выберите тему обращения ниже или опишите вопрос — мы постараемся помочь как можно быстрее.'
FEEDBACK_INTRO = 'Пожалуйста, поделитесь вашими впечатлениями и предложениями по улучшению <b>PP BOT</b>.\n\nМы внимательно относимся к обратной связи и учитываем пожелания пользователей, чтобы ежедневно совершенствовать сервис и делать его более удобным и полезным для вас 🤍'
FEEDBACK_THANKS = 'Благодарим вас за обратную связь и уделённое время.\n\nВаши пожелания и предложения очень ценны для нас — именно благодаря таким отзывам мы можем развивать <b>PP BOT</b> и делать его ещё удобнее и полезнее 🤍'
ISSUE_ACCEPTED = 'Принято 🤍 Спасибо! Мы уже разбираемся и вернёмся с ответом.'
PAYMENT_HEADER = '<b>Благодарим за обращение 🤍</b>'
PAYMENT_BODY = 'Пожалуйста, опишите подробнее, с какой именно сложностью при оплате вы столкнулись:\n<i>— на каком этапе возникает ошибка;\n— появляется ли уведомление или сообщение об отказе;\n— каким способом вы пытались произвести оплату.</i>\n\nЧем подробнее будет информация, тем быстрее мы сможем разобраться и помочь вам.'
PAYMENT_PROMPT = PAYMENT_HEADER + '\n\n' + PAYMENT_BODY
BOT_PROMPT = '<b>Благодарим за сообщение 🤍</b>\n\nПожалуйста, уточните, в чём именно заключается проблема с работой бота:\n<i>— бот не отвечает на команды;\n— некорректно открываются разделы;\n— не отображается контент;\n— появляется ошибка или уведомление.</i>\n\nОпишите ситуацию подробнее (при необходимости укажите устройство и версию Telegram) — это поможет нам быстрее выявить причину и устранить проблему.'
OPERATOR_REPLY = 'Ваш запрос передан специалисту.\nВ ближайшее время к диалогу подключится оператор и поможет вам решить вопрос.\n\n<i>Благодарим за ожидание 🤍</i>'

def _get_message_text(msg: Message) -> str:
    if msg.text:
        return msg.text
    if msg.caption:
        return msg.caption
    return '[медиа без подписи]'

@router.message(CommandStart(), F.chat.type == 'private')
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    try:
        await message.answer(START_TEXT, reply_markup=kb.main_menu())
    except Exception as e:
        logger.exception('cmd_start: %s', e)

@router.message(Command('cancel'), F.chat.type == 'private')
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    try:
        await message.answer('Действие отменено. Вы в главном меню.', reply_markup=kb.main_menu())
    except Exception as e:
        logger.exception('cmd_cancel: %s', e)

@router.message(F.text.in_([kb.BTN_BACK_MENU, kb.BTN_BACK]), F.chat.type == 'private')
async def btn_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    try:
        await message.answer(START_TEXT, reply_markup=kb.main_menu())
    except Exception as e:
        logger.exception('btn_back: %s', e)

@router.message(F.text == kb.BTN_FEEDBACK, F.chat.type == 'private')
async def btn_feedback(message: Message, state: FSMContext) -> None:
    await state.update_data(topic='FEEDBACK')
    await state.set_state(SupportStates.waiting_message)
    await message.answer(FEEDBACK_INTRO, reply_markup=kb.back_to_menu())

@router.message(F.text == kb.BTN_ISSUES, F.chat.type == 'private')
async def btn_issues(message: Message, state: FSMContext) -> None:
    await message.answer('Выберите тип проблемы:', reply_markup=kb.issues_submenu())

@router.message(F.text.in_([kb.BTN_ISSUE_PAYMENT, kb.BTN_ISSUE_BOT, kb.BTN_ISSUE_OTHER]), F.chat.type == 'private')
async def btn_issue_topic(message: Message, state: FSMContext) -> None:
    if message.text == kb.BTN_ISSUE_PAYMENT:
        topic = 'ISSUE_PAYMENT'
        text = PAYMENT_PROMPT
    elif message.text == kb.BTN_ISSUE_BOT:
        topic = 'ISSUE_BOT'
        text = BOT_PROMPT
    else:
        topic = 'OTHER'
        text = 'Опишите проблему одним сообщением.'
    await state.update_data(topic=topic)
    await state.set_state(SupportStates.waiting_message)
    await message.answer(text, reply_markup=kb.back_to_menu())

@router.message(F.text | F.photo | F.document | F.video, F.chat.type == 'private')
async def any_message(message: Message, state: FSMContext, bot: Bot) -> None:
    current = await state.get_state()
    if current == SupportStates.waiting_message.state:
        data = await state.get_data()
        topic = data.get('topic', 'OTHER')
        user_id = message.from_user.id if message.from_user else 0
        body = _get_message_text(message)
        db.insert_ticket(user_id, topic, body)
        mark_recent_submitter(user_id)
        await send_ticket_to_forum(bot, topic, message, body)
        if topic == 'FEEDBACK':
            reply = FEEDBACK_THANKS
        elif topic in ('ISSUE_PAYMENT', 'ISSUE_BOT'):
            reply = OPERATOR_REPLY
        else:
            reply = ISSUE_ACCEPTED
        await state.clear()
        try:
            await message.answer(reply, reply_markup=kb.main_menu())
        except Exception as e:
            logger.exception('reply after ticket: %s', e)
        return
    if message.from_user and is_recent_submitter(message.from_user.id):
        await safe_send(bot, message.chat.id, ALREADY_ACCEPTED)
        clear_recent_submitter(message.from_user.id)
        return
    try:
        await message.answer('Выберите пункт меню ниже или нажмите /start.', reply_markup=kb.main_menu())
    except Exception:
        pass

@router.message(F.chat.id == SUPPORT_GROUP_ID)
async def admin_reply_from_forum(message: Message, bot: Bot) -> None:
    if not message.from_user or message.from_user.is_bot:
        return
    thread_id = message.message_thread_id
    if thread_id is None:
        return
    user_id_str = db.get_user_by_topic(thread_id)
    if not user_id_str:
        return
    try:
        user_id = int(user_id_str)
    except ValueError:
        return
    try:
        if message.text:
            await bot.send_message(user_id, message.text)
        elif message.photo:
            photo = message.photo[-1].file_id
            await bot.send_photo(user_id, photo, caption=message.caption or None)
        elif message.document:
            await bot.send_document(user_id, message.document.file_id, caption=message.caption or None)
        elif message.video:
            await bot.send_video(user_id, message.video.file_id, caption=message.caption or None)
        elif message.voice:
            await bot.send_voice(user_id, message.voice.file_id, caption=message.caption or None)
        else:
            return
    except Exception as e:
        logger.exception('Failed to forward admin reply to user %s: %s', user_id, e)
        return
    await safe_send(bot, SUPPORT_GROUP_ID, 'Ответ отправлен пользователю ✅', message_thread_id=thread_id)