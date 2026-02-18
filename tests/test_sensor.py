"""Tests for Honda Generator sensor entities."""

from __future__ import annotations

import time
from unittest.mock import MagicMock


from custom_components.honda_generator.api import DeviceType
from custom_components.honda_generator.coordinator import HondaGeneratorCoordinator
from custom_components.honda_generator.sensor import (
    EU3200I_SENSOR_DESCRIPTIONS,
    POLL_SENSOR_DESCRIPTIONS,
    HondaGeneratorPersistentEnumSensor,
    HondaGeneratorPersistentMeasurementSensor,
    HondaGeneratorPersistentSensor,
    HondaGeneratorSensor,
)


def _get_description(key: str, descriptions=POLL_SENSOR_DESCRIPTIONS):
    """Get a sensor description by key."""
    for desc in descriptions:
        if desc.key == key:
            return desc
    raise ValueError(f"Description not found: {key}")


class TestHondaGeneratorSensor:
    """Test basic HondaGeneratorSensor."""

    def test_native_value_from_device_state(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test native_value returns device state."""
        desc = _get_description("output_current")
        sensor = HondaGeneratorSensor(entity_coordinator, desc)

        assert sensor.native_value == 5.5  # From create_mock_devices default

    def test_native_value_none_when_missing_device(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test native_value returns 0 when device is missing."""
        desc = _get_description("output_current")
        sensor = HondaGeneratorSensor(entity_coordinator, desc)

        # Remove all devices
        entity_coordinator.data.devices = []

        assert sensor.native_value == 0

    def test_zero_when_unavailable(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test zero_when_unavailable returns 0 when offline."""
        desc = _get_description("output_current")
        assert desc.zero_when_unavailable is True
        sensor = HondaGeneratorSensor(entity_coordinator, desc)

        entity_coordinator.last_update_success = False
        assert sensor.native_value == 0

    def test_startup_grace_unavailable(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test sensor is unavailable during startup grace."""
        entity_coordinator._has_connected_once = False
        entity_coordinator._startup_time = time.monotonic()
        entity_coordinator._startup_grace_period = 60

        desc = _get_description("output_current")
        sensor = HondaGeneratorSensor(entity_coordinator, desc)

        assert sensor.available is False

    def test_available_with_zero_when_unavailable(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test sensor with zero_when_unavailable stays available when offline."""
        desc = _get_description("output_current")
        sensor = HondaGeneratorSensor(entity_coordinator, desc)

        entity_coordinator.last_update_success = False
        entity_coordinator._has_connected_once = True

        assert sensor.available is True

    def test_output_power_value(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test output_power sensor value."""
        desc = _get_description("output_power")
        sensor = HondaGeneratorSensor(entity_coordinator, desc)

        assert sensor.native_value == 660  # From create_mock_devices default

    def test_output_voltage_value(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test output_voltage sensor value."""
        desc = _get_description("output_voltage")
        sensor = HondaGeneratorSensor(entity_coordinator, desc)

        assert sensor.native_value == 120  # From create_mock_devices default


class TestHondaGeneratorPersistentSensor:
    """Test persistent sensor (runtime_hours)."""

    def test_live_data_when_online(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test native_value returns live data when online."""
        desc = _get_description("runtime_hours")
        sensor = HondaGeneratorPersistentSensor(entity_coordinator, desc)

        assert sensor.native_value == 123.4  # From create_mock_devices default

    def test_fallback_to_stored_runtime_hours(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test fallback to stored runtime hours when offline."""
        desc = _get_description("runtime_hours")
        sensor = HondaGeneratorPersistentSensor(entity_coordinator, desc)
        sensor._first_update_attempted = True

        entity_coordinator.last_update_success = False
        entity_coordinator._stored_runtime_hours = 200

        assert sensor.native_value == 200

    def test_fallback_max_of_restored_and_stored(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test fallback uses max of restored and stored values."""
        desc = _get_description("runtime_hours")
        sensor = HondaGeneratorPersistentSensor(entity_coordinator, desc)
        sensor._first_update_attempted = True
        sensor._restored_value = 150.0

        entity_coordinator.last_update_success = False
        entity_coordinator._stored_runtime_hours = 200

        assert sensor.native_value == 200  # max(150, 200)

    def test_fallback_restored_higher(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test fallback prefers restored when it's higher."""
        desc = _get_description("runtime_hours")
        sensor = HondaGeneratorPersistentSensor(entity_coordinator, desc)
        sensor._first_update_attempted = True
        sensor._restored_value = 250.0

        entity_coordinator.last_update_success = False
        entity_coordinator._stored_runtime_hours = 200

        assert sensor.native_value == 250.0  # max(250, 200)

    def test_none_before_first_update(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test returns None before first update attempt."""
        desc = _get_description("runtime_hours")
        sensor = HondaGeneratorPersistentSensor(entity_coordinator, desc)

        entity_coordinator.last_update_success = False
        assert sensor.native_value is None

    def test_usage_rate_attribute(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test usage_rate_hours_per_day in extra_state_attributes."""
        desc = _get_description("runtime_hours")
        sensor = HondaGeneratorPersistentSensor(entity_coordinator, desc)

        entity_coordinator.get_hours_per_day = MagicMock(return_value=2.5)

        attrs = sensor.extra_state_attributes
        assert attrs["usage_rate_hours_per_day"] == 2.5

    def test_data_stale_attribute_online(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test data_stale is False when online."""
        desc = _get_description("runtime_hours")
        sensor = HondaGeneratorPersistentSensor(entity_coordinator, desc)

        attrs = sensor.extra_state_attributes
        assert attrs["data_stale"] is False

    def test_data_stale_attribute_offline(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test data_stale is True when offline."""
        desc = _get_description("runtime_hours")
        sensor = HondaGeneratorPersistentSensor(entity_coordinator, desc)

        entity_coordinator.last_update_success = False
        attrs = sensor.extra_state_attributes
        assert attrs["data_stale"] is True

    def test_cleared_restored_value_on_live_update(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test restored value is cleared on successful live update."""
        desc = _get_description("runtime_hours")
        sensor = HondaGeneratorPersistentSensor(entity_coordinator, desc)
        sensor._restored_value = 100.0

        # Simulate coordinator update
        sensor._handle_coordinator_update()

        assert sensor._restored_value is None

    def test_available_with_stored_data(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test available when offline but has stored data."""
        desc = _get_description("runtime_hours")
        sensor = HondaGeneratorPersistentSensor(entity_coordinator, desc)
        sensor._first_update_attempted = True

        entity_coordinator.last_update_success = False
        entity_coordinator._stored_runtime_hours = 100

        assert sensor.available is True


class TestHondaGeneratorPersistentEnumSensor:
    """Test persistent enum sensor (engine_event, engine_error)."""

    def test_int_to_key_translation(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test int state translates to enum key."""
        desc = _get_description("engine_event")
        sensor = HondaGeneratorPersistentEnumSensor(entity_coordinator, desc)

        # engine_event default state is 0 -> "no_event"
        assert sensor.native_value == "no_event"

    def test_int_to_key_engine_start(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test engine_start event translates correctly."""
        desc = _get_description("engine_event")
        sensor = HondaGeneratorPersistentEnumSensor(entity_coordinator, desc)

        # Set engine_event state to 1
        device = entity_coordinator.get_device_by_id(DeviceType.ENGINE_EVENT, 1)
        device.state = 1

        assert sensor.native_value == "engine_start"

    def test_fallback_to_last_live_value(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test fallback to last live value when offline."""
        desc = _get_description("engine_event")
        sensor = HondaGeneratorPersistentEnumSensor(entity_coordinator, desc)
        sensor._first_update_attempted = True

        # Simulate a live update first
        sensor._handle_coordinator_update()
        assert sensor._last_live_value == "no_event"

        # Go offline
        entity_coordinator.last_update_success = False
        assert sensor.native_value == "no_event"

    def test_fallback_to_restored(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test fallback to restored value when offline with no live value."""
        desc = _get_description("engine_event")
        sensor = HondaGeneratorPersistentEnumSensor(entity_coordinator, desc)
        sensor._first_update_attempted = True
        sensor._restored_value = "error"

        entity_coordinator.last_update_success = False
        assert sensor.native_value == "error"

    def test_none_before_first_update(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test returns None before first update."""
        desc = _get_description("engine_event")
        sensor = HondaGeneratorPersistentEnumSensor(entity_coordinator, desc)

        entity_coordinator.last_update_success = False
        assert sensor.native_value is None

    def test_unknown_int_value(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test unknown int state produces unknown_N key."""
        desc = _get_description("engine_event")
        sensor = HondaGeneratorPersistentEnumSensor(entity_coordinator, desc)

        device = entity_coordinator.get_device_by_id(DeviceType.ENGINE_EVENT, 1)
        device.state = 99

        assert sensor.native_value == "unknown_99"


class TestHondaGeneratorPersistentMeasurementSensor:
    """Test persistent measurement sensor (fuel_level, etc.)."""

    def test_live_data_when_online(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test native_value returns live data when online."""
        desc = _get_description("fuel_level", EU3200I_SENSOR_DESCRIPTIONS)

        # Set the fuel level state on the existing device
        device = entity_coordinator.get_device_by_id(DeviceType.FUEL_LEVEL, 1)
        device.state = 75

        sensor = HondaGeneratorPersistentMeasurementSensor(entity_coordinator, desc)
        assert sensor.native_value == 75

    def test_fallback_to_last_live(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test fallback to last live value when offline."""
        desc = _get_description("fuel_level", EU3200I_SENSOR_DESCRIPTIONS)
        sensor = HondaGeneratorPersistentMeasurementSensor(entity_coordinator, desc)
        sensor._first_update_attempted = True
        sensor._last_live_value = 50

        entity_coordinator.last_update_success = False
        assert sensor.native_value == 50

    def test_fallback_to_restored(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test fallback to restored value when offline."""
        desc = _get_description("fuel_level", EU3200I_SENSOR_DESCRIPTIONS)
        sensor = HondaGeneratorPersistentMeasurementSensor(entity_coordinator, desc)
        sensor._first_update_attempted = True
        sensor._restored_value = 30.0

        entity_coordinator.last_update_success = False
        assert sensor.native_value == 30.0

    def test_data_stale_attribute(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test data_stale attribute when offline."""
        desc = _get_description("fuel_level", EU3200I_SENSOR_DESCRIPTIONS)
        sensor = HondaGeneratorPersistentMeasurementSensor(entity_coordinator, desc)

        entity_coordinator.last_update_success = False
        attrs = sensor.extra_state_attributes
        assert attrs["data_stale"] is True
