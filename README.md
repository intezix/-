# Payment Bot (Telegram + YooKassa)

Отдельный production-ready бот оплаты подписки (590 ₽ / 30 дней), не смешанный с основным ботом.

## Что реализовано

- Webhook-first архитектура:
  - Telegram webhook endpoint
  - YooKassa webhook endpoint (основной канал синхронизации платежей)
  - `Проверить оплату` как fallback UX
- FSM для email перед оплатой
- Идемпотентность:
  - повторное создание платежа ограничено reuse pending
  - обработка `succeeded` только один раз через `processed_at`
  - `idempotence_key` в YooKassa create payment
- Подписка:
  - активация на 30 дней
  - статус подписки
  - отключение автопродления
- Admin email notify:
  - отправка только после `succeeded` + активации подписки + наличия email
  - outbox/retry-safe механизм (`notification_outbox`)
  - защита от дублей по `dedupe_key`
- Recurring:
  - отдельная история попыток в `recurring_attempts`
  - отдельный renew script
- Миграции через Alembic

## Структура

```
payment_bot/
  main.py
  webhook_app.py
  config.py
  app_context.py
  requirements.txt
  .env.example
  handlers/
  services/
  keyboards/
  states/
  db/
  migrations/
  scripts/
  tests/
```

## Запуск локально

1. Создайте venv и установите зависимости:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Скопируйте `.env.example` -> `.env` и заполните значения.

3. Примените миграции:

```bash
alembic -c alembic.ini upgrade head
```

4. Запустите бота:

```bash
python -m payment_bot.main
```

## Интеграция в уже существующую БД проекта

Бот можно подключать к вашей текущей PostgreSQL базе безопасно: все таблицы payment-бота изолированы префиксом `pb_`:
- `pb_users`
- `pb_payments`
- `pb_subscriptions`
- `pb_events`
- `pb_notification_outbox`
- `pb_recurring_attempts`

Поэтому конфликта с существующими `users/payments/subscriptions` таблицами проекта не будет.

## Docker для безопасного теста

В `payment_bot/docker-compose.yml` есть отдельный тестовый Postgres и сервис бота.

Запуск:

```bash
cd payment_bot
docker compose up -d --build payment_db
docker compose run --rm payment_bot alembic -c payment_bot/alembic.ini upgrade head
docker compose up -d payment_bot
```

Проверка:

```bash
curl http://127.0.0.1:8080/healthz
```

Остановка:

```bash
docker compose down
```

## Webhook endpoints

- Telegram: `POST {WEBHOOK_BASE_URL}{TELEGRAM_WEBHOOK_PATH}`
- YooKassa: `POST {WEBHOOK_BASE_URL}{YOOKASSA_WEBHOOK_PATH}`
- Health: `GET /healthz`

## Nginx reverse proxy (пример)

```nginx
server {
    listen 443 ssl http2;
    server_name pay.example.com;

    # ssl_certificate /etc/letsencrypt/live/pay.example.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/pay.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

YooKassa webhook в кабинете нужно направить на:
`https://pay.example.com/webhook/yookassa`

## systemd (bot service)

`/etc/systemd/system/payment-bot.service`

```ini
[Unit]
Description=Telegram payment bot (webhook-first)
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/payment_bot
EnvironmentFile=/opt/payment_bot/.env
ExecStart=/opt/payment_bot/.venv/bin/python -m payment_bot.main
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

## systemd (renew job + timer)

`/etc/systemd/system/payment-bot-renew.service`

```ini
[Unit]
Description=Payment bot recurring renew job
After=network.target

[Service]
Type=oneshot
User=www-data
WorkingDirectory=/opt/payment_bot
EnvironmentFile=/opt/payment_bot/.env
ExecStart=/opt/payment_bot/.venv/bin/python -m payment_bot.scripts.renew_subscriptions
```

`/etc/systemd/system/payment-bot-renew.timer`

```ini
[Unit]
Description=Run payment renew job every 15 minutes

[Timer]
OnCalendar=*:0/15
Persistent=true
Unit=payment-bot-renew.service

[Install]
WantedBy=timers.target
```

## Ручные скрипты

- Проверка кандидатов на продление:
  - `python -m payment_bot.scripts.check_subscriptions`
- Принудительная обработка outbox:
  - `python -m payment_bot.scripts.process_outbox`

## Как протестировать (ключевые кейсы)

1. Успешная оплата:
   - `/start` -> `Оплатить подписку`
   - ввести email
   - оплатить в YooKassa
   - дождаться webhook или нажать `Проверить оплату`
   - убедиться, что подписка активна
   - проверить, что сообщение ушло в admin chat
2. Идемпотентность:
   - повторно нажать `Проверить оплату` несколько раз
   - убедиться, что подписка не продлевается повторно за тот же payment
   - убедиться, что в admin chat нет дубля по payment_id
3. Pending/canceled:
   - проверить, что до `succeeded` уведомление в admin chat не уходит
4. Без email:
   - до ввода email платеж не создается
5. Автопродление:
   - запустить renew job
   - проверить запись в `recurring_attempts`
   - при успехе проверить отдельное admin-уведомление

## Что менять под прод

- `WEBHOOK_BASE_URL`, SSL и DNS
- ограничения доступа к endpoint-ам на уровне reverse proxy / firewall
- секреты (`BOT_TOKEN`, `YOOKASSA_SECRET_KEY`) только в env/secrets manager
- уровень логирования (`LOG_LEVEL`)
- интервалы retry/outbox и таймер renew job
- мониторинг:
  - ошибки webhook обработки
  - количество retry в `notification_outbox`
  - долю failed в `recurring_attempts`

