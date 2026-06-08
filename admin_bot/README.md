# PP BOT — admin_bot

Отдельный Telegram админ-бот для администрирования/мониторинга экосистемы PP BOT.

## Возможности (v1)
- **Пользователи**: поиск по `telegram_user_id`, `username`, `email` (по данным `payment_bot`).
- **Доступ**: выдать бессрочный / отозвать / заблокировать (через `payment_bot` PostgreSQL).
- **Платежи**: списки по статусам и карточка платежа, raw JSON доступен только владельцу/администратору.
- **Логи/события**: единый журнал на базе `pb_events` в PostgreSQL.
- **Ошибки**: красивые алерты в Telegram, просмотр контекста и “логи до ошибки”.
- **Статистика**: базовые метрики по периодам.
- **Health**: ручной health-check + автоотчёт каждые 12 часов.
- **Роли**: владелец / администратор / поддержка / наблюдатель.
- **Тест-режимы**: через `adm_user_overrides` (без порчи прод-данных).

## Требования
- Python 3.11+ (рекомендуется)
- PostgreSQL с уже развёрнутым `payment_bot` (таблицы `pb_*`).

## Быстрый запуск (polling)
1) Создайте виртуальное окружение и установите зависимости:

```bash
python -m venv .venv
.\.venv\Scripts\python -m pip install -r admin_bot\requirements.txt
```

2) Создайте файл `admin_bot/.env` на основе `.env.example` и заполните:
- `BOT_TOKEN`
- `OWNER_TELEGRAM_ID`
- `POSTGRES_DSN`

3) Засейдите владельца:

```bash
.\.venv\Scripts\python admin_bot\scripts\seed_owner.py
```

4) Запустите админ-бот:

```bash
.\.venv\Scripts\python admin_bot\main.py
```

## Миграции
Админ-бот использует Alembic (скрипты в `admin_bot/db/migrations`).

Пример:

```bash
set POSTGRES_DSN=postgresql://...
.\.venv\Scripts\python -m alembic -c admin_bot\alembic.ini upgrade head
```

## Production (systemd)
Примеры unit/timer будут добавлены в `admin_bot/deploy/systemd/`.

## Подключение к другим ботам
- **source-of-truth** по подпискам/платежам: PostgreSQL `payment_bot` (`pb_users`, `pb_subscriptions`, `pb_payments`).
- `main_bot` SQLite и `support_bot` SQLite используются **только как дополнительные источники истории**, записи туда admin-бот не делает без отдельного adapter-action.
- **единая таблица событий**: `pb_events` (расширяется/индексируется миграциями `admin_bot`).

