"""Honda Generator integration for Home Assistant."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
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

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_STOP_ENGINE = "stop_engine"


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


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Honda Generator integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_ENGINE,
        lambda call: _async_stop_engine(hass, call),
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
