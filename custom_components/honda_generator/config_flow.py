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

"""Config flow for Honda Generator integration."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
from bluetooth_data_tools import human_readable_name
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import (
    API,
    APIAuthError,
    APIConnectionError,
    Architecture,
    create_api,
    get_architecture_from_device_name,
    get_model_from_device_name,
    get_model_spec,
    is_valid_credential,
)
from .const import (
    CONF_ARCHITECTURE,
    CONF_MODEL,
    CONF_RECONNECT_AFTER_FAILURES,
    CONF_SERIAL,
    CONF_STARTUP_GRACE_PERIOD,
    CONF_STOP_ATTEMPTS,
    DEFAULT_RECONNECT_AFTER_FAILURES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STARTUP_GRACE_PERIOD,
    DEFAULT_STOP_ATTEMPTS,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# Service UUIDs used to identify Honda generators
HONDA_SERVICE_UUIDS = {
    "066b0001-5d90-4939-a7ba-7b9222f53e81",  # Poll architecture
    "01b60001-875a-4c56-b8bf-5103cafaeec7",  # Push architecture
}

# Default credential shown to the user (a fresh generator's PIN is "0000").
DEFAULT_CREDENTIAL = "0000"

_ALL_ZERO_PATTERN = re.compile(r"^[0]+$")


def _credential_error(architecture: Architecture, value: str) -> str | None:
    """Return an error key if the credential is not valid for the architecture."""
    if is_valid_credential(architecture, value):
        return None
    return "invalid_password" if architecture == Architecture.PUSH else "invalid_pin"


def _display_credential(value: str) -> str:
    """Prefill value for the form: show the short default for any all-zeros value."""
    return DEFAULT_CREDENTIAL if _ALL_ZERO_PATTERN.fullmatch(value or "") else value


def _credential_schema(suggested: str) -> vol.Schema:
    """Build the credential form schema.

    The field is optional: a blank submission is treated as the default (no
    password set), so the user can leave it empty rather than typing zeros.
    """
    return vol.Schema(
        {vol.Optional(CONF_PASSWORD, description={"suggested_value": suggested}): str}
    )


def _resolve_credential(user_input: dict[str, Any]) -> str:
    """Return the submitted credential, treating a blank value as the default."""
    return (user_input.get(CONF_PASSWORD) or "").strip() or DEFAULT_CREDENTIAL


def _credential_hint(architecture: Architecture) -> str:
    """Help text describing the expected credential for the architecture."""
    if architecture == Architecture.PUSH:
        return (
            "Enter the Bluetooth code printed in your generator's manual, or leave "
            "blank if no code is set. A blank/default means anyone in range can "
            "connect."
        )
    return (
        "Leave blank if no PIN is set (the default), or enter your PIN if you set "
        "one in the Honda app. A blank/default PIN means anyone in range can connect."
    )


def _is_honda_generator(service_info: BluetoothServiceInfoBleak) -> bool:
    """Check if a service info is from a Honda generator."""
    for uuid in service_info.service_uuids:
        if uuid.lower() in HONDA_SERVICE_UUIDS:
            return True
    return False


async def validate_input(
    hass: HomeAssistant,
    ble_device,
    data: dict[str, Any],
    architecture: Architecture = Architecture.POLL,
) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    api = create_api(ble_device, data[CONF_PASSWORD], architecture=architecture)
    try:
        await api.connect()
        serial = api.serial or "Unknown"
        model = API.get_model_from_serial(serial)
    except APIAuthError as err:
        raise InvalidAuth from err
    except APIConnectionError as err:
        raise CannotConnect from err
    finally:
        await api.disconnect()
    return {
        CONF_SERIAL: serial,
        CONF_MODEL: model,
        CONF_ARCHITECTURE: architecture.value,
    }


class HondaGeneratorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Honda Generator integration."""

    VERSION = 3
    _input_data: dict[str, Any]

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HondaGeneratorOptionsFlowHandler:
        """Get the options flow for this handler."""
        return HondaGeneratorOptionsFlowHandler(config_entry)

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": human_readable_name(
                None, discovery_info.name, discovery_info.address
            )
        }
        return await self.async_step_password()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        # If we already have discovery info (from bluetooth discovery),
        # go directly to password entry
        if self._discovery_info is not None:
            return await self.async_step_password()

        # Manual setup: show device picker
        if user_input is not None:
            address = user_input["address"]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._discovery_info = self._discovered_devices[address]
            return await self.async_step_password()

        # Scan for Honda generators
        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass):
            if discovery_info.address in current_addresses:
                continue
            if _is_honda_generator(discovery_info):
                self._discovered_devices[discovery_info.address] = discovery_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        device_options = {
            address: human_readable_name(None, info.name, address)
            for address, info in self._discovered_devices.items()
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("address"): vol.In(device_options)}),
        )

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the password entry step."""
        errors: dict[str, str] = {}

        # Detect architecture from device name; it selects the credential format.
        architecture = (
            get_architecture_from_device_name(self._discovery_info.name)
            if self._discovery_info is not None
            else Architecture.POLL
        )

        # Models with no settable PIN and no factory Bluetooth code (the EU2200i)
        # always use the default credential, so there is nothing to ask for - skip
        # the prompt and connect with the default. If that unexpectedly fails we
        # fall through to the form below so a credential can still be entered.
        model = (
            get_model_from_device_name(self._discovery_info.name)
            if self._discovery_info is not None
            else None
        )
        spec = get_model_spec(model) if model else None
        if user_input is None and spec is not None and not spec.requires_password:
            user_input = {CONF_PASSWORD: DEFAULT_CREDENTIAL}

        if user_input is not None and self._discovery_info is not None:
            _LOGGER.debug(
                "Detected architecture %s from device name %s",
                architecture,
                self._discovery_info.name,
            )

            credential = _resolve_credential(user_input)
            user_input = {**user_input, CONF_PASSWORD: credential}
            cred_error = _credential_error(architecture, credential)
            if cred_error:
                errors["base"] = cred_error
            else:
                try:
                    info = await validate_input(
                        self.hass,
                        self._discovery_info.device,
                        user_input,
                        architecture=architecture,
                    )
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"

                if "base" not in errors:
                    await self.async_set_unique_id(self._discovery_info.address)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"{info[CONF_MODEL]} ({info[CONF_SERIAL]})",
                        data={
                            **user_input,
                            CONF_SERIAL: info[CONF_SERIAL],
                            CONF_MODEL: info[CONF_MODEL],
                            CONF_ARCHITECTURE: info[CONF_ARCHITECTURE],
                        },
                    )

        return self.async_show_form(
            step_id="password",
            data_schema=_credential_schema(""),
            errors=errors,
            description_placeholders={
                "credential_hint": _credential_hint(architecture)
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        # Use existing architecture from config entry; it selects the format.
        architecture = Architecture(
            config_entry.data.get(CONF_ARCHITECTURE, Architecture.POLL)
        )

        if user_input is not None:
            credential = _resolve_credential(user_input)
            user_input = {**user_input, CONF_PASSWORD: credential}
            cred_error = _credential_error(architecture, credential)
            if cred_error:
                errors["base"] = cred_error
            else:
                # Get BLE device from the config entry's unique_id (BLE address)
                ble_device = bluetooth.async_ble_device_from_address(
                    self.hass, config_entry.unique_id
                )
                if ble_device is None:
                    errors["base"] = "cannot_connect"
                else:
                    try:
                        await validate_input(
                            self.hass,
                            ble_device,
                            user_input,
                            architecture=architecture,
                        )
                    except CannotConnect:
                        errors["base"] = "cannot_connect"
                    except InvalidAuth:
                        errors["base"] = "invalid_auth"
                    except Exception:  # pylint: disable=broad-except
                        _LOGGER.exception("Unexpected exception")
                        errors["base"] = "unknown"
                    else:
                        return self.async_update_reload_and_abort(
                            config_entry,
                            unique_id=config_entry.unique_id,
                            data={**config_entry.data, **user_input},
                            reason="reconfigure_successful",
                        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_credential_schema(
                _display_credential(config_entry.data[CONF_PASSWORD])
            ),
            errors=errors,
        )


class HondaGeneratorOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Honda Generator."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        # Check if this is a Push architecture device
        architecture = Architecture(
            self.config_entry.data.get(CONF_ARCHITECTURE, Architecture.POLL)
        )

        if user_input is not None:
            options = self.config_entry.options | user_input
            return self.async_create_entry(title="", data=options)

        # Push architecture doesn't need scan interval (data is streamed)
        if architecture == Architecture.PUSH:
            data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_RECONNECT_AFTER_FAILURES,
                        default=self.options.get(
                            CONF_RECONNECT_AFTER_FAILURES,
                            DEFAULT_RECONNECT_AFTER_FAILURES,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=10, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_STARTUP_GRACE_PERIOD,
                        default=self.options.get(
                            CONF_STARTUP_GRACE_PERIOD,
                            DEFAULT_STARTUP_GRACE_PERIOD,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=300, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            )
        else:
            data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_RECONNECT_AFTER_FAILURES,
                        default=self.options.get(
                            CONF_RECONNECT_AFTER_FAILURES,
                            DEFAULT_RECONNECT_AFTER_FAILURES,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=10, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_STARTUP_GRACE_PERIOD,
                        default=self.options.get(
                            CONF_STARTUP_GRACE_PERIOD,
                            DEFAULT_STARTUP_GRACE_PERIOD,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=300, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_STOP_ATTEMPTS,
                        default=self.options.get(
                            CONF_STOP_ATTEMPTS,
                            DEFAULT_STOP_ATTEMPTS,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=30, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            )

        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
