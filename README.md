# AI Review Analyst

> **Prototype / supporting project.**
>
> Это ранний прототип, который больше не является отдельным представителем портфолио. Идея анализа отзывов была позже переработана и встроена в [Smart Shopper](https://github.com/d3c0r1x/smart-shopper).
>
> Проект оставлен публичным как история развития конкретной функции, а не как основной продукт.

## Что это за проект

Telegram-бот получает товар Wildberries и набор отзывов, после чего LLM выделяет повторяющиеся преимущества и проблемы и возвращает строго структурированный результат.

Главная инженерная задача здесь — не сам prompt, а контроль формата ответа модели.

```
reviews
  ↓
LLM
  ↓
structured JSON
  ↓
Pydantic validation
  ↓
retry/fallback
  ↓
Telegram result
```

## Что демонстрирует

- вызов LLM через HTTP;
- structured output;
- Pydantic validation;
- retry при невалидном ответе;
- Telegram interface;
- deterministic tests без live model.

## Структура

```
bot.py          # Telegram interface
reviews.py      # review fetching / processing
llm.py          # LLM requests
models.py       # Pydantic result schemas
config.py       # environment
middlewares.py  # Telegram middleware
tests/          # smoke tests
```

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

Windows:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
start.bat
```

## Пример результата

Для товара бот должен вернуть структурированный набор вроде:

```json
{
  "advantages": ["..."],
  "problems": ["..."],
  "summary": "..."
}
```

Конкретная схема определяется Pydantic-моделями в `models.py`.

## Тесты

```bash
pytest -q
```

Тесты не требуют реального LLM, что делает проверку детерминированной.

## Почему проект архивный

Это был полезный технический этап:

```
prototype
   ↓
structured output
   ↓
validation
   ↓
integration into larger product
```

Сейчас самостоятельной ценности у него меньше, чем у Smart Shopper.

## Ограничения

- качество зависит от модели;
- публичные review endpoint'ы могут блокировать автоматические запросы;
- проект рассчитан на конкретный узкий сценарий.

## AI-assisted development

AI использовался для черновой реализации и рутинных модулей. Этот репозиторий сознательно оставлен как прозрачный прототип, а не выдан за самостоятельный флагман.

## Лицензия

MIT.
