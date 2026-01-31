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
from unittest.mock import AsyncMock, MagicMock


class SubscriptableMock(MagicMock):
    """A MagicMock that supports subscripting (e.g., Generic[T])."""

    def __getitem__(self, item):
        return self


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
    _mock_ha.core = MagicMock()
    _mock_ha.core.HomeAssistant = MagicMock
    _mock_ha.core.callback = lambda f: f
    _mock_ha.helpers = MagicMock()
    _mock_ha.helpers.device_registry = MagicMock()
    _mock_ha.helpers.device_registry.DeviceInfo = dict
    _mock_ha.helpers.device_registry.CONNECTION_BLUETOOTH = "bluetooth"
    _mock_ha.helpers.update_coordinator = MagicMock()
    _mock_ha.helpers.update_coordinator.CoordinatorEntity = SubscriptableMock()
    _mock_ha.helpers.update_coordinator.DataUpdateCoordinator = SubscriptableMock()
    _mock_ha.helpers.entity_platform = MagicMock()
    _mock_ha.helpers.restore_state = MagicMock()
    _mock_ha.helpers.restore_state.RestoreEntity = MagicMock
    _mock_ha.components = MagicMock()
    _mock_ha.components.sensor = MagicMock()
    _mock_ha.components.sensor.SensorEntity = MagicMock
    _mock_ha.components.sensor.SensorDeviceClass = MagicMock()
    _mock_ha.components.sensor.SensorStateClass = MagicMock()
    _mock_ha.components.sensor.SensorEntityDescription = MagicMock
    _mock_ha.components.binary_sensor = MagicMock()
    _mock_ha.components.binary_sensor.BinarySensorEntity = MagicMock
    _mock_ha.components.binary_sensor.BinarySensorDeviceClass = MagicMock()
    _mock_ha.components.binary_sensor.BinarySensorEntityDescription = MagicMock
    _mock_ha.components.button = MagicMock()
    _mock_ha.components.button.ButtonEntity = MagicMock
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
    _mock_ha.helpers.storage.Store = MagicMock
    sys.modules["homeassistant.helpers.storage"] = _mock_ha.helpers.storage
    sys.modules["homeassistant.components"] = _mock_ha.components
    sys.modules["homeassistant.components.sensor"] = _mock_ha.components.sensor
    sys.modules["homeassistant.components.binary_sensor"] = (
        _mock_ha.components.binary_sensor
    )
    sys.modules["homeassistant.components.button"] = _mock_ha.components.button
    sys.modules["homeassistant.exceptions"] = _mock_ha.exceptions


if __name__ == "__main__":
    # Set up mocks before importing pytest
    setup_mocks()

    # Now import and run pytest
    import pytest

    # Default to running tests/test_api.py and tests/test_codes.py
    # (these don't have import issues with relative imports)
    args = (
        sys.argv[1:]
        if len(sys.argv) > 1
        else ["-v", "tests/test_api.py", "tests/test_codes.py"]
    )

    sys.exit(pytest.main(args))
