"""Telegram-бот "AI-Аналитик отзывов" (aiogram v3).

Стек (строго по ТЗ): aiogram, httpx, yandex-cloud-ml-sdk (или openai), pydantic.

Запуск:  python bot.py   (задайте WB_BOT_TOKEN; для реального LLM — LLM_PROVIDER
и ключи, иначе работает демо-режим с mock-отзывами и mock-анализом).
"""
from __future__ import annotations

import asyncio
import html as _html
import json
import logging
import os
import re

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

import config
from llm import LLMProvider, get_provider
from reviews import fetch_reviews

# Логирование в консоль и в файл bot.log рядом с ботом
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(config.BASE_DIR, "bot.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

router = Router()
provider: LLMProvider = get_provider()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я <b>AI-Аналитик отзывов Wildberries</b>.\n\n"
        "/analyze <b>АРТИКУЛ</b> или <b>ССЫЛКА</b> — проанализирую последние "
        f"{config.MAX_REVIEWS} отзывов и выявлю топ-3 проблемы и топ-3 преимущества "
        "товара.\n\n"
        f"Текущий LLM-провайдер: <b>{config.LLM_PROVIDER}</b>"
    )


@router.message(Command("analyze"))
async def cmd_analyze(message: Message) -> None:
    articul = _extract_articul(message.text or "")
    if articul is None:
        await message.answer("Формат: /analyze АРТИКУЛ или ССЫЛКА на товар")
        return

    status = await message.answer("🔍 Парсим отзывы Wildberries…")
    try:
        reviews = await fetch_reviews(articul)
    except Exception as exc:
        await status.edit_text(f"⚠️ Не удалось получить отзывы: {exc}")
        return

    if not reviews:
        await status.edit_text(
            "Отзывы не найдены. Попробуйте другой артикул или включите демо-режим "
            "(WB_DEMO_MODE=1)."
        )
        return

    await status.edit_text(
        f"🧠 Отправляем {len(reviews)} отзывов в LLM "
        f"(провайдер: <b>{config.LLM_PROVIDER}</b>)…"
    )
    try:
        result = await provider.analyze(reviews)
    except Exception as exc:
        logger.exception("Ошибка LLM")
        await status.edit_text(f"⚠️ Ошибка LLM: {exc}")
        return

    # ВАЖНО: ответ LLM — непроверенный текст, экранируем HTML (как в Проекте 1),
    # иначе символы < и & сломают разбор сущностей Telegram
    def esc(value: str) -> str:
        return _html.escape(value, quote=False)

    answer = (
        f"📊 <b>Анализ товара {articul}</b> (по {len(reviews)} отзывам)\n\n"
        "👍 <b>Топ-3 преимущества:</b>\n"
        + "\n".join(f"• {esc(p)}" for p in result.pros)
        + "\n\n👎 <b>Топ-3 проблемы:</b>\n"
        + "\n".join(f"• {esc(c)}" for c in result.cons)
        + f"\n\nТональность: <b>{esc(result.sentiment)}</b>\n"
        + f"Средняя оценка: <b>{result.average_rating:.1f}/5</b>"
    )
    await status.edit_text(answer)

    raw = json.dumps(result.model_dump(), ensure_ascii=False, indent=2)
    await message.answer(f"<b>JSON (валидирован pydantic):</b>\n<pre>{esc(raw)}</pre>")


def _extract_articul(text: str) -> int | None:
    """Артикул из текста: число из 4+ цифр, выдерживает ссылки вида nm=12345678."""
    match = re.search(r"(?:\bnm=)?(\d{4,})", text)
    return int(match.group(1)) if match else None


def _check_provider_dependencies() -> None:
    """Fail fast: проверяем установку библиотеки выбранного LLM-провайдера.

    Раньше ошибка всплывала только при первом /analyze; теперь бот не стартует
    с нерабочей конфигурацией.
    """
    if config.LLM_PROVIDER == "yandex":
        try:
            import yandex_cloud_ml_sdk  # noqa: F401
        except ImportError:
            raise SystemExit(
                "LLM_PROVIDER=yandex, но не установлена библиотека yandex-cloud-ml-sdk.\n"
                "Установите: pip install yandex-cloud-ml-sdk"
            )
        if not config.YANDEX_FOLDER_ID or not config.YANDEX_API_KEY:
            raise SystemExit(
                "LLM_PROVIDER=yandex, но не заданы YANDEX_FOLDER_ID / YANDEX_API_KEY"
            )
    elif config.LLM_PROVIDER == "openai":
        try:
            import openai  # noqa: F401
        except ImportError:
            raise SystemExit(
                "LLM_PROVIDER=openai, но не установлена библиотека openai.\n"
                "Установите: pip install openai"
            )
        if not config.OPENAI_API_KEY:
            raise SystemExit("LLM_PROVIDER=openai, но не задан OPENAI_API_KEY")
    elif config.LLM_PROVIDER != "mock":
        raise SystemExit(
            f"Неизвестный LLM_PROVIDER: {config.LLM_PROVIDER!r} "
            "(допустимо: mock | yandex | openai)"
        )


async def main() -> None:
    _check_provider_dependencies()
    if not config.BOT_TOKEN:
        raise SystemExit(
            "Не задан WB_BOT_TOKEN. Скопируйте .env.example и задайте токен."
        )
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    logger.info("Бот запущен. LLM-провайдер: %s", config.LLM_PROVIDER)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
