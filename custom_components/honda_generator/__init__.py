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

"""Honda Generator integration for Home Assistant."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .api import API, Architecture
from .const import CONF_ARCHITECTURE, CONF_MODEL, CONF_SERIAL, DOMAIN
from .coordinator import HondaGeneratorCoordinator
from .services import ServiceType

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_STOP_ENGINE = "stop_engine"
SERVICE_CLEAR_DISCOVERIES = "clear_discoveries"
SERVICE_SET_SERVICE_RECORD = "set_service_record"


@dataclass
class RuntimeData:
    """Class to hold runtime data."""

    coordinator: HondaGeneratorCoordinator
    cancel_update_listener: Callable


HondaGeneratorConfigEntry: TypeAlias = ConfigEntry[RuntimeData]


def _get_config_entry_from_device_id(
    hass: HomeAssistant, device_id: str
) -> HondaGeneratorConfigEntry | None:
    """Get the config entry associated with a device ID."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if device_entry is None:
        return None

    for entry_id in device_entry.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry and entry.domain == DOMAIN:
            return entry
    return None


async def _async_stop_engine(hass: HomeAssistant, service_call: ServiceCall) -> None:
    """Handle the stop_engine service call."""
    device_ids = service_call.data.get("device_id", [])
    if isinstance(device_ids, str):
        device_ids = [device_ids]

    for device_id in device_ids:
        config_entry = _get_config_entry_from_device_id(hass, device_id)
        if config_entry is None:
            raise HomeAssistantError(f"Device {device_id} not found")

        coordinator = config_entry.runtime_data.coordinator
        if coordinator.api is None or not coordinator.api.connected:
            raise HomeAssistantError("Generator not connected")

        _LOGGER.info("Service call: stopping generator engine")
        success = await coordinator.api.engine_stop()
        if not success:
            raise HomeAssistantError("Failed to stop engine")
        _LOGGER.info("Engine stop command sent successfully via service")


async def _async_set_service_record(
    hass: HomeAssistant, service_call: ServiceCall
) -> None:
    """Handle the set_service_record service call."""
    device_id = service_call.data.get("device_id")
    service_type_str = service_call.data.get("service_type")
    hours = service_call.data.get("hours")
    date_value = service_call.data.get("date")

    if isinstance(device_id, list):
        device_id = device_id[0]

    config_entry = _get_config_entry_from_device_id(hass, device_id)
    if config_entry is None:
        raise HomeAssistantError(f"Device {device_id} not found")

    # Validate service type
    try:
        service_type = ServiceType(service_type_str)
    except ValueError:
        raise HomeAssistantError(f"Invalid service type: {service_type_str}")

    # Parse date - can be datetime.date or string
    if isinstance(date_value, str):
        try:
            service_date = datetime.fromisoformat(date_value)
        except ValueError:
            raise HomeAssistantError(f"Invalid date format: {date_value}")
    else:
        # datetime.date from selector
        service_date = datetime.combine(date_value, datetime.min.time())

    coordinator = config_entry.runtime_data.coordinator

    # Directly set the service record
    coordinator._service_records[service_type.value] = {
        "hours": int(hours),
        "date": service_date.isoformat(),
    }
    await coordinator._async_save_storage()
    coordinator.async_update_listeners()

    _LOGGER.info(
        "Set service record for %s: %d hours on %s",
        service_type.value,
        hours,
        service_date.date().isoformat(),
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Honda Generator integration."""

    async def async_clear_discoveries(call: ServiceCall) -> None:
        """Clear all pending discovery flows."""
        flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        count = len(flows)
        for flow in flows:
            hass.config_entries.flow.async_abort(flow["flow_id"])
        _LOGGER.info("Cleared %d pending discovery flow(s)", count)

    async def async_stop_engine(call: ServiceCall) -> None:
        """Handle stop_engine service call."""
        await _async_stop_engine(hass, call)

    async def async_set_service_record(call: ServiceCall) -> None:
        """Handle set_service_record service call."""
        await _async_set_service_record(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_ENGINE,
        async_stop_engine,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_DISCOVERIES,
        async_clear_discoveries,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SERVICE_RECORD,
        async_set_service_record,
    )
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to new version."""
    _LOGGER.debug("Migrating config entry from version %s", config_entry.version)

    if config_entry.version == 1:
        # In v1, the title was just the serial number
        serial = config_entry.title
        model = API.get_model_from_serial(serial)
        new_data = {
            **config_entry.data,
            CONF_SERIAL: serial,
            CONF_MODEL: model,
        }
        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            title=f"{model} ({serial})",
            version=2,
        )
        _LOGGER.info("Migrated config entry to version 2")

    if config_entry.version < 3:
        # Version 3: Add architecture field (default to POLL for existing entries)
        new_data = {**config_entry.data}
        if CONF_ARCHITECTURE not in new_data:
            new_data[CONF_ARCHITECTURE] = Architecture.POLL.value
        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            version=3,
        )
        _LOGGER.info("Migrated config entry to version 3 (added architecture)")

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: HondaGeneratorConfigEntry
) -> bool:
    """Set up Honda Generator integration from a config entry."""
    coordinator = HondaGeneratorCoordinator(hass, config_entry)
    await coordinator.async_first_refresh_or_default()

    cancel_update_listener = config_entry.add_update_listener(_async_update_listener)

    config_entry.runtime_data = RuntimeData(coordinator, cancel_update_listener)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def _async_update_listener(
    hass: HomeAssistant, config_entry: HondaGeneratorConfigEntry
) -> None:
    """Handle config options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: HondaGeneratorConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Delete device if selected from UI."""
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: HondaGeneratorConfigEntry
) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading config entry %s", config_entry.unique_id)
    runtime_data = config_entry.runtime_data

    # Cancel the update listener
    _LOGGER.debug("Cancelling update listener")
    runtime_data.cancel_update_listener()

    # Disconnect the API (this will wait for any in-progress operations)
    if runtime_data.coordinator.api:
        _LOGGER.debug("Disconnecting API for %s", config_entry.unique_id)
        await runtime_data.coordinator.api.disconnect()
        _LOGGER.debug("API disconnected for %s", config_entry.unique_id)
    else:
        _LOGGER.debug("No API to disconnect for %s", config_entry.unique_id)

    # Unload platforms
    _LOGGER.debug("Unloading platforms for %s", config_entry.unique_id)
    result = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    _LOGGER.debug("Platforms unloaded for %s: %s", config_entry.unique_id, result)
    return result
