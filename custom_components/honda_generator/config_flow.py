"""Config flow for Honda Generator integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from bluetooth_data_tools import human_readable_name
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
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
)
from .const import (
    CONF_ARCHITECTURE,
    CONF_MODEL,
    CONF_RECONNECT_AFTER_FAILURES,
    CONF_RECONNECT_GRACE_PERIOD,
    CONF_SERIAL,
    CONF_STARTUP_GRACE_PERIOD,
    CONF_STOP_ATTEMPTS,
    DEFAULT_RECONNECT_AFTER_FAILURES,
    DEFAULT_RECONNECT_GRACE_PERIOD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STARTUP_GRACE_PERIOD,
    DEFAULT_STOP_ATTEMPTS,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD, description={"suggested_value": "00000000"}): str,
    }
)


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
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if self._discovery_info is None:
            errors["base"] = "detectonly"

        if user_input is not None and self._discovery_info is not None:
            # Detect architecture from device name
            architecture = get_architecture_from_device_name(self._discovery_info.name)
            _LOGGER.debug(
                "Detected architecture %s from device name %s",
                architecture,
                self._discovery_info.name,
            )

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
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        if user_input is not None:
            # Get BLE device from the config entry's unique_id (BLE address)
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, config_entry.unique_id
            )
            if ble_device is None:
                errors["base"] = "cannot_connect"
            else:
                # Use existing architecture from config entry
                architecture = Architecture(
                    config_entry.data.get(CONF_ARCHITECTURE, Architecture.POLL)
                )
                try:
                    await validate_input(
                        self.hass, ble_device, user_input, architecture=architecture
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
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PASSWORD, default=config_entry.data[CONF_PASSWORD]
                    ): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    async def async_migrate_entry(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Migrate old entry to new version."""
        _LOGGER.debug("Migrating config entry from version %s", config_entry.version)

        if config_entry.version < 3:
            # Version 3: Add architecture field (default to POLL for existing entries)
            new_data = {**config_entry.data}
            if CONF_ARCHITECTURE not in new_data:
                new_data[CONF_ARCHITECTURE] = Architecture.POLL.value
                _LOGGER.debug("Added architecture field (default: poll)")

            hass.config_entries.async_update_entry(
                config_entry, data=new_data, version=3
            )
            _LOGGER.debug("Migration to version 3 successful")

        return True


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
                    vol.Required(
                        CONF_RECONNECT_GRACE_PERIOD,
                        default=self.options.get(
                            CONF_RECONNECT_GRACE_PERIOD,
                            DEFAULT_RECONNECT_GRACE_PERIOD,
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
                        CONF_RECONNECT_GRACE_PERIOD,
                        default=self.options.get(
                            CONF_RECONNECT_GRACE_PERIOD,
                            DEFAULT_RECONNECT_GRACE_PERIOD,
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
