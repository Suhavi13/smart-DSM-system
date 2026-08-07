"""Apply the client-confirmed W/kWh metadata to an existing database.

Run from the backend directory:
    python update_energy_units.py
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = Path(__file__).resolve().parents[1]
for path in (PROJECT_ROOT, SERVICE_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.cache_service import cache
from app.database import SessionLocal
from app.models import SensorPoint


POWER_SENSOR_CODES = {
    "30000_TL342",
    "30000_TL335",
    "30000_TL3",
    "30000_TL252",
    "30000_TL253",
    "30000_TL208",
    "30000_TL209",
    "30000_TL210",
    "30000_TL211",
    "30000_TL212",
    "30000_TL213",
    "30000_TL343",
    "30000_TL344",
    "30000_TL345",
}
CUMULATIVE_ENERGY_SENSOR_CODE = "30000_TL388"


def main() -> None:
    db = SessionLocal()
    try:
        updated = 0
        missing = []

        for sensor_code in sorted(POWER_SENSOR_CODES):
            sensor = (
                db.query(SensorPoint)
                .filter(SensorPoint.sensor_code == sensor_code)
                .first()
            )
            if sensor is None:
                missing.append(sensor_code)
                continue

            sensor.raw_unit = "W"
            sensor.display_unit = "W"
            sensor.scale_factor = 1.0
            if sensor_code in {"30000_TL343", "30000_TL344", "30000_TL345"}:
                sensor.data_type = "phase_power"
            else:
                sensor.data_type = "power"
            updated += 1

        cumulative = (
            db.query(SensorPoint)
            .filter(
                SensorPoint.sensor_code == CUMULATIVE_ENERGY_SENSOR_CODE
            )
            .first()
        )
        if cumulative is None:
            missing.append(CUMULATIVE_ENERGY_SENSOR_CODE)
        else:
            cumulative.raw_unit = "kWh"
            cumulative.display_unit = "kWh"
            cumulative.scale_factor = 1.0
            cumulative.data_type = "cumulative_energy"
            updated += 1

        db.commit()
        cleared = cache.clear_namespace()
        print(f"Updated {updated} energy sensor record(s).")
        print(f"Cleared {cleared} cached response(s).")
        if missing:
            print("Not found in the current database: " + ", ".join(missing))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
