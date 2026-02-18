"""Tests for Honda Generator base entity."""

from __future__ import annotations

import time

from custom_components.honda_generator.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    HondaGeneratorBinarySensor,
)
from custom_components.honda_generator.coordinator import HondaGeneratorCoordinator

from .conftest import TEST_FIRMWARE, TEST_MODEL, TEST_SERIAL


class TestHondaGeneratorEntity:
    """Test HondaGeneratorEntity base class via HondaGeneratorBinarySensor."""

    def test_unavailable_during_startup_grace(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test entity is unavailable during startup grace period."""
        entity_coordinator._has_connected_once = False
        entity_coordinator._startup_time = time.monotonic()
        entity_coordinator._startup_grace_period = 60

        desc = BINARY_SENSOR_DESCRIPTIONS[0]  # eco_mode
        entity = HondaGeneratorBinarySensor(entity_coordinator, desc)

        assert entity.available is False

    def test_available_after_connection(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test entity is available after first connection."""
        desc = BINARY_SENSOR_DESCRIPTIONS[0]  # eco_mode
        entity = HondaGeneratorBinarySensor(entity_coordinator, desc)

        # entity_coordinator has _has_connected_once=True, last_update_success=True
        assert entity.available is True

    def test_device_info_manufacturer(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test device_info has correct manufacturer."""
        desc = BINARY_SENSOR_DESCRIPTIONS[0]
        entity = HondaGeneratorBinarySensor(entity_coordinator, desc)

        info = entity.device_info
        assert info["manufacturer"] == "Honda"

    def test_device_info_model_and_serial(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test device_info has correct model and serial."""
        desc = BINARY_SENSOR_DESCRIPTIONS[0]
        entity = HondaGeneratorBinarySensor(entity_coordinator, desc)

        info = entity.device_info
        assert info["model"] == TEST_MODEL
        assert info["serial_number"] == TEST_SERIAL
        assert info["sw_version"] == TEST_FIRMWARE

    def test_device_info_name(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test device_info name includes model and serial."""
        desc = BINARY_SENSOR_DESCRIPTIONS[0]
        entity = HondaGeneratorBinarySensor(entity_coordinator, desc)

        info = entity.device_info
        assert info["name"] == f"{TEST_MODEL} ({TEST_SERIAL})"
