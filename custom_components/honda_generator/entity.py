# Copyright 2024-2026 Ken Sanislo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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

        During the startup grace period, entities report as unavailable to
        preserve dashboard state while waiting for the initial connection.

        After the grace period expires, availability depends on coordinator's
        last_update_success. Entities that want to show offline defaults
        (e.g., false_when_unavailable, zero_when_unavailable) must override
        this method to return True in those cases.
        """
        # Startup grace period - waiting for first connection
        if self.coordinator.in_startup_grace_period:
            return False
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
