"""Base entity for Honda Generator integration."""

import logging

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HondaGeneratorCoordinator

_LOGGER = logging.getLogger(__name__)


class HondaGeneratorEntity(CoordinatorEntity[HondaGeneratorCoordinator]):
    """Base entity for Honda Generator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HondaGeneratorCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._last_known_firmware: str | None = None

    @property
    def available(self) -> bool:
        """Return if entity is available.

        During the startup grace period, entities report as unavailable
        to preserve dashboard state while waiting for the generator.
        After the grace period expires without a connection, entities
        become available showing default offline values.
        """
        if self.coordinator.in_startup_grace_period:
            return False
        if not self.coordinator.has_connected_once:
            # Grace period expired without connection - show defaults as available
            return True
        return super().available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update device registry if firmware version changed from unknown to a real value
        firmware = self.coordinator.data.firmware_version
        if firmware != "unknown" and self._last_known_firmware != firmware:
            self._last_known_firmware = firmware
            self._update_device_registry()
        super()._handle_coordinator_update()

    def _update_device_registry(self) -> None:
        """Update device registry with current data."""
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, self.coordinator.data.controller_name)}
        )
        if device_entry:
            device_registry.async_update_device(
                device_entry.id,
                name=f"{self.coordinator.data.model} ({self.coordinator.data.serial_number})",
                sw_version=self.coordinator.data.firmware_version,
                model=self.coordinator.data.model,
                serial_number=self.coordinator.data.serial_number,
            )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.controller_name)},
            connections={
                (dr.CONNECTION_BLUETOOTH, self.coordinator.data.controller_name)
            },
            name=f"{self.coordinator.data.model} ({self.coordinator.data.serial_number})",
            manufacturer="Honda",
            model=self.coordinator.data.model,
            serial_number=self.coordinator.data.serial_number,
            sw_version=self.coordinator.data.firmware_version,
        )
