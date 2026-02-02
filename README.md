# Honda Generator integration for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/ksanislo/honda_generator)](https://github.com/ksanislo/honda_generator/releases)
[![License](https://img.shields.io/github/license/ksanislo/honda_generator)](LICENSE)

Unofficial Home Assistant integration for remote monitoring and control of Honda generators via Bluetooth Low Energy (BLE).

## Features

- **Automatic Discovery**: Detects Honda generators via Bluetooth
- **Real-time Monitoring**: View generator diagnostics updated every 10 seconds (configurable)
- **Engine Control**: Start and stop the generator remotely via Home Assistant (model-dependent)
- **ECO Mode Control**: Toggle ECO mode on supported models
- **Fuel Monitoring**: View fuel level and remaining runtime on supported models
- **Automatic Reconnection**: Handles BLE connection drops gracefully
- **Diagnostics Support**: Download debug information for troubleshooting

## Supported Devices and Features

| Model | Remote Start | ECO Control | Fuel Sensor | Architecture |
|-------|--------------|-------------|-------------|--------------|
| Honda EU2200i | - | - | - | Poll |
| Honda EU3200i | - | - | ✅ | Push |
| Honda EM5000SX | ✅ | ✅ | - | Poll |
| Honda EM6500SX | ✅ | ✅ | - | Poll |
| Honda EU7000is | ✅ | - | ✅ | Poll |

**Architecture Notes:**
- **Poll**: Data is polled at configurable intervals (default: 10 seconds)
- **Push**: Data is streamed continuously in real-time via CAN bus

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select **Custom repositories**
4. Add `https://github.com/ksanislo/honda_generator` with category **Integration**
5. Click **Add**
6. Search for "Honda Generator" and click **Download**
7. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub Releases](https://github.com/ksanislo/honda_generator/releases)
2. Extract and copy the `honda_generator` folder to your `custom_components` directory:
   ```bash
   cp -r honda_generator /config/custom_components/
   ```
3. Restart Home Assistant

## Configuration

1. Ensure Bluetooth is enabled on your Home Assistant host
2. Power on your Honda generator within Bluetooth range
3. Go to **Settings** → **Devices & Services**
4. The generator should be auto-discovered, or click **Add Integration** and search for "Honda Generator"
5. Enter your generator's Bluetooth password (default: `00000000`)

### Options

After setup, you can configure:

- **Scan Interval**: How often to poll the generator (default: 10 seconds) - *Poll architecture only*

Note: EU3200i (Push architecture) streams data continuously, so scan interval does not apply.

## Entities

### Sensors

| Entity | Description | Unit | Notes |
|--------|-------------|------|-------|
| Runtime Hours | Total engine runtime | hours | |
| Output Current | Current electrical output | A | |
| Output Power | Apparent power output | VA | |
| Output Voltage | Output voltage | V | |
| Engine Event | Last engine event | - | Poll architecture only |
| Engine Error | Current error code | - | Poll architecture only |
| Fuel Level | Current fuel tank level | % | EU7000is, EU3200i |
| Fuel Volume | Current fuel volume | mL | EU3200i only |
| Fuel Gauge Level | Discrete fuel gauge level (0-17) | - | EU3200i only |
| Fuel Remaining Time | Estimated runtime remaining | min | EU7000is, EU3200i |
| Output Voltage Setting | Configured output voltage | V | EU3200i only |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| ECO Mode | Whether ECO throttle mode is active |
| Engine Running | Whether the engine is currently running |
| Warning/Fault Codes | Individual warning and fault flags (disabled by default) |

### Buttons

| Entity | Description | Notes |
|--------|-------------|-------|
| Stop Engine | Remotely stop the generator engine | All models |
| Start Engine | Remotely start the generator engine | EM5000SX, EM6500SX, EU7000is only |

### Switches

| Entity | Description | Notes |
|--------|-------------|-------|
| ECO Mode | Toggle ECO throttle mode | EM5000SX, EM6500SX only |

### Services

| Service | Description |
|---------|-------------|
| `honda_generator.stop_engine` | Stop the generator engine (for use in automations) |

### Device Info

- **Model**: Detected from serial number prefix (EU2200i, EU3200i, EM5000SX, EM6500SX, EU7000is, or Unknown)
- **Serial Number**: Generator serial number
- **Firmware Version**: Generator firmware version

## Requirements

- Home Assistant 2024.1.0 or newer
- Bluetooth adapter or ESPHome Bluetooth Proxy
- Honda generator with Bluetooth module
- Generator within Bluetooth range (~30 feet / 10 meters)

## Troubleshooting

### Bluetooth Pairing

- Your Bluetooth adapter **must be very close** (~3 feet / 1 meter) during initial pairing
- You must discover and begin configuring your generator within ~30 seconds after engine startup
- Pairing occurs automatically during detection and configuration
- After pairing, Bluetooth operates at normal range

### Generator Not Discovered

- Ensure the generator is powered on
- Verify Home Assistant has a working Bluetooth adapter or ESPHome proxy
- Move your Bluetooth device closer to the generator
- Check Home Assistant logs for Bluetooth errors

### Connection Drops Frequently

- The integration automatically reconnects on the next poll cycle
- Consider adjusting the scan interval in options
- Minimize interference between the Bluetooth adapter and generator
- An ESPHome Bluetooth proxy near the generator improves reliability

### Authentication Failed

- Verify you're using the correct Bluetooth password
- The default password is `00000000` (eight zeros)
- Try removing and re-adding the integration

### Download Diagnostics

If you need help troubleshooting:
1. Go to **Settings** → **Devices & Services** → **Honda Generator**
2. Click the three dots menu → **Download diagnostics**
3. Attach the file when creating a GitHub issue

## Development

### Running Tests

```bash
python3 run_tests.py
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the tests (`python3 run_tests.py`)
5. Submit a pull request

If you have a Honda generator model that isn't currently supported, please [create an issue](https://github.com/ksanislo/honda_generator/issues) with your model information.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not affiliated with or endorsed by Honda Motor Co., Ltd. Use at your own risk. Always follow proper safety procedures when operating generators.
