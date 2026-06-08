from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from config import Texts, PROTECT_CONTENT
from services import RecipeService
from services.favourites_service import FavouritesService
from keyboards import InlineKeyboards
from keyboards.inline import CallbackData
from handlers.common import (
    get_context,
    save_context,
    save_message_id,
    show_recipes_list,
    build_selection_context,
    restore_recipes_from_context,
    restore_context_from_string,
    clear_slot,
    set_ui_slot,
)
from states import UserState
router = Router()
service = RecipeService()
favourites_service = FavouritesService()

@router.callback_query(F.data == CallbackData.FAVOURITES)
async def handle_favourites(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.common import get_context, save_context
    context = await get_context(state)
    context.clear_messages()
    await save_context(state, context)
    # Перед входом в избранное очищаем текущий CONTENT-слот,
    # чтобы список избранного всегда занимал один UI#3.
    chat_id = callback.message.chat.id
    await clear_slot(callback.bot, state, chat_id, 'CONTENT')
    user_id = callback.from_user.id
    recipe_ids = favourites_service.get_favourite_recipe_ids(user_id)
    if not recipe_ids:
        text = Texts.FAVOURITES_EMPTY
        keyboard = InlineKeyboards.favourites_list([], False, False)
        sent = await callback.message.answer(text, reply_markup=keyboard, protect_content=PROTECT_CONTENT)
        from handlers.common import save_message_id
        await save_message_id(state, sent.message_id)
        await set_ui_slot(state, 'CONTENT', sent.message_id)
        return
    recipes = []
    for recipe_id in recipe_ids:
        recipe = service.get_recipe_by_id(recipe_id)
        if recipe:
            recipes.append(recipe)
    await show_favourites_list(callback.message, state, recipes, 0)

@router.callback_query(F.data == CallbackData.FAV_PAGE_PREV)
async def handle_fav_page_prev(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    context = await get_context(state)
    current_state = await state.get_state()
    delete_mode = False
    if current_state == UserState.selecting_favourites and context.source == 'favourites':
        context.selected_recipe_ids = set()
        await save_context(state, context)
    user_id = callback.from_user.id
    if context.page > 0:
        context.page -= 1
        await save_context(state, context)
    recipe_ids = favourites_service.get_favourite_recipe_ids(user_id)
    recipes = []
    for recipe_id in recipe_ids:
        recipe = service.get_recipe_by_id(recipe_id)
        if recipe:
            recipes.append(recipe)
    await show_favourites_list(callback.message, state, recipes, context.page, delete_mode=delete_mode)

@router.callback_query(F.data == CallbackData.FAV_PAGE_NEXT)
async def handle_fav_page_next(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    context = await get_context(state)
    current_state = await state.get_state()
    delete_mode = False
    if current_state == UserState.selecting_favourites and context.source == 'favourites':
        context.selected_recipe_ids = set()
        await save_context(state, context)
    user_id = callback.from_user.id
    context.page += 1
    await save_context(state, context)
    recipe_ids = favourites_service.get_favourite_recipe_ids(user_id)
    recipes = []
    for recipe_id in recipe_ids:
        recipe = service.get_recipe_by_id(recipe_id)
        if recipe:
            recipes.append(recipe)
    await show_favourites_list(callback.message, state, recipes, context.page, delete_mode=delete_mode)

@router.callback_query(F.data.startswith(f'{CallbackData.FAV_ENTER}:'))
async def handle_fav_enter(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data_without_prefix = callback.data[len(f'{CallbackData.FAV_ENTER}:'):]
    if '|' not in data_without_prefix:
        try:
            page_offset = int(data_without_prefix)
            context_str = ''
        except ValueError:
            await callback.answer('Ошибка формата', show_alert=True)
            return
    else:
        parts = data_without_prefix.split('|', 1)
        if len(parts) < 1:
            await callback.answer('Ошибка формата', show_alert=True)
            return
        try:
            page_offset = int(parts[0])
        except ValueError:
            await callback.answer('Ошибка формата offset', show_alert=True)
            return
        context_str = parts[1] if len(parts) > 1 else ''
    context = await get_context(state)
    if not context_str:
        context_str = build_selection_context(context)
        print(f'[CALLBACK DEBUG] FAV_ENTER: context был пустой, восстановлен из state: {context_str}')
        if not context_str or context_str == 'category:unknown:unknown':
            context_str = ''
            print(f'[CALLBACK DEBUG] FAV_ENTER: не удалось восстановить context, используем пустой')
    context.selection_context = context_str
    context.page = page_offset
    context.reset_selection()
    if context.selected_recipe_ids is None:
        context.selected_recipe_ids = set()
    if context_str:
        restore_context_from_string(context, context_str)
    await save_context(state, context)
    if context_str:
        recipes = restore_recipes_from_context(context_str, service, callback.from_user.id)
    else:
        if context.source == 'filters':
            recipes = service.get_recipes_by_filters(context.meal_type, context.selected_filters)
        elif context.source == 'category':
            recipes = service.get_recipes_by_category(context.meal_type, context.category_id)
        else:
            recipes = []
        print(f'[CALLBACK DEBUG] FAV_ENTER: восстановлен список из state, source={context.source}, recipes_count={len(recipes)}')
    if not recipes:
        await callback.answer('Ошибка: не удалось восстановить список', show_alert=True)
        return
    await show_recipes_list(callback.message, state, recipes, page_offset, context.source, selection_mode=True)

@router.callback_query(F.data.startswith(f'{CallbackData.FAV_TOGGLE}:'))
async def handle_fav_toggle(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(':', 2)
    if len(parts) < 3:
        await callback.answer('Ошибка формата', show_alert=True)
        return
    try:
        idx = int(parts[2])
    except ValueError:
        await callback.answer('Ошибка формата', show_alert=True)
        return
    context = await get_context(state)
    ids = getattr(context, 'page_recipe_ids', None) or []
    if idx < 0 or idx >= len(ids):
        await callback.answer('Ошибка', show_alert=True)
        return
    recipe_id = ids[idx]
    if context.selected_recipe_ids is None:
        context.selected_recipe_ids = set()
    context.toggle_recipe_selection(recipe_id)
    await save_context(state, context)
    context = await get_context(state)
    is_delete_mode = context.source == 'favourites' and context.selection_context == 'favourites:'
    if is_delete_mode:
        user_id = callback.from_user.id
        recipe_ids = favourites_service.get_favourite_recipe_ids(user_id)
        recipes = []
        for rid in recipe_ids:
            r = service.get_recipe_by_id(rid)
            if r:
                recipes.append(r)
        if not recipes:
            await callback.answer('Избранное пусто', show_alert=True)
            return
        from config import RECIPES_PER_PAGE
        page_recipes, total, has_prev, has_next = service.paginate(recipes, context.page)
        context.page_recipe_ids = [r.id for r in page_recipes]
        if context.selected_recipe_ids is None:
            context.selected_recipe_ids = set()
        await save_context(state, context)
        context = await get_context(state)
        telegraph_urls = {}
        for recipe in page_recipes:
            if recipe.telegraph_url and recipe.telegraph_url.startswith('https://telegra.ph/'):
                telegraph_urls[recipe.id] = recipe.telegraph_url
        keyboard = InlineKeyboards.favourites_list(page_recipes, has_prev, has_next, telegraph_urls=telegraph_urls, delete_mode=True, selected_recipe_ids=context.selected_recipe_ids, page_offset=context.page)
    else:
        if not context.selection_context:
            context.selection_context = build_selection_context(context)
            if not context.selection_context or context.selection_context == 'category:unknown:unknown':
                await callback.answer('Ошибка: потерян контекст', show_alert=True)
                return
            await save_context(state, context)
        recipes = restore_recipes_from_context(context.selection_context, service, callback.from_user.id)
        if not recipes:
            await callback.answer('Ошибка: не удалось восстановить список', show_alert=True)
            return
        from config import RECIPES_PER_PAGE
        page_recipes, total, has_prev, has_next = service.paginate(recipes, context.page)
        context.page_recipe_ids = [r.id for r in page_recipes]
        if context.selected_recipe_ids is None:
            context.selected_recipe_ids = set()
        await save_context(state, context)
        context = await get_context(state)
        keyboard = InlineKeyboards.recipes_list(page_recipes, has_prev, has_next, selection_mode=True, selected_recipe_ids=context.selected_recipe_ids, selection_context=context.selection_context, page_offset=context.page)
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=callback.message.caption, reply_markup=keyboard, parse_mode='HTML')
        else:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        if 'message is not modified' not in str(e):
            print(f'Ошибка обновления клавиатуры: {e}')

@router.callback_query(F.data == CallbackData.FAV_COMMIT)
async def handle_fav_commit(callback: CallbackQuery, state: FSMContext):
    context = await get_context(state)
    user_id = callback.from_user.id
    if not context.selected_recipe_ids:
        await callback.answer('Выберите рецепты', show_alert=True)
        return
    added_count = 0
    already_in_fav_count = 0
    for recipe_id in context.selected_recipe_ids:
        if favourites_service.add_favourite(user_id, recipe_id):
            added_count += 1
        else:
            already_in_fav_count += 1
    total_selected = len(context.selected_recipe_ids)
    if added_count > 0:
        if added_count == 1:
            text = f'Добавлено: {added_count} рецепт ⭐'
        elif added_count in [2, 3, 4]:
            text = f'Добавлено: {added_count} рецепта ⭐'
        else:
            text = f'Добавлено: {added_count} рецептов ⭐'
        if already_in_fav_count > 0:
            if already_in_fav_count == 1:
                text += f'\n{already_in_fav_count} уже был в избранном'
            else:
                text += f'\n{already_in_fav_count} уже были в избранном'
        await callback.answer(text, show_alert=False)
        selection_context_backup = context.selection_context
        if selection_context_backup:
            restore_context_from_string(context, selection_context_backup)
        else:
            selection_context_backup = build_selection_context(context)
            if not selection_context_backup or selection_context_backup == 'category:unknown:unknown':
                await callback.answer('Ошибка: потерян контекст', show_alert=True)
                return
        context.reset_selection()
        context.selection_context = selection_context_backup
        await save_context(state, context)
        recipes = restore_recipes_from_context(selection_context_backup, service, callback.from_user.id)
        if not recipes:
            await callback.answer('Ошибка: не удалось восстановить список', show_alert=True)
            return
        await show_recipes_list(callback.message, state, recipes, context.page, context.source, selection_mode=False)
    else:
        if total_selected == 1:
            await callback.answer('Рецепт уже в избранном', show_alert=False)
        else:
            await callback.answer('Все рецепты уже в избранном', show_alert=False)
        if not context.selection_context:
            context.selection_context = build_selection_context(context)
            if not context.selection_context or context.selection_context == 'category:unknown:unknown':
                await callback.answer('Ошибка: потерян контекст', show_alert=True)
                return
            await save_context(state, context)
        recipes = restore_recipes_from_context(context.selection_context, service, callback.from_user.id)
        if not recipes:
            await callback.answer('Ошибка: не удалось восстановить список', show_alert=True)
            return
        from config import RECIPES_PER_PAGE
        page_recipes, total, has_prev, has_next = service.paginate(recipes, context.page)
        keyboard = InlineKeyboards.recipes_list(page_recipes, has_prev, has_next, selection_mode=True, selected_recipe_ids=context.selected_recipe_ids, selection_context=context.selection_context, page_offset=context.page)
        try:
            if callback.message.photo:
                await callback.message.edit_caption(caption=callback.message.caption, reply_markup=keyboard, parse_mode='HTML')
            else:
                await callback.message.edit_reply_markup(reply_markup=keyboard)
        except Exception as e:
            if 'message is not modified' not in str(e):
                print(f'Ошибка обновления клавиатуры: {e}')

@router.callback_query(F.data == CallbackData.FAV_CANCEL)
async def handle_fav_cancel(callback: CallbackQuery, state: FSMContext):
    context = await get_context(state)
    selection_context_backup = context.selection_context
    page_backup = context.page
    if not selection_context_backup:
        selection_context_backup = build_selection_context(context)
        if not selection_context_backup or selection_context_backup == 'category:unknown:unknown':
            await callback.answer('Ошибка: потерян контекст', show_alert=True)
            return
    restore_context_from_string(context, selection_context_backup)
    context.page = page_backup
    context.selected_recipe_ids = set()
    await save_context(state, context)
    recipes = restore_recipes_from_context(selection_context_backup, service, callback.from_user.id)
    if not recipes:
        await callback.answer('Ошибка: не удалось восстановить список', show_alert=True)
        return
    await callback.answer('Отменено', show_alert=False)
    await show_recipes_list(callback.message, state, recipes, context.page, context.source, selection_mode=False)

async def show_favourites_list(message: Message, state: FSMContext, recipes: list, page: int, delete_mode: bool=False, edit_message_id: int=None) -> None:
    from config import RECIPES_PER_PAGE, RECIPES_HEADER_IMAGE_URL
    from handlers.common import save_message_id, delete_previous_messages, clear_slot, set_ui_slot
    from states import UserState
    from services.ui_registry import register_ui_message
    if delete_mode:
        await state.set_state(UserState.selecting_favourites)
    else:
        await state.set_state(UserState.browsing_recipes)
    edit_existing = edit_message_id is not None
    can_edit = not edit_existing and message.photo is not None
    if not can_edit and (not edit_existing):
        # Для избранного также применяем политику одного CONTENT-слота:
        try:
            await clear_slot(message.bot, state, message.chat.id, 'CONTENT')
        except Exception:
            pass
        await delete_previous_messages(message, state)
    context = await get_context(state)
    context.page = page
    context.source = 'favourites'
    if not delete_mode:
        context.selected_recipe_ids = set()
    elif not context.selection_context:
        context.selection_context = 'favourites:'
    await save_context(state, context)
    page_recipes, total, has_prev, has_next = service.paginate(recipes, page)
    context.page_recipe_ids = [r.id for r in page_recipes]
    await save_context(state, context)
    if not page_recipes:
        context.page_recipe_ids = []
        await save_context(state, context)
        text = Texts.FAVOURITES_EMPTY
        keyboard = InlineKeyboards.favourites_list([], False, False, delete_mode=delete_mode)
        if edit_existing:
            try:
                await message.bot.edit_message_caption(chat_id=message.chat.id, message_id=edit_message_id, caption=text, reply_markup=keyboard, parse_mode='HTML')
                await set_ui_slot(state, 'CONTENT', edit_message_id)
                register_ui_message(
                    user_id=message.chat.id,
                    chat_id=message.chat.id,
                    message_id=edit_message_id,
                    kind='favourites_list',
                    is_persistent=False,
                )
            except Exception:
                pass
            await save_context(state, context)
            return
        if can_edit:
            try:
                await message.edit_caption(caption=text, reply_markup=keyboard, parse_mode='HTML')
                context.favourites_list_message_id = message.message_id
                await set_ui_slot(state, 'CONTENT', message.message_id)
                register_ui_message(
                    user_id=message.chat.id,
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    kind='favourites_list',
                    is_persistent=False,
                )
                await save_context(state, context)
            except Exception:
                sent = await message.answer(text, reply_markup=keyboard, protect_content=PROTECT_CONTENT)
                await save_message_id(state, sent.message_id)
                context.favourites_list_message_id = sent.message_id
                await set_ui_slot(state, 'CONTENT', sent.message_id)
                register_ui_message(
                    user_id=message.chat.id,
                    chat_id=message.chat.id,
                    message_id=sent.message_id,
                    kind='favourites_list',
                    is_persistent=False,
                )
                await save_context(state, context)
        else:
            sent = await message.answer(text, reply_markup=keyboard, protect_content=PROTECT_CONTENT)
            await save_message_id(state, sent.message_id)
            context.favourites_list_message_id = sent.message_id
            await set_ui_slot(state, 'CONTENT', sent.message_id)
            register_ui_message(
                user_id=message.chat.id,
                chat_id=message.chat.id,
                message_id=sent.message_id,
                kind='favourites_list',
                is_persistent=False,
            )
            await save_context(state, context)
        return
    caption = f'\n\n<b>{Texts.FAVOURITES_TITLE}</b>\n\n'
    telegraph_urls = {}
    for recipe in page_recipes:
        if recipe.telegraph_url and recipe.telegraph_url.startswith('https://telegra.ph/'):
            telegraph_urls[recipe.id] = recipe.telegraph_url
    keyboard = InlineKeyboards.favourites_list(page_recipes, has_prev, has_next, telegraph_urls=telegraph_urls, delete_mode=delete_mode, selected_recipe_ids=context.selected_recipe_ids if delete_mode else None, page_offset=page)
    if edit_existing:
        try:
            await message.bot.edit_message_caption(chat_id=message.chat.id, message_id=edit_message_id, caption=caption, reply_markup=keyboard, parse_mode='HTML')
            await set_ui_slot(state, 'CONTENT', edit_message_id)
            register_ui_message(
                user_id=message.chat.id,
                chat_id=message.chat.id,
                message_id=edit_message_id,
                kind='favourites_list',
                is_persistent=False,
            )
        except Exception:
            pass
        await save_context(state, context)
        return
    if can_edit:
        try:
            await message.edit_caption(caption=caption, reply_markup=keyboard, parse_mode='HTML')
            context.favourites_list_message_id = message.message_id
            await set_ui_slot(state, 'CONTENT', message.message_id)
            register_ui_message(
                user_id=message.chat.id,
                chat_id=message.chat.id,
                message_id=message.message_id,
                kind='favourites_list',
                is_persistent=False,
            )
            await save_context(state, context)
            return
        except Exception:
            pass
    try:
        sent = await message.answer_photo(photo=RECIPES_HEADER_IMAGE_URL, caption=caption, reply_markup=keyboard, parse_mode='HTML', protect_content=PROTECT_CONTENT)
    except Exception:
        sent = await message.answer(caption, reply_markup=keyboard, parse_mode='HTML')
    await save_message_id(state, sent.message_id)
    context.favourites_list_message_id = sent.message_id
    await set_ui_slot(state, 'CONTENT', sent.message_id)
    register_ui_message(
        user_id=message.chat.id,
        chat_id=message.chat.id,
        message_id=sent.message_id,
        kind='favourites_list',
        is_persistent=False,
    )
    await save_context(state, context)

@router.callback_query(F.data.startswith(f'{CallbackData.FAV_DELETE_ENTER}:'))
async def handle_fav_delete_enter(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(':', 2)
    if len(parts) < 3:
        await callback.answer('Ошибка формата', show_alert=True)
        return
    page_offset = int(parts[2])
    context = await get_context(state)
    context.selection_context = 'favourites:'
    context.page = page_offset
    context.selected_recipe_ids = set()
    context.source = 'favourites'
    await save_context(state, context)
    user_id = callback.from_user.id
    recipe_ids = favourites_service.get_favourite_recipe_ids(user_id)
    recipes = []
    for recipe_id in recipe_ids:
        recipe = service.get_recipe_by_id(recipe_id)
        if recipe:
            recipes.append(recipe)
    if not recipes:
        await callback.answer('Избранное пусто', show_alert=True)
        return
    await show_favourites_list(callback.message, state, recipes, page_offset, delete_mode=True)

@router.callback_query(F.data == CallbackData.FAV_DELETE_COMMIT)
async def handle_fav_delete_commit(callback: CallbackQuery, state: FSMContext):
    context = await get_context(state)
    user_id = callback.from_user.id
    if not context.selected_recipe_ids:
        await callback.answer('Выберите рецепты', show_alert=True)
        return
    deleted_count = 0
    for recipe_id in context.selected_recipe_ids:
        if favourites_service.remove_favourite(user_id, recipe_id):
            deleted_count += 1
    if deleted_count > 0:
        if deleted_count == 1:
            text = f'Удалено: {deleted_count} рецепт'
        elif deleted_count in [2, 3, 4]:
            text = f'Удалено: {deleted_count} рецепта'
        else:
            text = f'Удалено: {deleted_count} рецептов'
        await callback.answer(text, show_alert=False)
        context.selected_recipe_ids = set()
        await save_context(state, context)
        recipe_ids = favourites_service.get_favourite_recipe_ids(user_id)
        recipes = []
        for recipe_id in recipe_ids:
            recipe = service.get_recipe_by_id(recipe_id)
            if recipe:
                recipes.append(recipe)
        await show_favourites_list(callback.message, state, recipes, context.page, delete_mode=False)
    else:
        await callback.answer('Рецепты не найдены в избранном', show_alert=False)

@router.callback_query(F.data == CallbackData.FAV_DELETE_CANCEL)
async def handle_fav_delete_cancel(callback: CallbackQuery, state: FSMContext):
    context = await get_context(state)
    context.selected_recipe_ids = set()
    await save_context(state, context)
    user_id = callback.from_user.id
    recipe_ids = favourites_service.get_favourite_recipe_ids(user_id)
    recipes = []
    for recipe_id in recipe_ids:
        recipe = service.get_recipe_by_id(recipe_id)
        if recipe:
            recipes.append(recipe)
    await callback.answer('Отменено', show_alert=False)
    await show_favourites_list(callback.message, state, recipes, context.page, delete_mode=False)