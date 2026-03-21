"""OpenAI GPT-4o wrapper with structured JSON output and graceful error handling."""

import json
import logging
import openai
from app.config import get_settings

log = logging.getLogger(__name__)


async def ask_json(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> dict:
    settings = get_settings()
    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-your"):
        log.warning("OpenAI API key not configured, returning empty analysis")
        return {"error": "OpenAI API key not configured"}

    try:
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

    except openai.RateLimitError:
        log.error("OpenAI quota exceeded - check billing at platform.openai.com")
        return {"error": "OpenAI quota exceeded. Please check your plan and billing."}
    except openai.AuthenticationError:
        log.error("OpenAI API key invalid")
        return {"error": "OpenAI API key is invalid."}
    except Exception as e:
        log.error(f"OpenAI call failed: {e}")
        return {"error": f"LLM analysis failed: {str(e)[:200]}"}


async def ask_text(system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
    settings = get_settings()
    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-your"):
        return ""

    try:
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
    except Exception as e:
        log.error(f"OpenAI text call failed: {e}")
        return ""
