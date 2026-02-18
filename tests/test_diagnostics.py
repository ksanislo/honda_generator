"""Tests for Honda Generator diagnostics module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.honda_generator.diagnostics import (
    _redact_serial,
    async_get_config_entry_diagnostics,
)


class TestRedactSerial:
    """Test _redact_serial function."""

    def test_normal_serial(self) -> None:
        """Test normal serial redaction keeps first 4 chars."""
        assert _redact_serial("EAMT-1234567") == "EAMTXXXXXXXX"

    def test_short_serial_4_chars(self) -> None:
        """Test 4-char serial is returned unchanged."""
        assert _redact_serial("EAMT") == "EAMT"

    def test_short_serial_3_chars(self) -> None:
        """Test 3-char serial is returned unchanged."""
        assert _redact_serial("EAM") == "EAM"

    def test_empty_serial(self) -> None:
        """Test empty serial is returned unchanged."""
        assert _redact_serial("") == ""

    def test_long_serial(self) -> None:
        """Test long serial redaction."""
        assert _redact_serial("EAMT-1234567890") == "EAMTXXXXXXXXXXX"

    def test_5_char_serial(self) -> None:
        """Test 5-char serial has 1 char redacted."""
        assert _redact_serial("EAMT1") == "EAMTX"


class TestDiagnosticAssembly:
    """Test async_get_config_entry_diagnostics function."""

    @pytest.mark.asyncio
    async def test_password_redacted(self) -> None:
        """Test that password is redacted in diagnostics."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_id"
        entry.version = 3
        entry.domain = "honda_generator"
        entry.title = "EU2200i (EAMT-1234567)"
        entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            "password": "12345678",
            "serial": "EAMT-1234567",
        }
        entry.options = {}

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.data = None
        coordinator.api = None

        runtime_data = MagicMock()
        runtime_data.coordinator = coordinator
        hass.data = {"honda_generator": {"test_id": runtime_data}}

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["config_entry"]["data"]["password"] == "**REDACTED**"

    @pytest.mark.asyncio
    async def test_mac_partially_redacted(self) -> None:
        """Test that MAC address is partially redacted."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_id"
        entry.version = 3
        entry.domain = "honda_generator"
        entry.title = "EU2200i"
        entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            "password": "12345678",
        }
        entry.options = {}

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.data = None
        coordinator.api = None

        runtime_data = MagicMock()
        runtime_data.coordinator = coordinator
        hass.data = {"honda_generator": {"test_id": runtime_data}}

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["config_entry"]["data"]["address"] == "AA:BB:CC:XX:XX:XX"

    @pytest.mark.asyncio
    async def test_output_has_expected_keys(self) -> None:
        """Test that output has expected top-level keys."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_id"
        entry.version = 3
        entry.domain = "honda_generator"
        entry.title = "EU2200i"
        entry.data = {"address": "AA:BB:CC:DD:EE:FF", "password": "12345678"}
        entry.options = {"scan_interval": 10}

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.data = None
        coordinator.api = None

        runtime_data = MagicMock()
        runtime_data.coordinator = coordinator
        hass.data = {"honda_generator": {"test_id": runtime_data}}

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert "config_entry" in result
        assert "coordinator" in result
        assert result["config_entry"]["entry_id"] == "test_id"
        assert result["coordinator"]["last_update_success"] is True
