# AI Review Analyst

> **Prototype / extracted component.** This idea was later incorporated into the larger [Smart Shopper](https://github.com/d3c0r1x/smart-shopper) project.

LLM-powered analysis of marketplace reviews. Given a Wildberries product, the service extracts recurring problems and advantages from a review set and returns a validated structured result.

## What it demonstrates

- LLM integration through HTTP API;
- structured JSON output validated with Pydantic;
- retry/fallback when the model returns invalid data;
- simple Telegram interface;
- deterministic tests without requiring a live model.

## Stack

Python · aiogram · httpx · Pydantic · LLM API · pytest · GitHub Actions

The project is kept public as an example of the smaller prototype that later became a feature inside Smart Shopper.
