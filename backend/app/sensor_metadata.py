"""Metadata inference and confirmed overrides for GBTAC sensors.

Sheet1 contains the complete inventory. General metadata is inferred
conservatively from the supplied naming rules, and confirmed/specific points
are then overlaid using SENSOR_METADATA.
"""

from typing import Any

from .dashboard_sensors import INDOOR_WALL_TEMPERATURE_SENSOR_CODES
from .sensor_naming import infer_inventory_identity


SENSOR_METADATA: dict[str, dict[str, Any]] = {
    "30000_TL342": {
        "raw_unit": "W",
        "display_unit": "kW",
        "scale_factor": 0.001,
        "sign_convention": (
            "Preserve the source sign. Negative values require client "
            "confirmation and may represent flow direction or net export."
        ),
        "data_type": "power",
    },
    "30000_TL335": {
        "raw_unit": "W",
        "display_unit": "kW",
        "scale_factor": 0.001,
        "sign_convention": "Negative values may represent net export.",
        "data_type": "power",
    },
    "30000_TL3": {
        "raw_unit": "W",
        "display_unit": "kW",
        "scale_factor": 0.001,
        "data_type": "power",
    },
    "30000_TL252": {
        "raw_unit": "W",
        "display_unit": "kW",
        "scale_factor": 0.001,
        "data_type": "power",
    },
    "30000_TL253": {
        "raw_unit": "W",
        "display_unit": "kW",
        "scale_factor": 0.001,
        "data_type": "power",
    },
    "30000_TL388": {
        "raw_unit": "kWh",
        "display_unit": "kWh",
        "scale_factor": 1.0,
        "data_type": "cumulative_energy",
    },
    "30000_TL208": {
        "raw_unit": "W",
        "display_unit": "kW",
        "scale_factor": 0.001,
        "data_type": "power",
    },
    "30000_TL209": {
        "raw_unit": "W",
        "display_unit": "kW",
        "scale_factor": 0.001,
        "data_type": "power",
    },
    "30000_TL210": {
        "raw_unit": "W",
        "display_unit": "kW",
        "scale_factor": 0.001,
        "data_type": "power",
    },
    "30000_TL211": {
        "raw_unit": "W",
        "display_unit": "kW",
        "scale_factor": 0.001,
        "data_type": "power",
    },
    "30000_TL212": {
        "raw_unit": "W",
        "display_unit": "kW",
        "scale_factor": 0.001,
        "data_type": "power",
    },
    "30000_TL213": {
        "raw_unit": "W",
        "display_unit": "kW",
        "scale_factor": 0.001,
        "data_type": "power",
    },
    "30000_TL343": {
        "raw_unit": "W",
        "display_unit": "kW",
        "scale_factor": 0.001,
        "data_type": "phase_power",
    },
    "30000_TL344": {
        "raw_unit": "W",
        "display_unit": "kW",
        "scale_factor": 0.001,
        "data_type": "phase_power",
    },
    "30000_TL345": {
        "raw_unit": "W",
        "display_unit": "kW",
        "scale_factor": 0.001,
        "data_type": "phase_power",
    },
    "20000_TL92": {
        "raw_unit": "°C",
        "display_unit": "°C",
        "scale_factor": 1.0,
        "data_type": "outside_temperature",
        "category": "Temperature",
        "location": "Outside building",
    },
    "30000_TL207": {
        "raw_unit": "°C",
        "display_unit": "°C",
        "scale_factor": 1.0,
        "data_type": "temperature",
    },
    "20016_TL5": {
        "raw_unit": "ppm",
        "display_unit": "ppm",
        "scale_factor": 1.0,
        "data_type": "co2",
        "category": "Air Quality",
        "location": "Inside building",
    },
    "30000_TL4": {
        "raw_unit": "%",
        "display_unit": "%",
        "scale_factor": 1.0,
        "data_type": "percentage",
    },
}


# The client confirmed that TL55 through TL71 are temperature sensors installed
# inside the building walls. Exact overrides are required because several rows
# in the source inventory use a measurement-property value that is otherwise
# ambiguous.
for wall_sensor_code in INDOOR_WALL_TEMPERATURE_SENSOR_CODES:
    SENSOR_METADATA.setdefault(wall_sensor_code, {}).update(
        {
            "raw_unit": "°C",
            "display_unit": "°C",
            "scale_factor": 1.0,
            "data_type": "wall_temperature",
            "category": "Temperature",
        }
    )


def get_sensor_metadata(
    sensor_code: str,
    display_name: str | None = None,
    measurement_property: int | None = None,
) -> dict[str, Any]:
    """Return naming-derived metadata with exact sensor overrides applied."""
    metadata = infer_inventory_identity(
        sensor_code=sensor_code,
        display_name=display_name,
        measurement_property=measurement_property,
    )
    metadata.update(SENSOR_METADATA.get(sensor_code, {}))
    return metadata
