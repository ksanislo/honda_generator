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

"""Diagnostics support for Honda Generator integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime_data.coordinator

    # Redact sensitive information
    redacted_data = dict(entry.data)
    if CONF_PASSWORD in redacted_data:
        redacted_data[CONF_PASSWORD] = "**REDACTED**"
    if CONF_ADDRESS in redacted_data:
        # Partially redact MAC address (show first 3 octets only)
        addr = redacted_data[CONF_ADDRESS]
        if ":" in addr:
            parts = addr.split(":")
            redacted_data[CONF_ADDRESS] = f"{parts[0]}:{parts[1]}:{parts[2]}:XX:XX:XX"

    diagnostics_data: dict[str, Any] = {
        "config_entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": redacted_data,
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
        },
    }

    # Add coordinator data if available
    if coordinator.data:
        data = coordinator.data
        diagnostics_data["generator"] = {
            "model": data.model,
            "serial_number": _redact_serial(data.serial_number),
            "firmware_version": data.firmware_version,
            "last_update": data.last_update.isoformat() if data.last_update else None,
        }

        # Add device states
        diagnostics_data["devices"] = [
            {
                "type": device.device_type,
                "name": device.name,
                "state": device.state,
            }
            for device in data.devices
        ]

    # Add API state if available
    if coordinator.api:
        api = coordinator.api
        diagnostics_data["api"] = {
            "connected": api.connected,
            "warnings_raw": api._warnings_raw,
            "faults_raw": api._faults_raw,
            "engine_event": api._engine_event,
            "engine_running": api._engine_running,
            "engine_error": api._engine_error,
            "output_voltage": api._output_voltage,
        }

    return diagnostics_data


def _redact_serial(serial: str) -> str:
    """Redact serial number, keeping only first 4 characters."""
    if len(serial) > 4:
        return f"{serial[:4]}{'X' * (len(serial) - 4)}"
    return serial
