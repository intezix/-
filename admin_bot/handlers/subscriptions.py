from __future__ import annotations

import time

from aiogram import Router
from aiogram.types import CallbackQuery

from admin_bot.app_context import AppContext
from admin_bot.keyboards.inline import InlineKeyboards


router = Router()
kb = InlineKeyboards()

CONFIRM_TTL_SECONDS = 15


def _now() -> int:
    return int(time.time())


def _confirm_yes(action: str, target_id: int) -> str:
    return f"confirm:{action}:{target_id}:{_now()}"


def _parse_confirm(data: str) -> tuple[str, int, int] | None:
    parts = (data or "").split(":")
    if len(parts) != 4:
        return None
    _, action, tg_id_raw, ts_raw = parts
    if not tg_id_raw.isdigit() or not ts_raw.isdigit():
        return None
    return action, int(tg_id_raw), int(ts_raw)


def _is_confirm_fresh(ts: int) -> bool:
    return (_now() - ts) <= CONFIRM_TTL_SECONDS


@router.callback_query(lambda c: c.data and c.data.startswith("sub:grant_menu:"))
async def sub_grant_menu(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    tg_id = int((callback.data or "").split(":")[2])
    text = "\n".join(
        [
            "♾️ <b>Выдать бессрочный доступ</b>",
            "",
            f"Пользователь: <code>{tg_id}</code>",
            "",
            "Доступ без срока и без автопродления.",
            "",
            "Подтвердить?",
        ]
    )
    await callback.message.edit_text(text, reply_markup=kb.grant_lifetime_confirm(tg_id))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("sub:do_grant_lifetime:"))
async def sub_do_grant_lifetime(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    tg_id = int((callback.data or "").split(":")[2])
    await ctx.subscriptions.grant_lifetime(
        actor_telegram_user_id=callback.from_user.id,
        target_telegram_user_id=tg_id,
    )
    _, card_text = await ctx.users.build_user_card(telegram_user_id=tg_id)
    await callback.message.edit_text(
        "✅ Готово — выдан <b>бессрочный доступ</b>.\n\n" + card_text,
        reply_markup=kb.user_card(tg_id),
    )
    await callback.answer("Доступ выдан")


# Legacy callbacks from old day-based grants → lifetime
@router.callback_query(
    lambda c: c.data
    and c.data.startswith("sub:do_grant:")
    and not c.data.startswith("sub:do_grant_lifetime:")
)
async def sub_do_grant_legacy(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    tg_id = int((callback.data or "").split(":")[3])
    await ctx.subscriptions.grant_lifetime(
        actor_telegram_user_id=callback.from_user.id,
        target_telegram_user_id=tg_id,
    )
    _, card_text = await ctx.users.build_user_card(telegram_user_id=tg_id)
    await callback.message.edit_text(
        "✅ Готово — выдан <b>бессрочный доступ</b>.\n\n" + card_text,
        reply_markup=kb.user_card(tg_id),
    )
    await callback.answer("Доступ выдан")


@router.callback_query(lambda c: c.data and c.data.startswith("sub:grant_preset:"))
async def sub_grant_preset_legacy(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    tg_id = int((callback.data or "").split(":")[3])
    text = "\n".join(
        [
            "♾️ <b>Выдать бессрочный доступ</b>",
            "",
            f"Пользователь: <code>{tg_id}</code>",
            "",
            "Подтвердить?",
        ]
    )
    await callback.message.edit_text(text, reply_markup=kb.grant_lifetime_confirm(tg_id))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("confirm:grant30:"))
async def confirm_grant30(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    parsed = _parse_confirm(callback.data or "")
    if not parsed or not _is_confirm_fresh(parsed[2]):
        await callback.answer("⏱ Подтверждение истекло. Повторите действие.", show_alert=True)
        await callback.message.edit_text("Подтверждение истекло.", reply_markup=kb.to_menu())
        return
    _, tg_id, _ = parsed
    await ctx.subscriptions.grant_lifetime(
        actor_telegram_user_id=callback.from_user.id,
        target_telegram_user_id=tg_id,
    )
    _, card_text = await ctx.users.build_user_card(telegram_user_id=tg_id)
    await callback.message.edit_text("✅ Готово.\n\n" + card_text, reply_markup=kb.user_card(tg_id))
    await callback.answer("Доступ выдан")


@router.callback_query(lambda c: c.data and c.data.startswith("sub:grant30:"))
async def sub_grant30(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    tg_id = int((callback.data or "").split(":")[2])
    confirm_id = _confirm_yes("grant30", tg_id)
    text = "\n".join(
        [
            "♾️ <b>Выдать бессрочный доступ</b>",
            "",
            f"Пользователь: <code>{tg_id}</code>",
            "",
            "Подтвердить?",
        ]
    )
    await callback.message.edit_text(
        text,
        reply_markup=kb.confirm(action="grant30", yes_data=confirm_id, no_data=f"user:open:{tg_id}"),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("sub:expire:"))
async def sub_expire(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    tg_id = int((callback.data or "").split(":")[2])
    confirm_id = _confirm_yes("expire", tg_id)
    text = "\n".join(
        [
            "⏳ <b>Отозвать доступ</b>",
            "",
            f"Пользователь: <code>{tg_id}</code>",
            "",
            "Подтвердить?",
        ]
    )
    await callback.message.edit_text(
        text,
        reply_markup=kb.confirm(action="expire", yes_data=confirm_id, no_data=f"user:open:{tg_id}"),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("confirm:expire:"))
async def confirm_expire(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    parsed = _parse_confirm(callback.data or "")
    if not parsed or not _is_confirm_fresh(parsed[2]):
        await callback.answer("⏱ Подтверждение истекло.", show_alert=True)
        return
    _, tg_id, _ = parsed
    await ctx.subscriptions.set_expired(actor_telegram_user_id=callback.from_user.id, target_telegram_user_id=tg_id)
    _, card_text = await ctx.users.build_user_card(telegram_user_id=tg_id)
    await callback.message.edit_text("✅ Доступ отозван.\n\n" + card_text, reply_markup=kb.user_card(tg_id))
    await callback.answer("Готово")


@router.callback_query(lambda c: c.data and c.data.startswith("sub:revoke:"))
async def sub_revoke(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    tg_id = int((callback.data or "").split(":")[2])
    confirm_id = _confirm_yes("revoke", tg_id)
    text = "\n".join(
        [
            "🔴 <b>Заблокировать доступ</b>",
            "",
            f"Пользователь: <code>{tg_id}</code>",
            "",
            "Подтвердить?",
        ]
    )
    await callback.message.edit_text(
        text,
        reply_markup=kb.confirm(action="revoke", yes_data=confirm_id, no_data=f"user:open:{tg_id}"),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("confirm:revoke:"))
async def confirm_revoke(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    parsed = _parse_confirm(callback.data or "")
    if not parsed or not _is_confirm_fresh(parsed[2]):
        await callback.answer("⏱ Подтверждение истекло.", show_alert=True)
        return
    _, tg_id, _ = parsed
    await ctx.subscriptions.revoke(actor_telegram_user_id=callback.from_user.id, target_telegram_user_id=tg_id)
    _, card_text = await ctx.users.build_user_card(telegram_user_id=tg_id)
    await callback.message.edit_text("✅ Доступ заблокирован.\n\n" + card_text, reply_markup=kb.user_card(tg_id))
    await callback.answer("Готово")
