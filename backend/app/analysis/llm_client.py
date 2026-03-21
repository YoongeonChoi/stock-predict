"""OpenAI GPT-4o wrapper with structured JSON output."""

import json
import openai
from app.config import get_settings


async def ask_json(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> dict:
    settings = get_settings()
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    text = response.choices[0].message.content or "{}"
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "Failed to parse LLM response", "raw": text[:500]}


async def ask_text(system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
    settings = get_settings()
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )

    return response.choices[0].message.content or ""
