"""Tests for Honda Generator codes module."""

from __future__ import annotations

import pytest

from custom_components.honda_generator.codes import (
    EU2200I_FAULT_CODES,
    EU2200I_WARNING_CODES,
    EU3200I_FAULT_CODES,
    EU3200I_WARNING_CODES,
    EU7000IS_FAULT_CODES,
    EU7000IS_WARNING_CODES,
    MODEL_FAULT_CODES,
    MODEL_WARNING_CODES,
    AlertCode,
    get_code_description,
    get_code_translation_key,
    get_fault_codes,
    get_warning_codes,
)


class TestAlertCode:
    """Test AlertCode dataclass."""

    def test_alert_code_creation(self) -> None:
        """Test AlertCode creation."""
        code = AlertCode(bit=2, code="C-03")
        assert code.bit == 2
        assert code.code == "C-03"

    def test_alert_code_frozen(self) -> None:
        """Test AlertCode is immutable."""
        code = AlertCode(bit=2, code="C-03")
        with pytest.raises(AttributeError):
            code.bit = 5


class TestEU2200ICodes:
    """Test EU2200i specific codes."""

    def test_warning_codes_defined(self) -> None:
        """Test warning codes are defined."""
        assert len(EU2200I_WARNING_CODES) == 2
        codes = {c.code for c in EU2200I_WARNING_CODES}
        assert "C-03" in codes
        assert "C-04" in codes

    def test_fault_codes_defined(self) -> None:
        """Test fault codes are defined."""
        assert len(EU2200I_FAULT_CODES) == 9
        codes = {c.code for c in EU2200I_FAULT_CODES}
        assert "E-12" in codes
        assert "E-13" in codes
        assert "E-15" in codes
        assert "C-2A" in codes
        assert "E-16" in codes
        assert "E-17" in codes
        assert "E-19" in codes
        assert "E-1A" in codes
        assert "E-1B" in codes

    def test_warning_code_bits_unique(self) -> None:
        """Test warning code bits are unique."""
        bits = [c.bit for c in EU2200I_WARNING_CODES]
        assert len(bits) == len(set(bits))

    def test_fault_code_bits_unique(self) -> None:
        """Test fault code bits are unique."""
        bits = [c.bit for c in EU2200I_FAULT_CODES]
        assert len(bits) == len(set(bits))


class TestModelCodeMappings:
    """Test model code mappings."""

    def test_eu2200i_in_warning_codes(self) -> None:
        """Test EU2200i is in warning codes mapping."""
        assert "EU2200i" in MODEL_WARNING_CODES
        assert MODEL_WARNING_CODES["EU2200i"] == EU2200I_WARNING_CODES

    def test_eu2200i_in_fault_codes(self) -> None:
        """Test EU2200i is in fault codes mapping."""
        assert "EU2200i" in MODEL_FAULT_CODES
        assert MODEL_FAULT_CODES["EU2200i"] == EU2200I_FAULT_CODES


class TestGetCodes:
    """Test get_warning_codes and get_fault_codes functions."""

    def test_get_warning_codes_eu2200i(self) -> None:
        """Test getting warning codes for EU2200i."""
        codes = get_warning_codes("EU2200i")
        assert codes == EU2200I_WARNING_CODES

    def test_get_warning_codes_unknown_model(self) -> None:
        """Test getting warning codes for unknown model."""
        codes = get_warning_codes("Unknown")
        assert codes == []

    def test_get_fault_codes_eu2200i(self) -> None:
        """Test getting fault codes for EU2200i."""
        codes = get_fault_codes("EU2200i")
        assert codes == EU2200I_FAULT_CODES

    def test_get_fault_codes_unknown_model(self) -> None:
        """Test getting fault codes for unknown model."""
        codes = get_fault_codes("Unknown")
        assert codes == []

    def test_get_warning_codes_empty_model(self) -> None:
        """Test getting warning codes for empty model."""
        codes = get_warning_codes("")
        assert codes == []

    def test_get_fault_codes_empty_model(self) -> None:
        """Test getting fault codes for empty model."""
        codes = get_fault_codes("")
        assert codes == []


class TestEU3200ICodes:
    """Test EU3200i specific codes."""

    def test_warning_codes_count(self) -> None:
        """Test EU3200i has 8 warning codes."""
        assert len(EU3200I_WARNING_CODES) == 8

    def test_fault_codes_count(self) -> None:
        """Test EU3200i has 25 fault codes."""
        assert len(EU3200I_FAULT_CODES) == 25

    def test_warning_bits_unique(self) -> None:
        """Test EU3200i warning code bits are unique."""
        bits = [c.bit for c in EU3200I_WARNING_CODES]
        assert len(bits) == len(set(bits))

    def test_fault_codes_all_have_codes(self) -> None:
        """Test all EU3200i fault codes have code strings."""
        for code in EU3200I_FAULT_CODES:
            assert code.code  # Not empty


class TestEU7000isCodes:
    """Test EU7000is specific codes."""

    def test_warning_codes_count(self) -> None:
        """Test EU7000is has 10 warning codes."""
        assert len(EU7000IS_WARNING_CODES) == 10

    def test_fault_codes_count(self) -> None:
        """Test EU7000is has 37 fault codes."""
        assert len(EU7000IS_FAULT_CODES) == 37

    def test_warning_bits_unique(self) -> None:
        """Test EU7000is warning code bits are unique."""
        bits = [c.bit for c in EU7000IS_WARNING_CODES]
        assert len(bits) == len(set(bits))

    def test_fault_bits_unique(self) -> None:
        """Test EU7000is fault code bits are unique."""
        bits = [c.bit for c in EU7000IS_FAULT_CODES]
        assert len(bits) == len(set(bits))


class TestCodeDescriptions:
    """Test code description and translation functions."""

    def test_get_code_description_known(self) -> None:
        """Test getting description for known code."""
        assert get_code_description("C-01") == "Check engine"
        assert get_code_description("E-03") == "Low oil"

    def test_get_code_description_unknown(self) -> None:
        """Test getting description for unknown code returns None."""
        assert get_code_description("X-99") is None

    def test_get_code_translation_key_known(self) -> None:
        """Test getting translation key for known code."""
        assert get_code_translation_key("C-01") == "c_01"
        assert get_code_translation_key("E-03") == "e_03"

    def test_get_code_translation_key_unknown(self) -> None:
        """Test getting translation key for unknown code returns None."""
        assert get_code_translation_key("X-99") is None

    def test_alert_code_description_property(self) -> None:
        """Test AlertCode.description property."""
        code = AlertCode(bit=0, code="C-01")
        assert code.description == "Check engine"

    def test_alert_code_description_unknown(self) -> None:
        """Test AlertCode.description for unknown code."""
        code = AlertCode(bit=0, code="X-99")
        assert code.description is None
