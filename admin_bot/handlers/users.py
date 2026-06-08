from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import default_state
from aiogram.types import CallbackQuery, Message

from admin_bot.app_context import AppContext
from admin_bot.keyboards.inline import InlineKeyboards


router = Router()
kb = InlineKeyboards()


@router.message(Command("user"))
async def cmd_user(message: Message, ctx: AppContext) -> None:
    await ctx.roles.require_access(message.from_user.id)
    await message.answer(
        "\n".join(
            [
                "👤 <b>Поиск пользователя</b>",
                "",
                "Отправьте одним сообщением:",
                "├ <b>ID</b>",
                "├ <b>@username</b>",
                "└ <b>email</b>",
            ]
        ),
        reply_markup=kb.to_menu(),
    )


# StateFilter(default_state) гарантирует, что этот обработчик НЕ перехватывает
# сообщения, когда активен любой FSM-флоу (AddAdminStates, GrantDaysStates и т.д.)
@router.message(StateFilter(default_state))
async def handle_user_search(message: Message, ctx: AppContext) -> None:
    text = (message.text or "").strip()
    if not text:
        return
    if not (text.isdigit() or text.startswith("@") or "@" in text):
        return
    try:
        await ctx.roles.require_access(message.from_user.id)
    except Exception:
        return

    user = await ctx.users.find_user(query=text)
    if not user:
        await message.answer("Ничего не найдено. Проверьте запрос.", reply_markup=kb.to_menu())
        return

    tg_id = int(user["telegram_user_id"])
    _, card_text = await ctx.users.build_user_card(telegram_user_id=tg_id)
    await message.answer(card_text, reply_markup=kb.user_card(tg_id), disable_web_page_preview=True)


@router.callback_query(lambda c: c.data and c.data.startswith("users:list:"))
async def users_list_page(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    try:
        page = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        page = 0
    users, total = await ctx.users.list_page(page=page)
    total_pages = max(1, (total + 14) // 15)
    text = "\n".join([
        f"👤 <b>Пользователи</b>  <i>({total} всего, стр. {page + 1}/{total_pages})</i>",
        "",
        "Нажмите на пользователя для просмотра карточки.",
        "Или введите в чат: <b>ID</b>, <b>@username</b> или <b>email</b> для поиска.",
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb.users_list(users, page=page, total=total))
    except Exception:
        pass
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("user:open:"))
async def open_user(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    tg_id = int((callback.data or "").split(":")[2])
    _, card_text = await ctx.users.build_user_card(telegram_user_id=tg_id)
    await callback.message.edit_text(card_text, reply_markup=kb.user_card(tg_id), disable_web_page_preview=True)
    await callback.answer()
