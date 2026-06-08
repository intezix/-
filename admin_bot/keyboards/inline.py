from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


class InlineKeyboards:
    def menu(self) -> InlineKeyboardMarkup:
        rows = [
            [_btn("👤 Пользователи", "nav:users")],
            [_btn("💳 Платежи", "nav:payments"), _btn("📊 Статистика", "nav:stats")],
            [_btn("🚨 Ошибки", "nav:errors"), _btn("✅ Состояние", "nav:health")],
            [_btn("⚙️ Администраторы", "nav:roles"), _btn("🧪 Тест-режимы", "nav:test_modes")],
            [_btn("🖥️ Система", "nav:system"), _btn("📢 Рассылка", "nav:broadcast")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def to_menu(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[[_btn("📋 В меню", "nav:menu")]])

    def back_and_menu(self, back_data: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[[ _btn("🔙 Назад", back_data), _btn("📋 В меню", "nav:menu") ]])

    def users_list(
        self,
        users: list[dict],
        *,
        page: int,
        total: int,
        per_page: int = 15,
    ) -> InlineKeyboardMarkup:
        """Paginated list of users: each row is one user button, then prev/next nav."""
        rows: list[list[InlineKeyboardButton]] = []
        for u in users:
            tg_id = int(u["telegram_user_id"])
            uname = str(u.get("username") or "")
            label = f"👤 {tg_id}" + (f"  @{uname}" if uname else "")
            if len(label) > 48:
                label = label[:48]
            rows.append([_btn(label, f"user:open:{tg_id}")])

        nav_row: list[InlineKeyboardButton] = []
        if page > 0:
            nav_row.append(_btn("◀ Назад", f"users:list:{page - 1}"))
        if (page + 1) * per_page < total:
            nav_row.append(_btn("Вперёд ▶", f"users:list:{page + 1}"))
        if nav_row:
            rows.append(nav_row)
        rows.append([_btn("📋 В меню", "nav:menu")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def user_card(self, telegram_user_id: int) -> InlineKeyboardMarkup:
        rows = [
            [_btn("📄 Логи пользователя", f"user:logs:{telegram_user_id}")],
            [_btn("💳 Платежи", f"user:payments:{telegram_user_id}"), _btn("🧪 Тест-режимы", f"user:test:{telegram_user_id}")],
            [_btn("♾️ Выдать бессрочный доступ", f"sub:grant_menu:{telegram_user_id}")],
            [_btn("⏳ Отозвать доступ", f"sub:expire:{telegram_user_id}"), _btn("🔴 Заблокировать", f"sub:revoke:{telegram_user_id}")],
            [_btn("🔙 Назад", "nav:users"), _btn("📋 В меню", "nav:menu")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def confirm(self, *, action: str, yes_data: str, no_data: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [_btn("✅ Подтвердить", yes_data), _btn("✖️ Отмена", no_data)],
                [_btn("📋 В меню", "nav:menu")],
            ]
        )

    def payments_filters(self) -> InlineKeyboardMarkup:
        rows = [
            [_btn("✅ Успешные", "pay:list:succeeded:24h"), _btn("🕒 В обработке", "pay:list:pending:24h")],
            [_btn("❌ Ошибка/отмена", "pay:list:canceled:24h"), _btn("📜 Старые автоплатежи", "pay:list:recurring:7d")],
            [_btn("24 часа", "nav:payments"), _btn("7 дней", "pay:period:7d")],
            [_btn("🔙 Назад", "nav:menu")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def payment_list_keyboard(self, payments: list[dict]) -> InlineKeyboardMarkup:
        """List view: per-payment open buttons + filter navigation."""
        _STATUS_ICON = {
            "succeeded": "✅",
            "pending": "🕒",
            "canceled": "❌",
            "failed": "❌",
        }
        rows: list[list[InlineKeyboardButton]] = []
        for p in payments[:8]:
            pid = str(p.get("payment_id") or "")
            if not pid:
                continue
            amount = str(p.get("amount") or "")
            status = str(p.get("status") or "")
            dt = p.get("created_at")
            date_str = dt.astimezone().strftime("%m-%d %H:%M") if dt else "—"
            icon = _STATUS_ICON.get(status, "💳")
            label = f"{icon} {date_str} · {amount}₽"
            if len(label) > 48:
                label = label[:48]
            rows.append([_btn(label, f"pay:open:{pid}")])
        rows += [
            [_btn("✅ Успешные", "pay:list:succeeded:24h"), _btn("🕒 В обработке", "pay:list:pending:24h")],
            [_btn("❌ Ошибка/отмена", "pay:list:canceled:24h")],
            [_btn("📋 В меню", "nav:menu")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def stats_periods(self) -> InlineKeyboardMarkup:
        rows = [
            [_btn("Сегодня", "stats:period:today"), _btn("7 дней", "stats:period:7d")],
            [_btn("30 дней", "stats:period:30d"), _btn("За всё время", "stats:period:all")],
            [_btn("🔙 Назад", "nav:menu")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def health_actions(self) -> InlineKeyboardMarkup:
        rows = [
            [_btn("📍 Сформировать отчёт", "health:show")],
            [_btn("🔙 Назад", "nav:menu")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def errors_actions(self) -> InlineKeyboardMarkup:
        rows = [
            [_btn("📋 Показать последние", "errors:list")],
            [_btn("🔙 Назад", "nav:menu")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def roles_entry(self) -> InlineKeyboardMarkup:
        rows = [
            [_btn("📋 Список администраторов", "roles:list")],
            [_btn("➕ Добавить администратора", "roles:add")],
            [_btn("🔙 Назад", "nav:menu")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def grant_lifetime_confirm(self, telegram_user_id: int) -> InlineKeyboardMarkup:
        tg = telegram_user_id
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [_btn("✅ Выдать бессрочно", f"sub:do_grant_lifetime:{tg}"), _btn("✖️ Отмена", f"user:open:{tg}")],
            ]
        )

    def cancel_fsm_kb(self, back_data: str) -> InlineKeyboardMarkup:
        """Клавиатура с единственной кнопкой «Отмена» для FSM-шагов."""
        return InlineKeyboardMarkup(inline_keyboard=[[_btn("✖️ Отмена", back_data)]])

    def role_picker_new_admin(self, target_tg_id: int) -> InlineKeyboardMarkup:
        """Выбор роли при добавлении нового администратора."""
        tg = target_tg_id
        rows = [
            [_btn("👑 Владелец", f"roles:newadmin_set:{tg}:owner"), _btn("🛠 Администратор", f"roles:newadmin_set:{tg}:admin")],
            [_btn("🧑‍💻 Поддержка", f"roles:newadmin_set:{tg}:support"), _btn("👁 Наблюдатель", f"roles:newadmin_set:{tg}:viewer")],
            [_btn("✖️ Отмена", "nav:roles")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def grant_confirm_kb(self, days: int, telegram_user_id: int) -> InlineKeyboardMarkup:
        del days
        return self.grant_lifetime_confirm(telegram_user_id)

    # ── System panel ─────────────────────────────────────────────────────────

    def system_overview(self, statuses: list[dict]) -> InlineKeyboardMarkup:
        """Главная страница System-панели: список ботов + обновить."""
        from admin_bot.services.system_service import MANAGED_SERVICES
        rows: list[list[InlineKeyboardButton]] = []
        for svc in MANAGED_SERVICES:
            info = next((s for s in statuses if s["service"] == svc), None)
            icon = info["icon"] if info else "❓"
            label = MANAGED_SERVICES[svc]
            rows.append([_btn(f"{icon} {label}", f"sys:bot:{svc}")])
        rows.append([_btn("🔄 Обновить статусы", "sys:overview")])
        rows.append([_btn("🔙 В меню", "nav:menu")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def bot_detail(self, service: str) -> InlineKeyboardMarkup:
        """Детальная карточка бота: перезапуск, логи, назад."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [_btn("🔄 Перезапустить", f"sys:restart:{service}")],
                [_btn("📋 Логи (50 строк)", f"sys:logs:{service}")],
                [_btn("🔙 Назад", "sys:overview"), _btn("📋 В меню", "nav:menu")],
            ]
        )

    def restart_confirm(self, service: str) -> InlineKeyboardMarkup:
        """Подтверждение перезапуска контейнера."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [_btn("✅ Да, перезапустить", f"sys:do_restart:{service}"), _btn("✖️ Нет", f"sys:bot:{service}")],
            ]
        )

    # ── Broadcast ─────────────────────────────────────────────────────────────

    def broadcast_confirm(self) -> InlineKeyboardMarkup:
        """Подтверждение рассылки после предпросмотра."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [_btn("✅ Отправить всем", "broadcast:confirm"), _btn("✖️ Отмена", "nav:menu")],
                [_btn("✏️ Изменить текст", "broadcast:edit")],
            ]
        )

    def test_modes_self(self) -> InlineKeyboardMarkup:
        rows = [
            [_btn("🚫 Без подписки", "tm:self:set:no_sub:2"), _btn("✅ Активная", "tm:self:set:active:2")],
            [_btn("⏳ Истёкшая", "tm:self:set:expired:2"), _btn("♾️ Бессрочная", "tm:self:set:canceled:2")],
            [_btn("🕒 Pending payment", "tm:self:set:pending:1"), _btn("❌ Failed payment", "tm:self:set:failed:1")],
            [_btn("🧹 Снять тест-режим", "tm:self:clear")],
            [_btn("🔙 Назад", "nav:menu")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def test_modes_user(self, telegram_user_id: int) -> InlineKeyboardMarkup:
        rows = [
            [_btn("🚫 Без подписки", f"tm:user:set:{telegram_user_id}:no_sub:2"), _btn("✅ Активная", f"tm:user:set:{telegram_user_id}:active:2")],
            [_btn("⏳ Истёкшая", f"tm:user:set:{telegram_user_id}:expired:2"), _btn("♾️ Бессрочная", f"tm:user:set:{telegram_user_id}:canceled:2")],
            [_btn("🕒 Pending payment", f"tm:user:set:{telegram_user_id}:pending:1"), _btn("❌ Failed payment", f"tm:user:set:{telegram_user_id}:failed:1")],
            [_btn("🧹 Снять тест-режим", f"tm:user:clear:{telegram_user_id}")],
            [_btn("🔙 Назад", f"user:open:{telegram_user_id}"), _btn("📋 В меню", "nav:menu")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def roles_list(self, items: list[tuple[int, bool, bool, str]]) -> InlineKeyboardMarkup:
        """
        items: [(telegram_user_id, is_active, notify_enabled, role_code)]
        """
        rows = []
        for tg_id, is_active, notify_enabled, role_code in items[:12]:
            active = "✅" if is_active else "⛔️"
            bell = "🔔" if notify_enabled else "🔕"
            rows.append([_btn(f"{active} {bell} {tg_id}", f"role:open:{tg_id}")])
        rows.append([_btn("🔙 Назад", "nav:menu")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def role_card(self, telegram_user_id: int, *, is_active: bool, notify_enabled: bool, role_code: str) -> InlineKeyboardMarkup:
        active_txt = "Отключить доступ" if is_active else "Включить доступ"
        notify_txt = "Уведомления: выкл" if notify_enabled else "Уведомления: вкл"
        rows = [
            [_btn("👑 owner", f"role:set:{telegram_user_id}:owner"), _btn("🛠 admin", f"role:set:{telegram_user_id}:admin")],
            [_btn("🧑‍💻 support", f"role:set:{telegram_user_id}:support"), _btn("👁 viewer", f"role:set:{telegram_user_id}:viewer")],
            [_btn(f"🚦 {active_txt}", f"role:toggle_active:{telegram_user_id}")],
            [_btn(f"🔔 {notify_txt}", f"role:toggle_notify:{telegram_user_id}")],
            [_btn("🔙 Назад", "roles:list"), _btn("📋 В меню", "nav:menu")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def payment_card(self, payment_id: str, telegram_user_id: int, *, allow_raw: bool) -> InlineKeyboardMarkup:
        rows = [
            [_btn("👤 Открыть пользователя", f"user:open:{telegram_user_id}")],
        ]
        if allow_raw:
            rows.append([_btn("🧾 Raw JSON", f"pay:raw:{payment_id}")])
        rows.append([_btn("🔙 Назад", "nav:payments"), _btn("📋 В меню", "nav:menu")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def logs_filters(self, telegram_user_id: int) -> InlineKeyboardMarkup:
        rows = [
            [_btn("⚠️ Ошибки", f"log:errors:{telegram_user_id}"), _btn("💳 Платежи", f"log:payments:{telegram_user_id}")],
            [_btn("🔘 Кнопки", f"log:buttons:{telegram_user_id}"), _btn("Показать больше", f"log:more:{telegram_user_id}")],
            [_btn("🔙 Назад", f"user:open:{telegram_user_id}"), _btn("📋 В меню", "nav:menu")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def error_actions(self, *, event_id: int, telegram_user_id: int | None) -> InlineKeyboardMarkup:
        rows = []
        if telegram_user_id:
            rows.append([_btn("👤 Открыть пользователя", f"user:open:{telegram_user_id}")])
            rows.append([_btn("📄 Логи до ошибки", f"err:logs:{event_id}:{telegram_user_id}")])
        rows.append([_btn("✅ Пометить решённой", f"err:resolve:{event_id}")])
        rows.append([_btn("🔙 Назад", "nav:errors"), _btn("📋 В меню", "nav:menu")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

