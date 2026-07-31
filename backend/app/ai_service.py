"""OpenRouter helper for optional AI-written recommendation text."""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)


def generate_recommendation(weather, predicted_power):
    """Ask the configured model for one short building recommendation."""
    response = client.chat.completions.create(
        model="qwen/qwen3-8b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI assistant for a smart building. "
                    "Generate short, forecast-based energy-saving recommendations."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Weather: {weather}\n"
                    f"Predicted Power: {predicted_power} W\n\n"
                    "Provide one professional recommendation."
                ),
            },
        ],
        max_tokens=120,
    )

    return response.choices[0].message.content
