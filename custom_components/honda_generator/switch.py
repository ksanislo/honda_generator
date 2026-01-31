"""Honda Generator switch for ECO mode control."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import DeviceType, get_model_spec
from .const import DOMAIN
from .entity import HondaGeneratorEntity

if TYPE_CHECKING:
    from . import HondaGeneratorConfigEntry
    from .coordinator import HondaGeneratorCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HondaGeneratorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switches."""
    coordinator = config_entry.runtime_data.coordinator

    entities: list[SwitchEntity] = []

    # Add ECO mode switch only for models with ECO control support
    if coordinator.api:
        model_spec = get_model_spec(coordinator.api.model)
        if model_spec and model_spec.eco_control:
            entities.append(EcoModeSwitch(coordinator))

    async_add_entities(entities)


class EcoModeSwitch(HondaGeneratorEntity, SwitchEntity):
    """Switch to control ECO mode (supported models only)."""

    _attr_translation_key = "eco_mode"
    _attr_icon = "mdi:leaf"

    def __init__(self, coordinator: HondaGeneratorCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{DOMAIN}-{coordinator.data.controller_name}_eco_mode_switch"
        )
        self._pending_state: bool | None = None

    @property
    def available(self) -> bool:
        """Return True if the switch is available."""
        return self.coordinator.api is not None and self.coordinator.api.connected

    @property
    def is_on(self) -> bool | None:
        """Return True if ECO mode is enabled."""
        # If we have a pending state (awaiting confirmation), show that
        if self._pending_state is not None:
            return self._pending_state

        # Get current state from coordinator
        device = self.coordinator.get_device_by_id(DeviceType.ECO_MODE, 1)
        if device is None:
            return None
        return bool(device.state)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Clear pending state when we get fresh data
        if self.coordinator.last_update_success:
            self._pending_state = None
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on ECO mode."""
        if self.coordinator.api is None:
            _LOGGER.error("Cannot enable ECO mode: not connected")
            return
        _LOGGER.info("Enabling ECO mode")
        self._pending_state = True
        self.async_write_ha_state()
        success = await self.coordinator.api.set_eco_mode(True)
        if success:
            _LOGGER.info("ECO mode enable command sent successfully")
            # Trigger a refresh to confirm the state change
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to enable ECO mode")
            self._pending_state = None
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off ECO mode."""
        if self.coordinator.api is None:
            _LOGGER.error("Cannot disable ECO mode: not connected")
            return
        _LOGGER.info("Disabling ECO mode")
        self._pending_state = False
        self.async_write_ha_state()
        success = await self.coordinator.api.set_eco_mode(False)
        if success:
            _LOGGER.info("ECO mode disable command sent successfully")
            # Trigger a refresh to confirm the state change
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to disable ECO mode")
            self._pending_state = None
            self.async_write_ha_state()
