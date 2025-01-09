"""API Placeholder.

You should create your api seperately and have it hosted on PYPI.  This is included here for the sole purpose
of making this example code executable.
"""

from dataclasses import dataclass
from enum import StrEnum
import logging
from random import choice, randrange

from uuid import UUID
import asyncio
from contextlib import AsyncExitStack

from bleak import BleakClient
from bleak.exc import BleakError

from bleak.backends.characteristic import BleakGATTCharacteristic

REMOTE_CONTROL_SERVICE_UUID = "066B0001-5D90-4939-A7BA-7B9222F53E81";
ENGINE_CONTROL_CHARACTERISTIC_UUID = "066B0002-5D90-4939-A7BA-7B9222F53E81";
ENGINE_DRIVE_STATUS_CHARACTERISTIC_UUID = "066B0003-5D90-4939-A7BA-7B9222F53E81";
CONTROL_SEQUENCE_CONFIGURATION_CHARACTERISTIC_UUID = "066B0004-5D90-4939-A7BA-7B9222F53E81";
FRAME_NUMBER_CHARACTERISTIC_UUID = "066B0005-5D90-4939-A7BA-7B9222F53E81";
UNLOCK_PROTECT_CHARACTERISTIC_UUID = "066B0006-5D90-4939-A7BA-7B9222F53E81";
CHANGE_PASSWORD_CHARACTERISTIC_UUID = "066B0007-5D90-4939-A7BA-7B9222F53E81";

DIAGNOSTIC_CONTROL_SERVICE_UUID = "B4EF0001-62D2-483C-8293-119E2A99A82B";
DIAGNOSTIC_COMMAND_CHARACTERISTIC_UUID = "B4EF0002-62D2-483C-8293-119E2A99A82B";
DIAGNOSTIC_RESPONSE_CHARACTERISTIC_UUID = "B4EF0003-62D2-483C-8293-119E2A99A82B";
FIRMWARE_VERSION_CHARACTERISTIC_UUID = "B4EF0004-62D2-483C-8293-119E2A99A82B";
UNIT_OPERATION_CHARACTERISTIC_UUID = "B4EF0005-62D2-483C-8293-119E2A99A82B";


_LOGGER = logging.getLogger(__name__)

class DeviceType(StrEnum):
    """Device types."""

    TEMP_SENSOR = "temp_sensor"
    DOOR_SENSOR = "door_sensor"
    OTHER = "other"


DEVICES = [
    {"id": 1, "type": DeviceType.TEMP_SENSOR},
    #{"id": 2, "type": DeviceType.TEMP_SENSOR},
    #{"id": 3, "type": DeviceType.TEMP_SENSOR},
    #{"id": 4, "type": DeviceType.TEMP_SENSOR},
    {"id": 1, "type": DeviceType.DOOR_SENSOR},
    #{"id": 2, "type": DeviceType.DOOR_SENSOR},
    #{"id": 3, "type": DeviceType.DOOR_SENSOR},
    #{"id": 4, "type": DeviceType.DOOR_SENSOR},
]


@dataclass
class Device:
    """API device."""

    device_id: int
    device_unique_id: str
    device_type: DeviceType
    name: str
    state: int | bool


class API:
    """Class for example API."""

    def __init__(self, ble_device, pwd: str) -> None:
        """Initialise."""
        self._ble_device = ble_device
        self._client: BleakClient | None = None
        self._client_stack = AsyncExitStack()
        self._lock = asyncio.Lock()
        self.pwd = pwd
        self.connected: bool = False

    @property
    def controller_name(self) -> str:
        """Return the name of the controller."""
        return self._ble_device.address

    async def connect(self) -> bool:
        """Connect to api."""
        async with self._lock:
            if not self._client:
                _LOGGER.debug("Connecting")
                try:
                    self._client = await self._client_stack.enter_async_context(BleakClient(self._ble_device, timeout=30))
                except asyncio.TimeoutError as exc:
                    _LOGGER.debug("Timeout on connect", exc_info=True)
                    raise APIConnectionError("Timeout on connect") from exc
                except BleakError as exc:
                    _LOGGER.debug("Error on connect", exc_info=True)
                    raise APIAuthError("Error connecting to api. Invalid username or password.") from exc
            else:
                _LOGGER.debug("Connection reused")
            await self._client.pair()
            await self._client.write_gatt_char(UNLOCK_PROTECT_CHARACTERISTIC_UUID, bytearray([0x01])+self.pwd.encode())

            self.connected = True
            return True

    async def disconnect(self) -> bool:
        """Disconnect from api."""
        self.connected = False
        return True

    async def get_devices(self) -> list[Device]:
        """Get devices on api."""
        return [
            Device(
                device_id = device.get("id"),
                device_unique_id = await self.get_device_unique_id(
                    device.get("id"), device.get("type")
                ),
                device_type = device.get("type"),
                name = await self.get_device_name(device.get("id"), device.get("type")),
                state = await self.get_device_value(device.get("id"), device.get("type")),
            )
            for device in DEVICES
        ]

    async def get_device_unique_id(self, device_id: str, device_type: DeviceType) -> str:
        """Return a unique device id."""
        if device_type == DeviceType.DOOR_SENSOR:
            return f"{self.controller_name}_D{device_id}"
        if device_type == DeviceType.TEMP_SENSOR:
            return f"{self.controller_name}_T{device_id}"
        return f"{self.controller_name}_Z{device_id}"

    async def get_device_name(self, device_id: str, device_type: DeviceType) -> str:
        """Return the device name."""
        if device_type == DeviceType.DOOR_SENSOR:
            return f"DoorSensor{device_id}"
        if device_type == DeviceType.TEMP_SENSOR:
            return f"TempSensor{device_id}"
        return f"OtherSensor{device_id}"

    async def get_device_value(self, device_id: str, device_type: DeviceType) -> int | bool:
        """Get device random value."""
        if device_type == DeviceType.DOOR_SENSOR:
            return choice([True, False])
        if device_type == DeviceType.TEMP_SENSOR:
            return randrange(15, 28)
        return randrange(1, 10)

    async def get_serial(self):
        serial = await self._client.read_gatt_char(FRAME_NUMBER_CHARACTERISTIC_UUID)
        return serial.decode().split(" ", 1)[0]
        


class APIAuthError(Exception):
    """Exception class for auth error."""


class APIConnectionError(Exception):
    """Exception class for connection error."""
