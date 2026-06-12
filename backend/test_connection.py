from sqlalchemy import create_engine

engine = create_engine(
    "postgresql://postgres:password@localhost/smart_building_dsm"
)

with engine.connect() as conn:
    print("Database Connected Successfully!")