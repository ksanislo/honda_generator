"""Tests for Honda Generator button entities."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.honda_generator.button import (
    EngineStartButton,
    EngineStopButton,
    ServiceCompleteButton,
)
from custom_components.honda_generator.coordinator import HondaGeneratorCoordinator
from custom_components.honda_generator.services import ServiceType


class TestEngineStopButton:
    """Test engine stop button."""

    def test_available_when_connected(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test button is available when API is connected."""
        button = EngineStopButton(entity_coordinator)
        assert button.available is True

    def test_unavailable_when_disconnected(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test button is unavailable when API is disconnected."""
        entity_coordinator.api.connected = False
        button = EngineStopButton(entity_coordinator)
        assert button.available is False

    def test_unavailable_when_no_api(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test button is unavailable when no API."""
        entity_coordinator.api = None
        button = EngineStopButton(entity_coordinator)
        assert button.available is False

    @pytest.mark.asyncio
    async def test_press_calls_stop(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test pressing calls stop_diagnostics, engine_stop, and refresh."""
        button = EngineStopButton(entity_coordinator)

        await button.async_press()

        entity_coordinator.api.stop_diagnostics.assert_called_once()
        entity_coordinator.api.engine_stop.assert_called_once_with(
            max_attempts=entity_coordinator.stop_attempts
        )
        entity_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_press_failure_no_refresh(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test no refresh when engine_stop fails."""
        entity_coordinator.api.engine_stop = AsyncMock(return_value=False)
        button = EngineStopButton(entity_coordinator)

        await button.async_press()

        entity_coordinator.api.stop_diagnostics.assert_called_once()
        entity_coordinator.async_request_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_press_no_api(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test pressing with no API does nothing."""
        entity_coordinator.api = None
        button = EngineStopButton(entity_coordinator)

        await button.async_press()  # Should not raise


class TestEngineStartButton:
    """Test engine start button."""

    def test_available_when_connected(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test button is available when API is connected."""
        button = EngineStartButton(entity_coordinator)
        assert button.available is True

    def test_unavailable_when_disconnected(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test button is unavailable when API is disconnected."""
        entity_coordinator.api.connected = False
        button = EngineStartButton(entity_coordinator)
        assert button.available is False

    @pytest.mark.asyncio
    async def test_press_calls_start(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test pressing calls engine_start and refresh."""
        button = EngineStartButton(entity_coordinator)

        await button.async_press()

        entity_coordinator.api.engine_start.assert_called_once()
        entity_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_press_failure_no_refresh(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test no refresh when engine_start fails."""
        entity_coordinator.api.engine_start = AsyncMock(return_value=False)
        button = EngineStartButton(entity_coordinator)

        await button.async_press()

        entity_coordinator.async_request_refresh.assert_not_called()


class TestServiceCompleteButton:
    """Test service complete button."""

    def test_always_available(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test service button is always available."""
        entity_coordinator.last_update_success = False
        entity_coordinator.api = None
        button = ServiceCompleteButton(entity_coordinator, ServiceType.OIL_CHANGE)

        assert button.available is True

    def test_entity_category_config(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test entity_category is CONFIG."""
        from homeassistant.const import EntityCategory

        button = ServiceCompleteButton(entity_coordinator, ServiceType.OIL_CHANGE)
        assert button._attr_entity_category == EntityCategory.CONFIG

    @pytest.mark.asyncio
    async def test_press_calls_mark_service_complete(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test pressing calls async_mark_service_complete."""
        entity_coordinator.async_mark_service_complete = AsyncMock()
        button = ServiceCompleteButton(entity_coordinator, ServiceType.OIL_CHANGE)

        await button.async_press()

        entity_coordinator.async_mark_service_complete.assert_called_once_with(
            ServiceType.OIL_CHANGE
        )

    def test_oil_change_enabled_by_default(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test oil change button is enabled by default."""
        button = ServiceCompleteButton(entity_coordinator, ServiceType.OIL_CHANGE)
        assert button._attr_entity_registry_enabled_default is True

    def test_other_service_disabled_by_default(
        self, entity_coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Test non-oil-change button is disabled by default."""
        button = ServiceCompleteButton(entity_coordinator, ServiceType.AIR_FILTER_CLEAN)
        assert button._attr_entity_registry_enabled_default is False
