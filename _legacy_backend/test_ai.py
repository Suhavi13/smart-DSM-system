from app.ai_service import generate_recommendation

print(
    generate_recommendation(
        "Temperature 30°C, Humidity 60%",
        22000,
    )
)