import asyncio
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from typing import Optional
from config import UX_MODE, UXMode, Texts, FIRST_RECIPE_ID, GUIDE_IMAGE_URL, GUIDE_RECIPES, PROTECT_CONTENT, RECIPES_PER_PAGE, FilterTag
from states import UserState, UserContext
from services import RecipeService
from keyboards import InlineKeyboards
from keyboards.inline import CallbackData
from handlers.common import (
    get_context,
    save_context,
    save_message_id,
    delete_previous_messages,
    is_inline_mode,
    show_meals_screen,
    show_categories_screen,
    show_recipes_list,
    show_recipe_detail,
    show_recipe_accepted,
    show_guide_image,
    restore_recipes_from_context,
    build_selection_context,
    show_recipe_photos,
    resolve_click_slot,
    clear_slot,
    set_ui_slot,
)
from services.user_activity_service import UserActivityService
from services.inactivity_flow import is_start_over_text, process_start_over
from events_writer import log_event


router = Router()
service = RecipeService()
activity_service = UserActivityService()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == CallbackData.WELCOME_CONTINUE)
async def handle_welcome_continue(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await log_event(
        source_bot="main_bot",
        telegram_user_id=callback.from_user.id,
        event_type="UI_CALLBACK",
        action="Продолжить",
        screen="welcome_1",
        status="ok",
        payload_json={},
        callback_data=callback.data,
        username=callback.from_user.username,
    )
    data = await state.get_data()
    mid1 = data.get('welcome_step1_message_id')
    if mid1 is not None:
        try:
            await callback.bot.edit_message_text(chat_id=callback.message.chat.id, message_id=mid1, text=Texts.WELCOME_STEP1_NO_BUTTON, reply_markup=None, parse_mode='HTML')
        except Exception:
            try:
                await callback.bot.edit_message_reply_markup(chat_id=callback.message.chat.id, message_id=mid1, reply_markup=None)
            except Exception:
                pass
    from handlers.common import show_welcome_step2
    await show_welcome_step2(callback.message, state)

@router.callback_query(F.data == CallbackData.WELCOME_PAY)
async def handle_welcome_pay(callback: CallbackQuery, state: FSMContext):
    from handlers.common import show_welcome_step3

    await callback.answer()
    await log_event(
        source_bot="main_bot",
        telegram_user_id=callback.from_user.id,
        event_type="UI_CALLBACK",
        action="Оплатить (фейк/пропуск)",
        screen="welcome_2",
        status="ok",
        payload_json={},
        callback_data=callback.data,
        username=callback.from_user.username,
    )
    # Делаем доступ бесплатным: сразу переходим к следующему шагу без оплаты.
    await show_welcome_step3(callback.message, state)

@router.callback_query(F.data == CallbackData.WELCOME_GO_TO_CATEGORIES)
async def handle_welcome_go_to_categories(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await log_event(
        source_bot="main_bot",
        telegram_user_id=callback.from_user.id,
        event_type="UI_CALLBACK",
        action="Перейти к категориям",
        screen="welcome_3",
        status="ok",
        payload_json={},
        callback_data=callback.data,
        username=callback.from_user.username,
    )
    data = await state.get_data()
    chat_id = callback.message.chat.id
    mid1 = data.get('welcome_step1_message_id')
    mid2 = data.get('welcome_step2_message_id')
    if mid1 is not None:
        try:
            await callback.bot.edit_message_text(chat_id=chat_id, message_id=mid1, text=Texts.WELCOME_STEP1_NO_BUTTON, reply_markup=None, parse_mode='HTML')
        except Exception:
            try:
                await callback.bot.edit_message_reply_markup(chat_id=chat_id, message_id=mid1, reply_markup=None)
            except Exception:
                pass
    to_delete = []
    if mid2 is not None:
        to_delete.append(mid2)
    to_delete.append(callback.message.message_id)
    if to_delete:
        to_delete = sorted(to_delete, reverse=True)

        async def _del(mid):
            try:
                await callback.bot.delete_message(chat_id, mid)
            except Exception:
                pass
        tasks = [asyncio.create_task(_del(mid)) for mid in to_delete]
        await asyncio.gather(*tasks)
        from services.ui_registry import delete_ui_message
        for mid in to_delete:
            try:
                delete_ui_message(user_id=chat_id, message_id=mid)
            except Exception:
                pass
    await state.update_data(welcome_step1_message_id=None, welcome_step2_message_id=None, welcome_step3_message_id=None)
    await show_meals_screen(callback.message, state)

@router.callback_query(F.data == CallbackData.LETS_GO)
async def handle_lets_go(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await log_event(
        source_bot="main_bot",
        telegram_user_id=callback.from_user.id,
        event_type="UI_CALLBACK",
        action="Продолжить (lets_go)",
        screen="welcome",
        status="ok",
        payload_json={},
        callback_data=callback.data,
        username=callback.from_user.username,
    )
    from config import Texts
    try:
        await callback.message.edit_text(Texts.WELCOME_NO_BUTTON, reply_markup=None, parse_mode='HTML')
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    await show_meals_screen(callback.message, state)

@router.callback_query(F.data.startswith(f'{CallbackData.MEAL}:'))
async def handle_meal_selection(callback: CallbackQuery, state: FSMContext):
    slot = await resolve_click_slot(callback, state)
    if slot != 'MEALS':
        await callback.answer('Это старое меню. Нажмите кнопки внизу 👇', show_alert=False)
        return
    await callback.answer()
    await log_event(
        source_bot="main_bot",
        telegram_user_id=callback.from_user.id,
        event_type="MEAL_CLICK",
        action="Выбор приёма пищи",
        screen="meals",
        status="ok",
        payload_json={},
        callback_data=callback.data,
        username=callback.from_user.username,
    )
    chat_id = callback.message.chat.id
    await clear_slot(callback.bot, state, chat_id, 'CATEGORIES')
    await clear_slot(callback.bot, state, chat_id, 'CONTENT')
    meal_type = callback.data.split(':')[1]
    await show_categories_screen(callback.message, state, meal_type)

@router.callback_query(F.data == CallbackData.TO_MEALS)
async def handle_to_meals(callback: CallbackQuery, state: FSMContext):
    slot = await resolve_click_slot(callback, state)
    if slot not in ('CATEGORIES', 'CONTENT'):
        await callback.answer('Это старое меню. Нажмите кнопки внизу 👇', show_alert=False)
        return
    await callback.answer()
    chat_id = callback.message.chat.id
    await clear_slot(callback.bot, state, chat_id, 'CATEGORIES')
    await clear_slot(callback.bot, state, chat_id, 'CONTENT')
    # Всегда используем единый рендерер слотов для MEALS
    await show_meals_screen(callback.message, state)

@router.callback_query(F.data.startswith(f'{CallbackData.CATEGORY}:'))
async def handle_category_selection(callback: CallbackQuery, state: FSMContext):
    slot = await resolve_click_slot(callback, state)
    if slot != 'CATEGORIES':
        await callback.answer('Это старое меню. Нажмите кнопки внизу 👇', show_alert=False)
        return
    await callback.answer()
    await log_event(
        source_bot="main_bot",
        telegram_user_id=callback.from_user.id,
        event_type="CATEGORY_CLICK",
        action="Выбор категории",
        screen="categories",
        status="ok",
        payload_json={},
        callback_data=callback.data,
        username=callback.from_user.username,
    )
    chat_id = callback.message.chat.id
    await clear_slot(callback.bot, state, chat_id, 'CONTENT')
    # Обновляем токен контента: только последний клик по категории должен отрисовать список
    data = await state.get_data()
    content_token = (data.get('ui_content_token') or 0) + 1
    await state.update_data(ui_content_token=content_token)
    category_id = callback.data.split(':')[1]
    context = await get_context(state)
    context.category_id = category_id
    context.source = 'category'
    context.reset_pagination()
    await save_context(state, context)
    recipes = service.get_recipes_by_category(context.meal_type, category_id)
    await show_recipes_list(callback.message, state, recipes, 0, 'category', content_token=content_token)

@router.callback_query(F.data == CallbackData.TO_MENU)
async def handle_to_menu(callback: CallbackQuery, state: FSMContext):
    slot = await resolve_click_slot(callback, state)
    if slot not in ('CONTENT', 'CATEGORIES'):
        await callback.answer('Это старое меню. Нажмите кнопки внизу 👇', show_alert=False)
        return
    await callback.answer()
    context = await get_context(state)
    current_state = await state.get_state()
    if current_state == UserState.selecting_favourites:
        context.reset_selection()
        await save_context(state, context)
    if current_state in [UserState.browsing_recipes.state, UserState.choosing_filters.state, UserState.selecting_favourites.state, UserState.viewing_recipe.state]:
        extra_ids = [callback.message.message_id]
        if current_state == UserState.viewing_recipe.state:
            extra_ids.extend(getattr(context, 'recipes_list_message_ids', None) or [])
        await delete_previous_messages(callback.message, state, extra_ids=extra_ids)
        # При возврате "В меню" из контента очищаем CONTENT-слот
        await set_ui_slot(state, 'CONTENT', None)
        if current_state == UserState.viewing_recipe.state:
            context = await get_context(state)
            context.recipes_list_message_ids = []
            await save_context(state, context)
        await state.set_state(UserState.browsing_categories)
    elif context.meal_type:
        await show_categories_screen(callback.message, state, context.meal_type)
    else:
        await show_meals_screen(callback.message, state)

@router.callback_query(F.data == CallbackData.SHOW_FILTERS)
async def handle_show_filters(callback: CallbackQuery, state: FSMContext):
    slot = await resolve_click_slot(callback, state)
    if slot != 'CATEGORIES':
        await callback.answer('Это старое меню. Нажмите кнопки внизу 👇', show_alert=False)
        return
    await callback.answer()
    await log_event(
        source_bot="main_bot",
        telegram_user_id=callback.from_user.id,
        event_type="FILTERS_OPEN",
        action="Открыть фильтры",
        screen="categories",
        status="ok",
        payload_json={},
        callback_data=callback.data,
        username=callback.from_user.username,
    )
    await state.set_state(UserState.choosing_filters)
    # Удаляем все предыдущие контент-сообщения (рецепты/списки), которые ещё могли остаться,
    # чтобы фильтры всегда отображались без "прилипшего" рецепта над ними.
    await delete_previous_messages(callback.message, state)
    context = await get_context(state)
    text = '<b>🔍 ФИЛЬТРЫ</b>\n\n<i>Можно выбрать несколько</i>'
    keyboard = InlineKeyboards.filters(context.selected_filters, meal_type=context.meal_type, recipe_service=service)
    chat_id = callback.message.chat.id
    # Явно очищаем текущий CONTENT-слот (рецепт / список) перед показом фильтров,
    # чтобы фильтры всегда занимали один актуальный UI#3.
    await clear_slot(callback.bot, state, chat_id, 'CONTENT')
    sent = await callback.message.answer(text, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
    await set_ui_slot(state, 'CONTENT', sent.message_id)
    from services.ui_registry import register_ui_message
    register_ui_message(
        user_id=chat_id,
        chat_id=chat_id,
        message_id=sent.message_id,
        kind='filters_screen',
        is_persistent=False,
    )

@router.callback_query(F.data.startswith(f'{CallbackData.FILTER}:'))
async def handle_filter_toggle(callback: CallbackQuery, state: FSMContext):
    filter_tag = callback.data.split(':')[1]
    context = await get_context(state)
    if filter_tag in context.selected_filters:
        await callback.answer()
        context.toggle_filter(filter_tag)
        await save_context(state, context)
        keyboard = InlineKeyboards.filters(context.selected_filters, meal_type=context.meal_type, recipe_service=service)
        try:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        except Exception:
            pass
        return
    if context.meal_type in ('lunch', 'dinner'):
        test_filters = set(context.selected_filters) | {filter_tag}
        recipes = service.get_recipes_by_filters(context.meal_type, test_filters)
        if len(recipes) == 0:
            await callback.answer('По выбранным фильтрам рецептов нет. Выберите другой фильтр.', show_alert=False)
            return
    await callback.answer()
    context.toggle_filter(filter_tag)
    await save_context(state, context)
    keyboard = InlineKeyboards.filters(context.selected_filters, meal_type=context.meal_type, recipe_service=service)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass

@router.callback_query(F.data == CallbackData.APPLY_FILTERS)
async def handle_apply_filters(callback: CallbackQuery, state: FSMContext):
    context = await get_context(state)
    if not context.meal_type:
        await callback.answer('Ошибка: не выбран приём пищи', show_alert=False)
        return
    if context.meal_type in ('lunch', 'dinner'):
        only_protein = context.selected_filters == {'protein'}
        only_balanced = context.selected_filters == {'balanced'}
        if only_protein or only_balanced:
            await callback.answer('По выбранным фильтрам рецептов нет. Выберите другие фильтры.', show_alert=False)
            return
    context.source = 'filters'
    context.reset_pagination()
    await save_context(state, context)
    recipes = service.get_recipes_by_filters(context.meal_type, context.selected_filters)
    try:
        await callback.answer()
    except Exception:
        pass
    await log_event(
        source_bot="main_bot",
        telegram_user_id=callback.from_user.id,
        event_type="FILTERS_APPLY",
        action="Применить фильтры",
        screen="filters",
        status="ok",
        payload_json={"filters": sorted(list(context.selected_filters))},
        callback_data=callback.data,
        username=callback.from_user.username,
    )
    # Очистить текущий CONTENT-слот (экран фильтров) перед показом списка
    chat_id = callback.message.chat.id
    await clear_slot(callback.bot, state, chat_id, 'CONTENT')
    await show_recipes_list(callback.message, state, recipes, 0, 'filters')

@router.callback_query(F.data == CallbackData.CLEAR_FILTERS)
async def handle_clear_filters(callback: CallbackQuery, state: FSMContext):
    context = await get_context(state)
    context.reset_filters()
    await save_context(state, context)
    keyboard = InlineKeyboards.filters(context.selected_filters, meal_type=context.meal_type, recipe_service=service)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass
    await callback.answer('Фильтры сброшены')

@router.callback_query(F.data == CallbackData.PAGE_PREV)
async def handle_page_prev(callback: CallbackQuery, state: FSMContext):
    slot = await resolve_click_slot(callback, state)
    if slot != 'CONTENT':
        await callback.answer('Это старое меню. Нажмите кнопки внизу 👇', show_alert=False)
        return
    await callback.answer()
    context = await get_context(state)
    current_state = await state.get_state()
    if current_state == UserState.selecting_favourites:
        context.reset_selection()
        await save_context(state, context)
    if context.page > 0:
        context.page -= 1
        await save_context(state, context)
    if context.source == 'filters':
        recipes = service.get_recipes_by_filters(context.meal_type, context.selected_filters)
    elif context.source == 'favourites':
        from services.favourites_service import FavouritesService
        favourites_service = FavouritesService()
        recipe_ids = favourites_service.get_favourite_recipe_ids(callback.from_user.id)
        recipes = []
        for recipe_id in recipe_ids:
            recipe = service.get_recipe_by_id(recipe_id)
            if recipe:
                recipes.append(recipe)
    else:
        recipes = service.get_recipes_by_category(context.meal_type, context.category_id)
    selection_mode = False
    await show_recipes_list(callback.message, state, recipes, context.page, context.source, selection_mode=selection_mode)

@router.callback_query(F.data == CallbackData.PAGE_NEXT)
async def handle_page_next(callback: CallbackQuery, state: FSMContext):
    slot = await resolve_click_slot(callback, state)
    if slot != 'CONTENT':
        await callback.answer('Это старое меню. Нажмите кнопки внизу 👇', show_alert=False)
        return
    await callback.answer()
    context = await get_context(state)
    current_state = await state.get_state()
    if current_state == UserState.selecting_favourites:
        context.reset_selection()
        await save_context(state, context)
    context.page += 1
    await save_context(state, context)
    if context.source == 'filters':
        recipes = service.get_recipes_by_filters(context.meal_type, context.selected_filters)
    elif context.source == 'favourites':
        from services.favourites_service import FavouritesService
        favourites_service = FavouritesService()
        recipe_ids = favourites_service.get_favourite_recipe_ids(callback.from_user.id)
        recipes = []
        for recipe_id in recipe_ids:
            recipe = service.get_recipe_by_id(recipe_id)
            if recipe:
                recipes.append(recipe)
    else:
        recipes = service.get_recipes_by_category(context.meal_type, context.category_id)
    selection_mode = False
    await show_recipes_list(callback.message, state, recipes, context.page, context.source, selection_mode=selection_mode)

@router.callback_query(F.data.in_({CallbackData.RECIPE_BACK, CallbackData.RECIPE_PHOTOS_BACK}))
async def handle_recipe_back(callback: CallbackQuery, state: FSMContext):
    import logging
    logger = logging.getLogger(__name__)
    await callback.answer()
    try:
        context = await get_context(state)
        if callback.data == CallbackData.RECIPE_PHOTOS_BACK:
            try:
                await delete_previous_messages(callback.message, state, extra_ids=[callback.message.message_id])
            except Exception as e:
                logger.warning(f'Error deleting recipe photo messages: {e}')
            context.current_recipe_id = None
            context.clear_messages()
            await save_context(state, context)
            return
        try:
            await delete_previous_messages(callback.message, state, extra_ids=[callback.message.message_id])
        except Exception as e:
            logger.warning(f'Error deleting recipe messages: {e}')
        context.clear_messages()
        logger.debug(f'Context for back: meal_type={context.meal_type}, source={context.source}, category_id={context.category_id}, selection_context={context.selection_context}')
        if not context.meal_type or (context.source == 'category' and (not context.category_id)):
            logger.warning('Incomplete context, returning to categories')
            await show_categories_screen(callback.message, state, context.meal_type or 'breakfast', edit=False)
            return
        context.current_recipe_id = None
        context.clear_messages()
        await save_context(state, context)
        context_str = context.selection_context if context.selection_context else build_selection_context(context)
        logger.debug(f'Restoring recipes from context_str: {context_str}')
        recipes = restore_recipes_from_context(context_str, service, callback.from_user.id)
        logger.debug(f'Restored {len(recipes)} recipes')
        if recipes:
            await show_recipes_list(callback.message, state, recipes, context.page, context.source)
        else:
            logger.warning('No recipes restored, returning to categories')
            await show_categories_screen(callback.message, state, context.meal_type, edit=False)
    except Exception as e:
        logger.exception(f'Ошибка в handle_recipe_back: {e}')
        try:
            context = await get_context(state)
            meal = context.meal_type or 'breakfast'
            await show_categories_screen(callback.message, state, meal, edit=False)
        except Exception as e2:
            logger.error(f'Error showing categories screen: {e2}', exc_info=True)

@router.callback_query(F.data == CallbackData.RECIPE_GUIDE)
async def handle_recipe_guide(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_guide_image(callback.message, state)

@router.callback_query(F.data.startswith(f'{CallbackData.RECIPE}:'))
async def handle_recipe_selection(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await log_event(
        source_bot="main_bot",
        telegram_user_id=callback.from_user.id,
        event_type="RECIPE_OPEN",
        action="Открыть рецепт",
        screen="recipes_list",
        status="ok",
        payload_json={},
        callback_data=callback.data,
        username=callback.from_user.username,
    )
    context = await get_context(state)
    ids = getattr(context, 'page_recipe_ids', None) or []
    try:
        i = int(callback.data.split(':')[1])
    except (IndexError, ValueError):
        await callback.message.answer('Ошибка', protect_content=PROTECT_CONTENT)
        return
    if i < 0 or i >= len(ids):
        await callback.message.answer('Рецепт не найден', protect_content=PROTECT_CONTENT)
        return
    recipe_id = ids[i]
    recipe = service.get_recipe_by_id(recipe_id)
    if not recipe:
        await callback.message.answer('Рецепт не найден', protect_content=PROTECT_CONTENT)
        return
    photos_shown = await show_recipe_photos(callback.message, state, recipe)
    if photos_shown:
        return
    await callback.message.answer('Фото для этого рецепта скоро добавим 🤍', protect_content=PROTECT_CONTENT)

@router.callback_query(F.data == CallbackData.RECIPE_PHOTO_FAV)
async def handle_recipe_photo_fav(callback: CallbackQuery, state: FSMContext):
    from services.favourites_service import FavouritesService
    context = await get_context(state)
    recipe_id = context.current_recipe_id
    if not recipe_id:
        await callback.answer('Ошибка: рецепт не найден', show_alert=True)
        return
    favourites_service = FavouritesService()
    user_id = callback.from_user.id
    added = favourites_service.add_favourite(user_id, recipe_id)
    if added:
        await callback.answer(Texts.FAVOURITES_ADDED, show_alert=False)
    else:
        await callback.answer(Texts.FAVOURITES_ALREADY, show_alert=False)
    await log_event(
        source_bot="main_bot",
        telegram_user_id=callback.from_user.id,
        event_type="FAVOURITE_ADD" if added else "FAVOURITE_ADD_DUP",
        action="Добавить в избранное",
        screen="recipe_photo",
        status="ok",
        payload_json={"recipe_id": recipe_id},
        callback_data=callback.data,
        username=callback.from_user.username,
    )

@router.callback_query(F.data == CallbackData.RECIPE_PHOTO_FAV_REMOVE)
async def handle_recipe_photo_fav_remove(callback: CallbackQuery, state: FSMContext):
    from services.favourites_service import FavouritesService
    from handlers.favourites_handlers import show_favourites_list
    context = await get_context(state)
    recipe_id = context.current_recipe_id
    if not recipe_id:
        await callback.answer('Ошибка: рецепт не найден', show_alert=True)
        return
    user_id = callback.from_user.id
    favourites_service = FavouritesService()
    favourites_service.remove_favourite(user_id, recipe_id)
    await callback.answer(Texts.FAVOURITES_REMOVED, show_alert=False)
    await log_event(
        source_bot="main_bot",
        telegram_user_id=callback.from_user.id,
        event_type="FAVOURITE_REMOVE",
        action="Удалить из избранного",
        screen="recipe_photo",
        status="ok",
        payload_json={"recipe_id": recipe_id},
        callback_data=callback.data,
        username=callback.from_user.username,
    )
    try:
        await delete_previous_messages(callback.message, state, extra_ids=[callback.message.message_id])
    except Exception:
        pass
    context = await get_context(state)
    context.current_recipe_id = None
    await save_context(state, context)
    recipe_ids = favourites_service.get_favourite_recipe_ids(user_id)
    recipes = []
    for rid in recipe_ids:
        r = service.get_recipe_by_id(rid)
        if r:
            recipes.append(r)
    total_pages = max(1, (len(recipes) + RECIPES_PER_PAGE - 1) // RECIPES_PER_PAGE)
    page = min(context.page, total_pages - 1) if total_pages else 0
    list_msg_id = getattr(context, 'favourites_list_message_id', None)
    await show_favourites_list(callback.message, state, recipes, page, delete_mode=False, edit_message_id=list_msg_id)

@router.callback_query(F.data == CallbackData.RECIPE_SUITABLE)
async def handle_recipe_suitable(callback: CallbackQuery, state: FSMContext):
    context = await get_context(state)
    recipe_id = context.current_recipe_id
    if not recipe_id:
        await callback.answer('Ошибка', show_alert=True)
        return
    recipe = service.get_recipe_by_id(recipe_id)
    if not recipe:
        await callback.answer('Рецепт не найден', show_alert=True)
        return
    telegraph_url = recipe.telegraph_url if recipe.telegraph_url else None
    await show_recipe_accepted(callback.message, state, recipe, telegraph_url)
    await callback.answer('✅ Отличный выбор!')

@router.callback_query(F.data == CallbackData.RECIPE_NOT_SUITABLE)
async def handle_recipe_not_suitable(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    context = await get_context(state)
    if context.source == 'filters':
        recipes = service.get_recipes_by_filters(context.meal_type, context.selected_filters)
    elif context.source == 'favourites':
        from services.favourites_service import FavouritesService
        favourites_service = FavouritesService()
        recipe_ids = favourites_service.get_favourite_recipe_ids(callback.from_user.id)
        recipes = []
        for recipe_id in recipe_ids:
            recipe = service.get_recipe_by_id(recipe_id)
            if recipe:
                recipes.append(recipe)
    else:
        recipes = service.get_recipes_by_category(context.meal_type, context.category_id)
    await show_recipes_list(callback.message, state, recipes, context.page, context.source, selection_mode=False)

async def reset_user_to_meals(
    user_id: int,
    chat_id: int,
    message: Message,
    state: FSMContext,
) -> None:
    """
    Рендерим "Приёмы пищи" заново (как будто пользователь зашёл заново),
    но с сохранением persistent welcome-сообщения из ui registry.
    """
    logger.info("[UI_REGISTRY] reset to meals user=%s", user_id)

    # Очищаем UI-слоты FSM, чтобы show_meals_screen не пытался редактировать удалённые сообщения.
    try:
        await clear_slot(message.bot, state, chat_id, "MEALS")
    except Exception:
        pass
    try:
        await clear_slot(message.bot, state, chat_id, "CATEGORIES")
    except Exception:
        pass
    try:
        await clear_slot(message.bot, state, chat_id, "CONTENT")
    except Exception:
        pass

    # Сбрасываем контекст рендера.
    context = UserContext()
    await save_context(state, context)

    await show_meals_screen(message, state)


async def on_inactivity_start(
    user_id: int,
    chat_id: int,
    current_start_message_id: Optional[int],
    message: Message,
    state: FSMContext,
) -> None:
    """
    Специальная обработка inactivity reminder:
    1) удалить все ui_messages кроме persistent welcome
    2) удалить сообщение с кнопкой "НАЧАТЬ" (prompt)
    3) очистить записи из таблицы
    4) заново прислать экран "Приёмы пищи"
    """
    logger.info("[UI_REGISTRY] inactivity start clicked user=%s", user_id)

    from services.ui_registry import clear_user_ui_session, delete_ui_message

    # 1) Clear all UI messages except persistent welcome.
    await clear_user_ui_session(
        user_id=user_id,
        preserve_persistent=True,
        preserve_message_ids=None,
        bot=message.bot,
    )

    # 2) Delete the prompt message itself (idempotent).
    if current_start_message_id is not None:
        try:
            await message.bot.delete_message(chat_id=chat_id, message_id=current_start_message_id)
        except Exception:
            try:
                await message.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=current_start_message_id,
                    reply_markup=None,
                )
            except Exception:
                pass
        try:
            delete_ui_message(user_id=user_id, message_id=current_start_message_id)
        except Exception:
            pass

    # 3) Clean reminder scheduling record.
    activity_service.clear_reminder(user_id)

    # 4) Re-render meals (снимаем залипшую reply-клавиатуру, если осталась от старых версий).
    from services.inactivity_flow import dismiss_reply_keyboard

    await dismiss_reply_keyboard(message.bot, chat_id)
    await reset_user_to_meals(user_id=user_id, chat_id=chat_id, message=message, state=state)


@router.callback_query(F.data == CallbackData.INACTIVITY_START)
async def handle_inactivity_start_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.message:
        return
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    await process_start_over(
        user_id=user_id,
        chat_id=chat_id,
        bot=callback.message.bot,
        state=state,
        anchor_message=callback.message,
        prompt_message_id=callback.message.message_id,
        delete_user_message=False,
    )


@router.message(F.func(lambda m: is_start_over_text(m.text)))
async def handle_start_over(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    chat_id = message.chat.id
    await process_start_over(
        user_id=user_id,
        chat_id=chat_id,
        bot=message.bot,
        state=state,
        anchor_message=message,
        prompt_message_id=None,
        delete_user_message=True,
    )