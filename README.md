# AI-Аналитик отзывов — Sentiment Analysis (Проект 2)

Бот принимает артикул/ссылку на товар Wildberries, парсит последние 50 отзывов,
отправляет их в LLM (YandexGPT или OpenAI) с промптом «Выяви топ-3 проблемы и
топ-3 преимущества», строго валидирует JSON-ответ через **pydantic** и показывает
результат.

## Стек (строго по ТЗ)

| Библиотека               | Зачем                                             |
|--------------------------|---------------------------------------------------|
| aiogram v3.x             | Telegram Bot API                                  |
| httpx                    | асинхронный парсинг отзывов WB                    |
| yandex-cloud-ml-sdk (или openai) | вызов LLM (подключается лениво)         |
| pydantic                 | строгая валидация JSON от нейросети (поля `pros`, `cons`, …) |

## Команды

- `/analyze АРТИКУЛ` или `/analyze ССЫЛКА` — анализ последних 50 отзывов

## Запуск

```bash
pip install -r requirements.txt
export WB_BOT_TOKEN=123456:ABC...
export LLM_PROVIDER=mock      # mock | yandex | openai
python bot.py
```

Для реального LLM задайте ключи (см. `.env.example`):
- `LLM_PROVIDER=yandex` → `YANDEX_FOLDER_ID`, `YANDEX_API_KEY`
  (документация SDK: [yandex.cloud — Foundation Models SDK](https://yandex.cloud/ru/docs/foundation-models/sdk/));
- `LLM_PROVIDER=openai` → `OPENAI_API_KEY`.

Без ключей работает демо-режим `mock` (выдуманный анализ) — бот полностью
функционален и без платного LLM.

## Честное примечание об источнике отзывов (проверено 2026-08-05)

- В ТЗ указан эндпоинт `feedbacks1.wildberries.ru`. Реально отзывы без токена
  продавца берутся с `feedbacks1.wb.ru/feedbacks/v1/{root_id}` — его используют
  open-source боты, например
  [nickisnotgaara/wildberries-reviews-bot](https://github.com/nickisnotgaara/wildberries-reviews-bot).
- **Проверить этот эндпоинт с этого компьютера не удалось**: он закрыт
  антибот-защитой (пустой ответ/403). Поэтому парсер написан устойчивым к смене
  структуры JSON, а для стабильной работы есть `WB_DEMO_MODE=1`.
- `root_id` для отзывов берётся из карточки товара (`card.wb.ru`, см. Проект 1).
- Официальный API отзывов `feedbacks-api.wildberries.ru` требует токен продавца —
  по ТЗ не используется.
