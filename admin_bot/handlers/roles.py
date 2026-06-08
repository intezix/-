from __future__ import annotations

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import CallbackQuery, Message

from admin_bot.app_context import AppContext
from admin_bot.db.repositories import AdminUserRepository
from admin_bot.keyboards.inline import InlineKeyboards
from admin_bot.services.role_service import ROLES
from admin_bot.states.admin import AddAdminStates


router = Router()
kb = InlineKeyboards()


# ─── Внутренние хелперы ───────────────────────────────────────────────────────

async def _render_roles_list(target: Message | CallbackQuery, *, ctx: AppContext) -> None:
    caller_id = target.from_user.id
    role = await ctx.roles.require_access(caller_id)
    if not ctx.roles.can_manage_roles(role):
        text = "Недостаточно прав. Управление администраторами доступно только владельцу."
        if isinstance(target, Message):
            await target.answer(text, reply_markup=kb.to_menu())
        else:
            await target.answer("Недостаточно прав", show_alert=True)
        return
    if not ctx.db.pool:
        raise RuntimeError("DB not connected")
    async with ctx.db.pool.acquire() as conn:
        repo = AdminUserRepository(conn)
        rows = await repo.list_admins()
    lines = ["⚙️ <b>Администраторы</b>", "", "Нажмите на пользователя, чтобы изменить роль/доступ/уведомления."]
    items: list[tuple[int, bool, bool, str]] = []
    for r in rows:
        tg_id = int(r["telegram_user_id"])
        uname = r["username"] or "—"
        rcode = str(r["role"] or "")
        title = ROLES.get(rcode).title_ru if rcode in ROLES else rcode
        active = "✅" if r["is_active"] else "⛔️"
        notify = "🔔" if r["notify_enabled"] else "🔕"
        lines.append(f"{active} {notify} <code>{tg_id}</code> — @{uname} — <b>{title}</b>")
        items.append((tg_id, bool(r["is_active"]), bool(r["notify_enabled"]), rcode))
    markup = kb.roles_list(items)
    text = "\n".join(lines)
    if isinstance(target, Message):
        await target.answer(text, reply_markup=markup)
    else:
        await target.message.edit_text(text, reply_markup=markup)
        await target.answer()


async def _render_role_card(callback: CallbackQuery, *, ctx: AppContext, tg_id: int) -> None:
    role = await ctx.roles.require_access(callback.from_user.id)
    if not ctx.roles.can_manage_roles(role):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    if not ctx.db.pool:
        raise RuntimeError("DB not connected")
    async with ctx.db.pool.acquire() as conn:
        repo = AdminUserRepository(conn)
        row = await repo.get_by_telegram_id(tg_id)
    if not row:
        await callback.answer("Не найдено", show_alert=False)
        return
    uname = row["username"] or "—"
    rcode = str(row["role"] or "")
    title = ROLES.get(rcode).title_ru if rcode in ROLES else rcode
    text = "\n".join(
        [
            "⚙️ <b>Администратор</b>",
            "",
            f"ID: <code>{tg_id}</code>",
            f"Username: @{uname}",
            f"Роль: <b>{title}</b>",
        ]
    )
    await callback.message.edit_text(
        text,
        reply_markup=kb.role_card(
            tg_id,
            is_active=bool(row["is_active"]),
            notify_enabled=bool(row["notify_enabled"]),
            role_code=rcode,
        ),
    )
    await callback.answer()


# ─── Список администраторов ───────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "roles:list")
async def roles_list_cb(callback: CallbackQuery, ctx: AppContext) -> None:
    await _render_roles_list(callback, ctx=ctx)


@router.callback_query(lambda c: c.data and c.data.startswith("role:open:"))
async def role_open_cb(callback: CallbackQuery, ctx: AppContext) -> None:
    tg_id = int((callback.data or "").split(":")[2])
    await _render_role_card(callback, ctx=ctx, tg_id=tg_id)


# ─── Изменение роли / доступа / уведомлений ───────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("role:toggle_active:"))
async def role_toggle_active(callback: CallbackQuery, ctx: AppContext) -> None:
    role = await ctx.roles.require_access(callback.from_user.id)
    if not ctx.roles.can_manage_roles(role):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    tg_id = int((callback.data or "").split(":")[2])
    if not ctx.db.pool:
        raise RuntimeError("DB not connected")
    async with ctx.db.pool.acquire() as conn:
        repo = AdminUserRepository(conn)
        row = await repo.get_by_telegram_id(tg_id)
    if not row:
        await callback.answer("Не найдено", show_alert=False)
        return
    await ctx.roles_admin.set_active(
        actor_telegram_user_id=callback.from_user.id,
        target_telegram_user_id=tg_id,
        is_active=(not bool(row["is_active"])),
    )
    await _render_role_card(callback, ctx=ctx, tg_id=tg_id)


@router.callback_query(lambda c: c.data and c.data.startswith("role:toggle_notify:"))
async def role_toggle_notify(callback: CallbackQuery, ctx: AppContext) -> None:
    role = await ctx.roles.require_access(callback.from_user.id)
    if not ctx.roles.can_manage_roles(role):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    tg_id = int((callback.data or "").split(":")[2])
    if not ctx.db.pool:
        raise RuntimeError("DB not connected")
    async with ctx.db.pool.acquire() as conn:
        repo = AdminUserRepository(conn)
        row = await repo.get_by_telegram_id(tg_id)
    if not row:
        await callback.answer("Не найдено", show_alert=False)
        return
    await ctx.roles_admin.set_notify_enabled(
        actor_telegram_user_id=callback.from_user.id,
        target_telegram_user_id=tg_id,
        notify_enabled=(not bool(row["notify_enabled"])),
    )
    await _render_role_card(callback, ctx=ctx, tg_id=tg_id)


@router.callback_query(lambda c: c.data and c.data.startswith("role:set:"))
async def role_set_cb(callback: CallbackQuery, ctx: AppContext) -> None:
    role = await ctx.roles.require_access(callback.from_user.id)
    if not ctx.roles.can_manage_roles(role):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    parts = (callback.data or "").split(":")
    tg_id = int(parts[2])
    new_role = parts[3].strip().lower()
    if new_role not in ROLES:
        await callback.answer("Неизвестная роль", show_alert=False)
        return
    await ctx.roles_admin.set_role(
        actor_telegram_user_id=callback.from_user.id,
        target_telegram_user_id=tg_id,
        role=new_role,
    )
    await _render_role_card(callback, ctx=ctx, tg_id=tg_id)


# ─── Добавить нового администратора (FSM) ─────────────────────────────────────

@router.callback_query(lambda c: c.data == "roles:add")
async def roles_add_start(callback: CallbackQuery, ctx: AppContext, state: FSMContext) -> None:
    role = await ctx.roles.require_access(callback.from_user.id)
    if not ctx.roles.can_manage_roles(role):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await state.set_state(AddAdminStates.waiting_for_id)
    text = "\n".join(
        [
            "➕ <b>Добавить администратора</b>",
            "",
            "Введите <b>Telegram ID</b> нового администратора",
            "(только цифры, например <code>613861214</code>):",
        ]
    )
    await callback.message.edit_text(text, reply_markup=kb.cancel_fsm_kb("nav:roles"))
    await callback.answer()


@router.message(StateFilter(AddAdminStates.waiting_for_id))
async def roles_add_got_id(message: Message, state: FSMContext, ctx: AppContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(
            "Введите числовой Telegram ID (только цифры):",
            reply_markup=kb.cancel_fsm_kb("nav:roles"),
        )
        return

    target_tg_id = int(text)
    await state.clear()

    confirm_text = "\n".join(
        [
            "➕ <b>Выберите роль</b>",
            "",
            f"Telegram ID: <code>{target_tg_id}</code>",
            "",
            "Какую роль назначить?",
        ]
    )
    await message.answer(confirm_text, reply_markup=kb.role_picker_new_admin(target_tg_id))


@router.callback_query(lambda c: c.data and c.data.startswith("roles:newadmin_set:"))
async def roles_newadmin_set(callback: CallbackQuery, ctx: AppContext) -> None:
    role = await ctx.roles.require_access(callback.from_user.id)
    if not ctx.roles.can_manage_roles(role):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    # roles:newadmin_set:<tg_id>:<role>
    parts = (callback.data or "").split(":")
    target_tg_id = int(parts[2])
    new_role = parts[3].strip().lower()
    if new_role not in ROLES:
        await callback.answer("Неизвестная роль", show_alert=False)
        return

    await ctx.roles_admin.create_or_update_admin(
        actor_telegram_user_id=callback.from_user.id,
        target_telegram_user_id=target_tg_id,
        role=new_role,
        username=None,
    )
    role_title = ROLES[new_role].title_ru
    await callback.message.edit_text(
        f"✅ Администратор <code>{target_tg_id}</code> добавлен как <b>{role_title}</b>.\n\n"
        "Управляйте администраторами через список ниже.",
        reply_markup=kb.roles_entry(),
    )
    await callback.answer("Добавлено")
