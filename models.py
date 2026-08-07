"""Pydantic-модели строгой валидации JSON-ответа нейросети (по ТЗ)."""
from __future__ import annotations

from pydantic import BaseModel, Field

# Промпт для LLM (по ТЗ: "Выяви топ-3 проблемы товара и топ-3 преимущества,
# верни результат в виде JSON")
SYSTEM_PROMPT = (
    "Ты — аналитик отзывов покупателей на маркетплейсе Wildberries. "
    "По списку отзывов выяви топ-3 проблемы товара и топ-3 преимущества. "
    "Ответь СТРОГО в формате JSON без markdown-обёртки: "
    '{"pros": ["..."], "cons": ["..."], "sentiment": "positive|neutral|negative", '
    '"average_rating": 4.3}'
)


class AnalysisResult(BaseModel):
    """Структурированный результат анализа отзывов."""

    pros: list[str] = Field(..., description="Топ-3 преимущества товара")
    cons: list[str] = Field(..., description="Топ-3 проблемы товара")
    sentiment: str = Field(..., description="Общая тональность: positive | neutral | negative")
    average_rating: float = Field(
        default=0.0, ge=0.0, le=5.0, description="Средняя оценка покупателей (0–5)"
    )
