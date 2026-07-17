from sqlalchemy import text

from backend.app.database import engine


ALTER_STATEMENTS = [
    "ALTER TABLE sensor_points ADD COLUMN IF NOT EXISTS raw_unit VARCHAR(50)",
    "ALTER TABLE sensor_points ADD COLUMN IF NOT EXISTS display_unit VARCHAR(50)",
    (
        "ALTER TABLE sensor_points ADD COLUMN IF NOT EXISTS "
        "scale_factor DOUBLE PRECISION NOT NULL DEFAULT 1.0"
    ),
    "ALTER TABLE sensor_points ADD COLUMN IF NOT EXISTS sign_convention TEXT",
    "ALTER TABLE sensor_points ADD COLUMN IF NOT EXISTS data_type VARCHAR(50)",
    "ALTER TABLE sensor_points ADD COLUMN IF NOT EXISTS location VARCHAR(150)",
    (
        "CREATE INDEX IF NOT EXISTS ix_sensor_readings_reading_time "
        "ON sensor_readings (reading_time)"
    ),
]


def main():
    with engine.begin() as connection:
        for statement in ALTER_STATEMENTS:
            connection.execute(text(statement))

    print("Phase 1 database migration completed successfully.")


if __name__ == "__main__":
    main()
