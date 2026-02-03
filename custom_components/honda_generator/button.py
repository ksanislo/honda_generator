"""Honda Generator button for engine control."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import get_model_spec
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
    """Set up the buttons."""
    coordinator = config_entry.runtime_data.coordinator

    entities: list[ButtonEntity] = [EngineStopButton(coordinator)]

    # Add engine start button only for models with remote start support
    if coordinator.api:
        model_spec = get_model_spec(coordinator.api.model)
        if model_spec and model_spec.remote_start:
            entities.append(EngineStartButton(coordinator))

    async_add_entities(entities)


class EngineStopButton(HondaGeneratorEntity, ButtonEntity):
    """Button to stop the generator engine."""

    _attr_translation_key = "stop_engine"
    _attr_icon = "mdi:engine-off"

    def __init__(self, coordinator: HondaGeneratorCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{DOMAIN}-{coordinator.data.controller_name}_engine_stop"
        )

    @property
    def available(self) -> bool:
        """Return True if the button is available."""
        return self.coordinator.api is not None and self.coordinator.api.connected

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.coordinator.api is None:
            _LOGGER.error("Cannot stop engine: not connected")
            return
        _LOGGER.info("Stopping generator engine")
        # Flag intentional disconnect to skip grace period when generator shuts down
        # This must be set BEFORE the command as the BT controller may disconnect immediately
        self.coordinator.set_intentional_disconnect()
        success = await self.coordinator.api.engine_stop()
        if success:
            _LOGGER.info("Engine stop command sent successfully")
            # Trigger a refresh to update entity states
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to send engine stop command")


class EngineStartButton(HondaGeneratorEntity, ButtonEntity):
    """Button to start the generator engine (remote start models only)."""

    _attr_translation_key = "start_engine"
    _attr_icon = "mdi:engine"

    def __init__(self, coordinator: HondaGeneratorCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{DOMAIN}-{coordinator.data.controller_name}_engine_start"
        )

    @property
    def available(self) -> bool:
        """Return True if the button is available."""
        return self.coordinator.api is not None and self.coordinator.api.connected

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.coordinator.api is None:
            _LOGGER.error("Cannot start engine: not connected")
            return
        _LOGGER.info("Starting generator engine")
        success = await self.coordinator.api.engine_start()
        if success:
            _LOGGER.info("Engine start command sent successfully")
            # Trigger a refresh to update entity states
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to send engine start command")
