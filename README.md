# 🍽 Telegram-бот рецептов питания

Telegram-бот для просмотра рецептов правильного питания с двумя UX-режимами.

## 🎯 Особенности

- **Два UX-режима** с разным пользовательским опытом
- **Фильтры** (только в режиме INLINE)
- **Пагинация** рецептов по 3 штуки
- **Telegraph** интеграция для красивого отображения рецептов
- **FSM** для корректного сохранения контекста пользователя
- **Модульная архитектура** для лёгкого масштабирования

## 📁 Структура проекта

```
├── main.py                 # Точка входа
├── config.py               # Конфигурация и константы
├── requirements.txt        # Зависимости
│
├── data/                   # Данные (JSON)
│   ├── recipes.json        # Рецепты
│   └── categories.json     # Категории по приёмам пищи
│
├── handlers/               # Обработчики сообщений
│   ├── start.py            # Команда /start
│   ├── common.py           # Общие функции
│   ├── inline_handlers.py  # Хендлеры для INLINE режима
│   └── reply_handlers.py   # Хендлеры для REPLY режима
│
├── keyboards/              # Клавиатуры
│   ├── inline.py           # Inline-кнопки
│   └── reply.py            # Reply-кнопки
│
├── services/               # Бизнес-логика
│   └── recipe_service.py   # Сервис работы с рецептами
│
├── states/                 # FSM состояния
│   └── user_states.py      # Состояния и контекст
│
└── utils/                  # Утилиты
    └── telegraph.py        # Telegraph интеграция
```

## 🔄 UX-режимы

### Режим 1: INLINE_WITH_FILTERS

- Inline-кнопки под сообщениями
- Фильтры (до 10 минут, на ходу, без готовки и т.д.)
- Рецепты открываются в Telegraph
- Сложный, но функциональный UX

### Режим 2: REPLY_SIMPLE

- Reply-клавиатура внизу экрана
- БЕЗ фильтров
- Рецепты показываются прямо в сообщении
- Простой и быстрый UX

## ⚙️ Установка

### 1. Клонирование

```bash
git clone <repo>
cd recipe-bot
```

### 2. Виртуальное окружение

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 3. Зависимости

```bash
pip install -r requirements.txt
```

### 4. Конфигурация

Отредактируйте `config.py`:

```python
# Токен бота (получить у @BotFather)
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Режим UX
UX_MODE = UXMode.INLINE_WITH_FILTERS  # или UXMode.REPLY_SIMPLE

# Опционально: токен Telegraph
TELEGRAPH_TOKEN = ""
```

Или используйте переменные окружения:

```bash
set BOT_TOKEN=your_token_here        # Windows
export BOT_TOKEN=your_token_here     # Linux/macOS
```

### 5. Запуск

```bash
python main.py
```

## 📊 Данные

### Добавление рецептов

Редактируйте `data/recipes.json`:

```json
{
  "id": "unique_id",
  "name": "Название блюда",
  "meal_type": "breakfast",  // breakfast, lunch, dinner
  "category_id": "eggs",     // ID категории
  "tags": ["quick", "sweet"], // Теги для фильтров
  "cooking_time": 15,
  "calories": 300,
  "proteins": 20,
  "fats": 15,
  "carbs": 25,
  "ingredients": [
    {"name": "Яйца", "amount": "2 шт", "grams": 120}
  ],
  "instructions": "Пошаговый рецепт...",
  "image_url": "https://..."
}
```

### Теги фильтров

- `quick` — до 10 минут
- `on_the_go` — на ходу
- `no_cooking` — без готовки
- `no_gluten_lactose` — без глютена и лактозы
- `sweet` — сладкие

### Добавление категорий

Редактируйте `data/categories.json`:

```json
{
  "breakfast": [
    {"id": "eggs", "name": "🥚 Яйца / омлет", "description": "..."}
  ],
  "lunch": [...],
  "dinner": [...]
}
```

## 🚀 Масштабирование

### Redis для FSM Storage

Замените в `main.py`:

```python
from aiogram.fsm.storage.redis import RedisStorage

storage = RedisStorage.from_url("redis://localhost:6379")
```

### База данных

Для большого количества рецептов замените JSON на SQLite/PostgreSQL:

1. Создайте модели в `models/`
2. Обновите `RecipeService` для работы с БД
3. Добавьте миграции

### Webhook вместо Polling

Для продакшена используйте webhook:

```python
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# В main.py
app = web.Application()
webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
webhook_handler.register(app, path="/webhook")
```

## 📝 Лицензия

MIT

## 👨‍💻 Разработка

Проект создан по ТЗ с чёткими требованиями:

- ❌ Без Telegram Mini App
- ❌ Без админки
- ✅ Только кнопки, пользователь ничего не пишет
- ✅ Два UX-режима с переключением
- ✅ Данные меняются вручную разработчиком
