#!/usr/bin/env python3
"""Test runner that sets up mocks for Home Assistant and BLE dependencies.

This script sets up mocks before importing any modules that depend on
Home Assistant or Bleak, allowing tests to run without these packages installed.

Usage:
    python3 run_tests.py [pytest args...]

Examples:
    python3 run_tests.py                    # Run all tests
    python3 run_tests.py -v                 # Run with verbose output
    python3 run_tests.py tests/test_api.py  # Run specific test file
"""

import sys
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock


class SubscriptableMock(MagicMock):
    """A MagicMock that supports subscripting (e.g., Generic[T])."""

    def __getitem__(self, item):
        return self


class _MockDataUpdateCoordinator:
    """Mock base class for DataUpdateCoordinator (supports inheritance)."""

    def __class_getitem__(cls, item):
        return cls

    def __init__(self, *args, **kwargs):
        pass

    def async_update_listeners(self):
        pass

    def async_set_updated_data(self, data):
        pass


class _MockCoordinatorEntity:
    """Mock base class for CoordinatorEntity (supports inheritance)."""

    def __class_getitem__(cls, item):
        return cls

    def __init__(self, coordinator=None, *args, **kwargs):
        if coordinator is not None:
            self.coordinator = coordinator
            self.hass = getattr(coordinator, "hass", None)

    @property
    def available(self):
        return getattr(self, "coordinator", None) is not None and getattr(
            self.coordinator, "last_update_success", False
        )

    def _handle_coordinator_update(self):
        pass

    def async_write_ha_state(self):
        pass


class _MockSensorEntity:
    """Mock base class for SensorEntity."""

    def __init__(self, *args, **kwargs):
        pass

    def async_write_ha_state(self):
        pass


class _MockBinarySensorEntity:
    """Mock base class for BinarySensorEntity."""

    def __init__(self, *args, **kwargs):
        pass

    def async_write_ha_state(self):
        pass


class _MockButtonEntity:
    """Mock base class for ButtonEntity."""

    def __init__(self, *args, **kwargs):
        pass


class _MockSwitchEntity:
    """Mock base class for SwitchEntity."""

    def __init__(self, *args, **kwargs):
        pass

    def async_write_ha_state(self):
        pass


class _MockRestoreEntity:
    """Mock base class for RestoreEntity."""

    def __init__(self, *args, **kwargs):
        pass

    async def async_added_to_hass(self):
        pass

    async def async_get_last_state(self):
        return None


class _MockUpdateFailed(Exception):
    """Mock UpdateFailed exception."""


@dataclass(frozen=True)
class _MockEntityDescription:
    """Mock base for entity description dataclasses.

    Must be a frozen dataclass so child classes can use
    @dataclass(frozen=True, kw_only=True) and inherit these fields.
    """

    key: str = ""
    translation_key: str | None = None
    device_class: object = None
    native_unit_of_measurement: object = None
    state_class: object = None
    suggested_display_precision: int | None = None
    icon: str | None = None
    entity_category: object = None
    entity_registry_enabled_default: bool = True
    options: list | None = None


class _MockStore:
    """Mock Store that accepts any constructor args."""

    def __init__(self, *args, **kwargs):
        self.async_save = AsyncMock()
        self.async_load = AsyncMock(return_value=None)


def setup_mocks():
    """Set up all required mocks before any other imports."""
    # Mock bleak
    _mock_bleak = MagicMock()
    _mock_bleak.BleakClient = MagicMock
    _mock_bleak.exc = MagicMock()
    _mock_bleak.exc.BleakError = Exception
    _mock_bleak.backends = MagicMock()
    _mock_bleak.backends.characteristic = MagicMock()
    _mock_bleak.backends.characteristic.BleakGATTCharacteristic = MagicMock
    _mock_bleak.backends.device = MagicMock()
    _mock_bleak.backends.device.BLEDevice = MagicMock

    sys.modules["bleak"] = _mock_bleak
    sys.modules["bleak.exc"] = _mock_bleak.exc
    sys.modules["bleak.backends"] = _mock_bleak.backends
    sys.modules["bleak.backends.characteristic"] = _mock_bleak.backends.characteristic
    sys.modules["bleak.backends.device"] = _mock_bleak.backends.device

    _mock_bleak_retry = MagicMock()
    _mock_bleak_retry.establish_connection = AsyncMock()
    sys.modules["bleak_retry_connector"] = _mock_bleak_retry

    # Mock homeassistant
    CONF_ADDRESS = "address"
    CONF_PASSWORD = "password"

    _mock_ha = MagicMock()
    _mock_ha.config_entries = MagicMock()
    _mock_ha.config_entries.ConfigEntry = SubscriptableMock()
    _mock_ha.const = MagicMock()
    _mock_ha.const.Platform = MagicMock()
    _mock_ha.const.CONF_ADDRESS = CONF_ADDRESS
    _mock_ha.const.CONF_PASSWORD = CONF_PASSWORD
    _mock_ha.const.CONF_SCAN_INTERVAL = "scan_interval"
    _mock_ha.const.EntityCategory = MagicMock()
    _mock_ha.const.UnitOfApparentPower = MagicMock()
    _mock_ha.const.UnitOfElectricCurrent = MagicMock()
    _mock_ha.const.UnitOfElectricPotential = MagicMock()
    _mock_ha.const.UnitOfTime = MagicMock()
    _mock_ha.core = MagicMock()
    _mock_ha.core.HomeAssistant = MagicMock
    _mock_ha.core.callback = lambda f: f
    _mock_ha.helpers = MagicMock()
    _mock_ha.helpers.device_registry = MagicMock()
    _mock_ha.helpers.device_registry.DeviceInfo = dict
    _mock_ha.helpers.device_registry.CONNECTION_BLUETOOTH = "bluetooth"
    _mock_ha.helpers.update_coordinator = MagicMock()
    _mock_ha.helpers.update_coordinator.DataUpdateCoordinator = (
        _MockDataUpdateCoordinator
    )
    _mock_ha.helpers.update_coordinator.CoordinatorEntity = _MockCoordinatorEntity
    _mock_ha.helpers.update_coordinator.UpdateFailed = _MockUpdateFailed
    _mock_ha.helpers.entity_platform = MagicMock()
    _mock_ha.helpers.restore_state = MagicMock()
    _mock_ha.helpers.restore_state.RestoreEntity = _MockRestoreEntity
    _mock_ha.components = MagicMock()
    _mock_ha.components.sensor = MagicMock()
    _mock_ha.components.sensor.SensorEntity = _MockSensorEntity
    _mock_ha.components.sensor.SensorDeviceClass = MagicMock()
    _mock_ha.components.sensor.SensorStateClass = MagicMock()
    _mock_ha.components.sensor.SensorEntityDescription = _MockEntityDescription
    _mock_ha.components.binary_sensor = MagicMock()
    _mock_ha.components.binary_sensor.BinarySensorEntity = _MockBinarySensorEntity
    _mock_ha.components.binary_sensor.BinarySensorDeviceClass = MagicMock()
    _mock_ha.components.binary_sensor.BinarySensorEntityDescription = (
        _MockEntityDescription
    )
    _mock_ha.components.button = MagicMock()
    _mock_ha.components.button.ButtonEntity = _MockButtonEntity
    _mock_ha.components.switch = MagicMock()
    _mock_ha.components.switch.SwitchEntity = _MockSwitchEntity
    _mock_ha.exceptions = MagicMock()
    _mock_ha.exceptions.HomeAssistantError = Exception

    sys.modules["homeassistant"] = _mock_ha
    sys.modules["homeassistant.config_entries"] = _mock_ha.config_entries
    sys.modules["homeassistant.const"] = _mock_ha.const
    sys.modules["homeassistant.core"] = _mock_ha.core
    sys.modules["homeassistant.helpers"] = _mock_ha.helpers
    sys.modules["homeassistant.helpers.device_registry"] = (
        _mock_ha.helpers.device_registry
    )
    sys.modules["homeassistant.helpers.update_coordinator"] = (
        _mock_ha.helpers.update_coordinator
    )
    sys.modules["homeassistant.helpers.entity_platform"] = (
        _mock_ha.helpers.entity_platform
    )
    sys.modules["homeassistant.helpers.restore_state"] = _mock_ha.helpers.restore_state
    _mock_ha.helpers.storage = MagicMock()
    _mock_ha.helpers.storage.Store = _MockStore
    sys.modules["homeassistant.helpers.storage"] = _mock_ha.helpers.storage
    sys.modules["homeassistant.components"] = _mock_ha.components
    sys.modules["homeassistant.components.sensor"] = _mock_ha.components.sensor
    sys.modules["homeassistant.components.binary_sensor"] = (
        _mock_ha.components.binary_sensor
    )
    sys.modules["homeassistant.components.button"] = _mock_ha.components.button
    sys.modules["homeassistant.components.switch"] = _mock_ha.components.switch
    sys.modules["homeassistant.exceptions"] = _mock_ha.exceptions

    # Mock homeassistant.helpers.config_validation (imported by __init__.py)
    _mock_ha.helpers.config_validation = MagicMock()
    _mock_ha.helpers.config_validation.config_entry_only_config_schema = MagicMock(
        return_value=MagicMock()
    )
    sys.modules["homeassistant.helpers.config_validation"] = (
        _mock_ha.helpers.config_validation
    )

    # Mock homeassistant.helpers.entity_registry (imported by coordinator.py)
    _mock_ha.helpers.entity_registry = MagicMock()
    sys.modules["homeassistant.helpers.entity_registry"] = (
        _mock_ha.helpers.entity_registry
    )


if __name__ == "__main__":
    # Set up mocks before importing pytest
    setup_mocks()

    # Now import and run pytest
    import pytest

    args = sys.argv[1:] if len(sys.argv) > 1 else ["-v", "tests/"]

    sys.exit(pytest.main(args))
