"""Tests for Honda Generator API."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.honda_generator.api import (
    API,
    BOUNDS_CURRENT,
    BOUNDS_FUEL_LEVEL,
    BOUNDS_FUEL_REMAINING,
    BOUNDS_POWER,
    BOUNDS_RUNTIME_HOURS,
    DEVICE_NAMES,
    DEVICE_TYPE_TO_DIAGNOSTIC,
    DEVICE_TYPES_POLL,
    DEVICE_TYPES_PUSH,
    FUNC_START_ECO,
    FUNC_STOP_ECO,
    MODEL_SPECS,
    APIAuthError,
    APIConnectionError,
    APIReadError,
    Architecture,
    DeviceType,
    DiagnosticCategory,
    GeneratorAPIProtocol,
    PollAPI,
    PushAPI,
    create_api,
    get_architecture_from_device_name,
    get_model_spec,
)

from .conftest import TEST_ADDRESS, TEST_PASSWORD


class TestAPIStaticMethods:
    """Test API static/class methods."""

    def test_get_model_from_serial_eu2200i(self) -> None:
        """Test EU2200i model detection from serial."""
        assert API.get_model_from_serial("EAMT1234567") == "EU2200i"

    def test_get_model_from_serial_eu3200i(self) -> None:
        """Test EU3200i model detection from serial."""
        assert API.get_model_from_serial("EBKJ1234567") == "EU3200i"

    def test_get_model_from_serial_em5000sx(self) -> None:
        """Test EM5000SX model detection from serial."""
        assert API.get_model_from_serial("EBMC1234567") == "EM5000SX"

    def test_get_model_from_serial_em6500sx(self) -> None:
        """Test EM6500SX model detection from serial."""
        assert API.get_model_from_serial("EBJC1234567") == "EM6500SX"

    def test_get_model_from_serial_eu7000is(self) -> None:
        """Test EU7000is model detection from serial."""
        assert API.get_model_from_serial("EEJD1234567") == "EU7000is"

    def test_get_model_from_serial_unknown(self) -> None:
        """Test unknown model detection from serial."""
        assert API.get_model_from_serial("XXXX1234567") == "Unknown"

    def test_get_model_from_serial_short(self) -> None:
        """Test model detection with short serial."""
        assert API.get_model_from_serial("EA") == "Unknown"

    def test_get_model_from_serial_empty(self) -> None:
        """Test model detection with empty serial."""
        assert API.get_model_from_serial("") == "Unknown"


class TestArchitecture:
    """Test Architecture enum and related functions."""

    def test_architecture_values(self) -> None:
        """Test Architecture enum values."""
        assert Architecture.POLL == "poll"
        assert Architecture.PUSH == "push"

    def test_get_architecture_from_device_name_poll(self) -> None:
        """Test architecture detection for Poll models."""
        assert get_architecture_from_device_name("EAMT") == Architecture.POLL
        assert get_architecture_from_device_name("EBMC") == Architecture.POLL
        assert get_architecture_from_device_name("EBJC") == Architecture.POLL
        assert get_architecture_from_device_name("EEJD") == Architecture.POLL

    def test_get_architecture_from_device_name_push(self) -> None:
        """Test architecture detection for Push models."""
        assert get_architecture_from_device_name("EBKJ") == Architecture.PUSH

    def test_get_architecture_from_device_name_unknown(self) -> None:
        """Test architecture detection for unknown devices."""
        assert get_architecture_from_device_name("UNKNOWN") == Architecture.POLL
        assert get_architecture_from_device_name("") == Architecture.POLL
        assert get_architecture_from_device_name(None) == Architecture.POLL


class TestAPIFactory:
    """Test API factory function."""

    def test_create_api_poll(self, mock_ble_device: MagicMock) -> None:
        """Test creating a Poll API."""
        api = create_api(mock_ble_device, TEST_PASSWORD, Architecture.POLL)
        assert isinstance(api, PollAPI)
        assert isinstance(api, GeneratorAPIProtocol)

    def test_create_api_push(self, mock_ble_device: MagicMock) -> None:
        """Test creating a Push API."""
        api = create_api(mock_ble_device, TEST_PASSWORD, Architecture.PUSH)
        assert isinstance(api, PushAPI)
        assert isinstance(api, GeneratorAPIProtocol)

    def test_create_api_default_is_poll(self, mock_ble_device: MagicMock) -> None:
        """Test that default architecture is Poll."""
        api = create_api(mock_ble_device, TEST_PASSWORD)
        assert isinstance(api, PollAPI)


class TestPollAPIInit:
    """Test Poll API initialization."""

    def test_api_init(self, mock_ble_device: MagicMock) -> None:
        """Test API initialization."""
        api = PollAPI(mock_ble_device, TEST_PASSWORD)

        assert api.pwd == TEST_PASSWORD
        assert api.connected is False
        assert api._warnings_raw == 0
        assert api._faults_raw == 0
        assert api._engine_event == 0
        assert api._engine_running is False
        assert api._engine_error == 0
        assert api._output_voltage == 0

    def test_api_controller_name(self, mock_ble_device: MagicMock) -> None:
        """Test API controller_name property."""
        api = PollAPI(mock_ble_device, TEST_PASSWORD)
        assert api.controller_name == TEST_ADDRESS

    def test_api_alias(self, mock_ble_device: MagicMock) -> None:
        """Test that API is an alias for PollAPI."""
        api = API(mock_ble_device, TEST_PASSWORD)
        assert isinstance(api, PollAPI)


class TestPushAPIInit:
    """Test Push API initialization."""

    def test_push_api_init(self, mock_eu3200i_ble_device: MagicMock) -> None:
        """Test Push API initialization."""
        api = PushAPI(mock_eu3200i_ble_device, TEST_PASSWORD)

        assert api.pwd == TEST_PASSWORD
        assert api.connected is False
        assert api._stream_active is False

    def test_push_api_controller_name(self, mock_eu3200i_ble_device: MagicMock) -> None:
        """Test Push API controller_name property."""
        api = PushAPI(mock_eu3200i_ble_device, TEST_PASSWORD)
        assert api.controller_name == TEST_ADDRESS


class TestAPIConnect:
    """Test API connection methods."""

    @pytest.mark.asyncio
    async def test_connect_success(
        self, mock_ble_device: MagicMock, mock_establish_connection: AsyncMock
    ) -> None:
        """Test successful connection."""
        api = PollAPI(mock_ble_device, TEST_PASSWORD)

        # Mock successful authentication
        mock_client = mock_establish_connection.return_value
        mock_client.read_gatt_char = AsyncMock(return_value=b"\x01")

        await api.connect()

        assert api.connected is True
        mock_establish_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(
        self, mock_ble_device: MagicMock, mock_establish_connection: AsyncMock
    ) -> None:
        """Test disconnection."""
        api = PollAPI(mock_ble_device, TEST_PASSWORD)

        # Connect first
        mock_client = mock_establish_connection.return_value
        mock_client.read_gatt_char = AsyncMock(return_value=b"\x01")
        await api.connect()

        # Now disconnect
        await api.disconnect()

        mock_client.disconnect.assert_called_once()


class TestAPIWarningsFaults:
    """Test API warning and fault bit methods."""

    def test_get_warning_bit_set(self, mock_api: PollAPI) -> None:
        """Test getting a set warning bit."""
        mock_api._warnings_raw = 0b0100  # Bit 2 set
        assert mock_api.get_warning_bit(2) is True

    def test_get_warning_bit_unset(self, mock_api: PollAPI) -> None:
        """Test getting an unset warning bit."""
        mock_api._warnings_raw = 0b0100  # Bit 2 set
        assert mock_api.get_warning_bit(0) is False
        assert mock_api.get_warning_bit(1) is False
        assert mock_api.get_warning_bit(3) is False

    def test_get_fault_bit_set(self, mock_api: PollAPI) -> None:
        """Test getting a set fault bit."""
        mock_api._faults_raw = 0b1000  # Bit 3 set
        assert mock_api.get_fault_bit(3) is True

    def test_get_fault_bit_unset(self, mock_api: PollAPI) -> None:
        """Test getting an unset fault bit."""
        mock_api._faults_raw = 0b1000  # Bit 3 set
        assert mock_api.get_fault_bit(0) is False
        assert mock_api.get_fault_bit(1) is False
        assert mock_api.get_fault_bit(2) is False

    def test_multiple_warning_bits(self, mock_api: PollAPI) -> None:
        """Test multiple warning bits set."""
        mock_api._warnings_raw = 0b1010  # Bits 1 and 3 set
        assert mock_api.get_warning_bit(0) is False
        assert mock_api.get_warning_bit(1) is True
        assert mock_api.get_warning_bit(2) is False
        assert mock_api.get_warning_bit(3) is True


class TestDeviceTypes:
    """Test device type definitions."""

    def test_all_device_types_have_names(self) -> None:
        """Test that all device types have display names."""
        for device_type in DeviceType:
            assert device_type in DEVICE_NAMES

    def test_device_type_values(self) -> None:
        """Test device type string values."""
        assert DeviceType.RUNTIME_HOURS == "runtime_hours"
        assert DeviceType.CURRENT == "current"
        assert DeviceType.POWER == "power"
        assert DeviceType.ECO_MODE == "eco_mode"
        assert DeviceType.ENGINE_EVENT == "engine_event"
        assert DeviceType.ENGINE_RUNNING == "engine_running"
        assert DeviceType.ENGINE_ERROR == "engine_error"
        assert DeviceType.OUTPUT_VOLTAGE == "output_voltage"
        assert DeviceType.FUEL_LEVEL == "fuel_level"
        assert DeviceType.FUEL_REMAINING_TIME == "fuel_remaining_time"

    def test_eu3200i_device_types(self) -> None:
        """Test EU3200i-specific device types."""
        assert DeviceType.FUEL_LEVEL_ML == "fuel_level_ml"
        assert DeviceType.FUEL_REMAINS_LEVEL == "fuel_remains_level"
        assert DeviceType.OUTPUT_VOLTAGE_SETTING == "output_voltage_setting"

    def test_device_types_poll_list(self) -> None:
        """Test that Poll device types list is correct."""
        assert DeviceType.RUNTIME_HOURS in DEVICE_TYPES_POLL
        assert DeviceType.ENGINE_EVENT in DEVICE_TYPES_POLL
        assert DeviceType.FUEL_LEVEL_ML not in DEVICE_TYPES_POLL

    def test_device_types_push_list(self) -> None:
        """Test that Push device types list is correct."""
        assert DeviceType.RUNTIME_HOURS in DEVICE_TYPES_PUSH
        assert DeviceType.FUEL_LEVEL_ML in DEVICE_TYPES_PUSH
        assert DeviceType.ENGINE_EVENT not in DEVICE_TYPES_PUSH


class TestExceptions:
    """Test API exception classes."""

    def test_api_auth_error_is_exception(self) -> None:
        """Test that APIAuthError is an Exception."""
        assert issubclass(APIAuthError, Exception)

    def test_api_connection_error_is_exception(self) -> None:
        """Test that APIConnectionError is an Exception."""
        assert issubclass(APIConnectionError, Exception)

    def test_api_read_error_is_exception(self) -> None:
        """Test that APIReadError is an Exception."""
        assert issubclass(APIReadError, Exception)

    def test_can_raise_auth_error(self) -> None:
        """Test that APIAuthError can be raised and caught."""
        with pytest.raises(APIAuthError):
            raise APIAuthError("auth failed")

    def test_can_raise_connection_error(self) -> None:
        """Test that APIConnectionError can be raised and caught."""
        with pytest.raises(APIConnectionError):
            raise APIConnectionError("connection failed")

    def test_can_raise_read_error(self) -> None:
        """Test that APIReadError can be raised and caught."""
        with pytest.raises(APIReadError):
            raise APIReadError("diagnostic read failed")


class TestDiagnosticCategory:
    """Test DiagnosticCategory enum and mappings."""

    def test_diagnostic_category_values(self) -> None:
        """Test DiagnosticCategory string values."""
        assert DiagnosticCategory.WARNINGS_FAULTS == "warnings_faults"
        assert DiagnosticCategory.RUNTIME_HOURS == "runtime_hours"
        assert DiagnosticCategory.CURRENT == "current"
        assert DiagnosticCategory.POWER == "power"
        assert DiagnosticCategory.ECO_MODE == "eco_mode"
        assert DiagnosticCategory.FUEL == "fuel"

    def test_diagnostic_category_count(self) -> None:
        """Test that DiagnosticCategory has expected number of values."""
        assert len(DiagnosticCategory) == 6

    def test_device_type_to_diagnostic_mapping(self) -> None:
        """Test that device types map to correct diagnostic categories."""
        assert (
            DEVICE_TYPE_TO_DIAGNOSTIC[DeviceType.RUNTIME_HOURS]
            == DiagnosticCategory.RUNTIME_HOURS
        )
        assert (
            DEVICE_TYPE_TO_DIAGNOSTIC[DeviceType.CURRENT] == DiagnosticCategory.CURRENT
        )
        assert DEVICE_TYPE_TO_DIAGNOSTIC[DeviceType.POWER] == DiagnosticCategory.POWER
        assert (
            DEVICE_TYPE_TO_DIAGNOSTIC[DeviceType.ECO_MODE]
            == DiagnosticCategory.ECO_MODE
        )
        assert (
            DEVICE_TYPE_TO_DIAGNOSTIC[DeviceType.FUEL_LEVEL] == DiagnosticCategory.FUEL
        )
        assert (
            DEVICE_TYPE_TO_DIAGNOSTIC[DeviceType.FUEL_REMAINING_TIME]
            == DiagnosticCategory.FUEL
        )

    def test_notification_based_devices_not_in_mapping(self) -> None:
        """Test that notification-based device types are not in the mapping."""
        # These device types get their values from BLE notifications, not diagnostic reads
        assert DeviceType.ENGINE_EVENT not in DEVICE_TYPE_TO_DIAGNOSTIC
        assert DeviceType.ENGINE_RUNNING not in DEVICE_TYPE_TO_DIAGNOSTIC
        assert DeviceType.ENGINE_ERROR not in DEVICE_TYPE_TO_DIAGNOSTIC
        assert DeviceType.OUTPUT_VOLTAGE not in DEVICE_TYPE_TO_DIAGNOSTIC

    def test_mapping_covers_all_read_based_devices(self) -> None:
        """Test that all device types requiring reads are in the mapping."""
        # 6 device types require diagnostic reads (including fuel sensors)
        assert len(DEVICE_TYPE_TO_DIAGNOSTIC) == 6


class TestGetValueWithCategories:
    """Test _get_value behavior with enabled_categories."""

    @pytest.mark.asyncio
    async def test_get_value_skips_disabled_runtime_hours(
        self, mock_api: PollAPI
    ) -> None:
        """Test that runtime_hours returns 0 when its category is disabled."""
        enabled = {DiagnosticCategory.CURRENT, DiagnosticCategory.POWER}
        result = await mock_api._get_value(DeviceType.RUNTIME_HOURS, enabled)
        assert result == 0

    @pytest.mark.asyncio
    async def test_get_value_skips_disabled_current(self, mock_api: PollAPI) -> None:
        """Test that current returns 0 when its category is disabled."""
        enabled = {DiagnosticCategory.RUNTIME_HOURS, DiagnosticCategory.POWER}
        result = await mock_api._get_value(DeviceType.CURRENT, enabled)
        assert result == 0

    @pytest.mark.asyncio
    async def test_get_value_skips_disabled_power(self, mock_api: PollAPI) -> None:
        """Test that power returns 0 when its category is disabled."""
        enabled = {DiagnosticCategory.RUNTIME_HOURS, DiagnosticCategory.CURRENT}
        result = await mock_api._get_value(DeviceType.POWER, enabled)
        assert result == 0

    @pytest.mark.asyncio
    async def test_get_value_skips_disabled_eco_mode(self, mock_api: PollAPI) -> None:
        """Test that eco_mode returns False when its category is disabled."""
        enabled = {DiagnosticCategory.RUNTIME_HOURS}
        result = await mock_api._get_value(DeviceType.ECO_MODE, enabled)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_value_returns_notification_values_regardless(
        self, mock_api: PollAPI
    ) -> None:
        """Test that notification-based values are returned regardless of enabled categories."""
        # Even with empty enabled categories, notification-based values should work
        enabled: set[DiagnosticCategory] = set()

        assert (
            await mock_api._get_value(DeviceType.ENGINE_EVENT, enabled)
            == mock_api._engine_event
        )
        assert (
            await mock_api._get_value(DeviceType.ENGINE_RUNNING, enabled)
            == mock_api._engine_running
        )
        assert (
            await mock_api._get_value(DeviceType.ENGINE_ERROR, enabled)
            == mock_api._engine_error
        )
        assert (
            await mock_api._get_value(DeviceType.OUTPUT_VOLTAGE, enabled)
            == mock_api._output_voltage
        )


class TestSensorBounds:
    """Test sensor value bounds checking."""

    def test_bounds_constants_defined(self) -> None:
        """Test that bounds constants are properly defined."""
        assert BOUNDS_RUNTIME_HOURS == (0, 100000)
        assert BOUNDS_CURRENT == (0.0, 50.0)
        assert BOUNDS_POWER == (0, 10000)
        assert BOUNDS_FUEL_LEVEL == (0, 100)
        assert BOUNDS_FUEL_REMAINING == (0, 1440)

    def test_bounds_runtime_hours_reasonable(self) -> None:
        """Test that runtime hours bounds are reasonable."""
        min_val, max_val = BOUNDS_RUNTIME_HOURS
        assert min_val == 0  # Can't have negative runtime
        assert max_val >= 10000  # Should allow for high-use generators

    def test_bounds_current_reasonable(self) -> None:
        """Test that current bounds are reasonable."""
        min_val, max_val = BOUNDS_CURRENT
        assert min_val == 0.0  # Can't have negative current
        assert max_val >= 20.0  # EU2200i max is ~18A at 120V

    def test_bounds_power_reasonable(self) -> None:
        """Test that power bounds are reasonable."""
        min_val, max_val = BOUNDS_POWER
        assert min_val == 0  # Can't have negative power
        assert max_val >= 7000  # EU7000is rated at 7000 VA

    def test_bounds_fuel_level_reasonable(self) -> None:
        """Test that fuel level bounds are reasonable."""
        min_val, max_val = BOUNDS_FUEL_LEVEL
        assert min_val == 0  # 0% is empty
        assert max_val == 100  # 100% is full

    def test_bounds_fuel_remaining_reasonable(self) -> None:
        """Test that fuel remaining time bounds are reasonable."""
        min_val, max_val = BOUNDS_FUEL_REMAINING
        assert min_val == 0  # 0 minutes is empty
        assert max_val == 1440  # 24 hours max (in minutes)


class TestModelSpecs:
    """Test model specifications."""

    def test_all_models_have_specs(self) -> None:
        """Test that all known models have specifications."""
        assert "EU2200i" in MODEL_SPECS
        assert "EU3200i" in MODEL_SPECS
        assert "EM5000SX" in MODEL_SPECS
        assert "EM6500SX" in MODEL_SPECS
        assert "EU7000is" in MODEL_SPECS

    def test_get_model_spec_found(self) -> None:
        """Test getting spec for known model."""
        spec = get_model_spec("EU2200i")
        assert spec is not None
        assert spec.name == "EU2200i"
        assert spec.max_power_watts == 2200

    def test_get_model_spec_not_found(self) -> None:
        """Test getting spec for unknown model."""
        spec = get_model_spec("Unknown")
        assert spec is None

    def test_eu2200i_spec(self) -> None:
        """Test EU2200i specifications."""
        spec = get_model_spec("EU2200i")
        assert spec is not None
        assert spec.remote_start is False
        assert spec.fuel_sensor is False
        assert spec.eco_control is False
        assert spec.guest_mode is False
        assert spec.architecture == Architecture.POLL

    def test_eu3200i_spec(self) -> None:
        """Test EU3200i specifications."""
        spec = get_model_spec("EU3200i")
        assert spec is not None
        assert spec.max_power_watts == 3200
        assert spec.fuel_tank_liters == 4.7
        assert spec.remote_start is False
        assert spec.fuel_sensor is True
        assert spec.eco_control is False
        assert spec.architecture == Architecture.PUSH

    def test_em5000sx_spec(self) -> None:
        """Test EM5000SX specifications."""
        spec = get_model_spec("EM5000SX")
        assert spec is not None
        assert spec.remote_start is True
        assert spec.fuel_sensor is False
        assert spec.eco_control is True
        assert spec.guest_mode is True
        assert spec.architecture == Architecture.POLL

    def test_eu7000is_spec(self) -> None:
        """Test EU7000is specifications."""
        spec = get_model_spec("EU7000is")
        assert spec is not None
        assert spec.remote_start is True
        assert spec.fuel_sensor is True
        assert spec.eco_control is False
        assert spec.guest_mode is True
        assert spec.architecture == Architecture.POLL


class TestEcoModeConstants:
    """Test ECO mode function command constants."""

    def test_eco_mode_function_codes(self) -> None:
        """Test ECO mode function command codes."""
        assert FUNC_START_ECO == 0x1027
        assert FUNC_STOP_ECO == 0x1028

    def test_eco_mode_function_codes_different(self) -> None:
        """Test that ECO mode enable/disable codes are different."""
        assert FUNC_START_ECO != FUNC_STOP_ECO


class TestPushAPICAN:
    """Test Push API CAN message parsing."""

    def test_parse_can_message_inv_info(self, mock_push_api: PushAPI) -> None:
        """Test parsing INV_INFO CAN message."""
        # INV_INFO (0x332): power=1000W, voltage=120V, current=8.33A (4165/500)
        payload = bytes([0xE8, 0x03, 0x78, 0x00, 0x45, 0x10])
        mock_push_api._parse_can_message(0x332, payload)

        assert mock_push_api._state["power_watts"] == 1000
        assert mock_push_api._state["voltage"] == 120
        assert abs(mock_push_api._state["current"] - 8.33) < 0.01

    def test_parse_can_message_ecu_status(self, mock_push_api: PushAPI) -> None:
        """Test parsing ECU_STATUS CAN message."""
        # ECU_STATUS (0x312): engine_mode=1 (running), eco_status=0 (ECO on)
        payload = bytes([0x01, 0x00, 0x00])
        mock_push_api._parse_can_message(0x312, payload)

        assert mock_push_api._state["engine_mode"] == 1
        assert mock_push_api._state["eco_status"] is True

    def test_parse_can_message_inv_info2(self, mock_push_api: PushAPI) -> None:
        """Test parsing INV_INFO2 CAN message."""
        # INV_INFO2 (0x352): runtime_hours=500 at bytes 4-5
        payload = bytes([0x00, 0x00, 0x00, 0x00, 0xF4, 0x01])
        mock_push_api._parse_can_message(0x352, payload)

        assert mock_push_api._state["runtime_hours"] == 500

    def test_parse_can_message_fuel_info(self, mock_push_api: PushAPI) -> None:
        """Test parsing ECU_INFO_ETC CAN message."""
        # ECU_INFO_ETC (0x362): fuel_ml=2000, fuel_remaining=180min, fuel_level=10
        payload = bytes([0xD0, 0x07, 0xB4, 0x00, 0x00, 0x0A])
        mock_push_api._parse_can_message(0x362, payload)

        assert mock_push_api._state["fuel_ml"] == 2000
        assert mock_push_api._state["fuel_remaining_min"] == 180
        assert mock_push_api._state["fuel_level_discrete"] == 10
