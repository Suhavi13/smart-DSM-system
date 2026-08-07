"""Create read-performance indexes used by dashboard sensor queries."""

from sqlalchemy import text

from backend.app.database import engine


INDEX_STATEMENTS = [
    """
    CREATE INDEX IF NOT EXISTS ix_sensor_readings_sensor_time_desc
    ON sensor_readings (sensor_point_id, reading_time DESC)
    """,
]


def main():
    with engine.begin() as connection:
        for statement in INDEX_STATEMENTS:
            connection.execute(text(statement))

    print("Phase 2 database index migration completed successfully.")


if __name__ == "__main__":
    main()
