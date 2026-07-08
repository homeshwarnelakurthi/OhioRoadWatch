"""Classify OHGO camera snapshots using an NVIDIA NIM-hosted vision-language model.

NVIDIA NIM (https://build.nvidia.com) exposes an OpenAI-compatible endpoint,
so this uses the standard `openai` client pointed at NVIDIA's base URL.
Free tier: no credit card, ~40 requests/minute shared across your API key.

Default model is the 11B Llama 3.2 Vision variant (faster, lighter on the
shared rate limit). Swap to the 90B variant via NIM_VISION_MODEL in .env if
you want higher-quality classifications and can tolerate slower/fewer calls.
"""
import base64
import json
import os
from typing import Any, Dict

from openai import OpenAI

LABELS = [
    "clear",
    "wet",
    "snow",
    "ice",
    "fog",
    "heavy_traffic",
    "incident",
    "dark_low_visibility",
    "unknown",
]

CLASSIFY_PROMPT = f"""You are analyzing a live Ohio highway traffic camera snapshot for a road-conditions monitoring system.

Look at the image and respond with ONLY a JSON object (no markdown fences, no extra text) with these fields:
- "label": one of {LABELS}
- "confidence": a float between 0 and 1
- "notes": a short (under 15 words) plain-language note on what you see, e.g. "light traffic, dry pavement"

If the image is blank, dark, or unreadable, use label "unknown" with low confidence."""

_client = None
_VISION_MODEL = os.environ.get("NIM_VISION_MODEL", "meta/llama-3.2-11b-vision-instruct")


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            raise ValueError(
                "Missing NVIDIA_API_KEY. Get a free key (no credit card) at "
                "https://build.nvidia.com and set it in your .env file."
            )
        _client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)
    return _client


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text.lstrip("`")
        text = text[4:] if text.lower().startswith("json") else text
    return text.strip().strip("`").strip()


def classify_image_bytes(image_bytes: bytes, media_type: str = "image/jpeg") -> Dict[str, Any]:
    client = _get_client()
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{media_type};base64,{b64}"

    response = client.chat.completions.create(
        model=_VISION_MODEL,
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": CLASSIFY_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    )
    text = _strip_code_fences(response.choices[0].message.content or "")
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = {"label": "unknown", "confidence": 0.0, "notes": f"unparsed response: {text[:100]}"}
    return result


def classify_image_file(path: str) -> Dict[str, Any]:
    with open(path, "rb") as f:
        return classify_image_bytes(f.read())
