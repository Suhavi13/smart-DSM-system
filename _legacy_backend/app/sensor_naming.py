"""Helpers for interpreting GBTAC sensor names from Sheet1.

The parser uses only naming rules supplied for this project:
- W/S/E/N identify the building side.
- 0/1/2 identify basement/main/second floor.
- FTHC codes identify sensors installed inside walls.
- 20003_TL2 through 20016_TL2 are indoor ambient temperature sensors.

Unknown portions of a source name are preserved rather than guessed.
"""

from __future__ import annotations

import re
from typing import Any


DIRECTION_NAMES = {
    "W": "West",
    "S": "South",
    "E": "East",
    "N": "North",
}

FLOOR_NAMES = {
    "0": "basement",
    "1": "main floor",
    "2": "second floor",
    # Sheet1 also contains level-3 names. Keep the wording neutral because the
    # project naming notes only explicitly defined levels 0, 1, and 2.
    "3": "level 3",
}

AMBIENT_SENSOR_PATTERN = re.compile(r"^200(0[3-9]|1[0-6])_TL2$")
DIRECTIONAL_NAME_PATTERN = re.compile(
    r"^(?P<direction>[WSEN])(?P<floor>[0-3])(?P<body>[A-Z]+?)(?P<number>\d+)$",
    re.IGNORECASE,
)


def clean_source_label(value: str | None) -> str:
    """Remove common trend-label suffixes while preserving the source code."""
    if not value:
        return ""

    label = str(value).strip()
    label = re.sub(r"\s*-\s*TL$", "", label, flags=re.IGNORECASE)
    label = re.sub(r"\s+TL$", "", label, flags=re.IGNORECASE)
    return label.strip()


def ambient_sensor_number(sensor_code: str) -> str | None:
    if not AMBIENT_SENSOR_PATTERN.match(sensor_code):
        return None
    return sensor_code.split("_", maxsplit=1)[0]


def parse_directional_label(display_name: str | None) -> dict[str, Any]:
    """Parse orientation, floor, installation, and trailing sensor number."""
    normalized = clean_source_label(display_name).replace(" ", "")
    match = DIRECTIONAL_NAME_PATTERN.match(normalized)

    if not match:
        return {
            "orientation": None,
            "floor": None,
            "installation_type": None,
            "sensor_number": None,
            "location": None,
        }

    direction_code = match.group("direction").upper()
    floor_code = match.group("floor")
    body = match.group("body").upper()
    sensor_number = match.group("number")

    orientation = DIRECTION_NAMES.get(direction_code)
    floor = FLOOR_NAMES.get(floor_code, f"level {floor_code}")
    installation_type = "inside wall" if "FTHC" in body else None

    location_parts = [f"{orientation} side", floor]
    if installation_type:
        location_parts.append(installation_type)
    location_parts.append(f"sensor {sensor_number}")

    return {
        "orientation": orientation,
        "floor": floor,
        "installation_type": installation_type,
        "sensor_number": sensor_number,
        "location": ", ".join(location_parts),
    }


def infer_inventory_identity(
    sensor_code: str,
    display_name: str | None,
    measurement_property: int | None,
) -> dict[str, Any]:
    """Return a readable name plus conservative metadata inferred from Sheet1."""
    source_display_name = clean_source_label(display_name) or sensor_code
    ambient_number = ambient_sensor_number(sensor_code)

    if ambient_number:
        return {
            "display_name": f"Ambient Temperature {ambient_number}",
            "category": "Temperature",
            "raw_unit": "°C",
            "display_unit": "°C",
            "scale_factor": 1.0,
            "sign_convention": "Preserve the source value sign.",
            "data_type": "ambient_temperature",
            "location": f"Inside building, ambient sensor {ambient_number}",
        }

    parsed_name = parse_directional_label(source_display_name)
    lowered_name = source_display_name.lower()

    category = None
    raw_unit = "unconfirmed"
    display_unit = "unconfirmed"
    data_type = "numeric"

    if "humidity" in lowered_name:
        category = "Humidity"
        raw_unit = "%"
        display_unit = "%"
        data_type = "humidity"
    elif measurement_property == 6:
        # Across Sheet1, property 6 is used by the ambient and directional
        # temperature points. This inference is intentionally limited to 6.
        category = "Temperature"
        raw_unit = "°C"
        display_unit = "°C"
        data_type = (
            "wall_temperature"
            if parsed_name["installation_type"] == "inside wall"
            else "temperature"
        )
    elif parsed_name["installation_type"] == "inside wall":
        category = "Wall Sensor"
        data_type = "wall_sensor"

    return {
        "display_name": source_display_name,
        "category": category,
        "raw_unit": raw_unit,
        "display_unit": display_unit,
        "scale_factor": 1.0,
        "sign_convention": "Preserve the source value sign.",
        "data_type": data_type,
        "location": parsed_name["location"] or "GBTAC building",
    }
