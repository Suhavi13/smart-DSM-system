"""Authoritative sensor groups used by dashboard aggregation endpoints.

These groupings are based on client-confirmed GBTAC sensor identities.
Keeping them in the backend prevents browsers from choosing arbitrary sensors
or calculating building-wide values inconsistently.
"""

INDOOR_AMBIENT_TEMPERATURE_SENSOR_CODES = (
    "20003_TL2",
    "20004_TL2",
    "20005_TL2",
    "20006_TL2",
    "20007_TL2",
    "20008_TL2",
    "20009_TL2",
    "20010_TL2",
    "20011_TL2",
    "20012_TL2",
    "20013_TL2",
    "20014_TL2",
    "20015_TL2",
    "20016_TL2",
)

INDOOR_WALL_TEMPERATURE_SENSOR_CODES = (
    "30000_TL55",
    "30000_TL56",
    "30000_TL57",
    "30000_TL58",
    "30000_TL59",
    "30000_TL60",
    "30000_TL61",
    "30000_TL62",
    "30000_TL63",
    "30000_TL64",
    "30000_TL65",
    "30000_TL66",
    "30000_TL67",
    "30000_TL68",
    "30000_TL69",
    "30000_TL70",
    "30000_TL71",
)

INDOOR_TEMPERATURE_SENSOR_CODES = (
    INDOOR_AMBIENT_TEMPERATURE_SENSOR_CODES
    + INDOOR_WALL_TEMPERATURE_SENSOR_CODES
)

INDOOR_CO2_SENSOR_CODE = "20016_TL5"
