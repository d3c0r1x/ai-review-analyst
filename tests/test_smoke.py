"""Smoke-тесты: LLM-провайдеры, pydantic-валидация, парсер JSON."""
import asyncio

from llm import MockProvider, extract_json
from models import AnalysisResult
from reviews import mock_reviews


def test_mock_reviews_count() -> None:
    assert len(mock_reviews(50)) == 50


def test_extract_json_from_markdown() -> None:
    """LLM может обернуть JSON в ``` — extract_json обязан это срезать."""
    j = extract_json(
        '```json\n{"pros": ["a"], "cons": ["b"], "sentiment": "neutral", '
        '"average_rating": 3.5}\n```'
    )
    assert j["pros"] == ["a"]
    assert j["average_rating"] == 3.5


def test_mock_provider_returns_valid_model() -> None:
    """Результат провайдера проходит строгую валидацию pydantic."""
    result = asyncio.run(MockProvider().analyze(mock_reviews(50)))
    assert isinstance(result, AnalysisResult)
    assert len(result.pros) == 3 and len(result.cons) == 3
    assert 0.0 <= result.average_rating <= 5.0
