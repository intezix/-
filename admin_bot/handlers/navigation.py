from __future__ import annotations

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from admin_bot.app_context import AppContext
from admin_bot.keyboards.inline import InlineKeyboards
from admin_bot.states.admin import BroadcastStates


router = Router()
kb = InlineKeyboards()


async def _edit(callback: CallbackQuery, text: str, **kwargs) -> None:
    try:
        await callback.message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


def _menu_text() -> str:
    return "\n".join(["⚙️ <b>Админ-бот PP BOT</b>", "", "Выберите раздел."])


@router.callback_query(lambda c: c.data and c.data.startswith("nav:"))
async def nav(callback: CallbackQuery, ctx: AppContext, state: FSMContext) -> None:
    # Сбрасываем любой активный FSM-флоу при любой навигации
    await state.clear()

    data = callback.data or ""
    target = data.split(":", 1)[1] if ":" in data else ""

    if target == "menu":
        await _edit(callback, _menu_text(), reply_markup=kb.menu())
        await callback.answer()
        return

    if target == "users":
        await ctx.roles.require_access(callback.from_user.id)
        await _edit(callback, "👤 <b>Пользователи</b>\n\nЗагрузка…")
        users, total = await ctx.users.list_page(page=0)
        total_pages = max(1, (total + 14) // 15)
        text = "\n".join([
            f"👤 <b>Пользователи</b>  <i>({total} всего, стр. 1/{total_pages})</i>",
            "",
            "Нажмите на пользователя для просмотра карточки.",
            "Или введите в чат: <b>ID</b>, <b>@username</b> или <b>email</b> для поиска.",
        ])
        await _edit(callback, text, reply_markup=kb.users_list(users, page=0, total=total))
        await callback.answer()
        return

    if target == "payments":
        text = "\n".join(["💳 <b>Платежи</b>", "", "Выберите фильтр."])
        await _edit(callback, text, reply_markup=kb.payments_filters())
        await callback.answer()
        return

    if target == "stats":
        text = "\n".join(["📊 <b>Статистика</b>", "", "Выберите период."])
        await _edit(callback, text, reply_markup=kb.stats_periods())
        await callback.answer()
        return

    if target == "health":
        text = "\n".join(["✅ <b>Состояние системы</b>", "", "Сформировать отчёт по кнопке."])
        await _edit(callback, text, reply_markup=kb.health_actions())
        await callback.answer()
        return

    if target == "errors":
        text = "\n".join(["🚨 <b>Ошибки</b>", "", "Показать последние ошибки по кнопке."])
        await _edit(callback, text, reply_markup=kb.errors_actions())
        await callback.answer()
        return

    if target == "roles":
        text = "\n".join(["⚙️ <b>Администраторы</b>", "", "Открыть список администраторов."])
        await _edit(callback, text, reply_markup=kb.roles_entry())
        await callback.answer()
        return

    if target == "test_modes":
        text = "\n".join(["🧪 <b>Тест-режимы</b>", "", "Выберите режим для себя."])
        await _edit(callback, text, reply_markup=kb.test_modes_self())
        await callback.answer()
        return

    if target == "system":
        await ctx.roles.require_access(callback.from_user.id)
        if not ctx.system.is_configured():
            await callback.answer("DOCKER_PROJECT_NAME не настроен в .env", show_alert=True)
            return
        await _edit(callback, "🖥️ <b>Система</b>\n\nЗагрузка статусов…")
        statuses = await ctx.system.get_status()
        lines = ["🖥️ <b>Система — статус контейнеров</b>", ""]
        for s in statuses:
            lines.append(f"{s['icon']} {s['label']}: <code>{s['state']}</code>")
        await _edit(callback, "\n".join(lines), reply_markup=kb.system_overview(statuses))
        await callback.answer()
        return

    if target == "broadcast":
        await ctx.roles.require_access(callback.from_user.id)
        if not ctx.broadcast.is_configured():
            await callback.answer("PAYMENT_BOT_TOKEN не настроен в .env", show_alert=True)
            return
        await state.set_state(BroadcastStates.waiting_for_text)
        text = "\n".join(
            [
                "📢 <b>Рассылка</b>",
                "",
                "Введите текст сообщения (поддерживается HTML).",
                "Его получат все пользователи бота.",
                "",
                "<i>Нажмите «Отмена» чтобы выйти.</i>",
            ]
        )
        await _edit(callback, text, reply_markup=kb.cancel_fsm_kb("nav:menu"))
        await callback.answer()
        return

    await callback.answer("Раздел ещё в разработке", show_alert=False)
