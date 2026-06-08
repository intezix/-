from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, FSInputFile
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from typing import Optional, Tuple, List
import asyncio
import html
import logging
from config import UX_MODE, UXMode, Texts, MEAL_TEXTS, MealType, RECIPES_HEADER_IMAGE_URL, FIRST_RECIPE_ID, GUIDE_IMAGE_URL, GUIDE_RECIPES, PROTECT_CONTENT, RECIPE_PHOTOS_MODE
from states import UserState, UserContext
from services import RecipeService
from services.recipe_service import Recipe
from keyboards import InlineKeyboards, ReplyKeyboards
from keyboards.inline import CallbackData
router = Router()
service = RecipeService()
_photo_list_cache = None
logger = logging.getLogger(__name__)

from services.ui_registry import register_ui_message, delete_ui_message

UI_MEALS_KEY = 'ui_meals_msg_id'
UI_CATEGORIES_KEY = 'ui_categories_msg_id'
UI_CONTENT_KEY = 'ui_content_msg_id'
UI_CONTENT_TOKEN_KEY = 'ui_content_token'


async def get_ui_slots(state: FSMContext) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    data = await state.get_data()
    return data.get(UI_MEALS_KEY), data.get(UI_CATEGORIES_KEY), data.get(UI_CONTENT_KEY)


async def set_ui_slot(state: FSMContext, slot: str, message_id: Optional[int]) -> None:
    key = {
        'MEALS': UI_MEALS_KEY,
        'CATEGORIES': UI_CATEGORIES_KEY,
        'CONTENT': UI_CONTENT_KEY,
    }.get(slot)
    if not key:
        return
    await state.update_data(**{key: message_id})
    if slot == 'CATEGORIES':
        await state.update_data(categories_message_id=message_id)


async def clear_slot(bot, state: FSMContext, chat_id: int, slot: str) -> None:
    key = {
        'MEALS': UI_MEALS_KEY,
        'CATEGORIES': UI_CATEGORIES_KEY,
        'CONTENT': UI_CONTENT_KEY,
    }.get(slot)
    if not key:
        return
    data = await state.get_data()
    msg_id = data.get(key)
    if not msg_id:
        return
    ok = 0
    fail = 0
    method = 'delete'
    try:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            ok += 1
        except TelegramBadRequest as e:
            method = 'mute'
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=' ', reply_markup=None)
                ok += 1
            except TelegramBadRequest:
                fail += 1
                logger.debug('[UI] clear slot=%s fallback mute failed: %s', slot, e)
        except Exception as e:
            fail += 1
            logger.debug('[UI] clear slot=%s delete failed: %s', slot, e)
    finally:
        # Keep persistent UI registry in sync with Telegram deletions/edits.
        try:
            delete_ui_message(user_id=chat_id, message_id=msg_id)
        except Exception:
            pass
        await set_ui_slot(state, slot, None)
        logger.info('[UI] clear slot=%s method=%s ok=%s fail=%s', slot, method, ok, fail)


async def resolve_click_slot(callback: CallbackQuery, state: FSMContext) -> str:
    meals_id, categories_id, content_id = await get_ui_slots(state)
    msg_id = callback.message.message_id if callback.message else None
    slot = 'STALE'
    if msg_id and meals_id and msg_id == meals_id:
        slot = 'MEALS'
    elif msg_id and categories_id and msg_id == categories_id:
        slot = 'CATEGORIES'
    elif msg_id and content_id and msg_id == content_id:
        slot = 'CONTENT'
    logger.info(
        '[UI] click slot=%s user=%s msg=%s data=%s',
        slot,
        callback.from_user.id if callback.from_user else None,
        msg_id,
        callback.data,
    )
    return slot

async def get_context(state: FSMContext) -> UserContext:
    data = await state.get_data()
    return UserContext.from_dict(data.get('context'))

async def save_context(state: FSMContext, context: UserContext) -> None:
    await state.update_data(context=context.to_dict())

async def delete_previous_messages(message: Message, state: FSMContext, extra_ids: Optional[List[int]]=None) -> None:
    context = await get_context(state)
    chat_id = message.chat.id
    ids = list(context.message_ids)
    if extra_ids:
        ids.extend(extra_ids)
    ids = list(dict.fromkeys(ids))
    if ids:
        ids.sort(reverse=True)

        async def _delete(mid: int):
            try:
                await message.bot.delete_message(chat_id, mid)
            except Exception:
                pass
        tasks = [asyncio.create_task(_delete(mid)) for mid in ids]
        await asyncio.gather(*tasks)
        # Remove corresponding records from persistent UI registry.
        for mid in ids:
            try:
                delete_ui_message(user_id=chat_id, message_id=mid)
            except Exception:
                pass
    context.clear_messages()
    await save_context(state, context)

async def save_message_id(state: FSMContext, message_id: int) -> None:
    context = await get_context(state)
    context.add_message(message_id)
    await save_context(state, context)

def is_inline_mode() -> bool:
    return UX_MODE == UXMode.INLINE_WITH_FILTERS

async def ensure_start_over_keyboard(message: Message) -> None:
    if not is_inline_mode():
        return
    keyboard = ReplyKeyboards.start_over()
    try:
        sent = await message.answer('\u200b', reply_markup=keyboard, protect_content=PROTECT_CONTENT)
        register_ui_message(
            user_id=message.chat.id,
            chat_id=message.chat.id,
            message_id=sent.message_id,
            kind='start_over_keyboard',
            is_persistent=False,
        )
    except Exception:
        pass

def get_meal_type_by_text(text: str) -> Optional[str]:
    for meal_type, meal_text in MEAL_TEXTS.items():
        if text == meal_text:
            return meal_type.value
    return None

def get_category_id_by_text(text: str, meal_type: str) -> Optional[str]:
    categories = service.get_categories(meal_type)
    for cat in categories:
        if text == cat.name:
            return cat.id
    return None

def get_recipe_id_by_text(text: str, recipes: List[Recipe]) -> Optional[str]:
    for recipe in recipes:
        if recipe.name == text:
            return recipe.id
    return None

def build_selection_context(context: UserContext) -> str:
    if context.source == 'category':
        return f'category:{context.meal_type}:{context.category_id}'
    elif context.source == 'filters':
        filters_str = ','.join(sorted(context.selected_filters))
        return f'filters:{context.meal_type}:{filters_str}'
    elif context.source == 'favourites':
        return 'favourites:'
    else:
        return 'category:unknown:unknown'

def restore_context_from_string(context: UserContext, context_str: str) -> None:
    if not context_str:
        return
    parts = context_str.split(':', 2)
    if len(parts) < 2:
        return
    source_type = parts[0]
    if source_type == 'category':
        if len(parts) >= 3:
            context.meal_type = parts[1]
            context.category_id = parts[2]
            context.source = 'category'
            context.reset_filters()
    elif source_type == 'filters':
        if len(parts) >= 3:
            context.meal_type = parts[1]
            filters_str = parts[2]
            context.selected_filters = set(filters_str.split(',')) if filters_str else set()
            context.source = 'filters'
            context.category_id = None
    elif source_type == 'favourites':
        context.source = 'favourites'

def restore_recipes_from_context(context_str: str, service: RecipeService, user_id: int=None) -> List[Recipe]:
    if not context_str:
        return []
    parts = context_str.split(':', 2)
    if len(parts) < 2:
        return []
    source_type = parts[0]
    if source_type == 'category':
        if len(parts) < 3:
            return []
        meal_type = parts[1]
        category_id = parts[2]
        return service.get_recipes_by_category(meal_type, category_id)
    elif source_type == 'filters':
        if len(parts) < 3:
            return []
        meal_type = parts[1]
        filters_str = parts[2]
        selected_filters = set(filters_str.split(',')) if filters_str else set()
        return service.get_recipes_by_filters(meal_type, selected_filters)
    elif source_type == 'favourites':
        if user_id is None:
            return []
        from services.favourites_service import FavouritesService
        favourites_service = FavouritesService()
        recipe_ids = favourites_service.get_favourite_recipe_ids(user_id)
        recipes = []
        for recipe_id in recipe_ids:
            recipe = service.get_recipe_by_id(recipe_id)
            if recipe:
                recipes.append(recipe)
        return recipes
    return []

async def show_welcome_screen(message: Message, state: FSMContext) -> None:
    from services.subscription_service import SubscriptionService

    # Проверяем наличие активной подписки
    sub_service = SubscriptionService()
    has_subscription = sub_service.has_active_subscription(message.chat.id)

    # Если подписка активна, показываем приемы пищи
    if has_subscription:
        await show_meals_screen(message, state, edit=False)
        return

    # Иначе показываем приветствие
    await state.set_state(UserState.welcome_step1)
    context = UserContext()
    await save_context(state, context)
    if is_inline_mode():
        keyboard = InlineKeyboards.welcome_step1()
        sent = await message.answer(Texts.WELCOME_STEP1, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
    else:
        keyboard = ReplyKeyboards.welcome_step1()
        sent = await message.answer(Texts.WELCOME_STEP1, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
    await state.update_data(welcome_step1_message_id=sent.message_id)
    register_ui_message(
        user_id=message.chat.id,
        chat_id=message.chat.id,
        message_id=sent.message_id,
        kind='welcome_step1',
        is_persistent=True,
    )

async def show_welcome_step2(message: Message, state: FSMContext) -> None:
    await state.set_state(UserState.welcome_step2)
    if is_inline_mode():
        keyboard = InlineKeyboards.welcome_step2()
        sent = await message.answer(Texts.WELCOME_STEP2, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
    else:
        keyboard = ReplyKeyboards.welcome_step2()
        sent = await message.answer(Texts.WELCOME_STEP2, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
    await state.update_data(welcome_step2_message_id=sent.message_id)
    register_ui_message(
        user_id=message.chat.id,
        chat_id=message.chat.id,
        message_id=sent.message_id,
        kind='welcome_step2',
        is_persistent=False,
    )

async def show_welcome_step3(message: Message, state: FSMContext) -> None:
    await state.set_state(UserState.welcome_step3)
    if is_inline_mode():
        keyboard = InlineKeyboards.welcome_step3()
        sent = await message.answer(Texts.WELCOME_STEP3, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
    else:
        keyboard = ReplyKeyboards.welcome_step3()
        sent = await message.answer(Texts.WELCOME_STEP3, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
    await state.update_data(welcome_step3_message_id=sent.message_id)
    register_ui_message(
        user_id=message.chat.id,
        chat_id=message.chat.id,
        message_id=sent.message_id,
        kind='welcome_step3',
        is_persistent=False,
    )

async def show_meals_screen(message: Message, state: FSMContext, edit: bool=False) -> None:
    await state.set_state(UserState.choosing_meal)
    await delete_previous_messages(message, state)
    context = UserContext()
    await save_context(state, context)
    text = '<b>🍽 ВЫБЕРИТЕ ПРИЁМ ПИЩИ</b>'
    if is_inline_mode():
        keyboard = InlineKeyboards.meals()
        meals_id, _, _ = await get_ui_slots(state)
        chat_id = message.chat.id
        sent = None
        if meals_id:
            try:
                sent = await message.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=meals_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode='HTML',
                )
            except TelegramBadRequest:
                try:
                    await message.bot.delete_message(chat_id=chat_id, message_id=meals_id)
                except Exception:
                    pass
        if not sent:
            sent = await message.answer(text, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
        await set_ui_slot(state, 'MEALS', sent.message_id)
        await save_message_id(state, sent.message_id)
        register_ui_message(
            user_id=chat_id,
            chat_id=chat_id,
            message_id=sent.message_id,
            kind='meals_screen',
            is_persistent=False,
        )
        m_id, c_id, content_id = await get_ui_slots(state)
        logger.info('[UI] render meals=%s categories=%s content=%s', m_id, c_id, content_id)
    else:
        keyboard = ReplyKeyboards.meals()
        sent = await message.answer(text, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
        register_ui_message(
            user_id=message.chat.id,
            chat_id=message.chat.id,
            message_id=sent.message_id,
            kind='meals_screen',
            is_persistent=False,
        )

async def show_categories_screen(message: Message, state: FSMContext, meal_type: str, edit: bool=False) -> None:
    await state.set_state(UserState.browsing_categories)
    await delete_previous_messages(message, state, extra_ids=[message.message_id])
    context = await get_context(state)
    context.meal_type = meal_type
    context.category_id = None
    context.reset_filters()
    context.reset_pagination()
    context.clear_messages()
    await save_context(state, context)
    categories = service.get_categories(meal_type)
    meal_text = MEAL_TEXTS.get(MealType(meal_type), '')
    if meal_type in ('lunch', 'dinner'):
        text = f'<b>{meal_text.upper()}</b>\n\n<i>*Первые две категории универсальны для обедов и ужинов, поэтому они объединены</i>\n\n<i>{Texts.CHOOSE_CATEGORY}</i>'
    else:
        text = f'<b>{meal_text.upper()}</b>\n\n<i>{Texts.CHOOSE_CATEGORY}</i>'
    if is_inline_mode():
        keyboard = InlineKeyboards.categories(categories, show_filters_button=True)
        meals_id, categories_id, _ = await get_ui_slots(state)
        chat_id = message.chat.id
        sent = None
        if categories_id:
            try:
                sent = await message.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=categories_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode='HTML',
                )
            except (TelegramBadRequest, MessageNotModified):
                try:
                    await message.bot.delete_message(chat_id=chat_id, message_id=categories_id)
                except Exception:
                    pass
        if not sent:
            sent = await message.answer(text, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
        await set_ui_slot(state, 'CATEGORIES', sent.message_id)
        register_ui_message(
            user_id=message.chat.id,
            chat_id=message.chat.id,
            message_id=sent.message_id,
            kind='categories_screen',
            is_persistent=False,
        )
        m_id, c_id, content_id = await get_ui_slots(state)
        logger.info('[UI] render meals=%s categories=%s content=%s', m_id, c_id, content_id)
    else:
        keyboard = ReplyKeyboards.categories(categories)
        sent = await message.answer(text, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
        register_ui_message(
            user_id=message.chat.id,
            chat_id=message.chat.id,
            message_id=sent.message_id,
            kind='categories_screen',
            is_persistent=False,
        )

async def show_recipes_list(message: Message, state: FSMContext, recipes: List[Recipe], page: int, source: str, edit: bool=False, selection_mode: bool=False, content_token: Optional[int]=None) -> None:
    if selection_mode:
        await state.set_state(UserState.selecting_favourites)
    else:
        await state.set_state(UserState.browsing_recipes)
    current_state = await state.get_state()
    can_edit = message.photo is not None or current_state == UserState.viewing_recipe.state

    async def _is_token_valid() -> bool:
        if content_token is None:
            return True
        data = await state.get_data()
        current_token = data.get(UI_CONTENT_TOKEN_KEY)
        if current_token != content_token:
            logger.info('[UI] skip outdated content render: token=%s current=%s', content_token, current_token)
            return False
        return True
    if not can_edit:
        # Гарантируем, что для inline-режима существует только один актуальный CONTENT-слот.
        if is_inline_mode():
            try:
                await clear_slot(message.bot, state, message.chat.id, 'CONTENT')
            except Exception as e:
                logger.debug('[UI] clear_slot in show_recipes_list failed: %s', e)
        await delete_previous_messages(message, state)
    context = await get_context(state)
    context.page = page
    context.source = source
    context.selection_context = build_selection_context(context)
    if not selection_mode:
        context.reset_selection()
    await save_context(state, context)
    page_recipes, total, has_prev, has_next = service.paginate(recipes, page)
    context.page_recipe_ids = [r.id for r in page_recipes]
    if not page_recipes:
        context.page_recipe_ids = []
        await save_context(state, context)
        if not await _is_token_valid():
            return
        text = Texts.NO_RECIPES
        if is_inline_mode():
            keyboard = InlineKeyboards.recipes_list([], False, False)
            if can_edit:
                await message.edit_caption(caption=text, reply_markup=keyboard, parse_mode='HTML')
                await set_ui_slot(state, 'CONTENT', message.message_id)
                register_ui_message(
                    user_id=message.chat.id,
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    kind='recipes_list',
                    is_persistent=False,
                )
            else:
                if not await _is_token_valid():
                    return
                sent = await message.answer(text, reply_markup=keyboard, protect_content=PROTECT_CONTENT)
                await save_message_id(state, sent.message_id)
                await set_ui_slot(state, 'CONTENT', sent.message_id)
                register_ui_message(
                    user_id=message.chat.id,
                    chat_id=message.chat.id,
                    message_id=sent.message_id,
                    kind='recipes_list',
                    is_persistent=False,
                )
            m_id, c_id, content_id = await get_ui_slots(state)
            logger.info('[UI] render meals=%s categories=%s content=%s', m_id, c_id, content_id)
        else:
            keyboard = ReplyKeyboards.recipes_list([], False, False)
            sent = await message.answer(text, reply_markup=keyboard, protect_content=PROTECT_CONTENT)
            await save_message_id(state, sent.message_id)
            register_ui_message(
                user_id=message.chat.id,
                chat_id=message.chat.id,
                message_id=sent.message_id,
                kind='recipes_list',
                is_persistent=False,
            )
        return
    if source == 'category' and context.category_id:
        categories = service.get_categories(context.meal_type)
        category_name = None
        for cat in categories:
            if cat.id == context.category_id:
                category_name = cat.name
                break
        if category_name:
            caption = f'\n\n📋 Рецепты из категории\n<b>{category_name}</b>\n\n'
        else:
            caption = '<b>📋 РЕЦЕПТЫ</b>'
    elif source == 'filters':
        caption = '\n\n<b>📋 РЕЦЕПТЫ</b>\n\n'
    elif source == 'favourites':
        caption = '\n\n<b>📋 РЕЦЕПТЫ</b>\n\n'
    else:
        caption = '\n\n<b>📋 РЕЦЕПТЫ</b>\n\n'
    if is_inline_mode():
        telegraph_urls = {}
        for recipe in page_recipes:
            if recipe.telegraph_url and recipe.telegraph_url.startswith('https://telegra.ph/'):
                telegraph_urls[recipe.id] = recipe.telegraph_url
        from services.favourites_service import FavouritesService
        favourites_service = FavouritesService()
        user_id = message.from_user.id
        user_fav_ids = set(favourites_service.get_favourite_recipe_ids(user_id))
        if not selection_mode:
            selection_context_str = build_selection_context(context)
            if not selection_context_str or selection_context_str == 'category:unknown:unknown':
                selection_context_str = ''
        else:
            selection_context_str = None
        keyboard = InlineKeyboards.recipes_list(page_recipes, has_prev, has_next, telegraph_urls=telegraph_urls if not selection_mode else None, user_favourites=user_fav_ids if not selection_mode else None, selection_mode=selection_mode, selected_recipe_ids=context.selected_recipe_ids if selection_mode else None, selection_context=selection_context_str, page_offset=page)
        if can_edit:
            if not await _is_token_valid():
                return
            try:
                await message.edit_caption(caption=caption, reply_markup=keyboard, parse_mode='HTML')
                await save_context(state, context)
                await set_ui_slot(state, 'CONTENT', message.message_id)
                register_ui_message(
                    user_id=message.chat.id,
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    kind='recipes_list',
                    is_persistent=False,
                )
                m_id, c_id, content_id = await get_ui_slots(state)
                logger.info('[UI] render meals=%s categories=%s content=%s', m_id, c_id, content_id)
                return
            except Exception:
                if not await _is_token_valid():
                    return
                try:
                    await message.edit_text(text=caption, reply_markup=keyboard, parse_mode='HTML')
                    await save_context(state, context)
                    await set_ui_slot(state, 'CONTENT', message.message_id)
                    register_ui_message(
                        user_id=message.chat.id,
                        chat_id=message.chat.id,
                        message_id=message.message_id,
                        kind='recipes_list',
                        is_persistent=False,
                    )
                    m_id, c_id, content_id = await get_ui_slots(state)
                    logger.info('[UI] render meals=%s categories=%s content=%s', m_id, c_id, content_id)
                    return
                except Exception:
                    pass
        if not await _is_token_valid():
            return
        try:
            sent = await message.answer_photo(photo=RECIPES_HEADER_IMAGE_URL, caption=caption, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
        except Exception:
            sent = await message.answer(caption, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
        await save_message_id(state, sent.message_id)
        await set_ui_slot(state, 'CONTENT', sent.message_id)
        register_ui_message(
            user_id=message.chat.id,
            chat_id=message.chat.id,
            message_id=sent.message_id,
            kind='recipes_list',
            is_persistent=False,
        )
        await save_context(state, context)
        m_id, c_id, content_id = await get_ui_slots(state)
        logger.info('[UI] render meals=%s categories=%s content=%s', m_id, c_id, content_id)
        data = await state.get_data()
        if not data.get('start_over_keyboard_set'):
            await ensure_start_over_keyboard(message)
            await state.update_data(start_over_keyboard_set=True)
    else:
        keyboard = ReplyKeyboards.recipes_list(page_recipes, has_prev, has_next)
        if source == 'category' and context.category_id:
            categories = service.get_categories(context.meal_type)
            category_name = next((c.name for c in categories if c.id == context.category_id), None)
            header = f"\n\n<b>📋 Рецепты</b>\n<b>{category_name or 'Категория'}</b>\n\n"
        else:
            header = '\n\n<b>📋 РЕЦЕПТЫ</b>\n\n'
        await message.answer(header, parse_mode='HTML', protect_content=PROTECT_CONTENT)
        for i, recipe in enumerate(page_recipes):
            caption = recipe.format_short()
            is_last = i == len(page_recipes) - 1
            try:
                if recipe.image_url and recipe.image_url.startswith('http') and ('placeholder' not in recipe.image_url):
                    if is_last:
                        await message.answer_photo(photo=recipe.image_url, caption=caption, reply_markup=keyboard, parse_mode='HTML')
                    else:
                        await message.answer_photo(photo=recipe.image_url, caption=caption, parse_mode='HTML')
                elif is_last:
                    await message.answer(caption, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
                else:
                    await message.answer(caption, parse_mode='HTML', protect_content=PROTECT_CONTENT)
            except Exception:
                if is_last:
                    await message.answer(caption, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
                else:
                    await message.answer(caption, parse_mode='HTML', protect_content=PROTECT_CONTENT)
        await save_context(state, context)

async def show_recipe_detail(message: Message, state: FSMContext, recipe: Recipe, telegraph_url: Optional[str]=None, edit: bool=False) -> None:
    await state.set_state(UserState.viewing_recipe)
    await delete_previous_messages(message, state, extra_ids=[message.message_id])
    context = await get_context(state)
    context.current_recipe_id = recipe.id
    context.clear_messages()
    await save_context(state, context)
    if is_inline_mode():
        text = recipe.format_full()
        keyboard = InlineKeyboards.recipe_detail(recipe_id=recipe.id)
        sent = await message.answer(text, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
        await save_message_id(state, sent.message_id)
        await set_ui_slot(state, 'CONTENT', sent.message_id)
        register_ui_message(
            user_id=message.chat.id,
            chat_id=message.chat.id,
            message_id=sent.message_id,
            kind='recipe_detail',
            is_persistent=False,
        )
        m_id, c_id, content_id = await get_ui_slots(state)
        logger.info('[UI] render meals=%s categories=%s content=%s', m_id, c_id, content_id)
    else:
        text = recipe.format_full()
        keyboard = ReplyKeyboards.recipe_detail()
        try:
            from pathlib import Path
            from aiogram.types import FSInputFile
            image_url = recipe.image_url
            if image_url.startswith('http'):
                await message.answer_photo(photo=image_url, caption=text, reply_markup=keyboard, parse_mode='HTML')
            else:
                base_path = Path(__file__).parent.parent
                file_path = base_path / image_url
                if file_path.exists():
                    photo = FSInputFile(file_path)
                    await message.answer_photo(photo=photo, caption=text, reply_markup=keyboard, parse_mode='HTML')
                else:
                    await message.answer(text, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
        except Exception:
            await message.answer(text, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)

async def show_recipe_accepted(message: Message, state: FSMContext, recipe: Recipe, telegraph_url: Optional[str]=None, edit: bool=False) -> None:
    await state.set_state(UserState.recipe_accepted)
    await delete_previous_messages(message, state, extra_ids=[message.message_id])
    context = await get_context(state)
    context.clear_messages()
    await save_context(state, context)
    if is_inline_mode():
        text = f'✅ {Texts.RECIPE_CHOSEN}\n\n{recipe.format_full()}'
        keyboard = InlineKeyboards.recipe_accepted()
        sent = await message.answer(text, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
        await save_message_id(state, sent.message_id)
        register_ui_message(
            user_id=message.chat.id,
            chat_id=message.chat.id,
            message_id=sent.message_id,
            kind='recipe_accepted',
            is_persistent=False,
        )
    else:
        text = f'✅ {Texts.RECIPE_CHOSEN}\n\n{recipe.format_full()}'
        keyboard = ReplyKeyboards.recipe_accepted()
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)

async def show_guide_image(message: Message, state: FSMContext, recipe_id: Optional[str]=None) -> None:
    import logging
    from pathlib import Path
    from aiogram.types import BufferedInputFile
    from io import BytesIO
    logger = logging.getLogger(__name__)
    recipe_id = recipe_id or FIRST_RECIPE_ID
    try:
        context = await get_context(state)
        if not context.selection_context:
            try:
                context.selection_context = build_selection_context(context)
            except Exception as e:
                logger.warning(f'Error building selection_context: {e}')

        def _resize_for_telegram(data: bytes) -> bytes:
            try:
                from PIL import Image
                img = Image.open(BytesIO(data)).convert('RGB')
                w, h = img.size
                total, ratio = (w + h, max(w, h) / max(min(w, h), 1))
                max_side = 2560
                scale = 1.0
                if total > 10000:
                    scale = min(scale, 10000 / total)
                if ratio > 20:
                    scale = min(scale, 20 * min(w, h) / max(w, h))
                if max(w, h) > max_side:
                    scale = min(scale, max_side / max(w, h))
                nw, nh = (max(2, int(w * scale)), max(2, int(h * scale)))
                if nw % 2:
                    nw += 1
                if nh % 2:
                    nh += 1
                img = img.resize((nw, nh), Image.Resampling.LANCZOS)
                out = BytesIO()
                img.save(out, 'JPEG', quality=90)
                return out.getvalue()
            except Exception as e:
                logger.warning('Resize failed: %s', e)
                return data
        base_path = Path(__file__).resolve().parent.parent
        raw_data = None
        filenames = []
        if recipe_id and recipe_id in GUIDE_RECIPES:
            filenames.append(GUIDE_RECIPES[recipe_id])
        filenames.extend(('omletspomidorami1.png', 'омлет с помидорами.png', '2рецепт.png', 'guide.png'))
        seen = set()
        for guide_filename in filenames:
            if guide_filename in seen:
                continue
            seen.add(guide_filename)
            guide_path = base_path / guide_filename
            if guide_path.exists():
                try:
                    raw_data = guide_path.read_bytes()
                    break
                except Exception as e:
                    logger.warning('Failed to read %s: %s', guide_path, e)
        if not raw_data:
            logger.warning('Guide image not available')
            await message.answer('Гайд временно недоступен.', protect_content=PROTECT_CONTENT)
            return
        photo_data = _resize_for_telegram(raw_data)
        photo = BufferedInputFile(photo_data, filename='guide.jpg')
        keyboard = InlineKeyboards.guide_back()
        sent = await message.answer_photo(photo=photo, reply_markup=keyboard, protect_content=PROTECT_CONTENT)
        register_ui_message(
            user_id=message.chat.id,
            chat_id=message.chat.id,
            message_id=sent.message_id,
            kind='guide_image',
            is_persistent=False,
        )
        try:
            await delete_previous_messages(message, state, extra_ids=[message.message_id])
        except Exception as e:
            logger.warning(f'Error deleting previous messages: {e}')
        await state.set_state(UserState.viewing_recipe)
        context = await get_context(state)
        context.current_recipe_id = recipe_id
        context.message_ids = [sent.message_id]
        await save_context(state, context)
        await save_message_id(state, sent.message_id)
    except Exception as e:
        logger.exception('Error in show_guide_image: %s', e)
        try:
            await message.answer('Произошла ошибка при загрузке гайда.', protect_content=PROTECT_CONTENT)
        except Exception:
            pass

async def show_recipe_photos(message: Message, state: FSMContext, recipe: Recipe) -> bool:
    import asyncio
    import logging
    import re as _re
    from pathlib import Path
    from aiogram.types import BufferedInputFile
    logger = logging.getLogger(__name__)
    try:
        context = await get_context(state)
        if not context.selection_context:
            try:
                context.selection_context = build_selection_context(context)
                await save_context(state, context)
            except Exception as e:
                logger.warning(f'Error building selection_context for photos: {e}')
        base_path = Path(__file__).resolve().parent.parent
        candidates = [base_path / 'photo' / 'prodphoto', base_path / 'prodphoto']
        photos_dir = None
        for c in candidates:
            if c.exists():
                photos_dir = c
                break
        if photos_dir is None:
            logger.warning('Photos directory does not exist in any of %s', candidates)
            return False
        photo_files: List[Path] = []
        recipe_photos_path = base_path / 'data' / 'recipe_photos.json'
        if recipe_photos_path.exists():
            try:
                import json
                data = json.loads(recipe_photos_path.read_text(encoding='utf-8'))
                names = data.get(recipe.id)
                if names and len(names) >= 2:
                    two: List[Path] = []
                    for fn in names[:2]:
                        p = photos_dir / fn.strip()
                        if not p.exists() and ' _2' in fn and (not fn.strip().endswith(' .png')):
                            p = photos_dir / (fn.strip().replace(' _2.', ' _2 .') if ' _2.' in fn else fn.strip())
                        if not p.exists():
                            p = photos_dir / fn.replace(' _2 .', ' _2.').strip()
                        if p.exists():
                            two.append(p)
                    if len(two) == 2:
                        photo_files = two
            except Exception as e:
                logger.debug('recipe_photos.json load failed: %s', e)
        if not photo_files:
            strict_photo_files: List[Path] = []
            for suffix in ('_1', '_2'):
                found = None
                for ext in ('.png', '.jpg', '.jpeg', '.webp'):
                    p = photos_dir / f'{recipe.id}{suffix}{ext}'
                    if p.exists():
                        found = p
                        break
                if found:
                    strict_photo_files.append(found)
            if len(strict_photo_files) == 2:
                photo_files = strict_photo_files
        if not photo_files:

            def _normalize(s: str) -> str:
                if not s:
                    return ''
                s = s.lower().replace('ё', 'е')
                for ch in ('«', '»', '"', "'", '`', '_', '-'):
                    s = s.replace(ch, ' ')
                out = [c for c in s if 'a' <= c <= 'z' or '0' <= c <= '9' or 'а' <= c <= 'я' or c.isspace()]
                return _re.sub('\\s+', ' ', ''.join(out)).strip()
            name_prefix = (recipe.name or '').strip()
            name_without_emoji = name_prefix[1:].lstrip() if len(name_prefix) > 1 else name_prefix
            prefixes = [p for p in (name_prefix, name_without_emoji, recipe.id) if p]
            norm_recipe = _normalize(recipe.name or '')
            global _photo_list_cache
            dir_key = str(photos_dir.resolve())

            def _build_cache():
                entries = []
                for p in sorted(photos_dir.iterdir()):
                    if not p.is_file():
                        continue
                    stem = p.stem
                    base_stem = stem.replace('_2', '').rstrip('_')
                    norm_stem = _normalize(base_stem)
                    entries.append((p, stem, norm_stem))
                return entries
            if _photo_list_cache is None or _photo_list_cache[0] != dir_key:
                try:
                    entries = await asyncio.to_thread(_build_cache)
                    _photo_list_cache = (dir_key, entries)
                except Exception as e:
                    logger.warning('Error building photo cache: %s', e)
                    return False
            _, cached_entries = _photo_list_cache
            for p, stem, norm_stem in cached_entries:
                if any((stem.startswith(prefix) for prefix in prefixes)):
                    photo_files.append(p)
                    if len(photo_files) >= 2:
                        break
                    continue
                if norm_stem and norm_recipe and (norm_stem.startswith(norm_recipe) or norm_recipe.startswith(norm_stem)):
                    photo_files.append(p)
                    if len(photo_files) >= 2:
                        break

            def _order_key(path):
                s = path.stem
                return (0 if not s.endswith('_2') else 1, s)
            photo_files.sort(key=_order_key)
            photo_files = photo_files[:2]
        if not photo_files:
            logger.info('No local photos found for recipe name=%r id=%s in %s', recipe.name, recipe.id, photos_dir)
            return False
        current_state = await state.get_state()
        msg_ids = getattr(context, 'message_ids', None) or []
        is_photo_block = len(msg_ids) in (2, 3)
        edit_existing = is_photo_block and current_state in (UserState.viewing_recipe.state, UserState.browsing_recipes.state)

        def _resize_photo(path: Path) -> bytes:
            from io import BytesIO
            try:
                from PIL import Image
                data = path.read_bytes()
                img = Image.open(BytesIO(data)).convert('RGB')
                w, h = img.size
                max_side = 960
                if max(w, h) <= max_side:
                    scale = 1.0
                else:
                    scale = max_side / max(w, h)
                nw, nh = (max(2, int(w * scale)), max(2, int(h * scale)))
                img = img.resize((nw, nh), Image.Resampling.LANCZOS)
                out = BytesIO()
                img.save(out, 'JPEG', quality=78)
                return out.getvalue()
            except Exception as e:
                logger.warning('Resize photo %s failed: %s, sending as-is', path.name, e)
                return path.read_bytes()
        resize_tasks = [asyncio.to_thread(_resize_photo, p) for p in photo_files]
        results = await asyncio.gather(*resize_tasks, return_exceptions=True)
        payloads = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.warning('Failed to prepare photo %s: %s', photo_files[i], res)
                continue
            payloads.append(res)
        if len(payloads) == 0:
            return False
        if len(payloads) == 1:
            payloads.append(payloads[0])
        chat_id = message.chat.id
        in_favourites = getattr(context, 'source', None) == 'favourites'
        keyboard = InlineKeyboards.recipe_photos_controls(recipe.id, in_favourites=in_favourites, show_favourites=RECIPE_PHOTOS_MODE == 1)
        fallback_needed = False
        if edit_existing:
            try:
                existing_ids = list(context.message_ids)
                if not existing_ids:
                    edit_existing = False
                else:
                    is_mode1 = len(existing_ids) == 3
                    if is_mode1:
                        photo_ids, controls_id = (existing_ids[:-1], existing_ids[-1])
                    else:
                        photo_ids = existing_ids
                        controls_id = None
                    for i, payload in enumerate(payloads):
                        if i < len(photo_ids):
                            media = InputMediaPhoto(media=BufferedInputFile(payload, filename='photo.jpg'))
                            try:
                                await message.bot.edit_message_media(chat_id=chat_id, message_id=photo_ids[i], media=media)
                            except TelegramBadRequest as e:
                                err = str(e).lower()
                                if 'message is not modified' not in err and 'exactly the same' not in err:
                                    raise
                    if is_mode1 and controls_id is not None:
                        controls_text = f"<b>{html.escape(recipe.name or '')}</b>"
                        try:
                            await message.bot.edit_message_text(chat_id=chat_id, message_id=controls_id, text=controls_text, reply_markup=keyboard, parse_mode='HTML')
                        except TelegramBadRequest as e:
                            err = str(e).lower()
                            if 'message is not modified' not in err and 'exactly the same' not in err:
                                raise
                        context.message_ids = photo_ids + [controls_id]
                    else:
                        try:
                            await message.bot.edit_message_reply_markup(chat_id=chat_id, message_id=photo_ids[-1], reply_markup=keyboard)
                        except TelegramBadRequest as e:
                            err = str(e).lower()
                            if 'message is not modified' not in err and 'exactly the same' not in err:
                                raise
                        context.message_ids = photo_ids
                    context.current_recipe_id = recipe.id
                    await save_context(state, context)
                    # Registry sync: edit-in-place still corresponds to UI message ids.
                    try:
                        mids = list(getattr(context, "message_ids", None) or [])
                        if len(mids) == 3:
                            for pid in mids[:-1]:
                                register_ui_message(user_id=chat_id, chat_id=chat_id, message_id=pid, kind='recipe_photo')
                            register_ui_message(user_id=chat_id, chat_id=chat_id, message_id=mids[-1], kind='recipe_photo_controls')
                        else:
                            for pid in mids:
                                register_ui_message(user_id=chat_id, chat_id=chat_id, message_id=pid, kind='recipe_photo')
                    except Exception:
                        pass
                    return True
            except Exception as e:
                err_str = str(e).lower()
                if 'message is not modified' in err_str or 'exactly the same' in err_str:
                    context.current_recipe_id = recipe.id
                    await save_context(state, context)
                    try:
                        mids = list(getattr(context, "message_ids", None) or [])
                        if len(mids) == 3:
                            for pid in mids[:-1]:
                                register_ui_message(user_id=chat_id, chat_id=chat_id, message_id=pid, kind='recipe_photo')
                            register_ui_message(user_id=chat_id, chat_id=chat_id, message_id=mids[-1], kind='recipe_photo_controls')
                        else:
                            for pid in mids:
                                register_ui_message(user_id=chat_id, chat_id=chat_id, message_id=pid, kind='recipe_photo')
                    except Exception:
                        pass
                    return True
                fallback_needed = True
                logger.warning('Edit existing recipe photos failed, falling back to new messages: %s', e)
        if fallback_needed:
            ctx = await get_context(state)
            old_ids = ctx.message_ids or []
            if old_ids:
                old_ids = sorted(old_ids, reverse=True)

                async def _del(mid):
                    try:
                        await message.bot.delete_message(chat_id=chat_id, message_id=mid)
                    except Exception:
                        pass
                tasks = [asyncio.create_task(_del(mid)) for mid in old_ids]
                await asyncio.gather(*tasks)
            # Ensure registry doesn't keep stale photo records after fallback deletions.
            for mid in old_ids:
                try:
                    delete_ui_message(user_id=chat_id, message_id=mid)
                except Exception:
                    pass
        if RECIPE_PHOTOS_MODE == 1:
            controls_text = f"<b>{html.escape(recipe.name or '')}</b>"
            media = [InputMediaPhoto(media=BufferedInputFile(p, filename='photo.jpg')) for p in payloads]
            sent_media = await message.answer_media_group(media, protect_content=PROTECT_CONTENT)
            controls_msg = await message.answer(controls_text, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
            message_ids = [m.message_id for m in sent_media] + [controls_msg.message_id]
            for mid in message_ids[:-1]:
                register_ui_message(user_id=chat_id, chat_id=chat_id, message_id=mid, kind='recipe_photo')
            register_ui_message(user_id=chat_id, chat_id=chat_id, message_id=controls_msg.message_id, kind='recipe_photo_controls')
        else:
            first = await message.answer_photo(BufferedInputFile(payloads[0], filename='photo.jpg'), protect_content=PROTECT_CONTENT)
            second = await message.answer_photo(BufferedInputFile(payloads[1], filename='photo.jpg'), reply_markup=keyboard, protect_content=PROTECT_CONTENT)
            message_ids = [first.message_id, second.message_id]
            register_ui_message(user_id=chat_id, chat_id=chat_id, message_id=first.message_id, kind='recipe_photo')
            register_ui_message(user_id=chat_id, chat_id=chat_id, message_id=second.message_id, kind='recipe_photo')
        await state.set_state(UserState.viewing_recipe)
        context = await get_context(state)
        context.current_recipe_id = recipe.id
        context.recipes_list_message_ids = list(context.message_ids)
        context.message_ids = message_ids
        await save_context(state, context)
        return True
    except Exception as e:
        logger.exception('Error in show_recipe_photos for recipe %s: %s', getattr(recipe, 'id', '?'), e)
        try:
            await message.answer('Произошла ошибка при загрузке рецепта.', protect_content=PROTECT_CONTENT)
        except Exception:
            pass
        return False