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

"""Honda Generator integration using DataUpdateCoordinator."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from bleak.backends.device import BLEDevice
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    API,
    DEVICE_NAMES,
    DEVICE_TYPES,
    DEVICE_TYPES_PUSH,
    APIAuthError,
    APIConnectionError,
    APIReadError,
    Architecture,
    Device,
    DeviceType,
    DiagnosticCategory,
    GeneratorAPIProtocol,
    create_api,
    get_model_spec,
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
)
from .services import OIL_CHANGE_BREAKIN_INTERVAL, ServiceType, get_model_services

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = "honda_generator"


@dataclass
class HondaGeneratorData:
    """Class to hold API data."""

    controller_name: str
    serial_number: str
    model: str
    firmware_version: str
    devices: list[Device]
    last_update: datetime | None = None


class HondaGeneratorCoordinator(DataUpdateCoordinator[HondaGeneratorData]):
    """Honda Generator data update coordinator."""

    data: HondaGeneratorData

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.pwd: str = config_entry.data[CONF_PASSWORD]
        self.poll_interval: int = int(
            config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        self.config_entry = config_entry
        self.api: GeneratorAPIProtocol | None = None
        self._last_successful_data: HondaGeneratorData | None = None
        # Cached device info (only fetched once per connection)
        self._cached_serial: str | None = None
        self._cached_model: str | None = None
        self._cached_firmware: str | None = None
        # For start-to-start timing
        self._target_interval = timedelta(seconds=self.poll_interval)
        self._update_start_time: float = 0
        # Track consecutive failures for reconnect logic
        self._consecutive_failures: int = 0
        self._reconnect_after_failures: int = int(
            config_entry.options.get(
                CONF_RECONNECT_AFTER_FAILURES, DEFAULT_RECONNECT_AFTER_FAILURES
            )
        )
        # Startup grace period - keep entities unavailable until this expires
        self._startup_time: float = time.monotonic()
        self._startup_grace_period: int = int(
            config_entry.options.get(
                CONF_STARTUP_GRACE_PERIOD, DEFAULT_STARTUP_GRACE_PERIOD
            )
        )
        self._has_connected_once: bool = False
        self._grace_period_logged_expired: bool = False
        if self._startup_grace_period > 0:
            _LOGGER.debug(
                "Startup grace period: %ds (entities unavailable until connected)",
                self._startup_grace_period,
            )

        # Reconnect grace period - keep entities unavailable after disconnect
        self._disconnect_time: float | None = None
        self._reconnect_grace_period: int = int(
            config_entry.options.get(
                CONF_RECONNECT_GRACE_PERIOD, DEFAULT_RECONNECT_GRACE_PERIOD
            )
        )
        self._reconnect_grace_logged_expired: bool = False
        if self._reconnect_grace_period > 0:
            _LOGGER.debug(
                "Reconnect grace period: %ds (entities unavailable after disconnect)",
                self._reconnect_grace_period,
            )

        # Flag to skip grace period for intentional disconnects (e.g., stop engine)
        self._intentional_disconnect: bool = False

        # Number of stop command attempts (Poll architecture only)
        self._stop_attempts: int = int(
            config_entry.options.get(CONF_STOP_ATTEMPTS, DEFAULT_STOP_ATTEMPTS)
        )

        # Persistent storage for runtime hours and service records
        storage_key = f"{STORAGE_KEY_PREFIX}.{config_entry.entry_id}"
        self._store: Store = Store(hass, STORAGE_VERSION, storage_key)
        self._stored_runtime_hours: int | None = None
        self._stored_runtime_hours_timestamp: datetime | None = None

        # Service tracking: {service_type: {"hours": int, "date": str}}
        self._service_records: dict[str, dict] = {}

        # Detect architecture from config entry
        self._architecture = Architecture(
            config_entry.data.get(CONF_ARCHITECTURE, Architecture.POLL)
        )

        # For Push architecture, disable polling (data is streamed)
        update_interval = (
            None if self._architecture == Architecture.PUSH else self._target_interval
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            update_method=self.async_update_data,
            update_interval=update_interval,
        )

    @property
    def architecture(self) -> Architecture:
        """Return the communication architecture."""
        return self._architecture

    @property
    def has_connected_once(self) -> bool:
        """Return True if we've successfully connected at least once."""
        return self._has_connected_once

    @property
    def stored_runtime_hours(self) -> int | None:
        """Return the stored runtime hours value.

        This is the last known valid runtime hours value, persisted to storage.
        Used as a fallback when the sensor can't get live data.
        """
        return self._stored_runtime_hours

    @property
    def stop_attempts(self) -> int:
        """Return the configured number of stop command attempts."""
        return self._stop_attempts

    @property
    def in_startup_grace_period(self) -> bool:
        """Return True if we're in the startup grace period without a connection.

        During this period, entities should report as unavailable rather than
        showing default offline values. This preserves dashboard state while
        waiting for the generator to be discovered after a restart.
        """
        if self._has_connected_once:
            return False
        if self._startup_grace_period <= 0:
            return False
        elapsed = time.monotonic() - self._startup_time
        return elapsed < self._startup_grace_period

    def set_intentional_disconnect(self) -> None:
        """Mark that the next disconnect is intentional (e.g., stop engine command).

        This prevents the reconnect grace period from activating when the
        generator is intentionally stopped, allowing entities to immediately
        show offline defaults rather than "unavailable".
        """
        _LOGGER.debug("Intentional disconnect flagged (grace period will be skipped)")
        self._intentional_disconnect = True

    @property
    def in_reconnect_grace_period(self) -> bool:
        """Return True if we're in the reconnect grace period after a disconnect.

        During this period, entities should report as unavailable rather than
        showing default offline values. This preserves dashboard state while
        attempting to reconnect after a connection loss.
        """
        if self._disconnect_time is None:
            return False
        if self._reconnect_grace_period <= 0:
            return False
        elapsed = time.monotonic() - self._disconnect_time
        return elapsed < self._reconnect_grace_period

    async def async_load_stored_data(self) -> None:
        """Load persisted data from storage."""
        data = await self._store.async_load()
        if data and isinstance(data, dict):
            self._stored_runtime_hours = data.get("runtime_hours")
            timestamp_str = data.get("timestamp")
            if timestamp_str:
                try:
                    self._stored_runtime_hours_timestamp = datetime.fromisoformat(
                        timestamp_str
                    )
                except (ValueError, TypeError):
                    self._stored_runtime_hours_timestamp = None
            if self._stored_runtime_hours is not None:
                _LOGGER.debug(
                    "Loaded stored runtime hours: %d (from %s)",
                    self._stored_runtime_hours,
                    self._stored_runtime_hours_timestamp,
                )
            # Load service records
            self._service_records = data.get("service_records", {})
            if self._service_records:
                _LOGGER.debug("Loaded %d service records", len(self._service_records))

    async def _async_save_storage(self) -> None:
        """Save all persistent data to storage."""
        data = {
            "service_records": self._service_records,
        }
        if self._stored_runtime_hours is not None:
            data["runtime_hours"] = self._stored_runtime_hours
        if self._stored_runtime_hours_timestamp is not None:
            data["timestamp"] = self._stored_runtime_hours_timestamp.isoformat()
        await self._store.async_save(data)

    async def _async_save_runtime_hours(self, value: int) -> None:
        """Save runtime hours to persistent storage if validated."""
        now = datetime.now()

        # Validate the new value is plausible
        if not self._validate_runtime_hours(value, now):
            return

        # Check if this is the first time we're seeing runtime hours
        first_time = self._stored_runtime_hours is None

        # Save if this is a new max or first value
        if first_time or value > self._stored_runtime_hours:
            self._stored_runtime_hours = value
            self._stored_runtime_hours_timestamp = now
            await self._async_save_storage()
            _LOGGER.debug("Saved runtime hours: %d", value)

        # Initialize service records on first runtime hours reading
        if first_time:
            await self._async_initialize_service_records(value, now)

    async def _async_initialize_service_records(
        self, hours: int, date: datetime
    ) -> None:
        """Initialize service records for services that have no history.

        Sets the baseline for service tracking so intervals start counting
        from when the generator was first seen. For oil change on generators
        under 20 hours, initializes at 0 so break-in interval triggers at
        20 total hours.
        """
        model = self.config_entry.data.get(CONF_MODEL)
        model_services = get_model_services(model)
        initialized = []

        for service_type in model_services:
            if service_type.value not in self._service_records:
                init_hours = hours
                # For oil change on new engines, start from 0 so break-in
                # interval (20h) triggers at 20 total hours
                if (
                    service_type == ServiceType.OIL_CHANGE
                    and hours < OIL_CHANGE_BREAKIN_INTERVAL.hours
                ):
                    init_hours = 0

                self._service_records[service_type.value] = {
                    "hours": init_hours,
                    "date": date.isoformat(),
                }
                initialized.append(f"{service_type.value}@{init_hours}h")

        if initialized:
            await self._async_save_storage()
            _LOGGER.info(
                "Initialized %d service records: %s",
                len(initialized),
                ", ".join(initialized),
            )

    async def async_mark_service_complete(self, service_type: ServiceType) -> None:
        """Mark a service as complete at current runtime hours and date.

        Args:
            service_type: The type of service that was performed
        """
        now = datetime.now()
        current_hours = self._stored_runtime_hours or 0

        self._service_records[service_type.value] = {
            "hours": current_hours,
            "date": now.isoformat(),
        }
        await self._async_save_storage()
        _LOGGER.info(
            "Marked %s complete at %d hours on %s",
            service_type.value,
            current_hours,
            now.date().isoformat(),
        )
        # Notify entities to update
        self.async_update_listeners()

    def get_service_record(self, service_type: ServiceType) -> dict | None:
        """Get the service record for a service type.

        Args:
            service_type: The type of service

        Returns:
            Dict with "hours" and "date" keys, or None if never serviced
        """
        return self._service_records.get(service_type.value)

    def is_service_due(self, service_type: ServiceType) -> bool:
        """Check if a service is due based on hours and/or time.

        Args:
            service_type: The type of service to check

        Returns:
            True if service is due, False otherwise
        """
        model = self.config_entry.data.get(CONF_MODEL)
        model_services = get_model_services(model)

        # Service not applicable to this model
        if service_type not in model_services:
            return False

        interval = model_services[service_type]
        record = self.get_service_record(service_type)
        current_hours = self._stored_runtime_hours or 0

        # No record yet (generator not seen) - can't determine if due
        if record is None:
            return False

        last_service_hours = record.get("hours", 0)

        # Special handling for oil change - use break-in interval if last
        # service was recorded at < 20 hours (new engine)
        if (
            service_type == ServiceType.OIL_CHANGE
            and last_service_hours < OIL_CHANGE_BREAKIN_INTERVAL.hours
        ):
            interval = OIL_CHANGE_BREAKIN_INTERVAL

        # Check hours since last service
        if interval.hours:
            hours_since = current_hours - last_service_hours
            if hours_since >= interval.hours:
                return True

        # Check days since last service
        if interval.days:
            last_service_date_str = record.get("date")
            if last_service_date_str:
                try:
                    last_service_date = datetime.fromisoformat(last_service_date_str)
                    days_since = (datetime.now() - last_service_date).days
                    if days_since >= interval.days:
                        return True
                except (ValueError, TypeError):
                    pass

        return False

    def get_applicable_services(self) -> list[ServiceType]:
        """Get list of service types applicable to this generator's model.

        Returns:
            List of ServiceType values applicable to the model
        """
        model = self.config_entry.data.get(CONF_MODEL)
        model_services = get_model_services(model)
        return list(model_services.keys())

    def _validate_runtime_hours(self, value: int, now: datetime) -> bool:
        """Validate that runtime hours increase is plausible.

        Returns True if the value is valid, False if it should be rejected.
        The generator can't accumulate more runtime hours than wall-clock
        hours elapsed since we last saw it (plus 1 hour for rounding).
        """
        if self._stored_runtime_hours is None:
            return True  # No previous value to compare

        if value <= self._stored_runtime_hours:
            return True  # Not an increase, floor check handles this

        if self._stored_runtime_hours_timestamp is None:
            return True  # No timestamp to compare against

        elapsed_hours = (
            now - self._stored_runtime_hours_timestamp
        ).total_seconds() / 3600
        max_increase = elapsed_hours + 1  # +1 for rounding
        actual_increase = value - self._stored_runtime_hours

        if actual_increase > max_increase:
            _LOGGER.warning(
                "Runtime hours increase of %d is implausible "
                "(max possible: %.1f hours in %.1f elapsed hours), ignoring",
                actual_increase,
                max_increase,
                elapsed_hours,
            )
            return False

        return True

    def _apply_runtime_hours_bounds(self, devices: list[Device]) -> None:
        """Ensure runtime hours is within plausible bounds.

        Rejects values that are:
        - Below the stored maximum (backwards jump)
        - Above the maximum possible based on elapsed time (forwards jump)
        """
        if self._stored_runtime_hours is None:
            return

        now = datetime.now()

        for device in devices:
            if device.device_type == DeviceType.RUNTIME_HOURS:
                if device.state is None:
                    continue

                value = int(device.state)

                # Check for backwards jump
                if value < self._stored_runtime_hours:
                    _LOGGER.warning(
                        "Runtime hours %d is below stored maximum %d, using stored value",
                        value,
                        self._stored_runtime_hours,
                    )
                    device.state = self._stored_runtime_hours
                    continue

                # Check for implausible forward jump
                if not self._validate_runtime_hours(value, now):
                    device.state = self._stored_runtime_hours

    async def _async_refresh(
        self,
        log_failures: bool = True,
        raise_on_auth_failed: bool = False,
        scheduled: bool = False,
        raise_on_entry_error: bool = False,
    ) -> None:
        """Refresh data with start-to-start timing.

        Tracks when the update starts and adjusts the next update interval
        to maintain consistent start-to-start timing rather than end-to-start.
        """
        # Skip timing adjustment for Push architecture (no polling)
        if self._architecture == Architecture.PUSH:
            await super()._async_refresh(
                log_failures=log_failures,
                raise_on_auth_failed=raise_on_auth_failed,
                scheduled=scheduled,
                raise_on_entry_error=raise_on_entry_error,
            )
            return

        self._update_start_time = time.monotonic()

        await super()._async_refresh(
            log_failures=log_failures,
            raise_on_auth_failed=raise_on_auth_failed,
            scheduled=scheduled,
            raise_on_entry_error=raise_on_entry_error,
        )

        # Calculate elapsed time and adjust next interval for start-to-start timing
        elapsed = time.monotonic() - self._update_start_time
        remaining = self._target_interval.total_seconds() - elapsed
        # If update took longer than target interval, schedule immediately
        # Use small epsilon to ensure scheduler always queues a future event
        self.update_interval = timedelta(seconds=max(0.01, remaining))
        _LOGGER.debug(
            "Update took %.1fs, next update in %.1fs",
            elapsed,
            self.update_interval.total_seconds(),
        )

    @staticmethod
    def _get_default_state(device_type: DeviceType) -> int | float | bool:
        """Get the default state for a device type when unavailable."""
        if device_type == DeviceType.ENGINE_RUNNING:
            return False
        if device_type == DeviceType.ECO_MODE:
            return False
        # ENGINE_EVENT, ENGINE_ERROR, OUTPUT_VOLTAGE, and other numeric sensors default to 0
        return 0

    def _get_device_types(self) -> list[DeviceType]:
        """Get the appropriate device types for this architecture."""
        if self._architecture == Architecture.PUSH:
            return DEVICE_TYPES_PUSH
        return DEVICE_TYPES

    def _create_default_data(self) -> HondaGeneratorData:
        """Create default data structure when generator is unavailable."""
        controller_name = self.config_entry.unique_id or "unknown"
        # Use stored model/serial from config entry data (set during setup or migration)
        serial_number = self.config_entry.data.get(CONF_SERIAL, "unknown")
        model = self.config_entry.data.get(
            CONF_MODEL, API.get_model_from_serial(serial_number)
        )

        device_types = self._get_device_types()
        devices = [
            Device(
                device_id=1,
                device_unique_id=f"{controller_name}_{device_type}",
                device_type=device_type,
                name=DEVICE_NAMES.get(device_type, str(device_type)),
                state=self._get_default_state(device_type),
            )
            for device_type in device_types
        ]

        return HondaGeneratorData(
            controller_name=controller_name,
            serial_number=serial_number,
            model=model,
            firmware_version="unknown",
            devices=devices,
            last_update=None,
        )

    def _get_ble_device(self) -> BLEDevice | None:
        """Get the BLE device from Home Assistant."""
        address = self.config_entry.unique_id
        if not address:
            return None
        return bluetooth.async_ble_device_from_address(self.hass, address)

    def _handle_engine_status_update(
        self, event: int, running: bool, error: int, voltage: int
    ) -> None:
        """Handle engine status notification from BLE (Poll architecture)."""
        if self.data is None:
            return

        # Update the device states
        for device in self.data.devices:
            if device.device_type == DeviceType.ENGINE_EVENT:
                device.state = event
            elif device.device_type == DeviceType.ENGINE_RUNNING:
                device.state = running
            elif device.device_type == DeviceType.ENGINE_ERROR:
                device.state = error
            elif device.device_type == DeviceType.OUTPUT_VOLTAGE:
                device.state = voltage

        # Notify listeners of the update
        self.async_set_updated_data(self.data)

    def _handle_push_data_update(self, state: dict) -> None:
        """Handle data update from Push architecture stream.

        Called by PushAPI when new CAN data is received.
        """
        if self.data is None:
            return

        # Calculate fuel level percentage from mL using tank capacity
        fuel_ml = state.get("fuel_ml")
        fuel_level_percent: int | None = None
        if fuel_ml is not None and self._cached_model:
            model_spec = get_model_spec(self._cached_model)
            if model_spec and model_spec.fuel_tank_liters > 0:
                fuel_level_percent = min(
                    round((fuel_ml / (model_spec.fuel_tank_liters * 1000)) * 100), 100
                )

        # Map stream state to device values
        state_map: dict[DeviceType, int | float | bool | None] = {
            DeviceType.RUNTIME_HOURS: state.get("runtime_hours"),
            DeviceType.CURRENT: state.get("current"),
            DeviceType.POWER: state.get("power_watts"),
            DeviceType.ECO_MODE: state.get("eco_status"),
            DeviceType.ENGINE_RUNNING: state.get("engine_mode", 0) > 0,
            DeviceType.OUTPUT_VOLTAGE: state.get("voltage"),
            DeviceType.FUEL_LEVEL: fuel_level_percent,
            DeviceType.FUEL_VOLUME_ML: fuel_ml,
            DeviceType.FUEL_REMAINS_LEVEL: state.get("fuel_level_discrete"),
            DeviceType.FUEL_REMAINING_TIME: state.get("fuel_remaining_min"),
            DeviceType.OUTPUT_VOLTAGE_SETTING: state.get("voltage_setting"),
        }

        # Update device states
        for device in self.data.devices:
            if device.device_type in state_map:
                device.state = state_map[device.device_type]

        # Apply runtime hours floor and schedule save if increased
        self._apply_runtime_hours_bounds(self.data.devices)
        runtime_hours = state.get("runtime_hours")
        if runtime_hours is not None:
            self.hass.async_create_task(
                self._async_save_runtime_hours(int(runtime_hours))
            )

        # Update timestamp
        self.data.last_update = datetime.now()

        # Notify listeners of the update
        self.async_set_updated_data(self.data)

    def _get_enabled_diagnostic_categories(self) -> set[DiagnosticCategory]:
        """Determine which diagnostic categories have enabled entities.

        Checks the entity registry to see which entities are enabled,
        and returns the set of diagnostic categories that need to be read.
        """
        from homeassistant.helpers import entity_registry as er

        registry = er.async_get(self.hass)
        entries = er.async_entries_for_config_entry(
            registry, self.config_entry.entry_id
        )

        # First poll before entities exist - read everything
        if not entries:
            _LOGGER.debug(
                "No entities registered yet, reading all diagnostic categories"
            )
            return set(DiagnosticCategory)

        enabled: set[DiagnosticCategory] = set()
        for entry in entries:
            if entry.disabled_by is not None:
                continue

            uid = entry.unique_id
            if "_warning_" in uid or "_fault_" in uid:
                enabled.add(DiagnosticCategory.WARNINGS_FAULTS)
            elif "runtime_hours" in uid:
                enabled.add(DiagnosticCategory.RUNTIME_HOURS)
            elif "output_current" in uid:
                enabled.add(DiagnosticCategory.CURRENT)
            elif "output_power" in uid:
                enabled.add(DiagnosticCategory.POWER)
            elif "eco_mode" in uid:
                enabled.add(DiagnosticCategory.ECO_MODE)

        return enabled

    async def async_update_data(self) -> HondaGeneratorData:
        """Fetch data from the generator."""
        try:
            if self.api is None or not self.api.connected:
                ble_device = self._get_ble_device()
                if not ble_device:
                    raise UpdateFailed("Generator not available")

                _LOGGER.debug(
                    "Creating new API instance for %s (architecture: %s, previous api: %s)",
                    self.config_entry.unique_id,
                    self._architecture,
                    "exists" if self.api else "none",
                )

                # Use factory to create appropriate API based on architecture
                if self._architecture == Architecture.PUSH:
                    self.api = create_api(
                        ble_device,
                        pwd=self.pwd,
                        architecture=self._architecture,
                        on_data_update=self._handle_push_data_update,
                    )
                else:
                    self.api = create_api(
                        ble_device,
                        pwd=self.pwd,
                        architecture=self._architecture,
                        on_engine_status_update=self._handle_engine_status_update,
                    )

                _LOGGER.debug("API created, attempting to connect")
                connected = await self.api.connect()
                if not connected:
                    _LOGGER.debug("Connection returned False (possibly shutting down)")
                    raise UpdateFailed("Connection failed or shutting down")

                # Cache device info from API (populated during connect)
                self._cached_serial = self.api.serial or "unknown"
                self._cached_model = self.api.model or API.get_model_from_serial(
                    self._cached_serial
                )
                self._cached_firmware = self.api.firmware_version or "unknown"
                _LOGGER.debug(
                    "Device info: serial=%s, model=%s, firmware=%s",
                    self._cached_serial,
                    self._cached_model,
                    self._cached_firmware,
                )

            enabled_categories = self._get_enabled_diagnostic_categories()
            _LOGGER.debug("Enabled diagnostic categories: %s", enabled_categories)
            devices = await self.api.get_devices(enabled_categories=enabled_categories)

            # Apply runtime hours floor and save if increased
            self._apply_runtime_hours_bounds(devices)
            for device in devices:
                if device.device_type == DeviceType.RUNTIME_HOURS and device.state:
                    await self._async_save_runtime_hours(int(device.state))
                    break

            self._last_successful_data = HondaGeneratorData(
                self.api.controller_name,
                self._cached_serial or "unknown",
                self._cached_model or "Unknown",
                self._cached_firmware or "unknown",
                devices,
                last_update=datetime.now(),
            )
            # Reset failure counter on success and mark as connected
            self._consecutive_failures = 0
            if not self._has_connected_once:
                elapsed = time.monotonic() - self._startup_time
                _LOGGER.debug(
                    "First successful connection after %.1fs, ending startup grace period",
                    elapsed,
                )
                self._has_connected_once = True
            # Clear disconnect time on successful reconnection
            if self._disconnect_time is not None:
                elapsed = time.monotonic() - self._disconnect_time
                _LOGGER.debug(
                    "Reconnected after %.1fs, ending reconnect grace period",
                    elapsed,
                )
                self._disconnect_time = None
                self._reconnect_grace_logged_expired = False
            # Clear intentional disconnect flag if it was set but disconnect didn't happen
            if self._intentional_disconnect:
                _LOGGER.debug("Clearing unused intentional disconnect flag")
                self._intentional_disconnect = False
            return self._last_successful_data

        except APIAuthError as err:
            _LOGGER.error("Authentication error: %s", err)
            raise UpdateFailed(err) from err
        except (APIConnectionError, APIReadError, UpdateFailed) as err:
            self._consecutive_failures += 1
            if self.api is None:
                _LOGGER.debug(
                    "Update failed for %s (waiting for device): %s",
                    self.config_entry.unique_id,
                    err,
                )
            else:
                _LOGGER.debug(
                    "Update failed for %s (%d consecutive, reconnect at %d): %s",
                    self.config_entry.unique_id,
                    self._consecutive_failures,
                    self._reconnect_after_failures,
                    err,
                )

            # Start reconnect grace period on first failure after being connected
            # Skip grace period if this is an intentional disconnect (e.g., stop engine)
            if self._intentional_disconnect:
                _LOGGER.debug("Skipping grace period due to intentional disconnect")
                self._intentional_disconnect = False
                # Also clear any grace period that may have started during disconnect
                self._disconnect_time = None
            elif (
                self._has_connected_once
                and self._disconnect_time is None
                and self._reconnect_grace_period > 0
            ):
                self._disconnect_time = time.monotonic()
                _LOGGER.debug(
                    "Connection lost, starting reconnect grace period (%ds)",
                    self._reconnect_grace_period,
                )

            # Force reconnect after threshold (0 disables this feature)
            if (
                self._reconnect_after_failures > 0
                and self._consecutive_failures >= self._reconnect_after_failures
                and self.api is not None
            ):
                _LOGGER.warning(
                    "Forcing reconnect after %d consecutive failures",
                    self._consecutive_failures,
                )
                await self.api.disconnect()
                self.api = None
                self._consecutive_failures = 0

            # Check if startup grace period just expired - if so, notify entities
            # so they can transition from unavailable to showing defaults
            if (
                not self._has_connected_once
                and not self._grace_period_logged_expired
                and not self.in_startup_grace_period
            ):
                self._grace_period_logged_expired = True
                _LOGGER.debug(
                    "Startup grace period expired after %ds, notifying entities",
                    self._startup_grace_period,
                )
                # Notify entities to re-evaluate availability without marking
                # update as successful (which would make entities think we have data)
                self.async_update_listeners()

            # Check if reconnect grace period just expired
            if (
                self._disconnect_time is not None
                and not self._reconnect_grace_logged_expired
                and not self.in_reconnect_grace_period
            ):
                self._reconnect_grace_logged_expired = True
                _LOGGER.debug(
                    "Reconnect grace period expired after %ds, notifying entities",
                    self._reconnect_grace_period,
                )
                self.async_update_listeners()

            raise UpdateFailed(err) from err

    async def async_first_refresh_or_default(self) -> None:
        """Attempt first refresh, falling back to default data if unavailable."""
        # Load persisted runtime hours before first refresh
        await self.async_load_stored_data()
        await self.async_refresh()
        # If refresh failed and we have no data, use default data
        if self.data is None:
            self.data = self._last_successful_data or self._create_default_data()

    def get_device_by_id(
        self, device_type: DeviceType, device_id: int
    ) -> Device | None:
        """Return device by device id."""
        try:
            return [
                device
                for device in self.data.devices
                if device.device_type == device_type and device.device_id == device_id
            ][0]
        except IndexError:
            return None
