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

"""Honda Generator sensors."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .api import (
    ENGINE_ERROR_KEYS,
    ENGINE_ERROR_OPTIONS,
    ENGINE_EVENT_KEYS,
    ENGINE_EVENT_OPTIONS,
    Architecture,
    DeviceType,
    get_model_spec,
)
from .const import CONF_ARCHITECTURE, DOMAIN
from .entity import HondaGeneratorEntity

if TYPE_CHECKING:
    from . import HondaGeneratorConfigEntry
    from .coordinator import HondaGeneratorCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HondaGeneratorSensorEntityDescription(SensorEntityDescription):
    """Describes a Honda Generator sensor entity."""

    device_type: DeviceType
    zero_when_unavailable: bool = False
    persist_value: bool = False
    enum_keys: dict[int, str] | None = None  # Maps int values to translation keys


POLL_SENSOR_DESCRIPTIONS: tuple[HondaGeneratorSensorEntityDescription, ...] = (
    HondaGeneratorSensorEntityDescription(
        key="runtime_hours",
        translation_key="runtime_hours",
        device_type=DeviceType.RUNTIME_HOURS,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        icon="mdi:timer",
        persist_value=True,
    ),
    HondaGeneratorSensorEntityDescription(
        key="output_current",
        translation_key="output_current",
        device_type=DeviceType.CURRENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        zero_when_unavailable=True,
    ),
    HondaGeneratorSensorEntityDescription(
        key="output_power",
        translation_key="output_power",
        device_type=DeviceType.POWER,
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        zero_when_unavailable=True,
    ),
    HondaGeneratorSensorEntityDescription(
        key="output_voltage",
        translation_key="output_voltage",
        device_type=DeviceType.OUTPUT_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        zero_when_unavailable=True,
    ),
    HondaGeneratorSensorEntityDescription(
        key="engine_event",
        translation_key="engine_event",
        device_type=DeviceType.ENGINE_EVENT,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=ENGINE_EVENT_OPTIONS,
        icon="mdi:engine",
        enum_keys=ENGINE_EVENT_KEYS,
    ),
    HondaGeneratorSensorEntityDescription(
        key="engine_error",
        translation_key="engine_error",
        device_type=DeviceType.ENGINE_ERROR,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=ENGINE_ERROR_OPTIONS,
        icon="mdi:alert-octagon",
        enum_keys=ENGINE_ERROR_KEYS,
    ),
)

# Fuel sensors only available on models with fuel sensor support (e.g., EU7000is)
FUEL_SENSOR_DESCRIPTIONS: tuple[HondaGeneratorSensorEntityDescription, ...] = (
    HondaGeneratorSensorEntityDescription(
        key="fuel_level",
        translation_key="fuel_level",
        device_type=DeviceType.FUEL_LEVEL,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:fuel",
        persist_value=True,
    ),
    HondaGeneratorSensorEntityDescription(
        key="fuel_remaining_time",
        translation_key="fuel_remaining_time",
        device_type=DeviceType.FUEL_REMAINING_TIME,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:timer-outline",
    ),
)

# Sensors for Push architecture (common sensors like runtime_hours, current, power, voltage)
PUSH_SENSOR_DESCRIPTIONS: tuple[HondaGeneratorSensorEntityDescription, ...] = (
    HondaGeneratorSensorEntityDescription(
        key="runtime_hours",
        translation_key="runtime_hours",
        device_type=DeviceType.RUNTIME_HOURS,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        icon="mdi:timer",
        persist_value=True,
    ),
    HondaGeneratorSensorEntityDescription(
        key="output_current",
        translation_key="output_current",
        device_type=DeviceType.CURRENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        zero_when_unavailable=True,
    ),
    HondaGeneratorSensorEntityDescription(
        key="output_power",
        translation_key="output_power",
        device_type=DeviceType.POWER,
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        zero_when_unavailable=True,
    ),
    HondaGeneratorSensorEntityDescription(
        key="output_voltage",
        translation_key="output_voltage",
        device_type=DeviceType.OUTPUT_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        zero_when_unavailable=True,
    ),
)

# EU3200i-specific sensors (Push architecture)
EU3200I_SENSOR_DESCRIPTIONS: tuple[HondaGeneratorSensorEntityDescription, ...] = (
    HondaGeneratorSensorEntityDescription(
        key="fuel_level",
        translation_key="fuel_level",
        device_type=DeviceType.FUEL_LEVEL,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:fuel",
        persist_value=True,
    ),
    HondaGeneratorSensorEntityDescription(
        key="fuel_volume",
        translation_key="fuel_volume",
        device_type=DeviceType.FUEL_VOLUME_ML,
        native_unit_of_measurement="mL",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:fuel",
        persist_value=True,
    ),
    HondaGeneratorSensorEntityDescription(
        key="fuel_gauge_level",
        translation_key="fuel_gauge_level",
        device_type=DeviceType.FUEL_REMAINS_LEVEL,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:gauge",
        persist_value=True,
    ),
    HondaGeneratorSensorEntityDescription(
        key="fuel_remaining_time",
        translation_key="fuel_remaining_time",
        device_type=DeviceType.FUEL_REMAINING_TIME,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:timer-outline",
    ),
    HondaGeneratorSensorEntityDescription(
        key="output_voltage_setting",
        translation_key="output_voltage_setting",
        device_type=DeviceType.OUTPUT_VOLTAGE_SETTING,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=0,
        icon="mdi:flash",
        persist_value=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HondaGeneratorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = config_entry.runtime_data.coordinator

    # Detect architecture from config entry
    architecture = Architecture(
        config_entry.data.get(CONF_ARCHITECTURE, Architecture.POLL)
    )

    def _create_sensor(
        desc: HondaGeneratorSensorEntityDescription,
    ) -> SensorEntity:
        """Create the appropriate sensor class based on description flags."""
        if desc.persist_value and desc.state_class == SensorStateClass.TOTAL_INCREASING:
            return HondaGeneratorPersistentSensor(coordinator, desc)
        if desc.persist_value:
            return HondaGeneratorPersistentMeasurementSensor(coordinator, desc)
        if desc.enum_keys is not None:
            return HondaGeneratorPersistentEnumSensor(coordinator, desc)
        return HondaGeneratorSensor(coordinator, desc)

    entities: list[SensorEntity] = []

    if architecture == Architecture.PUSH:
        # Push architecture (EU3200i): Use Push-specific sensor descriptions
        for description in PUSH_SENSOR_DESCRIPTIONS:
            entities.append(_create_sensor(description))

        # Add EU3200i-specific sensors
        for description in EU3200I_SENSOR_DESCRIPTIONS:
            entities.append(_create_sensor(description))
    else:
        # Poll architecture: Use standard sensor descriptions
        for description in POLL_SENSOR_DESCRIPTIONS:
            entities.append(_create_sensor(description))

        # Add fuel sensors only for models with fuel sensor support
        if coordinator.api:
            model_spec = get_model_spec(coordinator.api.model)
            if model_spec and model_spec.fuel_sensor:
                for description in FUEL_SENSOR_DESCRIPTIONS:
                    entities.append(_create_sensor(description))

    async_add_entities(entities)


class HondaGeneratorSensor(HondaGeneratorEntity, SensorEntity):
    """Honda Generator sensor entity."""

    entity_description: HondaGeneratorSensorEntityDescription

    def __init__(
        self,
        coordinator: HondaGeneratorCoordinator,
        description: HondaGeneratorSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{DOMAIN}-{coordinator.data.controller_name}_{description.key}"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        self.async_write_ha_state()

    def _get_device_state(self) -> int | float | None:
        """Get the current device state from coordinator."""
        device = self.coordinator.get_device_by_id(
            self.entity_description.device_type, 1
        )
        if device is None:
            return 0
        # None state means bounds check failed - sensor should be unavailable
        if device.state is None:
            return None
        return device.state

    @property
    def native_value(self) -> int | float | str | None:
        """Return the state of the sensor."""
        state = self._get_device_state()
        # None state (bounds check failure) always returns None for unavailable
        if state is None:
            return None

        # For enum sensors, convert int state to translation key string
        if self.entity_description.enum_keys is not None:
            if self.coordinator.last_update_success:
                int_state = int(state)
            elif self.entity_description.zero_when_unavailable:
                int_state = 0
            else:
                int_state = int(state)
            return self.entity_description.enum_keys.get(
                int_state, f"unknown_{int_state}"
            )

        if self.coordinator.last_update_success:
            return state
        if self.entity_description.zero_when_unavailable:
            return 0
        return state

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        Sensors with zero_when_unavailable stay available to show offline
        defaults (0) when not connected. Other sensors become unavailable.
        """
        # Grace periods take priority - show unavailable while reconnecting
        if self.coordinator.in_startup_grace_period:
            return False
        if self.coordinator.in_reconnect_grace_period:
            return False
        # Sensors with zero_when_unavailable stay available to show offline default
        if self.entity_description.zero_when_unavailable:
            # But still unavailable if bounds check failed while connected
            if (
                self.coordinator.last_update_success
                and self._get_device_state() is None
            ):
                return False
            return True
        # If state is None (bounds check failed), sensor is unavailable
        if self._get_device_state() is None:
            return False
        # Regular sensors follow coordinator availability
        return super().available


class HondaGeneratorPersistentSensor(HondaGeneratorEntity, RestoreEntity, SensorEntity):
    """Honda Generator sensor that persists its last value when unavailable.

    For TOTAL_INCREASING sensors like runtime_hours, the restored value is only
    used after we've attempted to connect and failed. This prevents showing stale
    restored values immediately on HA restart before we've confirmed the current
    value, which would cause incorrect spikes in history graphs.
    """

    entity_description: HondaGeneratorSensorEntityDescription

    def __init__(
        self,
        coordinator: HondaGeneratorCoordinator,
        description: HondaGeneratorSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{DOMAIN}-{coordinator.data.controller_name}_{description.key}"
        )
        self._restored_value: int | float | None = None
        self._restored_last_update: datetime | None = None
        self._restoration_complete = False
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
            try:
                self._restored_value = float(last_state.state)
                _LOGGER.debug(
                    "Restored %s value: %s",
                    self.entity_description.key,
                    self._restored_value,
                )
                if last_state.attributes.get("last_update"):
                    self._restored_last_update = datetime.fromisoformat(
                        last_state.attributes["last_update"]
                    )
            except (ValueError, TypeError):
                self._restored_value = None
        self._restoration_complete = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        # Mark that we've attempted at least one update
        if not self._first_update_attempted:
            self._first_update_attempted = True
            _LOGGER.debug(
                "First update attempted for %s (success: %s)",
                self.entity_description.key,
                self.coordinator.last_update_success,
            )

        # If we get a successful update with a valid value, clear the restored value
        # to prevent it from being used again (the live data is now authoritative)
        if self.coordinator.last_update_success:
            if self._restored_value is not None:
                live_value = self._get_device_state()
                _LOGGER.debug(
                    "Clearing restored value for %s (restored: %s, live: %s)",
                    self.entity_description.key,
                    self._restored_value,
                    live_value,
                )
                self._restored_value = None
                self._restored_last_update = None

        self.async_write_ha_state()

    def _get_device_state(self) -> int | float | None:
        """Get the current device state from coordinator."""
        device = self.coordinator.get_device_by_id(
            self.entity_description.device_type, 1
        )
        return device.state if device else None

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor.

        When connected, use live data. When offline, use the best available
        fallback value. For runtime_hours (total_increasing), this means
        using the maximum of restored and stored values to avoid backwards jumps.
        """
        if self.coordinator.last_update_success:
            return self._get_device_state()

        # Don't use restored/stored value until we've tried to get fresh data
        if not self._first_update_attempted:
            return None

        # Use the best available offline value
        # For runtime_hours, prefer the higher value (stored is high-water mark)
        restored = self._restored_value
        stored = self.coordinator.stored_runtime_hours

        if restored is not None and stored is not None:
            # Use whichever is greater (runtime hours should never decrease)
            return max(restored, stored)
        if stored is not None:
            return stored
        if restored is not None:
            return restored

        if not self._restoration_complete:
            return None
        return self._get_device_state()

    @property
    def available(self) -> bool:
        """Return True if we have any data (live, restored, or stored).

        Returns unavailable until we've attempted the first update, to prevent
        restored values from being recorded before we've tried to get fresh data.
        Respects grace periods during reconnection attempts.
        """
        # Grace periods take priority - show unavailable while reconnecting
        if self.coordinator.in_startup_grace_period:
            return False
        if self.coordinator.in_reconnect_grace_period:
            return False

        if self.coordinator.last_update_success:
            return True

        # Don't report as available until we've tried to get fresh data
        if not self._first_update_attempted:
            return False

        # After first update attempt, available if we have restored data
        if self._restored_value is not None:
            return True

        # Fall back to coordinator's stored value (for runtime_hours)
        if self.coordinator.stored_runtime_hours is not None:
            return True

        if not self._restoration_complete:
            return False
        return self._get_device_state() is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {}

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


class HondaGeneratorPersistentEnumSensor(
    HondaGeneratorEntity, RestoreEntity, SensorEntity
):
    """Honda Generator enum sensor that persists its last value when unavailable.

    For enum sensors like engine_event and engine_error, the last known value
    is preserved when the generator goes offline so alarm states remain visible.
    """

    entity_description: HondaGeneratorSensorEntityDescription

    def __init__(
        self,
        coordinator: HondaGeneratorCoordinator,
        description: HondaGeneratorSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{DOMAIN}-{coordinator.data.controller_name}_{description.key}"
        )
        self._restored_value: str | None = None
        self._restored_last_update: datetime | None = None
        self._last_live_value: str | None = None
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
            self._restored_value = last_state.state
            _LOGGER.debug(
                "Restored %s value: %s",
                self.entity_description.key,
                self._restored_value,
            )
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

        # When we get live data, save the enum value and clear restored value
        if self.coordinator.last_update_success:
            live_value = self._get_live_enum_value()
            if live_value is not None:
                self._last_live_value = live_value
            if self._restored_value is not None:
                self._restored_value = None
                self._restored_last_update = None

        self.async_write_ha_state()

    def _get_device_state(self) -> int | float | None:
        """Get the current device state from coordinator."""
        device = self.coordinator.get_device_by_id(
            self.entity_description.device_type, 1
        )
        if device is None:
            return 0
        if device.state is None:
            return None
        return device.state

    def _get_live_enum_value(self) -> str | None:
        """Get the current enum string value from live data."""
        state = self._get_device_state()
        if state is None:
            return None
        if self.entity_description.enum_keys is not None:
            int_state = int(state)
            return self.entity_description.enum_keys.get(
                int_state, f"unknown_{int_state}"
            )
        return None

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor.

        When connected, use live data. When offline, persist the last known
        enum value so alarm states remain visible.
        """
        if self.coordinator.last_update_success:
            return self._get_live_enum_value()

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
        """Return True if we have any data (live or persisted).

        Respects grace periods during reconnection attempts.
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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes for persistent enum sensor."""
        attrs: dict[str, Any] = {}

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


class HondaGeneratorPersistentMeasurementSensor(
    HondaGeneratorEntity, RestoreEntity, SensorEntity
):
    """Honda Generator measurement sensor that persists its last value when unavailable.

    For measurement sensors like fuel level and voltage setting, the last known
    value is preserved when the generator goes offline.
    """

    entity_description: HondaGeneratorSensorEntityDescription

    def __init__(
        self,
        coordinator: HondaGeneratorCoordinator,
        description: HondaGeneratorSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{DOMAIN}-{coordinator.data.controller_name}_{description.key}"
        )
        self._restored_value: int | float | None = None
        self._restored_last_update: datetime | None = None
        self._last_live_value: int | float | None = None
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
            try:
                self._restored_value = float(last_state.state)
                _LOGGER.debug(
                    "Restored %s value: %s",
                    self.entity_description.key,
                    self._restored_value,
                )
                if last_state.attributes.get("last_update"):
                    self._restored_last_update = datetime.fromisoformat(
                        last_state.attributes["last_update"]
                    )
            except (ValueError, TypeError):
                self._restored_value = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        if not self._first_update_attempted:
            self._first_update_attempted = True

        # When we get live data, save it and clear restored value
        if self.coordinator.last_update_success:
            live_value = self._get_device_state()
            if live_value is not None:
                self._last_live_value = live_value
            if self._restored_value is not None:
                self._restored_value = None
                self._restored_last_update = None

        self.async_write_ha_state()

    def _get_device_state(self) -> int | float | None:
        """Get the current device state from coordinator."""
        device = self.coordinator.get_device_by_id(
            self.entity_description.device_type, 1
        )
        if device is None:
            return None
        if device.state is None:
            return None
        return device.state

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor.

        When connected, use live data. When offline, persist the last known
        measurement value.
        """
        if self.coordinator.last_update_success:
            return self._get_device_state()

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
        """Return True if we have any data (live or persisted).

        Respects grace periods during reconnection attempts.
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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes for persistent measurement sensor."""
        attrs: dict[str, Any] = {}

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
