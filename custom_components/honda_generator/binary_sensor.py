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

"""Honda Generator binary sensors."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .api import DeviceType, get_model_spec
from .codes import AlertCode, get_fault_codes, get_warning_codes
from .const import DOMAIN
from .entity import HondaGeneratorEntity
from .services import ServiceType, get_model_services, get_service_definition

if TYPE_CHECKING:
    from . import HondaGeneratorConfigEntry
    from .coordinator import HondaGeneratorCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HondaGeneratorBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Honda Generator binary sensor entity."""

    device_type: DeviceType
    false_when_unavailable: bool = False
    icon_on: str | None = None
    icon_off: str | None = None


BINARY_SENSOR_DESCRIPTIONS: tuple[HondaGeneratorBinarySensorEntityDescription, ...] = (
    HondaGeneratorBinarySensorEntityDescription(
        key="eco_mode",
        translation_key="eco_mode",
        device_type=DeviceType.ECO_MODE,
        icon_on="mdi:leaf",
        icon_off="mdi:leaf-off",
    ),
    HondaGeneratorBinarySensorEntityDescription(
        key="engine_status",
        translation_key="engine_status",
        device_type=DeviceType.ENGINE_RUNNING,
        device_class=BinarySensorDeviceClass.RUNNING,
        false_when_unavailable=True,
        icon_on="mdi:engine",
        icon_off="mdi:engine-off",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HondaGeneratorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator = config_entry.runtime_data.coordinator

    # Check if model has ECO control (switch) - if so, skip ECO binary sensor
    model_spec = get_model_spec(coordinator.data.model) if coordinator.data else None
    has_eco_control = model_spec and model_spec.eco_control

    entities: list[BinarySensorEntity] = [
        HondaGeneratorBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
        if not (description.device_type == DeviceType.ECO_MODE and has_eco_control)
    ]

    # Model-specific warning sensors
    for alert_code in get_warning_codes(coordinator.data.model):
        entities.append(
            HondaGeneratorAlertBinarySensor(coordinator, alert_code, is_fault=False)
        )

    # Model-specific fault sensors
    for alert_code in get_fault_codes(coordinator.data.model):
        entities.append(
            HondaGeneratorAlertBinarySensor(coordinator, alert_code, is_fault=True)
        )

    # Service due binary sensors (model-specific)
    model_services = get_model_services(coordinator.data.model)
    for service_type in model_services:
        entities.append(ServiceDueBinarySensor(coordinator, service_type))

    async_add_entities(entities)


class HondaGeneratorBinarySensor(HondaGeneratorEntity, BinarySensorEntity):
    """Honda Generator binary sensor entity."""

    entity_description: HondaGeneratorBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: HondaGeneratorCoordinator,
        description: HondaGeneratorBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{DOMAIN}-{coordinator.data.controller_name}_{description.key}"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        self.async_write_ha_state()

    def _get_device_state(self) -> bool:
        """Get the current device state from coordinator."""
        device = self.coordinator.get_device_by_id(
            self.entity_description.device_type, 1
        )
        return bool(device.state) if device else False

    @property
    def is_on(self) -> bool:
        """Return if the binary sensor is on."""
        if self.coordinator.last_update_success:
            return self._get_device_state()
        if self.entity_description.false_when_unavailable:
            return False
        return self._get_device_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        Sensors with false_when_unavailable stay available to show offline
        defaults (False) when not connected. Other sensors (like ECO mode)
        become unavailable when not connected.
        """
        # Grace periods take priority - show unavailable while reconnecting
        if self.coordinator.in_startup_grace_period:
            return False
        if self.coordinator.in_reconnect_grace_period:
            return False
        # Sensors with false_when_unavailable stay available to show offline default
        if self.entity_description.false_when_unavailable:
            return True
        # Regular sensors (like ECO mode) follow coordinator availability
        return super().available

    @property
    def icon(self) -> str | None:
        """Return the icon based on state."""
        desc = self.entity_description
        if desc.icon_on and desc.icon_off:
            return desc.icon_on if self.is_on else desc.icon_off
        return None


class HondaGeneratorAlertBinarySensor(
    HondaGeneratorEntity, RestoreEntity, BinarySensorEntity
):
    """Binary sensor for a model-specific warning or fault code."""

    def __init__(
        self,
        coordinator: HondaGeneratorCoordinator,
        alert_code: AlertCode,
        is_fault: bool,
    ) -> None:
        """Initialize the alert binary sensor."""
        super().__init__(coordinator)
        self._alert_code = alert_code
        self._is_fault = is_fault
        prefix = "fault" if is_fault else "warning"
        self._attr_unique_id = (
            f"{DOMAIN}-{coordinator.data.controller_name}_{prefix}_{alert_code.code}"
        )
        # Use translation key for proper HA localization
        code_key = alert_code.code.lower().replace("-", "_")
        self._attr_translation_key = f"{prefix}_{code_key}"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = False
        self._restored_value: bool | None = None
        self._restored_last_update: datetime | None = None
        self._last_live_value: bool | None = None
        self._first_update_attempted = False

    async def async_added_to_hass(self) -> None:
        """Restore last state when added to hass."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (
            None,
            "unknown",
            "unavailable",
        ):
            self._restored_value = last_state.state == "on"
            if last_state.attributes.get("last_update"):
                try:
                    self._restored_last_update = datetime.fromisoformat(
                        last_state.attributes["last_update"]
                    )
                except (ValueError, TypeError):
                    self._restored_last_update = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        if not self._first_update_attempted:
            self._first_update_attempted = True

        # When we get live data, save it and clear restored value
        if self.coordinator.last_update_success and self.coordinator.api:
            if self._is_fault:
                self._last_live_value = self.coordinator.api.get_fault_bit(
                    self._alert_code.bit
                )
            else:
                self._last_live_value = self.coordinator.api.get_warning_bit(
                    self._alert_code.bit
                )
            if self._restored_value is not None:
                self._restored_value = None
                self._restored_last_update = None

        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return if the binary sensor is on.

        Returns live data when connected. When offline, persists the last
        known value so alarm states remain visible after generator shuts off.
        """
        if self.coordinator.last_update_success and self.coordinator.api:
            if self._is_fault:
                return self.coordinator.api.get_fault_bit(self._alert_code.bit)
            return self.coordinator.api.get_warning_bit(self._alert_code.bit)

        # Don't use persisted value until we've tried to get fresh data
        if not self._first_update_attempted:
            return None

        # Use best available offline value
        if self._last_live_value is not None:
            return self._last_live_value
        if self._restored_value is not None:
            return self._restored_value
        return None

    @property
    def available(self) -> bool:
        """Return True when we have live or persisted data.

        Persists availability after first update so alarm states remain
        visible when the generator goes offline.
        """
        # Grace periods take priority - show unavailable while reconnecting
        if self.coordinator.in_startup_grace_period:
            return False
        if self.coordinator.in_reconnect_grace_period:
            return False
        if self.coordinator.last_update_success:
            return True
        # After first update attempt, available if we have persisted data
        if not self._first_update_attempted:
            return False
        if self._last_live_value is not None:
            return True
        if self._restored_value is not None:
            return True
        return False

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        state = self.is_on
        if self._is_fault:
            return "mdi:alert-circle" if state else "mdi:check-circle"
        return "mdi:alert" if state else "mdi:check-circle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {"code": self._alert_code.code}

        if self.coordinator.last_update_success:
            if self.coordinator.data.last_update:
                attrs["last_update"] = self.coordinator.data.last_update.isoformat()
            attrs["data_stale"] = False
        else:
            if self._restored_last_update:
                attrs["last_update"] = self._restored_last_update.isoformat()
            elif self.coordinator.data and self.coordinator.data.last_update:
                attrs["last_update"] = self.coordinator.data.last_update.isoformat()
            attrs["data_stale"] = True

        return attrs


class ServiceDueBinarySensor(HondaGeneratorEntity, BinarySensorEntity):
    """Binary sensor for service due status."""

    def __init__(
        self,
        coordinator: HondaGeneratorCoordinator,
        service_type: ServiceType,
    ) -> None:
        """Initialize the service due binary sensor."""
        super().__init__(coordinator)
        self._service_type = service_type
        service_def = get_service_definition(service_type)
        self._attr_unique_id = (
            f"{DOMAIN}-{coordinator.data.controller_name}_service_{service_type.value}"
        )
        self._attr_name = f"{service_def.name} Due"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = service_def.icon
        # Only oil change services enabled by default
        self._attr_entity_registry_enabled_default = service_def.enabled_by_default

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return True if service is due."""
        return self.coordinator.is_service_due(self._service_type)

    @property
    def available(self) -> bool:
        """Return True - service sensors are always available."""
        # Service due status is based on stored data, always available
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        record = self.coordinator.get_service_record(self._service_type)
        service_def = get_service_definition(self._service_type)
        model_services = get_model_services(self.coordinator.data.model)
        interval = model_services.get(self._service_type)

        attrs: dict[str, Any] = {
            "service_type": self._service_type.value,
        }

        if interval:
            if interval.hours:
                attrs["interval_hours"] = interval.hours
            if interval.days:
                attrs["interval_days"] = interval.days

        if record:
            attrs["last_service_hours"] = record.get("hours")
            attrs["last_service_date"] = record.get("date")
        else:
            attrs["last_service_hours"] = None
            attrs["last_service_date"] = None

        if service_def.is_dealer_service:
            attrs["dealer_service"] = True

        return attrs
