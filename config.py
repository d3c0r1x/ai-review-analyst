"""Конфигурация бота через переменные окружения (stdlib os.getenv)."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BOT_TOKEN = os.getenv("WB_BOT_TOKEN", "")

# Провайдер LLM: mock (демо, без ключей) | yandex | openai
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")

# YandexGPT (библиотека yandex-cloud-ml-sdk, по ТЗ)
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "")
YANDEX_MODEL = os.getenv("YANDEX_MODEL", "yandexgpt-lite")

# OpenAI (библиотека openai, по ТЗ)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# 1 = демо-режим (парсер отзывов не ходит в сеть), 0 = реальный парсинг
DEMO_MODE = os.getenv("WB_DEMO_MODE", "0") == "1"

# Сколько отзывов парсим (по ТЗ — последние 50)
MAX_REVIEWS = int(os.getenv("MAX_REVIEWS", "50"))

# --- Продвинутый уровень ---
# Резервные провайдеры через запятую (порядок попыток). По умолчанию основной
# провайдер LLM_PROVIDER, затем mock — бот не падает, если ключ не сработал.
LLM_FALLBACKS = [x.strip() for x in os.getenv("LLM_FALLBACKS", "mock").split(",") if x.strip()]
# Сколько раз переспрашивать LLM, если JSON не прошёл pydantic-валидацию
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
# TTL кэша отзывов по артикулу (секунды)
ANALYSIS_CACHE_TTL = float(os.getenv("ANALYSIS_CACHE_TTL", "300"))
# Минимальный интервал между сообщениями пользователя (секунды)
THROTTLE_MIN_INTERVAL = float(os.getenv("THROTTLE_MIN_INTERVAL", "0.7"))
