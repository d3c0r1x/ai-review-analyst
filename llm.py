"""Провайдеры LLM: YandexGPT (yandex-cloud-ml-sdk), OpenAI или Mock (демо).

По ТЗ используются: yandex-cloud-ml-sdk (или openai) + pydantic.

Продвинутый уровень:
  - ProviderChain — цепочка провайдеров: если основной не сработал,
    пробуем резервный (LLM_FALLBACKS), в конце — mock, бот никогда не падает;
  - analyze_with_retry — если ответ LLM не прошёл pydantic-валидацию,
    переспрашиваем с подсказкой «верни ТОЛЬКО валидный JSON» (до N попыток);
  - instruction — возможность докинуть инструкцию в промпт при повторе.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod

from pydantic import ValidationError

import config
from config import (
    LLM_FALLBACKS,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    YANDEX_API_KEY,
    YANDEX_FOLDER_ID,
    YANDEX_MODEL,
)
from models import SYSTEM_PROMPT, AnalysisResult

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Единый интерфейс анализа отзывов."""

    name: str = "base"

    @abstractmethod
    async def analyze(
        self, reviews: list[dict], instruction: str | None = None
    ) -> AnalysisResult:
        """Возвращает строго валидированный pydantic-объект."""


def _build_user_prompt(reviews: list[dict], instruction: str | None = None) -> str:
    lines = [
        f"{i + 1}. (оценка {r.get('productValuation', '?')}/5) {r.get('text', '')}"
        for i, r in enumerate(reviews)
    ]
    prompt = "Отзывы покупателей:\n" + "\n".join(lines)
    if instruction:
        prompt += "\n\n" + instruction
    return prompt


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

    name = "yandex"

    async def analyze(
        self, reviews: list[dict], instruction: str | None = None
    ) -> AnalysisResult:
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
                {"role": "user", "text": _build_user_prompt(reviews, instruction)},
            ],
        )
        text = result.alternatives[0].text
        return AnalysisResult.model_validate(extract_json(text))


class OpenAIProvider(LLMProvider):
    """OpenAI через официальную библиотеку openai (AsyncOpenAI)."""

    name = "openai"

    async def analyze(
        self, reviews: list[dict], instruction: str | None = None
    ) -> AnalysisResult:
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
                    {"role": "user", "content": _build_user_prompt(reviews, instruction)},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            text = response.choices[0].message.content or ""
            return AnalysisResult.model_validate(extract_json(text))
        finally:
            await client.close()


class MockProvider(LLMProvider):
    """Демо-режим без ключей: считает распределение по оценкам из отзывов."""

    name = "mock"

    async def analyze(
        self, reviews: list[dict], instruction: str | None = None
    ) -> AnalysisResult:
        ratings = [r.get("productValuation", 0) or 0 for r in reviews]
        avg = sum(ratings) / len(ratings) if ratings else 0.0
        distribution = {
            "positive": sum(1 for x in ratings if x >= 4),
            "neutral": sum(1 for x in ratings if x == 3),
            "negative": sum(1 for x in ratings if x <= 2),
        }
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
            distribution=distribution,
            summary=f"Средняя оценка {avg:.1f} из 5 по {len(ratings)} отзывам. "
            f"Положительных: {distribution['positive']}, нейтральных: "
            f"{distribution['neutral']}, отрицательных: {distribution['negative']}.",
        )


class ProviderChain(LLMProvider):
    """Пробует провайдеров по очереди; при сбое одного — следующий."""

    name = "chain"

    def __init__(self, providers: list[LLMProvider]) -> None:
        self._providers = providers

    async def analyze(
        self, reviews: list[dict], instruction: str | None = None
    ) -> AnalysisResult:
        last_exc: Exception | None = None
        for provider in self._providers:
            try:
                return await provider.analyze(reviews, instruction=instruction)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Провайдер %s не сработал (%s) — пробуем следующий",
                    provider.name, exc,
                )
        raise RuntimeError("Все LLM-провайдеры недоступны") from last_exc


def _build(name: str) -> LLMProvider:
    if name == "yandex":
        return YandexGPTProvider()
    if name == "openai":
        return OpenAIProvider()
    if name == "mock":
        return MockProvider()
    raise ValueError(f"Неизвестный LLM-провайдер: {name!r}")


def get_provider() -> LLMProvider:
    """Фабрика: основной провайдер + резервные из LLM_FALLBACKS (без дублей).

    Например LLM_PROVIDER=openai, LLM_FALLBACKS=mock → цепочка
    [OpenAI, Mock]: невалидный/недоступный ключ не уронит бота.
    """
    names: list[str] = [(LLM_PROVIDER or "").lower(), *(n.lower() for n in LLM_FALLBACKS)]
    providers: list[LLMProvider] = []
    seen: set[str] = set()
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        try:
            providers.append(_build(name))
        except ValueError as exc:
            logger.warning("Провайдер %r пропущен: %s", name, exc)
    if not providers:
        providers.append(MockProvider())
    if len(providers) == 1:
        return providers[0]
    logger.info("LLM-цепочка: %s", [p.name for p in providers])
    return ProviderChain(providers)


async def analyze_with_retry(
    provider: LLMProvider, reviews: list[dict], max_attempts: int = 2
) -> AnalysisResult:
    """Анализ с переспросом: если ответ не прошёл валидацию — пробуем ещё раз.

    При повторе в промпт добавляется инструкция «верни ТОЛЬКО валидный JSON»,
    что на практике решает 90% проблем с нестрогими ответами LLM.
    """
    last: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        instruction = None
        if attempt > 1:
            instruction = (
                "Твой предыдущий ответ не прошёл строгую валидацию схемы. "
                "Верни ТОЛЬКО валидный JSON без пояснений с полями pros, cons, "
                "sentiment, average_rating (и опционально distribution, summary)."
            )
        try:
            return await provider.analyze(reviews, instruction=instruction)
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            last = exc
            logger.warning(
                "Попытка %d/%d: ответ LLM не прошёл валидацию: %s", attempt, max_attempts, exc
            )
    raise RuntimeError("LLM не вернул валидный JSON после всех попыток") from last
