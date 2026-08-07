"""Add reversible recommendation decisions while preserving audit history.

Run from the project root:
    python -m backend.migrate_decision_reset
"""

from sqlalchemy import inspect, text

from backend.app.database import engine
from backend.app.models import RecommendationDecision


DECISION_COLUMNS = {
    "is_active": "BOOLEAN NOT NULL DEFAULT TRUE",
    "reverted_at": "TIMESTAMPTZ",
    "reverted_by": "VARCHAR(200)",
    "revert_comment": "TEXT",
}


def _add_missing_columns(connection) -> None:
    existing = {
        column["name"]
        for column in inspect(connection).get_columns(
            "recommendation_decisions"
        )
    }

    for column_name, definition in DECISION_COLUMNS.items():
        if column_name in existing:
            continue
        connection.execute(
            text(
                'ALTER TABLE "recommendation_decisions" '
                f'ADD COLUMN "{column_name}" {definition}'
            )
        )
        print(f"Added recommendation_decisions.{column_name}")


def main() -> None:
    RecommendationDecision.__table__.create(bind=engine, checkfirst=True)

    if engine.dialect.name != "postgresql":
        raise RuntimeError(
            "This migration targets the project's PostgreSQL database."
        )

    with engine.begin() as connection:
        _add_missing_columns(connection)

        # Existing installations used a table-wide unique constraint, which
        # prevented a new decision after an old one was returned to pending.
        connection.execute(
            text(
                "ALTER TABLE recommendation_decisions "
                "DROP CONSTRAINT IF EXISTS "
                "uq_recommendation_decision_version"
            )
        )

        # Also handle databases where PostgreSQL or a prior migration used a
        # different constraint name for the same two columns.
        connection.execute(
            text(
                """
                DO $$
                DECLARE
                    constraint_to_drop TEXT;
                BEGIN
                    FOR constraint_to_drop IN
                        SELECT conname
                        FROM pg_constraint
                        WHERE conrelid =
                            'recommendation_decisions'::regclass
                          AND contype = 'u'
                          AND pg_get_constraintdef(oid) =
                            'UNIQUE (recommendation_id, recommendation_version)'
                    LOOP
                        EXECUTE format(
                            'ALTER TABLE recommendation_decisions '
                            'DROP CONSTRAINT %I',
                            constraint_to_drop
                        );
                    END LOOP;
                END
                $$;
                """
            )
        )

        # Also remove an old manually-created index with the same purpose.
        connection.execute(
            text(
                "DROP INDEX IF EXISTS "
                "uq_recommendation_decision_version"
            )
        )

        # Only one current decision is allowed, while inactive decisions remain
        # available as audit history.
        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                    uq_active_recommendation_decision_version
                ON recommendation_decisions (
                    recommendation_id,
                    recommendation_version
                )
                WHERE is_active = TRUE
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                    ix_recommendation_decisions_is_active
                ON recommendation_decisions (is_active)
                """
            )
        )

    print("Decision reset migration completed successfully.")
    print("Existing decisions remain active and are not deleted.")


if __name__ == "__main__":
    main()
