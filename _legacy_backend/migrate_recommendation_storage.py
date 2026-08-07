"""Upgrade existing PostgreSQL recommendation tables for persisted API results.

Run once from the project root:
    python backend/migrate_recommendation_storage.py
"""

from sqlalchemy import inspect, text

from backend.app.database import engine
from backend.app.models import Recommendation, RecommendationDecision


RECOMMENDATION_COLUMNS = {
    "recommendation_key": "VARCHAR(100)",
    "recommendation_version": "INTEGER NOT NULL DEFAULT 1",
    "category": "VARCHAR(100)",
    "priority": "VARCHAR(20)",
    "recommendation_snapshot": "JSONB",
}

DECISION_COLUMNS = {
    "stored_recommendation_id": "INTEGER",
}


def _add_missing_columns(
    connection,
    table_name: str,
    definitions: dict[str, str],
) -> None:
    inspector = inspect(connection)
    existing = {
        column["name"] for column in inspector.get_columns(table_name)
    }

    for column_name, definition in definitions.items():
        if column_name in existing:
            continue
        connection.execute(
            text(
                f'ALTER TABLE "{table_name}" '
                f'ADD COLUMN "{column_name}" {definition}'
            )
        )
        print(f"Added {table_name}.{column_name}")


def main() -> None:
    # Creates complete tables on a new database. Existing tables are upgraded
    # by the ALTER statements below because create_all does not alter schemas.
    Recommendation.__table__.create(bind=engine, checkfirst=True)
    RecommendationDecision.__table__.create(bind=engine, checkfirst=True)

    if engine.dialect.name != "postgresql":
        raise RuntimeError(
            "This migration targets the project's PostgreSQL database."
        )

    with engine.begin() as connection:
        _add_missing_columns(
            connection,
            "recommendations",
            RECOMMENDATION_COLUMNS,
        )
        _add_missing_columns(
            connection,
            "recommendation_decisions",
            DECISION_COLUMNS,
        )

        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                    uq_recommendations_key_version
                ON recommendations (
                    recommendation_key,
                    recommendation_version
                )
                WHERE recommendation_key IS NOT NULL
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                    ix_recommendations_recommendation_key
                ON recommendations (recommendation_key)
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                    ix_recommendation_decisions_stored_recommendation_id
                ON recommendation_decisions (stored_recommendation_id)
                """
            )
        )

        connection.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conrelid =
                            'recommendation_decisions'::regclass
                          AND contype = 'f'
                          AND pg_get_constraintdef(oid) LIKE
                            'FOREIGN KEY (stored_recommendation_id)%'
                    ) THEN
                        ALTER TABLE recommendation_decisions
                        ADD CONSTRAINT
                            fk_decisions_stored_recommendation
                        FOREIGN KEY (stored_recommendation_id)
                        REFERENCES recommendations (recommendation_id)
                        ON DELETE SET NULL;
                    END IF;
                END
                $$;
                """
            )
        )

    print("Recommendation storage migration completed successfully.")


if __name__ == "__main__":
    main()
