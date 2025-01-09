#!/usr/bin/env python3

import argparse
import asyncio
import logging
import time
import struct

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

logger = logging.getLogger(__name__)

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


class DeviceNotFoundError(Exception):
    pass


async def run_ble_client(args: argparse.Namespace, queue: asyncio.Queue):
    async def callback_handler(sender: BleakGATTCharacteristic, data: bytearray):
        await queue.put((time.time(), data))

    def create_command_data(register: str, position: str):
        data = bytearray([0x01, 0x42, ord(register[0]), ord(position[0]), ord(position[1]), 0x30, 0x30, 0x00, 0x00, 0x04])
        return calculate_checksum(data)

    def calculate_checksum(data: bytearray):
        # This takes a 10 bytearray and overwrites the checksum bytes with their calculated value.
        # Returned data is ready for transmission, received data can be validated by ensuring that
        # the calling data is the same as the returned version.
        result = data[:]
        cksum = 0
        for i in range(1, 7):
            cksum ^= data[i]
        result[7] = ord(format(cksum & 240, 'X')[0]) # high 4 bits as ascii hex char
        result[8] = ord(format(cksum & 15, 'X')[0]) # low 4 bits as ascii hex char
        return result

    async def get_diagnostic_byte(register: str, byte: str):
        result = None

        while not result:
            try:
                await client.write_gatt_char(DIAGNOSTIC_COMMAND_CHARACTERISTIC_UUID, create_command_data(register, byte))
            except NotPermitted:
                await client.pair()
                await client.write_gatt_char(UNLOCK_PROTECT_CHARACTERISTIC_UUID, bytearray([0x01, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30]))
            await asyncio.sleep(0.1)
            _, data = await queue.get()
            data = data[1:]
            if data == calculate_checksum(data):
                result = bytes.fromhex(data[5:7].decode())
            else:
                result = 0
        return result

    logger.info("starting scan...")

    if args.address:
        device = await BleakScanner.find_device_by_address(
            args.address, cb=dict(use_bdaddr=args.macos_use_bdaddr)
        )
        if device is None:
            logger.error("could not find device with address '%s'", args.address)
            raise DeviceNotFoundError
    else:
        device = await BleakScanner.find_device_by_name(
            args.name, cb=dict(use_bdaddr=args.macos_use_bdaddr)
        )
        if device is None:
            logger.error("could not find device with name '%s'", args.name)
            raise DeviceNotFoundError

    logger.info("connecting to device...")

    async with BleakClient(device) as client:
        logger.info("connected")
        await client.start_notify(DIAGNOSTIC_RESPONSE_CHARACTERISTIC_UUID, callback_handler)

        try:
            model_number = await client.read_gatt_char(FRAME_NUMBER_CHARACTERISTIC_UUID)
        except:
            await client.pair()
            await client.write_gatt_char(UNLOCK_PROTECT_CHARACTERISTIC_UUID, bytearray([0x01, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30]))
            model_number = await client.read_gatt_char(FRAME_NUMBER_CHARACTERISTIC_UUID)

        print("Serial Number: {0}".format("".join(map(chr, model_number))))

        firmware_version = await client.read_gatt_char(FIRMWARE_VERSION_CHARACTERISTIC_UUID)
        print("Firmware Version:", struct.unpack('>h', firmware_version)[0])

        var = await get_diagnostic_byte('B', '00') + await get_diagnostic_byte('B', '01')
        print('Hours:', struct.unpack('>h', var)[0])

        var = await get_diagnostic_byte('B', '13') + await get_diagnostic_byte('B', '14')
        print('Current:', struct.unpack('>h', var)[0] / 10, 'A')

        var = await get_diagnostic_byte('B', '17') + await get_diagnostic_byte('B', '18')
        print('Power:', struct.unpack('>h', var)[0] * 10, 'VA')

        var = await get_diagnostic_byte('B', '19')
        print('ECO:', (var[0] & 1) ^ 1)

        var = await get_diagnostic_byte('C', '10')
        print('Warnings:', format(var[0], '08b'))

        var = await get_diagnostic_byte('D', '10') + await get_diagnostic_byte('D', '11')
        print('Faults:', format(var[0], '08b'), format(var[1], '08b'))

        var = await get_diagnostic_byte('A', '00') + await get_diagnostic_byte('A', '01') + await get_diagnostic_byte('A', '02') + await get_diagnostic_byte('A', '03') + await get_diagnostic_byte('A', '04')
        print('Code:', var.hex())

        await client.stop_notify(DIAGNOSTIC_RESPONSE_CHARACTERISTIC_UUID)

        if args.kill:
            await client.write_gatt_char(ENGINE_CONTROL_CHARACTERISTIC_UUID, bytearray([0x00]))
        # Send an "exit command to the consumer"
        #await queue.put((time.time(), None))

    logger.info("disconnected")


#async def run_queue_consumer(queue: asyncio.Queue):
#    logger.info("Starting queue consumer")
#
#    while True:
#        # Use await asyncio.wait_for(queue.get(), timeout=1.0) if you want a timeout for getting data.
#        epoch, data = await queue.get()
#        if data is None:
#            logger.info(
#                "Got message from client about disconnection. Exiting consumer loop..."
#            )
#            break
#        else:
#            logger.info("Received callback data via async queue at %s: %r", epoch, data)


async def main(args: argparse.Namespace):
    queue = asyncio.Queue()
    client_task = run_ble_client(args, queue)
    #consumer_task = run_queue_consumer(queue)

    try:
        await asyncio.gather(client_task) #, consumer_task)
    except DeviceNotFoundError:
        pass

    logger.info("Main method done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    device_group = parser.add_mutually_exclusive_group(required=True)

    device_group.add_argument(
        "--name",
        metavar="<name>",
        help="the name of the bluetooth device to connect to",
    )
    device_group.add_argument(
        "--address",
        metavar="<address>",
        help="the address of the bluetooth device to connect to",
    )

    parser.add_argument(
        "--macos-use-bdaddr",
        action="store_true",
        help="when true use Bluetooth address instead of UUID on macOS",
    )

    parser.add_argument(
        "-k",
        "--kill",
        action="store_true",
        help="shut down the generator after polling",
    )

    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="sets the logging level to debug",
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )

    asyncio.run(main(args))
