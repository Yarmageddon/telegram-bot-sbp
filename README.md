# Telegram Bot с подписками через СБП - aiogram 3.x

Современный Telegram бот с поддержкой подписок и оплатой через СБП.

##  Возможности

- ✅ Оформление подписок с оплатой через СБП
- ✅ Проверка статуса подписки
- ✅ Современный дизайн интерфейса
- ✅ Админ-панель
- ✅ SQLite база данных
- ✅ aiogram 3.x (современная версия)

## 📋 Требования

- Python 3.12+
- Без Docker
- Без PostgreSQL
- Без Redis

##  Установка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка конфигурации

Отредактируйте `.env`:

```env
BOT_TOKEN=your_bot_token_here
PAYMENT_TOKEN=your_payment_provider_token_here
ADMIN_IDS=your_telegram_id
```

### 3. Запуск бота

```bash
python bot.py
```

## 📱 Использование

### Команды бота

- `/start` - Главное меню
- `/status` - Проверить статус подписки
- `/subscribe` - Оформить подписку
- `/help` - Помощь
- `/admin` - Панель администратора (только для админов)
- `/stats` - Статистика (только для админов)

### Тарифные планы

- **Месячная подписка** - 990 ₽ (30 дней)
- **Годовая подписка** - 9 500 ₽ (365 дней)

## 🔧 Настройка оплаты СБП

### 1. Получение токена провайдера

1. Зарегистрироваться у платежного провайдера (Tinkoff, YooKassa, Сбер)
2. Получить токен провайдера
3. Добавить провайдера через @BotFather
4. Указать токен в `.env` как `PAYMENT_TOKEN`

### 2. Интеграция с платежным провайдером

В файле `bot.py` найдите функцию `process_plan_selection` и замените mock URL на реальный API вызов:

```python
# Пример для Tinkoff:
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "https://securepay.tinkoff.ru/v2/Init",
        json={
            "TerminalKey": "YOUR_TERMINAL_KEY",
            "Amount": amount,
            "OrderId": transaction_id,
            "Description": plan_name,
            "NotificationURL": f"{settings.WEBHOOK_HOST}/webhook/payment",
            "SuccessURL": f"https://t.me/{bot.username}",
        }
    )
    data = response.json()
    payment_url = data.get("PaymentURL")
```

##  База данных

Бот использует SQLite - файл `bot.db` создается автоматически при первом запуске.

### Структура БД

- **users** - пользователи
- **subscriptions** - подписки
- **payments** - платежи

### Резервное копирование

```bash
cp bot.db bot_backup.db
```

## ⚠️ ВАЖНО: Безопасность

**Вы опубликовали токены в открытом виде!**

**Немедленно выполните:**
1. Откройте @BotFather в Telegram
2. Отправьте `/mybots` → выберите бота → API Token → Revoke current token
3. Получите новый токен
4. Обновите `.env`

## 📝 Структура проекта

```
telegram_bot_v3/
├── bot.py              # Основной файл бота
├── models.py           # Модели БД
├── database.py         # Работа с БД
├── config.py           # Конфигурация
── keyboards.py        # Клавиатуры
── requirements.txt    # Зависимости
├── .env               # Конфигурация
└── README.md          # Документация
```

## 🐛 Типовые ошибки

### 1. Unauthorized (401)

**Причина:** Неверный BOT_TOKEN

**Решение:** Проверьте токен в `.env`

### 2. Payment provider token is invalid

**Причина:** Неверный PAYMENT_TOKEN

**Решение:** Добавьте провайдера через @BotFather

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи
2. Проверьте `.env` конфигурацию
3. Проверьте токены

## 📄 Лицензия

MIT
