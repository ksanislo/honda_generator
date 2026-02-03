"""Honda Generator BLE API.

Provides BLE communication with Honda generators (EU2200i, EU3200i, EM5000SX, EM6500SX, EU7000is)
for diagnostics and control via Bluetooth Low Energy.

Two architectures are supported:
- Poll: Request-response diagnostic reads (EU2200i, EM5000SX, EM6500SX, EU7000is)
- Push: Continuous CAN data stream (EU3200i)
"""

import asyncio
import logging
import struct
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

# BLE UUIDs - Remote Control Service (066B0001-...)
REMOTE_CONTROL_SERVICE_UUID = "066B0001-5D90-4939-A7BA-7B9222F53E81"
ENGINE_CONTROL_CHAR = "066B0002-5D90-4939-A7BA-7B9222F53E81"
ENGINE_STATUS_CHAR = "066B0003-5D90-4939-A7BA-7B9222F53E81"
CONTROL_SEQUENCE_CONFIG_CHAR = "066B0004-5D90-4939-A7BA-7B9222F53E81"
SERIAL_NUMBER_CHAR = "066B0005-5D90-4939-A7BA-7B9222F53E81"
AUTHENTICATION_CHAR = "066B0006-5D90-4939-A7BA-7B9222F53E81"
CHANGE_PASSWORD_CHAR = "066B0007-5D90-4939-A7BA-7B9222F53E81"

# BLE UUIDs - Diagnostic Control Service (B4EF0001-...)
DIAGNOSTIC_SERVICE_UUID = "B4EF0001-62D2-483C-8293-119E2A99A82B"
DIAGNOSTIC_COMMAND_CHAR = "B4EF0002-62D2-483C-8293-119E2A99A82B"
DIAGNOSTIC_RESPONSE_CHAR = "B4EF0003-62D2-483C-8293-119E2A99A82B"
FIRMWARE_VERSION_CHAR = "B4EF0004-62D2-483C-8293-119E2A99A82B"
UNIT_OPERATION_CHAR = "B4EF0005-62D2-483C-8293-119E2A99A82B"

# BLE UUIDs - Generator Data Service (01B60001-...) - Used by both Poll (ECO mode) and Push
GENERATOR_DATA_SERVICE_UUID = "01B60001-875A-4C56-B8BF-5103CAFAEEC7"
GENERATOR_DATA_REQUEST_CHAR = "01B60002-875A-4C56-B8BF-5103CAFAEEC7"
GENERATOR_DATA_RESPONSE_CHAR = "01B60003-875A-4C56-B8BF-5103CAFAEEC7"
GENERATOR_CAN_DATA_CHAR = "01B60004-875A-4C56-B8BF-5103CAFAEEC7"
GENERATOR_ERROR_WARNING_CHAR = "01B60005-875A-4C56-B8BF-5103CAFAEEC7"

# BLE UUIDs - BT Unit Service (92CD0001-...) - Push architecture auth and serial number
BT_UNIT_SERVICE_UUID = "92CD0001-4F59-4599-A73C-C92C4AC7AADE"
BT_AUTH_CHAR = "92CD0002-4F59-4599-A73C-C92C4AC7AADE"
BT_SERIAL_CHAR = "92CD0007-4F59-4599-A73C-C92C4AC7AADE"  # Serial number characteristic


class Architecture(StrEnum):
    """Generator communication architecture."""

    POLL = "poll"  # Request-response diagnostic reads
    PUSH = "push"  # Continuous CAN data stream


# Serial number prefix to model name mapping
SERIAL_PREFIX_TO_MODEL: dict[str, str] = {
    "EAMT": "EU2200i",
    "EBKJ": "EU3200i",
    "EBMC": "EM5000SX",
    "EBJC": "EM6500SX",
    "EEJD": "EU7000is",
}

# Device name prefix to architecture mapping (BLE advertised name is the serial prefix)
DEVICE_NAME_TO_ARCHITECTURE: dict[str, Architecture] = {
    "EAMT": Architecture.POLL,  # EU2200i
    "EBKJ": Architecture.PUSH,  # EU3200i
    "EBMC": Architecture.POLL,  # EM5000SX
    "EBJC": Architecture.POLL,  # EM6500SX
    "EEJD": Architecture.POLL,  # EU7000is
}


@dataclass(frozen=True)
class ModelSpec:
    """Specifications for a generator model."""

    name: str
    max_power_watts: int
    fuel_tank_liters: float
    remote_start: bool
    fuel_sensor: bool
    eco_control: bool
    guest_mode: bool
    control_sequence: bytes | None
    architecture: Architecture = Architecture.POLL


MODEL_SPECS: dict[str, ModelSpec] = {
    "EU2200i": ModelSpec(
        "EU2200i",
        2200,
        3.6,
        False,
        False,
        False,
        False,
        bytes([0x01, 0x50, 0x3C, 0x00, 0x00]),
        Architecture.POLL,
    ),
    "EU3200i": ModelSpec(
        "EU3200i", 3200, 4.7, False, True, False, False, None, Architecture.PUSH
    ),
    "EM5000SX": ModelSpec(
        "EM5000SX",
        5000,
        23.47,
        True,
        False,
        True,
        True,
        bytes([0x03, 0x3C, 0x28, 0x3C, 0x28]),
        Architecture.POLL,
    ),
    "EM6500SX": ModelSpec(
        "EM6500SX",
        6500,
        23.47,
        True,
        False,
        True,
        True,
        bytes([0x03, 0x3C, 0x28, 0x3C, 0x28]),
        Architecture.POLL,
    ),
    "EU7000is": ModelSpec(
        "EU7000is",
        7000,
        19.31,
        True,
        True,
        False,
        True,
        bytes([0x02, 0x3C, 0x28, 0x28, 0x3C]),
        Architecture.POLL,
    ),
}


def get_model_spec(model: str) -> ModelSpec | None:
    """Get the specification for a model."""
    return MODEL_SPECS.get(model)


# Engine event code to translation key mapping
ENGINE_EVENT_KEYS: dict[int, str] = {
    0: "no_event",
    1: "engine_start",
    2: "engine_stop",
    3: "error",
    4: "voltage_drop",
}

# Engine error code to translation key mapping
ENGINE_ERROR_KEYS: dict[int, str] = {
    0: "no_error",
    1: "co_detected",
    2: "stop_failure",
    3: "continuous_restarting",
    5: "starting_circuit_fault",
}

# All possible engine event/error options for enum sensors
ENGINE_EVENT_OPTIONS: list[str] = list(ENGINE_EVENT_KEYS.values())
ENGINE_ERROR_OPTIONS: list[str] = list(ENGINE_ERROR_KEYS.values())

_LOGGER = logging.getLogger(__name__)

# Sanity bounds for sensor values (to catch corrupted BLE data)
BOUNDS_RUNTIME_HOURS = (0, 100000)  # 0 to 100k hours
BOUNDS_CURRENT = (0.0, 50.0)  # 0 to 50 amps
BOUNDS_POWER = (0, 10000)  # 0 to 10000 VA
BOUNDS_FUEL_LEVEL = (0, 100)  # 0 to 100 percent
BOUNDS_FUEL_REMAINING = (0, 1440)  # 0 to 24 hours in minutes

# ECO mode function command codes (for Generator Data Service)
FUNC_START_ECO = 0x1027
FUNC_STOP_ECO = 0x1028


class DeviceType(StrEnum):
    """Honda generator device types."""

    RUNTIME_HOURS = "runtime_hours"
    CURRENT = "current"
    POWER = "power"
    ECO_MODE = "eco_mode"
    ENGINE_EVENT = "engine_event"
    ENGINE_RUNNING = "engine_running"
    ENGINE_ERROR = "engine_error"
    OUTPUT_VOLTAGE = "output_voltage"
    FUEL_LEVEL = "fuel_level"
    FUEL_REMAINING_TIME = "fuel_remaining_time"
    # EU3200i-specific types (Push architecture)
    FUEL_VOLUME_ML = "fuel_volume_ml"  # Fuel volume in milliliters
    FUEL_REMAINS_LEVEL = "fuel_remains_level"  # Discrete fuel level (0-17)
    OUTPUT_VOLTAGE_SETTING = "output_voltage_setting"  # Configured output voltage


class DiagnosticCategory(StrEnum):
    """Categories of diagnostic reads that can be independently skipped."""

    WARNINGS_FAULTS = "warnings_faults"  # C'10, D'10, D'11
    RUNTIME_HOURS = "runtime_hours"  # B'00, B'01
    CURRENT = "current"  # B'13, B'14
    POWER = "power"  # B'17, B'18
    ECO_MODE = "eco_mode"  # B'19
    FUEL = "fuel"  # B'40, B'41, B'42 (EU7000is only)


# Map DeviceType to DiagnosticCategory (only for types that require reads)
DEVICE_TYPE_TO_DIAGNOSTIC: dict[DeviceType, DiagnosticCategory] = {
    DeviceType.RUNTIME_HOURS: DiagnosticCategory.RUNTIME_HOURS,
    DeviceType.CURRENT: DiagnosticCategory.CURRENT,
    DeviceType.POWER: DiagnosticCategory.POWER,
    DeviceType.ECO_MODE: DiagnosticCategory.ECO_MODE,
    DeviceType.FUEL_LEVEL: DiagnosticCategory.FUEL,
    DeviceType.FUEL_REMAINING_TIME: DiagnosticCategory.FUEL,
}


# Device metadata: maps DeviceType to display name
DEVICE_NAMES: dict[DeviceType, str] = {
    DeviceType.RUNTIME_HOURS: "Runtime Hours",
    DeviceType.CURRENT: "Output Current",
    DeviceType.POWER: "Output Power",
    DeviceType.ECO_MODE: "ECO Mode",
    DeviceType.ENGINE_EVENT: "Engine Event",
    DeviceType.ENGINE_RUNNING: "Engine Status",
    DeviceType.ENGINE_ERROR: "Engine Error",
    DeviceType.OUTPUT_VOLTAGE: "Output Voltage",
    DeviceType.FUEL_LEVEL: "Fuel Level",
    DeviceType.FUEL_REMAINING_TIME: "Fuel Remaining Time",
    # EU3200i-specific names
    DeviceType.FUEL_VOLUME_ML: "Fuel Volume",
    DeviceType.FUEL_REMAINS_LEVEL: "Fuel Gauge Level",
    DeviceType.OUTPUT_VOLTAGE_SETTING: "Output Voltage Setting",
}


# Device types for Poll architecture models
DEVICE_TYPES_POLL: list[DeviceType] = [
    DeviceType.RUNTIME_HOURS,
    DeviceType.CURRENT,
    DeviceType.POWER,
    DeviceType.ECO_MODE,
    DeviceType.ENGINE_EVENT,
    DeviceType.ENGINE_RUNNING,
    DeviceType.ENGINE_ERROR,
    DeviceType.OUTPUT_VOLTAGE,
    DeviceType.FUEL_LEVEL,
    DeviceType.FUEL_REMAINING_TIME,
]

# Device types for Push architecture models (EU3200i)
DEVICE_TYPES_PUSH: list[DeviceType] = [
    DeviceType.RUNTIME_HOURS,
    DeviceType.CURRENT,
    DeviceType.POWER,
    DeviceType.ECO_MODE,
    DeviceType.ENGINE_RUNNING,
    DeviceType.OUTPUT_VOLTAGE,
    DeviceType.FUEL_LEVEL,
    DeviceType.FUEL_VOLUME_ML,
    DeviceType.FUEL_REMAINS_LEVEL,
    DeviceType.FUEL_REMAINING_TIME,
    DeviceType.OUTPUT_VOLTAGE_SETTING,
]

# All device types (for backwards compatibility)
DEVICE_TYPES: list[DeviceType] = DEVICE_TYPES_POLL


@dataclass
class Device:
    """API device."""

    device_id: int
    device_unique_id: str
    device_type: DeviceType
    name: str
    state: int | float | bool | str | None


class GeneratorAPIProtocol(ABC):
    """Abstract base class for generator API implementations.

    Defines the common interface for both Poll and Push architecture APIs.
    """

    @property
    @abstractmethod
    def connected(self) -> bool:
        """Return whether the API is connected."""

    @property
    @abstractmethod
    def controller_name(self) -> str:
        """Return the controller address."""

    @property
    @abstractmethod
    def serial(self) -> str | None:
        """Return the generator serial number."""

    @property
    @abstractmethod
    def model(self) -> str | None:
        """Return the generator model name."""

    @property
    @abstractmethod
    def firmware_version(self) -> str | None:
        """Return the generator firmware version."""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the generator."""

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from the generator."""

    @abstractmethod
    async def get_devices(
        self, enabled_categories: set[DiagnosticCategory] | None = None
    ) -> list[Device]:
        """Get all device states."""

    @abstractmethod
    async def engine_stop(self) -> bool:
        """Stop the generator engine."""

    async def engine_start(self) -> bool:
        """Start the generator engine (optional, only for models with remote start)."""
        return False

    async def set_eco_mode(self, enabled: bool) -> bool:
        """Set the ECO mode state (optional, only for models with ECO control)."""
        return False

    @staticmethod
    def get_model_from_serial(serial: str) -> str:
        """Get the generator model name from serial number prefix."""
        prefix = serial.split("-")[0] if "-" in serial else serial[:4]
        return SERIAL_PREFIX_TO_MODEL.get(prefix, "Unknown")


class PollAPI(GeneratorAPIProtocol):
    """Honda Generator BLE API for Poll architecture.

    Uses request-response diagnostic reads for EU2200i, EM5000SX, EM6500SX, EU7000is.
    """

    def __init__(
        self,
        ble_device,
        pwd: str,
        on_engine_status_update: "Callable[[int, bool, int, int], None] | None" = None,
    ) -> None:
        """Initialize the API."""
        self._ble_device = ble_device
        self._client: BleakClient | None = None
        self._lock = asyncio.Lock()
        self._queue: asyncio.Queue = asyncio.Queue()
        self.pwd = pwd
        self._connected: bool = False
        self._shutting_down: bool = False
        self._warnings_raw: int = 0
        self._faults_raw: int = 0
        # Engine control notification values
        self._engine_event: int = 0
        self._engine_running: bool = False
        self._engine_error: int = 0
        self._output_voltage: int = 0
        self._on_engine_status_update = on_engine_status_update
        # Device identification (populated during connect)
        self._serial: str | None = None
        self._model: str | None = None
        self._guest_validity: bool = False
        self._firmware_version: str | None = None

    @property
    def connected(self) -> bool:
        """Return whether the API is connected."""
        return self._connected

    @connected.setter
    def connected(self, value: bool) -> None:
        """Set the connected state."""
        self._connected = value

    @property
    def controller_name(self) -> str:
        """Return the controller address."""
        return self._ble_device.address

    @property
    def serial(self) -> str | None:
        """Return the generator serial number (populated during connect)."""
        return self._serial

    @property
    def model(self) -> str | None:
        """Return the generator model name (populated during connect)."""
        return self._model

    @property
    def guest_validity(self) -> bool:
        """Return whether guest mode is enabled on the generator."""
        return self._guest_validity

    @property
    def firmware_version(self) -> str | None:
        """Return the generator firmware version (populated during connect)."""
        return self._firmware_version

    def _on_disconnect(self, _client: BleakClient) -> None:
        """Handle BLE disconnection callback from bleak."""
        if self._shutting_down:
            _LOGGER.debug("BLE device disconnected (expected - shutting down)")
        else:
            _LOGGER.debug(
                "BLE device disconnected unexpectedly from %s",
                self._ble_device.address,
            )
        self.connected = False
        # Don't set _client to None here - let disconnect() handle cleanup
        # Setting it to None here can cause issues if disconnect() is still running

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle BLE notification."""
        self._queue.put_nowait(data)

    def _engine_drive_status_notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle ENGINE_DRIVE_STATUS characteristic notification."""
        if len(data) >= 4:
            self._engine_event = data[0]
            self._engine_running = bool(data[1])
            self._engine_error = data[2]
            self._output_voltage = data[3]
            _LOGGER.debug(
                "Engine drive status notification: event=%d, running=%s, error=%d, voltage=%d",
                self._engine_event,
                self._engine_running,
                self._engine_error,
                self._output_voltage,
            )
            if self._on_engine_status_update:
                self._on_engine_status_update(
                    self._engine_event,
                    self._engine_running,
                    self._engine_error,
                    self._output_voltage,
                )

    def _create_command(self, register: str, position: str) -> bytearray:
        """Create diagnostic command with checksum."""
        data = bytearray(
            [
                0x01,
                0x42,
                ord(register[0]),
                ord(position[0]),
                ord(position[1]),
                0x30,
                0x30,
                0x00,
                0x00,  # Checksum placeholder
                0x04,
            ]
        )
        # Calculate XOR checksum of bytes 1-6
        cksum = 0
        for i in range(1, 7):
            cksum ^= data[i]
        data[7] = ord(format(cksum >> 4, "X"))  # High nibble
        data[8] = ord(format(cksum & 0xF, "X"))  # Low nibble
        return data

    def _verify_checksum(self, data: bytearray) -> bool:
        """Verify response checksum."""
        cksum = 0
        for i in range(1, 7):
            cksum ^= data[i]
        expected_high = ord(format(cksum >> 4, "X"))
        expected_low = ord(format(cksum & 0xF, "X"))
        return data[7] == expected_high and data[8] == expected_low

    async def _read_diagnostic(self, register: str, position: str) -> bytes:
        """Read a diagnostic byte from the generator."""
        if self._shutting_down:
            _LOGGER.debug(
                "Skipping diagnostic read %s%s: shutting down", register, position
            )
            return b"\x00"

        if not self._client or not self._client.is_connected:
            raise BleakError("Not connected")

        for attempt in range(3):
            if self._shutting_down:
                _LOGGER.debug("Aborting diagnostic read: shutting down")
                return b"\x00"

            # Check if connection was lost (e.g., after engine_stop)
            if not self.connected or not self._client or not self._client.is_connected:
                _LOGGER.debug("Aborting diagnostic read: connection lost")
                raise BleakError("Connection lost")

            # Clear stale queue data
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            try:
                await asyncio.wait_for(
                    self._client.write_gatt_char(
                        DIAGNOSTIC_COMMAND_CHAR,
                        self._create_command(register, position),
                    ),
                    timeout=1.0,
                )
            except Exception as exc:
                _LOGGER.debug("Write failed (attempt %d): %s", attempt + 1, exc)
                if self._shutting_down:
                    return b"\x00"
                await asyncio.sleep(0.2)
                continue

            await asyncio.sleep(0.1)

            # Try to get the correct response, allowing for stale responses in the queue
            for response_attempt in range(3):
                try:
                    # Use shorter timeout after first response attempt since we're
                    # waiting for a potentially queued response
                    timeout = 2.0 if response_attempt == 0 else 0.5
                    raw = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                    data = bytearray(raw[1:])  # Skip first byte
                    if self._verify_checksum(data):
                        # Verify response matches request
                        resp_register = chr(data[2])
                        resp_position = data[3:5].decode()
                        if resp_register != register or resp_position != position:
                            _LOGGER.debug(
                                "Response mismatch (attempt %d.%d): requested %s%s, got %s%s, waiting for correct response",
                                attempt + 1,
                                response_attempt + 1,
                                register,
                                position,
                                resp_register,
                                resp_position,
                            )
                            continue
                        result = bytes.fromhex(data[5:7].decode())
                        _LOGGER.debug(
                            "Diagnostic read %s%s: 0x%s",
                            register,
                            position,
                            result.hex().upper(),
                        )
                        return result
                    _LOGGER.debug(
                        "Checksum mismatch (attempt %d.%d)",
                        attempt + 1,
                        response_attempt + 1,
                    )
                except TimeoutError:
                    if response_attempt == 0:
                        _LOGGER.debug("Timeout (attempt %d)", attempt + 1)
                    break  # No more responses coming, retry with new write

        raise APIReadError(
            f"Diagnostic read {register}{position} failed after 3 attempts"
        )

    async def connect(self) -> bool:
        """Connect to the generator following the protocol initialization sequence."""
        if self._shutting_down:
            _LOGGER.debug("Connect aborted: API is shutting down")
            return False

        async with self._lock:
            if self._shutting_down:
                _LOGGER.debug("Connect aborted (in lock): API is shutting down")
                return False

            # === BLE Connection ===
            if self._client is None or not self._client.is_connected:
                _LOGGER.debug(
                    "Initiating BLE connection to %s (name: %s)",
                    self._ble_device.address,
                    getattr(self._ble_device, "name", "unknown"),
                )
                try:
                    self._client = await establish_connection(
                        BleakClient,
                        self._ble_device,
                        self._ble_device.address,
                        disconnected_callback=self._on_disconnect,
                        max_attempts=3,
                    )
                    _LOGGER.debug(
                        "BLE connection established to %s (MTU: %s)",
                        self._ble_device.address,
                        getattr(self._client, "mtu_size", "unknown"),
                    )
                    if self._shutting_down:
                        _LOGGER.debug(
                            "Shutdown requested after connection established, aborting setup"
                        )
                        return False
                except TimeoutError as exc:
                    _LOGGER.debug(
                        "Connection timeout to %s: %s", self._ble_device.address, exc
                    )
                    self._client = None
                    raise APIConnectionError("Connection timeout") from exc
                except BleakError as exc:
                    _LOGGER.debug(
                        "Connection failed to %s: %s", self._ble_device.address, exc
                    )
                    self._client = None
                    raise APIConnectionError(f"Connection failed: {exc}") from exc
            else:
                _LOGGER.debug(
                    "Reusing existing connection to %s", self._ble_device.address
                )

            # Pair
            _LOGGER.debug("Attempting BLE pairing with %s", self._ble_device.address)
            try:
                await self._client.pair()
                _LOGGER.debug("Pairing completed with %s", self._ble_device.address)
            except Exception as exc:
                _LOGGER.debug("Pairing skipped (may already be paired): %s", exc)

            if self._shutting_down:
                _LOGGER.debug("Shutdown requested after pairing, aborting setup")
                return False

            # Subscribe to notifications
            _LOGGER.debug(
                "Subscribing to diagnostic response notifications on %s",
                self._ble_device.address,
            )
            await self._client.start_notify(
                DIAGNOSTIC_RESPONSE_CHAR, self._notification_handler
            )

            _LOGGER.debug(
                "Subscribing to engine status notifications on %s",
                self._ble_device.address,
            )
            await self._client.start_notify(
                ENGINE_STATUS_CHAR, self._engine_drive_status_notification_handler
            )

            if self._shutting_down:
                _LOGGER.debug("Shutdown requested after subscriptions, aborting setup")
                return False

            # === Initialization Sequence (per protocol) ===

            # Step 1: Read guest validity status
            _LOGGER.debug("Reading guest validity status")
            try:
                guest_data = await asyncio.wait_for(
                    self._client.read_gatt_char(CHANGE_PASSWORD_CHAR),
                    timeout=5.0,
                )
                self._guest_validity = bool(guest_data[0]) if guest_data else False
                _LOGGER.debug("Guest validity: %s", self._guest_validity)
            except (TimeoutError, BleakError) as exc:
                _LOGGER.debug("Failed to read guest validity: %s", exc)
                self._guest_validity = False

            if self._shutting_down:
                return False

            # Step 2: Authenticate
            _LOGGER.debug("Sending authentication to %s", self._ble_device.address)
            try:
                await asyncio.wait_for(
                    self._client.write_gatt_char(
                        AUTHENTICATION_CHAR, bytearray([0x01]) + self.pwd.encode()
                    ),
                    timeout=5.0,
                )
            except TimeoutError as exc:
                _LOGGER.debug("Authentication write timed out: %s", exc)
                raise APIConnectionError("Authentication timed out") from exc
            _LOGGER.debug("Authentication sent to %s", self._ble_device.address)

            if self._shutting_down:
                return False

            # Step 3: Read serial number and determine model
            _LOGGER.debug("Reading serial number")
            try:
                serial_data = await asyncio.wait_for(
                    self._client.read_gatt_char(SERIAL_NUMBER_CHAR),
                    timeout=5.0,
                )
                # Serial is ASCII string, strip null padding
                self._serial = serial_data.decode().rstrip("\x00").split(" ")[0]
                self._model = self.get_model_from_serial(self._serial)
                _LOGGER.debug("Serial: %s, Model: %s", self._serial, self._model)
            except (TimeoutError, BleakError) as exc:
                _LOGGER.debug("Failed to read serial number: %s", exc)
                raise APIConnectionError("Failed to read serial number") from exc

            if self._shutting_down:
                return False

            # Step 4: Read and verify control sequence config (check Profile ID only)
            model_spec = get_model_spec(self._model) if self._model else None
            if model_spec and model_spec.control_sequence:
                _LOGGER.debug("Reading control sequence config")
                try:
                    config_data = await asyncio.wait_for(
                        self._client.read_gatt_char(CONTROL_SEQUENCE_CONFIG_CHAR),
                        timeout=5.0,
                    )
                    expected = model_spec.control_sequence
                    expected_profile_id = expected[0]
                    actual_profile_id = config_data[0] if config_data else None

                    if actual_profile_id != expected_profile_id:
                        _LOGGER.warning(
                            "Control sequence profile ID mismatch: got 0x%02X, expected 0x%02X",
                            actual_profile_id,
                            expected_profile_id,
                        )
                        # Try to write correct sequence (only works as owner)
                        _LOGGER.debug("Attempting to write correct control sequence")
                        try:
                            await asyncio.wait_for(
                                self._client.write_gatt_char(
                                    CONTROL_SEQUENCE_CONFIG_CHAR, bytearray(expected)
                                ),
                                timeout=5.0,
                            )
                            # Read back to verify
                            config_data = await asyncio.wait_for(
                                self._client.read_gatt_char(
                                    CONTROL_SEQUENCE_CONFIG_CHAR
                                ),
                                timeout=5.0,
                            )
                            actual_profile_id = config_data[0] if config_data else None
                            if actual_profile_id != expected_profile_id:
                                _LOGGER.error(
                                    "Control sequence profile ID still mismatched after write: 0x%02X",
                                    actual_profile_id,
                                )
                        except (TimeoutError, BleakError) as exc:
                            _LOGGER.warning(
                                "Failed to correct control sequence: %s", exc
                            )
                    else:
                        _LOGGER.debug(
                            "Control sequence verified: profile ID 0x%02X, data %s",
                            actual_profile_id,
                            config_data.hex(),
                        )
                except (TimeoutError, BleakError) as exc:
                    _LOGGER.debug("Failed to read control sequence: %s", exc)

            if self._shutting_down:
                return False

            # Step 5: Write serial number to register (owner only)
            if self._serial:
                _LOGGER.debug("Registering serial number")
                try:
                    # Format: serial + 0x20 (space) + null padding
                    serial_bytes = self._serial.encode()
                    write_data = bytearray(17)
                    write_data[: len(serial_bytes)] = serial_bytes
                    write_data[len(serial_bytes)] = 0x20  # Space delimiter
                    # Remaining bytes are already 0x00

                    await asyncio.wait_for(
                        self._client.write_gatt_char(SERIAL_NUMBER_CHAR, write_data),
                        timeout=5.0,
                    )
                    _LOGGER.debug("Serial number registered")
                except (TimeoutError, BleakError) as exc:
                    _LOGGER.debug("Failed to register serial number: %s", exc)

            if self._shutting_down:
                return False

            # Step 6: Read firmware version
            _LOGGER.debug("Reading firmware version")
            try:
                fw_data = await asyncio.wait_for(
                    self._client.read_gatt_char(FIRMWARE_VERSION_CHAR),
                    timeout=5.0,
                )
                # Decode BCD: each nibble is a separate version component
                self._firmware_version = ".".join(
                    str((fw_data[i // 2] >> (4 if i % 2 == 0 else 0)) & 0x0F)
                    for i in range(4)
                )
                _LOGGER.debug("Firmware version: %s", self._firmware_version)
            except (TimeoutError, BleakError) as exc:
                _LOGGER.debug("Failed to read firmware version: %s", exc)

            self.connected = True
            _LOGGER.debug("Connection setup complete for %s", self._ble_device.address)
            return True

    async def disconnect(self) -> bool:
        """Disconnect from the generator.

        Sets shutdown flag to stop in-progress operations, then waits
        for the lock to ensure any pending operations complete cleanly.
        """
        _LOGGER.debug("Disconnect requested, setting shutdown flag")
        self._shutting_down = True

        # Wait for any in-progress operations to complete
        _LOGGER.debug("Waiting for lock to ensure pending operations complete")
        async with self._lock:
            _LOGGER.debug("Lock acquired, proceeding with disconnect")
            if self._client:
                try:
                    if self._client.is_connected:
                        _LOGGER.debug("Stopping diagnostic response notifications")
                        try:
                            await self._client.stop_notify(DIAGNOSTIC_RESPONSE_CHAR)
                        except Exception as exc:
                            _LOGGER.debug(
                                "Error stopping diagnostic notifications: %s", exc
                            )

                        _LOGGER.debug("Stopping engine drive status notifications")
                        try:
                            await self._client.stop_notify(ENGINE_STATUS_CHAR)
                        except Exception as exc:
                            _LOGGER.debug(
                                "Error stopping engine status notifications: %s", exc
                            )

                        # Brief pause to let any final notifications process
                        await asyncio.sleep(0.1)

                        _LOGGER.debug("Disconnecting BLE client")
                        await self._client.disconnect()
                        _LOGGER.debug("BLE client disconnected")
                    else:
                        _LOGGER.debug("Client already disconnected, cleaning up")
                except Exception as exc:
                    _LOGGER.debug("Disconnect error: %s", exc)
                finally:
                    self._client = None
            else:
                _LOGGER.debug("No client to disconnect")

        self.connected = False
        _LOGGER.debug("Disconnect complete")
        return True

    async def _read_engine_drive_status(self) -> None:
        """Read and parse ENGINE_DRIVE_STATUS characteristic."""
        if not self._client or not self._client.is_connected:
            return
        try:
            data = await asyncio.wait_for(
                self._client.read_gatt_char(ENGINE_STATUS_CHAR),
                timeout=1.0,
            )
            if len(data) >= 4:
                self._engine_event = data[0]
                self._engine_running = bool(data[1])
                self._engine_error = data[2]
                self._output_voltage = data[3]
                _LOGGER.debug(
                    "Engine drive status read: event=%d, running=%s, error=%d, voltage=%d",
                    self._engine_event,
                    self._engine_running,
                    self._engine_error,
                    self._output_voltage,
                )
        except (BleakError, TimeoutError) as exc:
            _LOGGER.debug("Failed to read engine drive status: %s", exc)

    async def get_devices(
        self, enabled_categories: set[DiagnosticCategory] | None = None
    ) -> list[Device]:
        """Get all device states.

        Args:
            enabled_categories: Set of diagnostic categories to read. If None,
                reads all categories. Categories not in this set will be skipped,
                and their corresponding devices will have default values.
        """
        if self._shutting_down:
            _LOGGER.debug("Skipping get_devices: shutting down")
            raise APIConnectionError("API is shutting down")

        # Default to all categories if not specified
        if enabled_categories is None:
            enabled_categories = set(DiagnosticCategory)

        try:
            # Pre-fetch warning/fault data for binary sensors (only if enabled)
            if DiagnosticCategory.WARNINGS_FAULTS in enabled_categories:
                self._warnings_raw = (await self._read_diagnostic("C", "10"))[0]
                if self._shutting_down:
                    raise APIConnectionError("API is shutting down")

                faults_bytes = await self._read_diagnostic(
                    "D", "10"
                ) + await self._read_diagnostic("D", "11")
                self._faults_raw = struct.unpack(">H", faults_bytes)[0]
                _LOGGER.debug(
                    "Warnings/faults read: warnings=0x%02X, faults=0x%04X",
                    self._warnings_raw,
                    self._faults_raw,
                )
            else:
                _LOGGER.debug("Skipping warnings/faults read (category disabled)")

            if self._shutting_down:
                raise APIConnectionError("API is shutting down")

            # Read engine drive status
            await self._read_engine_drive_status()

            devices = []
            for device_type in DEVICE_TYPES:
                if self._shutting_down:
                    raise APIConnectionError("API is shutting down")
                devices.append(
                    Device(
                        device_id=1,
                        device_unique_id=f"{self.controller_name}_{device_type}",
                        device_type=device_type,
                        name=DEVICE_NAMES.get(device_type, str(device_type)),
                        state=await self._get_value(device_type, enabled_categories),
                    )
                )
            return devices
        except BleakError as exc:
            _LOGGER.debug("BLE error: %s", exc)
            self.connected = False
            raise APIConnectionError("BLE connection lost") from exc

    async def _get_value(
        self,
        device_type: DeviceType,
        enabled_categories: set[DiagnosticCategory],
    ) -> int | float | bool | str | None:
        """Get value for a device type.

        Args:
            device_type: The device type to get the value for.
            enabled_categories: Set of enabled diagnostic categories.
                If the device type's category is not enabled, returns a default value.

        Returns:
            The sensor value, or None if the value failed bounds checking
            (which will cause the sensor to report as unavailable).
        """
        # Check if this device type requires a diagnostic read
        required_category = DEVICE_TYPE_TO_DIAGNOSTIC.get(device_type)
        if required_category and required_category not in enabled_categories:
            _LOGGER.debug(
                "Skipping %s read (category %s disabled)",
                device_type,
                required_category,
            )
            # Return default values for skipped reads
            if device_type == DeviceType.ECO_MODE:
                return False
            return 0

        match device_type:
            case DeviceType.RUNTIME_HOURS:
                data = await self._read_diagnostic(
                    "B", "00"
                ) + await self._read_diagnostic("B", "01")
                value = struct.unpack(">h", data)[0]
                if not BOUNDS_RUNTIME_HOURS[0] <= value <= BOUNDS_RUNTIME_HOURS[1]:
                    _LOGGER.warning(
                        "Runtime hours value %d out of bounds %s, marking unavailable",
                        value,
                        BOUNDS_RUNTIME_HOURS,
                    )
                    return None
                _LOGGER.debug("Runtime hours: %d", value)
                return value

            case DeviceType.CURRENT:
                data = await self._read_diagnostic(
                    "B", "13"
                ) + await self._read_diagnostic("B", "14")
                value = struct.unpack(">h", data)[0] / 10
                if not BOUNDS_CURRENT[0] <= value <= BOUNDS_CURRENT[1]:
                    _LOGGER.warning(
                        "Output current value %.1f out of bounds %s, marking unavailable",
                        value,
                        BOUNDS_CURRENT,
                    )
                    return None
                _LOGGER.debug("Output current: %.1f A", value)
                return value

            case DeviceType.POWER:
                data = await self._read_diagnostic(
                    "B", "17"
                ) + await self._read_diagnostic("B", "18")
                value = struct.unpack(">h", data)[0] * 10
                if not BOUNDS_POWER[0] <= value <= BOUNDS_POWER[1]:
                    _LOGGER.warning(
                        "Output power value %d out of bounds %s, marking unavailable",
                        value,
                        BOUNDS_POWER,
                    )
                    return None
                _LOGGER.debug("Output power: %d VA", value)
                return value

            case DeviceType.ECO_MODE:
                data = await self._read_diagnostic("B", "19")
                value = not bool(data[0] & 1)
                _LOGGER.debug("ECO mode: %s", value)
                return value

            case DeviceType.ENGINE_EVENT:
                return self._engine_event

            case DeviceType.ENGINE_RUNNING:
                return self._engine_running

            case DeviceType.ENGINE_ERROR:
                return self._engine_error

            case DeviceType.OUTPUT_VOLTAGE:
                return self._output_voltage

            case DeviceType.FUEL_LEVEL:
                # Fuel level is only available on EU7000is (B'40)
                model_spec = get_model_spec(self._model) if self._model else None
                if not model_spec or not model_spec.fuel_sensor:
                    return None  # Not supported on this model
                data = await self._read_diagnostic("B", "40")
                value = data[0]
                if not BOUNDS_FUEL_LEVEL[0] <= value <= BOUNDS_FUEL_LEVEL[1]:
                    _LOGGER.warning(
                        "Fuel level value %d out of bounds %s, marking unavailable",
                        value,
                        BOUNDS_FUEL_LEVEL,
                    )
                    return None
                _LOGGER.debug("Fuel level: %d%%", value)
                return value

            case DeviceType.FUEL_REMAINING_TIME:
                # Fuel remaining time is only available on EU7000is (B'41, B'42)
                model_spec = get_model_spec(self._model) if self._model else None
                if not model_spec or not model_spec.fuel_sensor:
                    return None  # Not supported on this model
                data = await self._read_diagnostic(
                    "B", "41"
                ) + await self._read_diagnostic("B", "42")
                value = struct.unpack(">H", data)[0]
                if not BOUNDS_FUEL_REMAINING[0] <= value <= BOUNDS_FUEL_REMAINING[1]:
                    _LOGGER.warning(
                        "Fuel remaining time value %d out of bounds %s, marking unavailable",
                        value,
                        BOUNDS_FUEL_REMAINING,
                    )
                    return None
                _LOGGER.debug("Fuel remaining time: %d minutes", value)
                return value

            case _:
                return 0

    def get_warning_bit(self, bit: int) -> bool:
        """Get the state of a warning bit."""
        return bool(self._warnings_raw & (1 << bit))

    def get_fault_bit(self, bit: int) -> bool:
        """Get the state of a fault bit."""
        return bool(self._faults_raw & (1 << bit))

    async def get_serial(self) -> str:
        """Get the generator serial number.

        Returns the cached serial from connect() if available,
        otherwise reads from the device.
        """
        # Return cached value if available
        if self._serial:
            return self._serial

        if not self._client or not self._client.is_connected:
            raise APIConnectionError("Not connected")
        try:
            data = await asyncio.wait_for(
                self._client.read_gatt_char(SERIAL_NUMBER_CHAR),
                timeout=5.0,
            )
        except TimeoutError as exc:
            _LOGGER.debug("Serial number read timed out: %s", exc)
            raise APIConnectionError("Serial number read timed out") from exc
        serial = data.decode().rstrip("\x00").split(" ")[0]
        _LOGGER.debug("Serial number read: %s", serial)
        return serial

    async def get_firmware_version(self) -> str:
        """Get the generator firmware version (BCD encoded).

        Returns the cached firmware version from connect() if available,
        otherwise reads from the device.
        """
        # Return cached value if available
        if self._firmware_version:
            return self._firmware_version

        if not self._client or not self._client.is_connected:
            raise APIConnectionError("Not connected")
        try:
            data = await asyncio.wait_for(
                self._client.read_gatt_char(FIRMWARE_VERSION_CHAR),
                timeout=5.0,
            )
        except TimeoutError as exc:
            _LOGGER.debug("Firmware version read timed out: %s", exc)
            raise APIConnectionError("Firmware version read timed out") from exc
        # Decode BCD: each nibble is a separate version component
        version = ".".join(
            str((data[i // 2] >> (4 if i % 2 == 0 else 0)) & 0x0F) for i in range(4)
        )
        _LOGGER.debug("Firmware version read: %s", version)
        return version

    async def engine_stop(self, max_attempts: int = 3) -> bool:
        """Stop the generator engine.

        Sends the stop command repeatedly until the connection drops
        (indicating the generator shut off) or max attempts reached.

        Args:
            max_attempts: Number of times to send the stop command (default 3).
        """
        if not self._client or not self._client.is_connected:
            _LOGGER.error("Cannot stop engine: not connected")
            return False

        attempts = 0

        while attempts < max_attempts:
            try:
                await asyncio.wait_for(
                    self._client.write_gatt_char(
                        ENGINE_CONTROL_CHAR, bytearray([0x00])
                    ),
                    timeout=1.0,
                )
                attempts += 1
                await asyncio.sleep(0.1)
            except TimeoutError:
                # Write timed out - generator likely shut off
                _LOGGER.debug(
                    "Engine stop: write timed out after %d attempts (generator shut off)",
                    attempts,
                )
                self.connected = False
                return True
            except Exception:
                # Connection dropped - generator likely shut off
                _LOGGER.debug(
                    "Engine stop: connection dropped after %d attempts (generator shut off)",
                    attempts,
                )
                self.connected = False
                return True

        _LOGGER.debug(
            "Engine stop command sent (%d attempts, connection still active)", attempts
        )
        return True

    async def engine_start(self) -> bool:
        """Start the generator engine (only for models with remote start support).

        Writes [0x01] to ENGINE_CONTROL_CHAR to start the engine.
        """
        if not self._client or not self._client.is_connected:
            _LOGGER.error("Cannot start engine: not connected")
            return False

        # Check if model supports remote start
        model_spec = get_model_spec(self._model) if self._model else None
        if not model_spec or not model_spec.remote_start:
            _LOGGER.error(
                "Cannot start engine: model %s does not support remote start",
                self._model or "Unknown",
            )
            return False

        try:
            await asyncio.wait_for(
                self._client.write_gatt_char(ENGINE_CONTROL_CHAR, bytearray([0x01])),
                timeout=5.0,
            )
            _LOGGER.info("Engine start command sent")
            return True
        except TimeoutError as exc:
            _LOGGER.error("Engine start command timed out: %s", exc)
            return False
        except BleakError as exc:
            _LOGGER.error("Engine start command failed: %s", exc)
            return False

    async def set_eco_mode(self, enabled: bool) -> bool:
        """Set the ECO mode state (only for models with ECO control support).

        Sends a function command via Generator Data Service:
        - Function 0x1027: Enable ECO mode
        - Function 0x1028: Disable ECO mode

        Args:
            enabled: True to enable ECO mode, False to disable.

        Returns:
            True if the command was sent successfully.
        """
        if not self._client or not self._client.is_connected:
            _LOGGER.error("Cannot set ECO mode: not connected")
            return False

        # Check if model supports ECO control
        model_spec = get_model_spec(self._model) if self._model else None
        if not model_spec or not model_spec.eco_control:
            _LOGGER.error(
                "Cannot set ECO mode: model %s does not support ECO control",
                self._model or "Unknown",
            )
            return False

        func_code = FUNC_START_ECO if enabled else FUNC_STOP_ECO

        # Build 14-byte function command packet
        # Format: [0x01, func_hi, func_lo, 0x00 x 11]
        packet = bytearray(14)
        packet[0] = 0x01  # Command type
        packet[1] = (func_code >> 8) & 0xFF  # Function code high byte
        packet[2] = func_code & 0xFF  # Function code low byte
        # Bytes 3-13 are parameter bytes (all zeros for ECO mode)

        try:
            await asyncio.wait_for(
                self._client.write_gatt_char(GENERATOR_DATA_REQUEST_CHAR, packet),
                timeout=5.0,
            )
            _LOGGER.info("ECO mode %s command sent", "enable" if enabled else "disable")
            return True
        except TimeoutError as exc:
            _LOGGER.error("ECO mode command timed out: %s", exc)
            return False
        except BleakError as exc:
            _LOGGER.error("ECO mode command failed: %s", exc)
            return False


# CAN message IDs for Push architecture (EU3200i)
CAN_ECU_STATUS = 0x312
CAN_INV_INFO = 0x332
CAN_INV_INFO2 = 0x352
CAN_ECU_INFO_ETC = 0x362
CAN_OUTPUT_SETTING = 0x5D2
CAN_ECU_ERROR = 0x3A2
CAN_INV_ERROR = 0x3B2
CAN_BT_ERROR = 0x3A5

# Function command codes for Push architecture
FUNC_ENGINE_STOP = 0x0402

# Voltage setting mapping for EU3200i
VOLTAGE_SETTINGS: dict[int, int] = {
    1: 100,
    2: 110,
    3: 115,
    4: 120,
    5: 220,
    6: 230,
    7: 240,
}


class PushAPI(GeneratorAPIProtocol):
    """Honda Generator BLE API for Push architecture.

    Uses continuous CAN data stream for EU3200i. Data is pushed from the generator
    rather than polled, providing real-time updates.
    """

    def __init__(
        self,
        ble_device,
        pwd: str,
        on_data_update: "Callable[[dict], None] | None" = None,
    ) -> None:
        """Initialize the Push API.

        Args:
            ble_device: The BLE device to connect to.
            pwd: The authentication password.
            on_data_update: Callback invoked when new data is received from the stream.
        """
        self._ble_device = ble_device
        self._client: BleakClient | None = None
        self._lock = asyncio.Lock()
        self.pwd = pwd
        self._connected: bool = False
        self._shutting_down: bool = False
        self._stream_active: bool = False
        self._on_data_update = on_data_update

        # Device identification
        self._serial: str | None = None
        self._model: str | None = None
        self._firmware_version: str | None = None

        # Cached state from CAN data stream
        self._state: dict = {
            "engine_mode": 0,
            "eco_status": False,
            "power_watts": 0,
            "voltage": 0,
            "current": 0.0,
            "runtime_hours": 0,
            "fuel_ml": 0,
            "fuel_remaining_min": 0,
            "fuel_level_discrete": 0,
            "voltage_setting": 0,
            "ecu_errors": [],
            "inv_errors": [],
            "bt_errors": [],
        }

        # Response queue for synchronous operations
        self._response_queue: asyncio.Queue = asyncio.Queue()

    @property
    def connected(self) -> bool:
        """Return whether the API is connected."""
        return self._connected

    @connected.setter
    def connected(self, value: bool) -> None:
        """Set the connected state."""
        self._connected = value

    @property
    def controller_name(self) -> str:
        """Return the controller address."""
        return self._ble_device.address

    @property
    def serial(self) -> str | None:
        """Return the generator serial number."""
        return self._serial

    @property
    def model(self) -> str | None:
        """Return the generator model name."""
        return self._model

    @property
    def firmware_version(self) -> str | None:
        """Return the generator firmware version."""
        return self._firmware_version

    def _on_disconnect(self, _client: BleakClient) -> None:
        """Handle BLE disconnection callback."""
        if self._shutting_down:
            _LOGGER.debug(
                "Push API: BLE device disconnected (expected - shutting down)"
            )
        else:
            _LOGGER.debug(
                "Push API: BLE device disconnected unexpectedly from %s",
                self._ble_device.address,
            )
        self._connected = False
        self._stream_active = False

    def _handle_data_response(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle data response characteristic notification (01B60003)."""
        _LOGGER.debug("Push API: Data response: %s", data.hex())
        self._response_queue.put_nowait(data)

    def _handle_can_data(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle CAN data characteristic notification (01B60004).

        Parses CAN messages and updates internal state.
        """
        if len(data) < 3:
            return

        # First byte is packet type, next two bytes are CAN ID (little-endian)
        packet_type = data[0]
        if packet_type != 0x01:  # Only process data packets
            return

        can_id = struct.unpack("<H", data[1:3])[0]
        payload = data[3:]

        _LOGGER.debug("Push API: CAN data ID=0x%03X payload=%s", can_id, payload.hex())

        self._parse_can_message(can_id, payload)

        # Notify callback of state update
        if self._on_data_update:
            self._on_data_update(self._state.copy())

    def _handle_error_warning(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle error/warning characteristic notification (01B60005)."""
        _LOGGER.debug("Push API: Error/warning notification: %s", data.hex())

    def _parse_can_message(self, can_id: int, payload: bytes) -> None:
        """Parse a CAN message and update internal state."""
        if len(payload) < 2:
            return

        if can_id == CAN_ECU_STATUS:
            # ECU_STATUS: engine_mode (byte 0), eco_status (byte 2)
            if len(payload) >= 1:
                self._state["engine_mode"] = payload[0]
            if len(payload) >= 3:
                # ECO is active when byte 2 is 0 or 2
                self._state["eco_status"] = payload[2] in (0, 2)

        elif can_id == CAN_INV_INFO:
            # INV_INFO: power (bytes 0-1), voltage (bytes 2-3), current (bytes 4-5)
            if len(payload) >= 2:
                self._state["power_watts"] = struct.unpack("<H", payload[0:2])[0]
            if len(payload) >= 4:
                self._state["voltage"] = struct.unpack("<H", payload[2:4])[0]
            if len(payload) >= 6:
                raw_current = struct.unpack("<H", payload[4:6])[0]
                self._state["current"] = raw_current / 500.0

        elif can_id == CAN_INV_INFO2:
            # INV_INFO2: engine_hours (bytes 4-5)
            if len(payload) >= 6:
                self._state["runtime_hours"] = struct.unpack("<H", payload[4:6])[0]

        elif can_id == CAN_ECU_INFO_ETC:
            # ECU_INFO_ETC: fuel_ml (0-1), fuel_remains_min (2-3), fuel_level_discrete (5)
            if len(payload) >= 2:
                self._state["fuel_ml"] = struct.unpack("<H", payload[0:2])[0]
            if len(payload) >= 4:
                self._state["fuel_remaining_min"] = struct.unpack("<H", payload[2:4])[0]
            if len(payload) >= 6:
                self._state["fuel_level_discrete"] = payload[5]

        elif can_id == CAN_OUTPUT_SETTING:
            # OUTPUT_SETTING: voltage_setting (byte 0)
            if len(payload) >= 1:
                setting = payload[0]
                self._state["voltage_setting"] = VOLTAGE_SETTINGS.get(setting, 0)

        elif can_id == CAN_ECU_ERROR:
            # ECU error codes
            self._state["ecu_errors"] = self._parse_error_bytes(payload)

        elif can_id == CAN_INV_ERROR:
            # Inverter error codes
            self._state["inv_errors"] = self._parse_error_bytes(payload)

        elif can_id == CAN_BT_ERROR:
            # Bluetooth unit error codes
            self._state["bt_errors"] = self._parse_error_bytes(payload)

    @staticmethod
    def _parse_error_bytes(payload: bytes) -> list[int]:
        """Parse error code bytes into a list of active error bits."""
        errors = []
        for byte_idx, byte_val in enumerate(payload):
            for bit_idx in range(8):
                if byte_val & (1 << bit_idx):
                    errors.append(byte_idx * 8 + bit_idx)
        return errors

    async def connect(self) -> bool:
        """Connect to the generator and start the data stream."""
        if self._shutting_down:
            _LOGGER.debug("Push API: Connect aborted - shutting down")
            return False

        async with self._lock:
            if self._shutting_down:
                return False

            # === BLE Connection ===
            if self._client is None or not self._client.is_connected:
                _LOGGER.debug(
                    "Push API: Initiating connection to %s",
                    self._ble_device.address,
                )
                try:
                    self._client = await establish_connection(
                        BleakClient,
                        self._ble_device,
                        self._ble_device.address,
                        disconnected_callback=self._on_disconnect,
                        max_attempts=3,
                    )
                    _LOGGER.debug(
                        "Push API: Connected to %s",
                        self._ble_device.address,
                    )
                except TimeoutError as exc:
                    _LOGGER.debug("Push API: Connection timeout: %s", exc)
                    self._client = None
                    raise APIConnectionError("Connection timeout") from exc
                except BleakError as exc:
                    _LOGGER.debug("Push API: Connection failed: %s", exc)
                    self._client = None
                    raise APIConnectionError(f"Connection failed: {exc}") from exc

            if self._shutting_down:
                return False

            # === Subscribe to notifications ===
            _LOGGER.debug("Push API: Subscribing to data notifications")
            try:
                await self._client.start_notify(
                    GENERATOR_DATA_RESPONSE_CHAR,
                    self._handle_data_response,
                )
                await self._client.start_notify(
                    GENERATOR_CAN_DATA_CHAR,
                    self._handle_can_data,
                )
                await self._client.start_notify(
                    GENERATOR_ERROR_WARNING_CHAR,
                    self._handle_error_warning,
                )
            except BleakError as exc:
                _LOGGER.error("Push API: Failed to subscribe to notifications: %s", exc)
                raise APIConnectionError(f"Notification setup failed: {exc}") from exc

            if self._shutting_down:
                return False

            # === Authenticate via BT Unit Service ===
            _LOGGER.debug("Push API: Authenticating")
            try:
                # Password format: [0x01] + password bytes
                auth_data = bytearray([0x01]) + self.pwd.encode()
                await asyncio.wait_for(
                    self._client.write_gatt_char(BT_AUTH_CHAR, auth_data),
                    timeout=5.0,
                )
                _LOGGER.debug("Push API: Authentication sent")
            except TimeoutError as exc:
                _LOGGER.error("Push API: Authentication timed out: %s", exc)
                raise APIConnectionError("Authentication timed out") from exc
            except BleakError as exc:
                _LOGGER.error("Push API: Authentication failed: %s", exc)
                raise APIConnectionError(f"Authentication failed: {exc}") from exc

            if self._shutting_down:
                return False

            # === Start data stream ===
            _LOGGER.debug("Push API: Starting data stream")
            try:
                await self._start_data_stream()
            except Exception as exc:
                _LOGGER.error("Push API: Failed to start data stream: %s", exc)
                raise APIConnectionError(f"Data stream start failed: {exc}") from exc

            if self._shutting_down:
                return False

            # === Read serial number (must pause stream first) ===
            _LOGGER.debug("Push API: Reading serial number")
            try:
                async with self._with_stream_paused():
                    serial_data = await asyncio.wait_for(
                        self._client.read_gatt_char(BT_SERIAL_CHAR),
                        timeout=5.0,
                    )
                    # Serial is ASCII string (e.g., "EBKJ-1234567"), strip null padding
                    self._serial = serial_data.decode().rstrip("\x00")
                    self._model = self.get_model_from_serial(self._serial)
                    _LOGGER.debug(
                        "Push API: Serial: %s, Model: %s",
                        self._serial,
                        self._model,
                    )
            except (TimeoutError, BleakError) as exc:
                _LOGGER.warning("Push API: Failed to read serial number: %s", exc)
                # Fall back to defaults
                self._model = "EU3200i"
                self._serial = "Unknown"

            self._connected = True
            _LOGGER.debug("Push API: Connection complete")
            return True

    async def _start_data_stream(self) -> None:
        """Start the CAN data stream.

        Sends command [0x03, 0x01, 0x00...] to GENERATOR_DATA_REQUEST_CHAR.
        """
        if not self._client or not self._client.is_connected:
            raise APIConnectionError("Not connected")

        # Build start stream command: [0x03, 0x01, 0x00 x 12]
        packet = bytearray(14)
        packet[0] = 0x03  # Command type: stream control
        packet[1] = 0x01  # Start stream

        await asyncio.wait_for(
            self._client.write_gatt_char(GENERATOR_DATA_REQUEST_CHAR, packet),
            timeout=5.0,
        )
        self._stream_active = True
        _LOGGER.debug("Push API: Data stream started")

    async def _stop_data_stream(self) -> None:
        """Stop the CAN data stream.

        Sends command [0x04, 0x00, 0x00...] to GENERATOR_DATA_REQUEST_CHAR.
        """
        if not self._client or not self._client.is_connected:
            return

        # Build stop stream command: [0x04, 0x00, 0x00 x 12]
        packet = bytearray(14)
        packet[0] = 0x04  # Command type: stream control
        packet[1] = 0x00  # Stop stream

        try:
            await asyncio.wait_for(
                self._client.write_gatt_char(GENERATOR_DATA_REQUEST_CHAR, packet),
                timeout=2.0,
            )
            self._stream_active = False
            _LOGGER.debug("Push API: Data stream stopped")
        except Exception as exc:
            _LOGGER.warning("Push API: Failed to stop data stream: %s", exc)
            # Continue anyway - we'll force the command through

    @asynccontextmanager
    async def _with_stream_paused(self) -> AsyncIterator[None]:
        """Context manager to pause the data stream for control operations."""
        was_active = self._stream_active
        if was_active:
            await self._stop_data_stream()
            # Brief pause to let stream stop
            await asyncio.sleep(0.1)
        try:
            yield
        finally:
            if was_active and self._connected:
                try:
                    await self._start_data_stream()
                except Exception as exc:
                    _LOGGER.warning("Push API: Failed to restart data stream: %s", exc)

    async def disconnect(self) -> bool:
        """Disconnect from the generator."""
        _LOGGER.debug("Push API: Disconnect requested")
        self._shutting_down = True

        async with self._lock:
            if self._client:
                try:
                    # Stop data stream first
                    if self._stream_active:
                        await self._stop_data_stream()

                    if self._client.is_connected:
                        _LOGGER.debug("Push API: Stopping notifications")
                        try:
                            await self._client.stop_notify(GENERATOR_DATA_RESPONSE_CHAR)
                            await self._client.stop_notify(GENERATOR_CAN_DATA_CHAR)
                            await self._client.stop_notify(GENERATOR_ERROR_WARNING_CHAR)
                        except Exception as exc:
                            _LOGGER.debug(
                                "Push API: Error stopping notifications: %s", exc
                            )

                        await asyncio.sleep(0.1)
                        _LOGGER.debug("Push API: Disconnecting")
                        await self._client.disconnect()
                except Exception as exc:
                    _LOGGER.debug("Push API: Disconnect error: %s", exc)
                finally:
                    self._client = None

        self._connected = False
        _LOGGER.debug("Push API: Disconnect complete")
        return True

    async def get_devices(
        self, enabled_categories: set[DiagnosticCategory] | None = None
    ) -> list[Device]:
        """Get all device states from cached stream data.

        For Push architecture, this returns the cached state from the CAN data stream.
        No blocking reads are performed.
        """
        if self._shutting_down:
            raise APIConnectionError("API is shutting down")

        devices = []
        controller_name = self.controller_name

        # Calculate fuel level percentage from mL using tank capacity
        fuel_ml = self._state["fuel_ml"]
        fuel_level_percent: int | None = None
        if fuel_ml is not None:
            model_spec = get_model_spec(self._model) if self._model else None
            if model_spec and model_spec.fuel_tank_liters > 0:
                fuel_level_percent = min(
                    round((fuel_ml / (model_spec.fuel_tank_liters * 1000)) * 100), 100
                )

        # Map internal state to device types
        device_values: dict[DeviceType, int | float | bool | None] = {
            DeviceType.RUNTIME_HOURS: self._state["runtime_hours"],
            DeviceType.CURRENT: self._state["current"],
            DeviceType.POWER: self._state["power_watts"],
            DeviceType.ECO_MODE: self._state["eco_status"],
            DeviceType.ENGINE_RUNNING: self._state["engine_mode"] > 0,
            DeviceType.OUTPUT_VOLTAGE: self._state["voltage"],
            DeviceType.FUEL_LEVEL: fuel_level_percent,
            DeviceType.FUEL_VOLUME_ML: fuel_ml,
            DeviceType.FUEL_REMAINS_LEVEL: self._state["fuel_level_discrete"],
            DeviceType.FUEL_REMAINING_TIME: self._state["fuel_remaining_min"],
            DeviceType.OUTPUT_VOLTAGE_SETTING: self._state["voltage_setting"],
        }

        for device_type in DEVICE_TYPES_PUSH:
            devices.append(
                Device(
                    device_id=1,
                    device_unique_id=f"{controller_name}_{device_type}",
                    device_type=device_type,
                    name=DEVICE_NAMES.get(device_type, str(device_type)),
                    state=device_values.get(device_type),
                )
            )

        return devices

    async def engine_stop(self) -> bool:
        """Stop the generator engine.

        Pauses the data stream, sends the function command, then resumes the stream.
        """
        if not self._client or not self._client.is_connected:
            _LOGGER.error("Push API: Cannot stop engine - not connected")
            return False

        async with self._with_stream_paused():
            # Build function command: [0x01, func_hi, func_lo, 0x00 x 11]
            packet = bytearray(14)
            packet[0] = 0x01  # Command type: function
            packet[1] = (FUNC_ENGINE_STOP >> 8) & 0xFF
            packet[2] = FUNC_ENGINE_STOP & 0xFF

            try:
                await asyncio.wait_for(
                    self._client.write_gatt_char(GENERATOR_DATA_REQUEST_CHAR, packet),
                    timeout=5.0,
                )
                _LOGGER.info("Push API: Engine stop command sent")
                # Give the generator time to process
                await asyncio.sleep(0.5)
                return True
            except TimeoutError as exc:
                _LOGGER.error("Push API: Engine stop timed out: %s", exc)
                return False
            except BleakError as exc:
                _LOGGER.error("Push API: Engine stop failed: %s", exc)
                return False

    def get_warning_bit(self, bit: int) -> bool:
        """Get the state of a warning bit (from CAN error data)."""
        # For Push, warnings come from CAN error messages
        return bit in self._state.get("ecu_errors", [])

    def get_fault_bit(self, bit: int) -> bool:
        """Get the state of a fault bit (from CAN error data)."""
        # For Push, faults come from CAN error messages
        all_errors = (
            self._state.get("ecu_errors", [])
            + self._state.get("inv_errors", [])
            + self._state.get("bt_errors", [])
        )
        return bit in all_errors


class APIError(Exception):
    """Base exception for Honda Generator API errors."""


class APIAuthError(APIError):
    """Authentication error."""


class APIConnectionError(APIError):
    """Connection error."""


class APIReadError(APIError):
    """Diagnostic read failed after retries."""


# Backwards compatibility alias
API = PollAPI


def create_api(
    ble_device,
    pwd: str,
    architecture: Architecture = Architecture.POLL,
    on_engine_status_update: "Callable[[int, bool, int, int], None] | None" = None,
    on_data_update: "Callable[[dict], None] | None" = None,
) -> GeneratorAPIProtocol:
    """Factory function to create the appropriate API based on architecture.

    Args:
        ble_device: The BLE device to connect to.
        pwd: The authentication password.
        architecture: The communication architecture (POLL or PUSH).
        on_engine_status_update: Callback for engine status updates (Poll only).
        on_data_update: Callback for data updates (Push only).

    Returns:
        An API instance implementing GeneratorAPIProtocol.
    """
    if architecture == Architecture.PUSH:
        return PushAPI(ble_device, pwd, on_data_update=on_data_update)
    return PollAPI(ble_device, pwd, on_engine_status_update=on_engine_status_update)


def get_architecture_from_device_name(device_name: str | None) -> Architecture:
    """Determine the architecture from a BLE device name.

    Args:
        device_name: The BLE advertised name (4-letter serial prefix, e.g., "EBKJ").

    Returns:
        The detected architecture, defaulting to POLL if unknown.
    """
    if not device_name:
        return Architecture.POLL
    for prefix, arch in DEVICE_NAME_TO_ARCHITECTURE.items():
        if device_name.startswith(prefix):
            return arch
    return Architecture.POLL
