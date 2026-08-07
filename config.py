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
