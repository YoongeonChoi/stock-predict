"""OpenAI GPT-4o wrapper with structured JSON output and error-coded responses."""

import json
import openai
from app.config import get_settings
from app.errors import SP_1001, SP_4001, SP_4002, SP_4003, SP_4004, SP_4005


async def ask_json(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> dict:
    settings = get_settings()
    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-your"):
        err = SP_1001()
        err.log("warning")
        return err.to_dict()

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
            err = SP_4003()
            err.log()
            return err.to_dict()

    except openai.RateLimitError:
        err = SP_4001()
        err.log()
        return err.to_dict()
    except openai.AuthenticationError:
        err = SP_4002()
        err.log()
        return err.to_dict()
    except openai.APITimeoutError:
        err = SP_4004()
        err.log()
        return err.to_dict()
    except Exception as e:
        err = SP_4005(str(e)[:200])
        err.log()
        return err.to_dict()


async def ask_text(system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
    settings = get_settings()
    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-your"):
        SP_1001().log("warning")
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
        SP_4005(str(e)[:200]).log()
        return ""
