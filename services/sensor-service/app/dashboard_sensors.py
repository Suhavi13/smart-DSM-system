"""Authoritative sensor groups used by dashboard aggregation endpoints.

These groupings are based on client-confirmed GBTAC sensor identities.

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

# The client could not confirm that this point is a valid CO2 measurement and
# asked that it be left out of the current project scope. The inventory row is
# preserved for traceability but import_selected_sensors.py marks it inactive
# so it is not displayed or used by dashboard calculations.
EXCLUDED_SENSOR_CODES = (
    "20016_TL5",
)


# This is the cumulative building-consumption counter provided in Wh. 
ENERGY_CONSUMPTION_SENSOR_CODE = "30000_TL337"
