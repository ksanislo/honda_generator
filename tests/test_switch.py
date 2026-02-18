"""Tests for Honda Generator switch entities."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.honda_generator.api import DeviceType
from custom_components.honda_generator.coordinator import HondaGeneratorCoordinator
from custom_components.honda_generator.switch import EcoModeSwitch


class TestEcoModeSwitch:
    """Test ECO mode switch."""

    def test_available_when_connected(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test switch is available when API is connected."""
        switch = EcoModeSwitch(entity_coordinator)
        assert switch.available is True

    def test_unavailable_when_disconnected(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test switch is unavailable when API is disconnected."""
        entity_coordinator.api.connected = False
        switch = EcoModeSwitch(entity_coordinator)
        assert switch.available is False

    def test_unavailable_when_no_api(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test switch is unavailable when no API."""
        entity_coordinator.api = None
        switch = EcoModeSwitch(entity_coordinator)
        assert switch.available is False

    def test_is_on_from_device_state(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test is_on returns device state."""
        switch = EcoModeSwitch(entity_coordinator)

        # eco_mode default is True in create_mock_devices
        assert switch.is_on is True

    def test_is_on_false(self, entity_coordinator: HondaGeneratorCoordinator) -> None:
        """Test is_on returns False when eco mode is off."""
        device = entity_coordinator.get_device_by_id(DeviceType.ECO_MODE, 1)
        device.state = False

        switch = EcoModeSwitch(entity_coordinator)
        assert switch.is_on is False

    def test_pending_state_after_turn_on(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test pending state is set after turn_on."""
        device = entity_coordinator.get_device_by_id(DeviceType.ECO_MODE, 1)
        device.state = False

        switch = EcoModeSwitch(entity_coordinator)
        assert switch.is_on is False

        # Manually set pending state (simulating start of turn_on)
        switch._pending_state = True
        assert switch.is_on is True

    def test_pending_state_after_turn_off(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test pending state is set after turn_off."""
        switch = EcoModeSwitch(entity_coordinator)
        assert switch.is_on is True  # eco_mode default is True

        switch._pending_state = False
        assert switch.is_on is False

    def test_pending_cleared_on_coordinator_update(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test pending state is cleared on coordinator update."""
        switch = EcoModeSwitch(entity_coordinator)
        switch._pending_state = True

        # Simulate coordinator update with success
        entity_coordinator.last_update_success = True
        switch._handle_coordinator_update()

        assert switch._pending_state is None

    def test_pending_not_cleared_on_failed_update(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test pending state is NOT cleared on failed coordinator update."""
        switch = EcoModeSwitch(entity_coordinator)
        switch._pending_state = True

        entity_coordinator.last_update_success = False
        switch._handle_coordinator_update()

        assert switch._pending_state is True

    @pytest.mark.asyncio
    async def test_turn_on_calls_set_eco_mode(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test turn_on calls set_eco_mode(True)."""
        switch = EcoModeSwitch(entity_coordinator)

        await switch.async_turn_on()

        entity_coordinator.api.set_eco_mode.assert_called_once_with(True)
        entity_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_turn_off_calls_set_eco_mode(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test turn_off calls set_eco_mode(False)."""
        switch = EcoModeSwitch(entity_coordinator)

        await switch.async_turn_off()

        entity_coordinator.api.set_eco_mode.assert_called_once_with(False)
        entity_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_turn_on_failure_clears_pending(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test pending state is cleared on API failure."""
        entity_coordinator.api.set_eco_mode = AsyncMock(return_value=False)
        switch = EcoModeSwitch(entity_coordinator)

        await switch.async_turn_on()

        assert switch._pending_state is None
        entity_coordinator.async_request_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_off_failure_clears_pending(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test pending state is cleared on API failure during turn_off."""
        entity_coordinator.api.set_eco_mode = AsyncMock(return_value=False)
        switch = EcoModeSwitch(entity_coordinator)

        await switch.async_turn_off()

        assert switch._pending_state is None
        entity_coordinator.async_request_refresh.assert_not_called()
