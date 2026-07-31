"""OpenRouter helper for optional AI-written recommendation text."""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

STRATEGIES = [
    "Peak Shaving",
    "Load Shifting",
    "Pre-Cooling",
    "HVAC Setpoint Optimization",
    "Ventilation Optimization",
]


def generate_recommendation(weather, predicted_power):
    """
    Generate multiple DSM recommendations using different strategies.
    """

    recommendations = []

    for strategy in STRATEGIES:

        response = client.chat.completions.create(
            model="qwen/qwen3-8b",
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are an AI assistant for a Smart Building Demand Side Management (DSM) system.

Generate exactly ONE DSM recommendation.

The strategy MUST be:

{strategy}

Your goal is to reduce building energy consumption while maintaining occupant comfort.

Rules:
- Base the recommendation ONLY on the forecast weather and predicted building power.
- Never invent sensor readings.
- Never describe current building conditions.
- Keep the recommendation practical and realistic.
- Use professional engineering language.
- Maximum 120 words.
- Do NOT use markdown.
- Do NOT use bullet points.

Return the response EXACTLY in this format.

Title:
<one line>

Recommendation:
<one or two sentences>

Reason:
<one sentence>

Expected Benefit:
<one sentence>

Leave one blank line between each section.
Each heading must start on its own line.
Do not combine everything into one paragraph.
"""
                },
                {
                    "role": "user",
                    "content": f"""
Forecast Weather:

{weather}

Predicted Site Power:

{predicted_power} W

Generate ONE DSM recommendation using the strategy:

{strategy}

Return ONLY this format.

Title:
<one line>

Recommendation:
<one or two sentences>

Reason:
<one sentence>

Expected Benefit:
<one sentence>
"""
                },
            ],
            max_tokens=180,
            temperature=0.7,
        )

        recommendations.append(
            response.choices[0].message.content.strip()
        )

    return recommendations