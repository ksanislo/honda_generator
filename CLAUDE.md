# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant custom integration for remote monitoring and control of Honda generators via Bluetooth Low Energy (BLE). Supported models include EU2200i, EU3200i, EM5000SX, EM6500SX, and EU7000is. The integration allows users to view generator diagnostics and control the engine through the Home Assistant UI.

The integration supports two communication architectures:
- **Poll**: Request-response diagnostic reads (EU2200i, EM5000SX, EM6500SX, EU7000is)
- **Push**: Continuous CAN data stream (EU3200i)

## Development Commands

**Run tests:**
```bash
python run_tests.py
```

**Lint and format:**
```bash
.venv/bin/ruff check .
.venv/bin/ruff format .
```

**Installation (deploy to Home Assistant):**
```bash
cp -r custom_components/honda_generator /config/custom_components/
# Then restart Home Assistant
```

No build step required - the integration is deployed as Python source files.

## Architecture

This is a standard Home Assistant custom integration following the coordinator pattern:

```
ConfigFlow (config_flow.py)    - BLE discovery and password-based setup
    ↓
Coordinator (coordinator.py)   - DataUpdateCoordinator (polling or push callbacks)
    ↓
API (api.py)                   - PollAPI or PushAPI via GeneratorAPIProtocol
    ↓
Base Entity (entity.py)        - Shared DeviceInfo and entity configuration
    ↓
Entities (sensor.py, binary_sensor.py, button.py, switch.py) - Platform-specific entities
```

**Key files** (in `custom_components/honda_generator/`):
- `manifest.json` - Integration metadata, BLE service UUIDs for discovery
- `const.py` - Domain name, scan interval settings, and configuration keys
- `entity.py` - Base entity class with shared DeviceInfo
- `api.py` - BLE communication with `PollAPI` and `PushAPI` classes implementing `GeneratorAPIProtocol`
- `codes.py` - Model-specific warning and fault code definitions
- `services.py` - Service maintenance definitions and model-specific intervals

**BLE Protocol:**
- Remote Control Service: `066B0001-5D90-4939-A7BA-7B9222F53E81` (Poll architecture)
- Generator Data Service: `01B60001-875A-4C56-B8BF-5103CAFAEEC7` (Push architecture)
- BT Unit Service: `92CD0001-4F59-4599-A73C-C92C4AC7AADE` (Push architecture auth/serial)
- Authentication via password written to Authentication characteristic

**Model Detection:**
- BLE advertised name is the 4-letter serial prefix (e.g., EAMT, EBKJ, EBMC, EBJC, EEJD)
- Architecture is determined from this prefix during discovery via `DEVICE_NAME_TO_ARCHITECTURE`
- Model name is determined from full serial number prefix via `SERIAL_PREFIX_TO_MODEL`
- Unknown prefixes default to "Unknown" model with Poll architecture
- To add support for new models, update `SERIAL_PREFIX_TO_MODEL`, `MODEL_SPECS`, and `DEVICE_NAME_TO_ARCHITECTURE` in `api.py`

## Dependencies

Managed through `manifest.json`:
- `bluetooth_adapters` - Home Assistant Bluetooth dependency
- `bleak-retry-connector` - Robust BLE connection handling

## Workflow

**Important**: When making changes, only commit locally. Do NOT push to remote or create GitHub releases without explicit approval. This allows for proper testing before changes go live.

1. Make changes and run tests (`python run_tests.py`)
2. Run linting (`ruff check . && ruff format .`)
3. Commit locally with descriptive message
4. **Stop and wait** - Do not push or release until asked
