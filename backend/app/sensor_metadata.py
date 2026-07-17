"""Display metadata for the selected Phase 1 sensors.

"""

from typing import Any


DEFAULT_SENSOR_METADATA: dict[str, Any] = {
    "raw_unit": "unconfirmed",
    "display_unit": "unconfirmed",
    "scale_factor": 1.0,
    "sign_convention": "Preserve the source value sign.",
    "data_type": "numeric",
    "location": "GBTAC building",
}


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
        "data_type": "temperature",
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
    },
    "30000_TL4": {
        "raw_unit": "%",
        "display_unit": "%",
        "scale_factor": 1.0,
        "data_type": "percentage",
    },
}


def get_sensor_metadata(sensor_code: str) -> dict[str, Any]:
    """Return a complete metadata dictionary for a sensor code."""
    metadata = DEFAULT_SENSOR_METADATA.copy()
    metadata.update(SENSOR_METADATA.get(sensor_code, {}))
    return metadata
