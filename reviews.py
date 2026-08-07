"""Парсер отзывов Wildberries (httpx, асинхронно).

Порядок: по артикулу получаем карточку (card.wb.ru, чтобы узнать root-ид товара),
затем тянем отзывы с публичного эндпоинта feedbacks1.wb.ru/feedbacks/v1/{root_id}.

Продвинутый уровень:
  - TTL-кэш по артикулу — повторный /analyze того же товара мгновенный;
  - @async_retry на сетевые ошибки/5xx с экспоненциальным backoff;
  - reviews_stats() — статистика по отзывам без обращения к LLM.

ЧЕСТНО ОБ ИСТОЧНИКЕ (проверено при разработке, 2026-08-05):
  - Эндпоинт отзывов — недокументированный, используется open-source ботами,
    например https://github.com/nickisnotgaara/wildberries-reviews-bot.
  - Он закрыт антибот-защитой: с части IP отдаёт 403/пустоту даже с браузерным
    User-Agent (проверено напрямую). Структура ответа может меняться, поэтому
    парсер написан устойчиво (ищет отзывы по нескольким ключам).
  - Если запросы блокируются — включайте демо-режим: WB_DEMO_MODE=1.
"""
from __future__ import annotations

import httpx

import config
from utils import TTLCache, async_retry

CARD_API_URL = "https://card.wb.ru/cards/v1/detail"
FEEDBACKS_URL = "https://feedbacks1.wb.ru/feedbacks/v1/{root_id}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_CARD_PARAMS = {"appType": "1", "curr": "rub", "dest": "-1257786", "spp": "30"}

# Кэш отзывов: articul -> список (на ANALYSIS_CACHE_TTL секунд)
_cache = TTLCache(ttl_seconds=config.ANALYSIS_CACHE_TTL)


async def get_root_id(articul: int) -> int | None:
    """Получает root-ид товара из публичной карточки WB (нужен для отзывов)."""
    params = {**_CARD_PARAMS, "nm": str(articul)}
    async with httpx.AsyncClient(timeout=15, headers=_HEADERS) as client:
        response = await client.get(CARD_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
    products = (data.get("payload") or data.get("data") or {}).get("products") or []
    if not products:
        return None
    return products[0].get("root") or products[0].get("id")


@async_retry(retries=3, retry_on=(httpx.HTTPError,))
async def _fetch_reviews_from_api(articul: int, limit: int) -> list[dict]:
    root_id = await get_root_id(articul)
    if root_id is None:
        return []
    async with httpx.AsyncClient(timeout=15, headers=_HEADERS) as client:
        response = await client.get(FEEDBACKS_URL.format(root_id=root_id))
        response.raise_for_status()
        data = response.json()
    return _extract_reviews(data, limit)


async def fetch_reviews(articul: int, limit: int = config.MAX_REVIEWS) -> list[dict]:
    """Возвращает список отзывов [{text, productValuation}] с TTL-кэшем."""
    if config.DEMO_MODE:
        return mock_reviews(limit)
    return await _cache.get_or_set(articul, lambda: _fetch_reviews_from_api(articul, limit))


def cache_info() -> tuple[int, float]:
    """(число артикулов в кэше, TTL в секундах)."""
    return _cache.size, config.ANALYSIS_CACHE_TTL


def clear_cache() -> None:
    _cache.invalidate()


def reviews_stats(reviews: list[dict]) -> dict:
    """Статистика по отзывам без обращения к LLM (для быстрого вывода)."""
    ratings = [int(r.get("productValuation") or 0) for r in reviews]
    n = len(ratings)
    distribution = {
        "positive": sum(1 for x in ratings if x >= 4),
        "neutral": sum(1 for x in ratings if x == 3),
        "negative": sum(1 for x in ratings if x <= 2),
    }
    return {
        "total": n,
        "average_rating": round(sum(ratings) / n, 2) if n else 0.0,
        "distribution": distribution,
    }


def _extract_reviews(data: object, limit: int) -> list[dict]:
    """Устойчивый парсер: структура недокументированного API может меняться."""
    if isinstance(data, list):
        raw = data
    elif isinstance(data, dict):
        raw = data.get("feedbacks") or data.get("reviews") or []
    else:
        raw = []

    reviews: list[dict] = []
    for item in raw[:limit]:
        if not isinstance(item, dict):
            continue
        text = (
            item.get("text")
            or item.get("feedbackText")
            or item.get("content")
            or item.get("comment")
            or ""
        )
        rating = item.get("productValuation") or item.get("rating") or 0
        if text:
            reviews.append({"text": str(text), "productValuation": int(rating)})
    return reviews


def mock_reviews(n: int = config.MAX_REVIEWS) -> list[dict]:
    """Демо-режим: правдоподобные выдуманные отзывы, чтобы бот работал без сети."""
    pool = [
        ("Товар хороший, качество сборки отличное, доставка быстрая.", 5),
        ("Отличное соотношение цены и качества, пользуюсь неделю, полёт нормальный.", 5),
        ("Качество на высоте, упаковка плотная, всё пришло целым.", 4),
        ("Размер меньше заявленного — брал как обычно, пришлось менять.", 2),
        ("Через две недели начал глючить, разочарован покупкой.", 1),
        ("Цена выше среднего, но качество оправдывает.", 4),
        ("Заряжается быстро, батареи хватает на долго.", 5),
        ("Инструкция на сайте не совпадает с реальностью, разобрался методом тыка.", 3),
        ("Курьерская доставка подвела, сам товар неплохой.", 3),
        ("Доставили быстро, товар полностью соответствует описанию.", 5),
        ("Слабый пластик, скрипит в местах соединения.", 2),
        ("Отличный вариант за свои деньги, рекомендую.", 5),
        ("Сенсор реагирует не всегда, иногда нужно нажимать несколько раз.", 3),
        ("Покупал в подарок, человек доволен.", 5),
    ]
    reviews = []
    for i in range(n):
        text, rating = pool[i % len(pool)]
        reviews.append({"text": text, "productValuation": rating})
    return reviews
