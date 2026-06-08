import asyncio
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from config import UX_MODE, UXMode, Texts, MEAL_TEXTS, MealType
from states import UserState, UserContext
from services import RecipeService
from keyboards import ReplyKeyboards
from handlers.common import get_context, save_context, get_meal_type_by_text, get_category_id_by_text, get_recipe_id_by_text, show_meals_screen, show_categories_screen, show_recipes_list, show_recipe_detail, show_recipe_accepted, show_recipe_photos


router = Router()
service = RecipeService()

@router.message(UserState.welcome_step1, F.text == Texts.CONTINUE)
async def handle_welcome_continue(message: Message, state: FSMContext):
    from handlers.common import show_welcome_step2
    await show_welcome_step2(message, state)

@router.message(UserState.welcome_step2, F.text == Texts.PAY)
async def handle_welcome_pay(message: Message, state: FSMContext):
    from handlers.common import show_welcome_step3

    # Делаем доступ бесплатным: сразу переходим к следующему шагу без оплаты.
    await show_welcome_step3(message, state)

@router.message(UserState.welcome_step3, F.text == Texts.GO_TO_CATEGORIES)
async def handle_welcome_go_to_categories(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = message.chat.id
    mid1 = data.get('welcome_step1_message_id')
    mid2 = data.get('welcome_step2_message_id')
    mid3 = data.get('welcome_step3_message_id')
    if mid1 is not None:
        try:
            await message.bot.edit_message_text(chat_id=chat_id, message_id=mid1, text=Texts.WELCOME_STEP1_NO_BUTTON, reply_markup=None, parse_mode='HTML')
        except Exception:
            try:
                await message.bot.edit_message_reply_markup(chat_id=chat_id, message_id=mid1, reply_markup=None)
            except Exception:
                pass
    ids_to_delete = [mid for mid in (mid2, mid3) if mid is not None]
    if ids_to_delete:
        ids_to_delete = sorted(ids_to_delete, reverse=True)

        async def _del(mid):
            try:
                await message.bot.delete_message(chat_id, mid)
            except Exception:
                pass
        tasks = [asyncio.create_task(_del(mid)) for mid in ids_to_delete]
        await asyncio.gather(*tasks)
    await state.update_data(welcome_step1_message_id=None, welcome_step2_message_id=None, welcome_step3_message_id=None)
    await show_meals_screen(message, state)

@router.message(UserState.welcome, F.text == Texts.LETS_GO)
async def handle_lets_go(message: Message, state: FSMContext):
    await show_meals_screen(message, state)

@router.message(UserState.choosing_meal, F.text.in_([MEAL_TEXTS[m] for m in [MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER] if m in MEAL_TEXTS]))
async def handle_meal_selection(message: Message, state: FSMContext):
    meal_type = get_meal_type_by_text(message.text)
    if meal_type:
        await show_categories_screen(message, state, meal_type)

@router.message(F.text == Texts.TO_MEALS)
async def handle_to_meals(message: Message, state: FSMContext):
    await show_meals_screen(message, state)

@router.message(UserState.browsing_categories)
async def handle_category_selection(message: Message, state: FSMContext):
    context = await get_context(state)
    if message.text == Texts.TO_MEALS:
        await show_meals_screen(message, state)
        return
    category_id = get_category_id_by_text(message.text, context.meal_type)
    if category_id:
        context.category_id = category_id
        context.source = 'category'
        context.reset_pagination()
        await save_context(state, context)
        recipes = service.get_recipes_by_category(context.meal_type, category_id)
        await show_recipes_list(message, state, recipes, 0, 'category')

@router.message(F.text == Texts.TO_MENU)
async def handle_to_menu(message: Message, state: FSMContext):
    context = await get_context(state)
    if context.meal_type:
        await show_categories_screen(message, state, context.meal_type)
    else:
        await show_meals_screen(message, state)

@router.message(UserState.browsing_recipes, F.text == Texts.BACK)
async def handle_page_prev(message: Message, state: FSMContext):
    context = await get_context(state)
    if context.page > 0:
        context.page -= 1
        await save_context(state, context)
    recipes = service.get_recipes_by_category(context.meal_type, context.category_id)
    await show_recipes_list(message, state, recipes, context.page, 'category')

@router.message(UserState.browsing_recipes, F.text == Texts.NEXT)
async def handle_page_next(message: Message, state: FSMContext):
    context = await get_context(state)
    context.page += 1
    await save_context(state, context)
    recipes = service.get_recipes_by_category(context.meal_type, context.category_id)
    await show_recipes_list(message, state, recipes, context.page, 'category')

@router.message(UserState.browsing_recipes, F.text == Texts.TO_MENU)
async def handle_recipes_to_menu(message: Message, state: FSMContext):
    context = await get_context(state)
    if context.meal_type:
        await show_categories_screen(message, state, context.meal_type)
    else:
        await show_meals_screen(message, state)

@router.message(UserState.browsing_recipes)
async def handle_recipe_selection(message: Message, state: FSMContext):
    context = await get_context(state)
    recipes = service.get_recipes_by_category(context.meal_type, context.category_id)
    recipe_id = get_recipe_id_by_text(message.text, recipes)
    if recipe_id:
        recipe = service.get_recipe_by_id(recipe_id)
        if recipe:
            photos_shown = await show_recipe_photos(message, state, recipe)
            if not photos_shown:
                await show_recipe_detail(message, state, recipe)

@router.message(UserState.viewing_recipe, F.text == Texts.SUITABLE)
async def handle_recipe_suitable(message: Message, state: FSMContext):
    context = await get_context(state)
    recipe = service.get_recipe_by_id(context.current_recipe_id)
    if not recipe:
        await show_meals_screen(message, state)
        return
    await show_recipe_accepted(message, state, recipe)

@router.message(UserState.viewing_recipe, F.text == Texts.NOT_SUITABLE)
async def handle_recipe_not_suitable(message: Message, state: FSMContext):
    context = await get_context(state)
    recipes = service.get_recipes_by_category(context.meal_type, context.category_id)
    await show_recipes_list(message, state, recipes, context.page, 'category')

@router.message(UserState.recipe_accepted, F.text == Texts.TO_MENU)
async def handle_accepted_to_menu(message: Message, state: FSMContext):
    context = await get_context(state)
    if context.meal_type:
        await show_categories_screen(message, state, context.meal_type)
    else:
        await show_meals_screen(message, state)