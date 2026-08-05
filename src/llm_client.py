"""Thin wrapper around the Qwen2.5-VL-7B-Instruct endpoint hosted on FPT AI
Marketplace. Every agent goes through here so the model name/config lives in
exactly one place, as required by README section 9.
"""

import json
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL_NAME = "Qwen2.5-VL-7B-Instruct"
MODEL_PARAMETER_SIZE = "7B"

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2

_client = OpenAI(
    api_key=os.getenv("QWEN_API_KEY"),
    base_url=os.getenv("QWEN_BASE_URL"),
)


def _parse_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    return json.loads(content)


def call_llm_json(system_prompt: str, user_prompt: str, temperature: float = 0.0) -> dict:
    """Call the model and parse its reply as JSON.

    The system prompt must instruct the model to respond with a single
    JSON object and nothing else. Retries on transient API errors or a
    malformed (non-JSON) reply, since third-party endpoints occasionally
    time out or truncate output. Raises ValueError only after exhausting
    retries, so callers can decide how to degrade gracefully.
    """
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = _client.chat.completions.create(
                model=MODEL_NAME,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content
            return _parse_json(content)
        except (json.JSONDecodeError, Exception) as exc:  # noqa: BLE001 - broad on purpose, retry any transient failure
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue

    raise ValueError(f"LLM call failed after {MAX_RETRIES} attempts: {last_error!r}") from last_error
