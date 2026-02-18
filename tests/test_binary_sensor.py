"""Tests for Honda Generator binary sensor entities."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from custom_components.honda_generator.api import DeviceType
from custom_components.honda_generator.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    HondaGeneratorAlertBinarySensor,
    HondaGeneratorBinarySensor,
    ServiceDueBinarySensor,
)
from custom_components.honda_generator.codes import AlertCode
from custom_components.honda_generator.coordinator import HondaGeneratorCoordinator
from custom_components.honda_generator.services import ServiceType


def _get_binary_description(key: str):
    """Get a binary sensor description by key."""
    for desc in BINARY_SENSOR_DESCRIPTIONS:
        if desc.key == key:
            return desc
    raise ValueError(f"Description not found: {key}")


class TestHondaGeneratorBinarySensor:
    """Test basic binary sensor."""

    def test_is_on_from_device_state(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test is_on returns device state."""
        desc = _get_binary_description("engine_status")
        sensor = HondaGeneratorBinarySensor(entity_coordinator, desc)

        # engine_running default is True in create_mock_devices
        assert sensor.is_on is True

    def test_is_on_false(self, entity_coordinator: HondaGeneratorCoordinator) -> None:
        """Test is_on returns False when device state is False."""
        desc = _get_binary_description("engine_status")
        sensor = HondaGeneratorBinarySensor(entity_coordinator, desc)

        device = entity_coordinator.get_device_by_id(DeviceType.ENGINE_RUNNING, 1)
        device.state = False

        assert sensor.is_on is False

    def test_false_when_unavailable(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test false_when_unavailable returns False when offline."""
        desc = _get_binary_description("engine_status")
        assert desc.false_when_unavailable is True
        sensor = HondaGeneratorBinarySensor(entity_coordinator, desc)

        entity_coordinator.last_update_success = False
        assert sensor.is_on is False

    def test_false_when_unavailable_stays_available(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test sensor with false_when_unavailable stays available."""
        desc = _get_binary_description("engine_status")
        sensor = HondaGeneratorBinarySensor(entity_coordinator, desc)

        entity_coordinator.last_update_success = False
        entity_coordinator._has_connected_once = True

        assert sensor.available is True

    def test_icon_on(self, entity_coordinator: HondaGeneratorCoordinator) -> None:
        """Test icon switches based on state - on."""
        desc = _get_binary_description("engine_status")
        sensor = HondaGeneratorBinarySensor(entity_coordinator, desc)

        # engine_running=True
        assert sensor.icon == "mdi:engine"

    def test_icon_off(self, entity_coordinator: HondaGeneratorCoordinator) -> None:
        """Test icon switches based on state - off."""
        desc = _get_binary_description("engine_status")
        sensor = HondaGeneratorBinarySensor(entity_coordinator, desc)

        device = entity_coordinator.get_device_by_id(DeviceType.ENGINE_RUNNING, 1)
        device.state = False

        assert sensor.icon == "mdi:engine-off"

    def test_eco_mode_icon(self, entity_coordinator: HondaGeneratorCoordinator) -> None:
        """Test eco_mode sensor icon switching."""
        desc = _get_binary_description("eco_mode")
        sensor = HondaGeneratorBinarySensor(entity_coordinator, desc)

        # eco_mode default is True
        assert sensor.icon == "mdi:leaf"

    def test_startup_grace_unavailable(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test binary sensor is unavailable during startup grace."""
        entity_coordinator._has_connected_once = False
        entity_coordinator._startup_time = time.monotonic()
        entity_coordinator._startup_grace_period = 60

        desc = _get_binary_description("engine_status")
        sensor = HondaGeneratorBinarySensor(entity_coordinator, desc)

        assert sensor.available is False

    def test_eco_mode_unavailable_when_offline(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test eco_mode (not false_when_unavailable) follows coordinator availability."""
        desc = _get_binary_description("eco_mode")
        assert desc.false_when_unavailable is False
        sensor = HondaGeneratorBinarySensor(entity_coordinator, desc)

        entity_coordinator.last_update_success = False

        # Without false_when_unavailable, follows super().available
        assert sensor.available is False


class TestHondaGeneratorAlertBinarySensor:
    """Test alert binary sensor (warnings/faults)."""

    def test_warning_calls_get_warning_bit(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test warning sensor calls get_warning_bit on API."""
        alert = AlertCode(bit=2, code="C-03")
        sensor = HondaGeneratorAlertBinarySensor(
            entity_coordinator, alert, is_fault=False
        )

        entity_coordinator.api.get_warning_bit.return_value = True
        assert sensor.is_on is True
        entity_coordinator.api.get_warning_bit.assert_called_with(2)

    def test_fault_calls_get_fault_bit(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test fault sensor calls get_fault_bit on API."""
        alert = AlertCode(bit=1, code="E-12")
        sensor = HondaGeneratorAlertBinarySensor(
            entity_coordinator, alert, is_fault=True
        )

        entity_coordinator.api.get_fault_bit.return_value = True
        assert sensor.is_on is True
        entity_coordinator.api.get_fault_bit.assert_called_with(1)

    def test_fallback_to_last_live_value(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test fallback to last live value when offline."""
        alert = AlertCode(bit=2, code="C-03")
        sensor = HondaGeneratorAlertBinarySensor(
            entity_coordinator, alert, is_fault=False
        )
        sensor._first_update_attempted = True

        # Simulate a live update
        entity_coordinator.api.get_warning_bit.return_value = True
        sensor._handle_coordinator_update()
        assert sensor._last_live_value is True

        # Go offline
        entity_coordinator.last_update_success = False
        entity_coordinator.api = None
        assert sensor.is_on is True

    def test_fallback_to_restored(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test fallback to restored value."""
        alert = AlertCode(bit=2, code="C-03")
        sensor = HondaGeneratorAlertBinarySensor(
            entity_coordinator, alert, is_fault=False
        )
        sensor._first_update_attempted = True
        sensor._restored_value = True

        entity_coordinator.last_update_success = False
        entity_coordinator.api = None
        assert sensor.is_on is True

    def test_code_attribute(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test code attribute in extra_state_attributes."""
        alert = AlertCode(bit=2, code="C-03")
        sensor = HondaGeneratorAlertBinarySensor(
            entity_coordinator, alert, is_fault=False
        )

        attrs = sensor.extra_state_attributes
        assert attrs["code"] == "C-03"

    def test_data_stale_attribute(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test data_stale attribute."""
        alert = AlertCode(bit=2, code="C-03")
        sensor = HondaGeneratorAlertBinarySensor(
            entity_coordinator, alert, is_fault=False
        )

        attrs = sensor.extra_state_attributes
        assert attrs["data_stale"] is False

        entity_coordinator.last_update_success = False
        attrs = sensor.extra_state_attributes
        assert attrs["data_stale"] is True

    def test_icon_warning_on(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test warning icon when on."""
        alert = AlertCode(bit=2, code="C-03")
        sensor = HondaGeneratorAlertBinarySensor(
            entity_coordinator, alert, is_fault=False
        )

        entity_coordinator.api.get_warning_bit.return_value = True
        assert sensor.icon == "mdi:alert"

    def test_icon_fault_on(self, entity_coordinator: HondaGeneratorCoordinator) -> None:
        """Test fault icon when on."""
        alert = AlertCode(bit=1, code="E-12")
        sensor = HondaGeneratorAlertBinarySensor(
            entity_coordinator, alert, is_fault=True
        )

        entity_coordinator.api.get_fault_bit.return_value = True
        assert sensor.icon == "mdi:alert-circle"

    def test_icon_off(self, entity_coordinator: HondaGeneratorCoordinator) -> None:
        """Test icon when off."""
        alert = AlertCode(bit=2, code="C-03")
        sensor = HondaGeneratorAlertBinarySensor(
            entity_coordinator, alert, is_fault=False
        )

        entity_coordinator.api.get_warning_bit.return_value = False
        assert sensor.icon == "mdi:check-circle"


class TestServiceDueBinarySensor:
    """Test service due binary sensor."""

    def test_delegates_to_coordinator(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test is_on delegates to coordinator.is_service_due."""
        entity_coordinator.is_service_due = MagicMock(return_value=True)
        sensor = ServiceDueBinarySensor(entity_coordinator, ServiceType.OIL_CHANGE)

        assert sensor.is_on is True
        entity_coordinator.is_service_due.assert_called_with(ServiceType.OIL_CHANGE)

    def test_not_due(self, entity_coordinator: HondaGeneratorCoordinator) -> None:
        """Test is_on is False when service is not due."""
        entity_coordinator.is_service_due = MagicMock(return_value=False)
        sensor = ServiceDueBinarySensor(entity_coordinator, ServiceType.OIL_CHANGE)

        assert sensor.is_on is False

    def test_always_available(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test service sensor is always available."""
        entity_coordinator.last_update_success = False
        sensor = ServiceDueBinarySensor(entity_coordinator, ServiceType.OIL_CHANGE)

        assert sensor.available is True

    def test_attributes_with_record(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test extra_state_attributes with service record."""
        entity_coordinator.get_service_record = MagicMock(
            return_value={"hours": 100, "date": "2025-01-01T00:00:00"}
        )
        entity_coordinator.get_estimated_service_date = MagicMock(return_value=None)
        entity_coordinator._stored_runtime_hours = 150

        sensor = ServiceDueBinarySensor(entity_coordinator, ServiceType.OIL_CHANGE)
        attrs = sensor.extra_state_attributes

        assert attrs["last_service_hours"] == 100
        assert attrs["last_service_date"] == "2025-01-01T00:00:00"
        assert attrs["service_type"] == "oil_change"

    def test_attributes_without_record(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test extra_state_attributes without service record."""
        entity_coordinator.get_service_record = MagicMock(return_value=None)
        entity_coordinator.get_estimated_service_date = MagicMock(return_value=None)

        sensor = ServiceDueBinarySensor(entity_coordinator, ServiceType.OIL_CHANGE)
        attrs = sensor.extra_state_attributes

        assert attrs["last_service_hours"] is None
        assert attrs["last_service_date"] is None

    def test_oil_change_enabled_by_default(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test oil change sensor is enabled by default."""
        sensor = ServiceDueBinarySensor(entity_coordinator, ServiceType.OIL_CHANGE)
        assert sensor._attr_entity_registry_enabled_default is True

    def test_other_service_disabled_by_default(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test non-oil-change service sensor is disabled by default."""
        sensor = ServiceDueBinarySensor(
            entity_coordinator, ServiceType.AIR_FILTER_CLEAN
        )
        assert sensor._attr_entity_registry_enabled_default is False
