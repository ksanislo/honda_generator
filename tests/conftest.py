"""Fixtures for Honda Generator tests.

Note: This file expects mocks to be set up BEFORE importing.
Use run_tests.py to run tests with proper mock setup.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.honda_generator.api import (
    DEVICE_NAMES,
    DEVICE_TYPES,
    DEVICE_TYPES_PUSH,
    Architecture,
    Device,
    DeviceType,
    PollAPI,
    PushAPI,
)
from custom_components.honda_generator.const import DOMAIN

# Home Assistant constants (defined locally to avoid HA dependency in tests)
CONF_ADDRESS = "address"
CONF_PASSWORD = "password"
CONF_ARCHITECTURE = "architecture"

# Test constants
TEST_ADDRESS = "AA:BB:CC:DD:EE:FF"
TEST_PASSWORD = "00000000"
TEST_SERIAL = "EAMT-1234567"
TEST_MODEL = "EU2200i"
TEST_FIRMWARE = "1.0.0"

# EU3200i test constants
TEST_EU3200I_SERIAL = "EBKJ-1234567"
TEST_EU3200I_MODEL = "EU3200i"


@pytest.fixture
def mock_ble_device() -> MagicMock:
    """Create a mock BLE device."""
    device = MagicMock()
    device.address = TEST_ADDRESS
    device.name = "EAMT"  # BLE advertised name is just the 4-letter serial prefix
    return device


@pytest.fixture
def mock_eu3200i_ble_device() -> MagicMock:
    """Create a mock BLE device for EU3200i."""
    device = MagicMock()
    device.address = TEST_ADDRESS
    device.name = "EBKJ"  # BLE advertised name is just the 4-letter serial prefix
    return device


@pytest.fixture
def mock_bleak_client() -> Generator[MagicMock, None, None]:
    """Mock the BleakClient."""
    with patch(
        "custom_components.honda_generator.api.BleakClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_connected = True
        mock_client.disconnect = AsyncMock()
        mock_client.start_notify = AsyncMock()
        mock_client.stop_notify = AsyncMock()
        mock_client.write_gatt_char = AsyncMock()
        mock_client.read_gatt_char = AsyncMock(return_value=b"\x01\x00\x00\x00")
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_establish_connection() -> Generator[AsyncMock, None, None]:
    """Mock the establish_connection function."""
    with patch(
        "custom_components.honda_generator.api.establish_connection"
    ) as mock_establish:
        mock_client = AsyncMock()
        mock_client.is_connected = True
        mock_client.disconnect = AsyncMock()
        mock_client.start_notify = AsyncMock()
        mock_client.stop_notify = AsyncMock()
        mock_client.write_gatt_char = AsyncMock()
        mock_client.read_gatt_char = AsyncMock(return_value=b"\x01\x00\x00\x00")
        mock_establish.return_value = mock_client
        yield mock_establish


@pytest.fixture
def mock_api(mock_ble_device: MagicMock) -> PollAPI:
    """Create a mock Poll API instance."""
    api = PollAPI(mock_ble_device, TEST_PASSWORD)
    api.connected = True
    api._warnings_raw = 0
    api._faults_raw = 0
    api._engine_event = 0
    api._engine_running = True
    api._engine_error = 0
    api._output_voltage = 120
    return api


@pytest.fixture
def mock_push_api(mock_eu3200i_ble_device: MagicMock) -> PushAPI:
    """Create a mock Push API instance."""
    api = PushAPI(mock_eu3200i_ble_device, TEST_PASSWORD)
    api.connected = True
    api._model = TEST_EU3200I_MODEL
    api._serial = TEST_EU3200I_SERIAL
    return api


def create_mock_devices(
    controller_name: str = TEST_ADDRESS,
    runtime_hours: float = 123.4,
    current: float = 5.5,
    power: int = 660,
    eco_mode: bool = True,
    engine_event: int = 0,
    engine_running: bool = True,
    engine_error: int = 0,
    output_voltage: int = 120,
) -> list[Device]:
    """Create a list of mock devices with specified values."""
    device_values: dict[DeviceType, int | float | bool] = {
        DeviceType.RUNTIME_HOURS: runtime_hours,
        DeviceType.CURRENT: current,
        DeviceType.POWER: power,
        DeviceType.ECO_MODE: eco_mode,
        DeviceType.ENGINE_EVENT: engine_event,
        DeviceType.ENGINE_RUNNING: engine_running,
        DeviceType.ENGINE_ERROR: engine_error,
        DeviceType.OUTPUT_VOLTAGE: output_voltage,
    }

    devices = []
    for device_type in DEVICE_TYPES:
        devices.append(
            Device(
                device_id=1,
                device_unique_id=f"{controller_name}_{device_type}",
                device_type=device_type,
                name=DEVICE_NAMES[device_type],
                state=device_values.get(device_type, 0),
            )
        )
    return devices


def create_mock_push_devices(
    controller_name: str = TEST_ADDRESS,
    runtime_hours: int = 100,
    current: float = 2.5,
    power: int = 500,
    eco_mode: bool = True,
    engine_running: bool = True,
    output_voltage: int = 120,
    fuel_ml: int = 2000,
    fuel_level_discrete: int = 10,
    fuel_remaining_min: int = 180,
    voltage_setting: int = 120,
) -> list[Device]:
    """Create a list of mock devices for Push architecture."""
    device_values: dict[DeviceType, int | float | bool] = {
        DeviceType.RUNTIME_HOURS: runtime_hours,
        DeviceType.CURRENT: current,
        DeviceType.POWER: power,
        DeviceType.ECO_MODE: eco_mode,
        DeviceType.ENGINE_RUNNING: engine_running,
        DeviceType.OUTPUT_VOLTAGE: output_voltage,
        DeviceType.FUEL_LEVEL_ML: fuel_ml,
        DeviceType.FUEL_REMAINS_LEVEL: fuel_level_discrete,
        DeviceType.FUEL_REMAINING_TIME: fuel_remaining_min,
        DeviceType.OUTPUT_VOLTAGE_SETTING: voltage_setting,
    }

    devices = []
    for device_type in DEVICE_TYPES_PUSH:
        devices.append(
            Device(
                device_id=1,
                device_unique_id=f"{controller_name}_{device_type}",
                device_type=device_type,
                name=DEVICE_NAMES[device_type],
                state=device_values.get(device_type, 0),
            )
        )
    return devices


@pytest.fixture
def mock_devices() -> list[Device]:
    """Create mock devices with default values."""
    return create_mock_devices()


@pytest.fixture
def mock_push_devices() -> list[Device]:
    """Create mock Push architecture devices with default values."""
    return create_mock_push_devices()


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.title = f"{TEST_MODEL} ({TEST_SERIAL})"
    entry.unique_id = TEST_ADDRESS
    entry.data = {
        CONF_ADDRESS: TEST_ADDRESS,
        CONF_PASSWORD: TEST_PASSWORD,
        "serial": TEST_SERIAL,
        "model": TEST_MODEL,
        CONF_ARCHITECTURE: Architecture.POLL.value,
    }
    entry.options = {"scan_interval": 10}
    entry.version = 3
    return entry


@pytest.fixture
def mock_push_config_entry() -> MagicMock:
    """Create a mock config entry for Push architecture (EU3200i)."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id_push"
    entry.domain = DOMAIN
    entry.title = f"{TEST_EU3200I_MODEL} ({TEST_EU3200I_SERIAL})"
    entry.unique_id = TEST_ADDRESS
    entry.data = {
        CONF_ADDRESS: TEST_ADDRESS,
        CONF_PASSWORD: TEST_PASSWORD,
        "serial": TEST_EU3200I_SERIAL,
        "model": TEST_EU3200I_MODEL,
        CONF_ARCHITECTURE: Architecture.PUSH.value,
    }
    entry.options = {}
    entry.version = 3
    return entry
