"""Тесты P2: mock-отзывы, провайдеры LLM, цепочка фолбэка, retry, статистика.

Запуск: python -m pytest tests -q
"""
import asyncio

from llm import (
    LLMProvider,
    MockProvider,
    ProviderChain,
    analyze_with_retry,
    extract_json,
)
from models import AnalysisResult
from reviews import mock_reviews, reviews_stats


def test_mock_reviews_count() -> None:
    assert len(mock_reviews(50)) == 50


def test_mock_provider_analysis() -> None:
    async def run() -> None:
        res = await MockProvider().analyze(mock_reviews(50))
        assert isinstance(res, AnalysisResult)
        assert len(res.pros) == 3 and len(res.cons) == 3
        assert 0.0 <= res.average_rating <= 5.0
        assert res.distribution["positive"] + res.distribution["neutral"] \
            + res.distribution["negative"] == 50
        assert res.summary  # продвинутое поле заполнено

    asyncio.run(run())


def test_extract_json_with_fence() -> None:
    j = extract_json(
        '```json\n{"pros": ["a"], "cons": ["b"], "sentiment": "neutral", '
        '"average_rating": 3.5}\n```'
    )
    assert j["pros"] == ["a"]


class _FailingProvider(LLMProvider):
    name = "failing"

    async def analyze(self, reviews, instruction=None):
        raise RuntimeError("ключ невалиден")


def test_provider_chain_fallback() -> None:
    """Если первый провайдер упал — результат отдаёт второй (mock)."""
    async def run() -> None:
        chain = ProviderChain([_FailingProvider(), MockProvider()])
        res = await chain.analyze(mock_reviews(10))
        assert isinstance(res, AnalysisResult)
        assert res.average_rating > 0

    asyncio.run(run())


class _FlakyProvider(LLMProvider):
    """Возвращает невалидный JSON при первом вызове, валидный — со второго."""

    name = "flaky"

    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, reviews, instruction=None):
        self.calls += 1
        if self.calls == 1:
            raise ValueError("В ответе LLM не найден JSON")
        assert instruction  # при повторе добавляется инструкция
        return AnalysisResult(
            pros=["a"], cons=["b"], sentiment="neutral", average_rating=3.5
        )


def test_analyze_with_retry() -> None:
    """Невалидный JSON переспрашивается с инструкцией — итог успешен."""
    async def run() -> None:
        flaky = _FlakyProvider()
        res = await analyze_with_retry(flaky, mock_reviews(5), max_attempts=2)
        assert res.average_rating == 3.5
        assert flaky.calls == 2

    asyncio.run(run())


def test_reviews_stats() -> None:
    reviews = [
        {"text": "ok", "productValuation": 5},
        {"text": "ok", "productValuation": 4},
        {"text": "meh", "productValuation": 3},
        {"text": "bad", "productValuation": 1},
    ]
    stats = reviews_stats(reviews)
    assert stats["total"] == 4
    assert stats["average_rating"] == 3.25
    assert stats["distribution"] == {"positive": 2, "neutral": 1, "negative": 1}


def test_reviews_cache_ttl() -> None:
    """TTL-кэш: фабрика не вызывается повторно при попадании."""
    from reviews import _cache

    async def run() -> None:
        calls = 0

        async def factory():
            nonlocal calls
            calls += 1
            return [{"text": f"review {calls}"}]

        _cache.invalidate()
        first = await _cache.get_or_set(17457977, factory)
        second = await _cache.get_or_set(17457977, factory)
        assert first == second
        assert calls == 1

    asyncio.run(run())
