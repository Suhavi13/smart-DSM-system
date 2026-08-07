"""Sensor naming and metadata inference tests."""

from backend.app.sensor_naming import (
    infer_inventory_identity,
    parse_directional_label,
)


def test_wall_sensor_location_is_parsed():
    identity = infer_inventory_identity(
        sensor_code="30000_TL61",
        display_name="W1FTHC019-TL",
        measurement_property=6,
    )

    assert identity["display_name"] == "W1FTHC019"
    assert identity["category"] == "Temperature"
    assert identity["data_type"] == "wall_temperature"
    assert identity["display_unit"] == "°C"
    assert identity["location"] == (
        "West side, main floor, inside wall, sensor 019"
    )


def test_ambient_sensor_gets_unique_display_name():
    identity = infer_inventory_identity(
        sensor_code="20011_TL2",
        display_name="Temperature",
        measurement_property=6,
    )

    assert identity["display_name"] == "Ambient Temperature 20011"
    assert identity["data_type"] == "ambient_temperature"
    assert identity["location"] == (
        "Inside building, ambient sensor 20011"
    )


def test_direction_and_floor_parse_without_wall_assumption():
    parsed = parse_directional_label("S2SWV105-TL")

    assert parsed["orientation"] == "South"
    assert parsed["floor"] == "second floor"
    assert parsed["installation_type"] is None
    assert parsed["sensor_number"] == "105"
    assert parsed["location"] == "South side, second floor, sensor 105"
