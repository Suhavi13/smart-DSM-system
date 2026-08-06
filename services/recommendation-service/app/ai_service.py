"""OpenRouter helper for optional AI-written recommendation text."""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI


STRATEGIES = [
    "Peak Shaving",
    "Load Shifting",
    "Pre-Cooling",
    "HVAC Setpoint Optimization",
    "Ventilation Optimization",
]


def _client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured; AI recommendations are skipped."
        )
    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )


def generate_recommendation(
    weather: dict[str, Any],
    predicted_power: float,
) -> list[str]:
    """Generate one optional AI recommendation for each DSM strategy."""
    client = _client()
    recommendations: list[str] = []

    for strategy in STRATEGIES:
        response = client.chat.completions.create(
            model=os.getenv("OPENROUTER_MODEL", "qwen/qwen3-8b"),
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are an AI assistant for a Smart Building Demand Side Management system.
Use only the supplied forecast weather and predicted building power.
The required strategy is {strategy}.
Do not invent sensor readings or describe current building conditions.
Keep the recommendation practical, professional, and under 120 words.
Return plain text using exactly these headings:
Title:
Recommendation:
Reason:
Expected Benefit:
""".strip(),
                },
                {
                    "role": "user",
                    "content": (
                        f"Forecast Weather:\n{weather}\n\n"
                        f"Predicted Site Power:\n{predicted_power} W\n\n"
                        f"Generate one recommendation using {strategy}."
                    ),
                },
            ],
            max_tokens=180,
            temperature=0.7,
        )
        content = response.choices[0].message.content
        if content:
            recommendations.append(content.strip())

    return recommendations
