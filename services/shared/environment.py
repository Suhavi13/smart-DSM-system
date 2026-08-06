
"""Load transition-era and service-specific environment settings."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_service_environment(service_root: Path) -> None:
    """Load the old monolith settings first, then service overrides.

    During the migration, backend/.env remains a convenient local fallback.
    A service-specific .env takes precedence and should be used for Azure.
    """
    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    load_dotenv(service_root / ".env", override=True)
