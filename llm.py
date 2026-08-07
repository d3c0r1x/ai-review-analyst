"""Провайдеры LLM: YandexGPT (yandex-cloud-ml-sdk), OpenAI или Mock (демо).

По ТЗ используются: yandex-cloud-ml-sdk (или openai) + pydantic.
Реальный провайдер подключается лениво (import внутри метода), поэтому бот
работает и в демо-режиме без установленных LLM-библиотек и ключей.
"""
from __future__ import annotations

import asyncio
import json
import re
from abc import ABC, abstractmethod

from config import (
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    YANDEX_API_KEY,
    YANDEX_FOLDER_ID,
    YANDEX_MODEL,
)
from models import SYSTEM_PROMPT, AnalysisResult


class LLMProvider(ABC):
    """Единый интерфейс анализа отзывов."""

    @abstractmethod
    async def analyze(self, reviews: list[dict]) -> AnalysisResult:
        """Возвращает строго валидированный pydantic-объект."""


def _build_user_prompt(reviews: list[dict]) -> str:
    lines = [
        f"{i + 1}. (оценка {r.get('productValuation', '?')}/5) {r.get('text', '')}"
        for i, r in enumerate(reviews)
    ]
    return "Отзывы покупателей:\n" + "\n".join(lines)


def extract_json(text: str) -> dict:
    """Достаёт JSON из ответа LLM (обрезает markdown-код-фенсы и пояснения)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("В ответе LLM не найден JSON")
    return json.loads(text[start : end + 1])


class YandexGPTProvider(LLMProvider):
    """YandexGPT через yandex-cloud-ml-sdk (документация: yandex.cloud, раздел
    Foundation Models SDK — https://yandex.cloud/ru/docs/foundation-models/sdk/)."""

    async def analyze(self, reviews: list[dict]) -> AnalysisResult:
        try:
            from yandex_cloud_ml_sdk import YandexMLSDK
        except ImportError as exc:
            raise RuntimeError("Установите библиотеку: pip install yandex-cloud-ml-sdk") from exc
        if not YANDEX_FOLDER_ID or not YANDEX_API_KEY:
            raise RuntimeError("Не заданы YANDEX_FOLDER_ID и YANDEX_API_KEY")

        sdk = YandexMLSDK(folder_id=YANDEX_FOLDER_ID, auth=YANDEX_API_KEY)
        model = sdk.models.completions(YANDEX_MODEL)
        # SDK синхронный — запускаем в отдельном потоке, чтобы не блокировать event loop
        result = await asyncio.to_thread(
            model.run,
            [
                {"role": "system", "text": SYSTEM_PROMPT},
                {"role": "user", "text": _build_user_prompt(reviews)},
            ],
        )
        text = result.alternatives[0].text
        return AnalysisResult.model_validate(extract_json(text))


class OpenAIProvider(LLMProvider):
    """OpenAI через официальную библиотеку openai (AsyncOpenAI)."""

    async def analyze(self, reviews: list[dict]) -> AnalysisResult:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("Установите библиотеку: pip install openai") from exc
        if not OPENAI_API_KEY:
            raise RuntimeError("Не задан OPENAI_API_KEY")

        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        try:
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_prompt(reviews)},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            text = response.choices[0].message.content or ""
            return AnalysisResult.model_validate(extract_json(text))
        finally:
            await client.close()


class MockProvider(LLMProvider):
    """Демо-режим без ключей: возвращает фиксированный результат."""

    async def analyze(self, reviews: list[dict]) -> AnalysisResult:
        ratings = [r.get("productValuation", 0) or 0 for r in reviews]
        avg = sum(ratings) / len(ratings) if ratings else 0.0
        return AnalysisResult(
            pros=[
                "Хорошее качество сборки",
                "Быстрая доставка и надёжная упаковка",
                "Отличное соотношение цены и качества",
            ],
            cons=[
                "Размер может не соответствовать заявленному",
                "После нескольких недель использования возможны глюки",
                "Пластик в местах соединения мог бы быть прочнее",
            ],
            sentiment="positive" if avg >= 3.5 else "neutral",
            average_rating=round(avg, 1),
        )


def get_provider() -> LLMProvider:
    """Фабрика провайдера по переменной окружения LLM_PROVIDER."""
    provider = (LLM_PROVIDER or "mock").lower()
    if provider == "yandex":
        return YandexGPTProvider()
    if provider == "openai":
        return OpenAIProvider()
    if provider == "mock":
        return MockProvider()
    raise ValueError(f"Неизвестный LLM_PROVIDER: {provider!r} (допустимо: mock | yandex | openai)")
