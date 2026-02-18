"""Tests for Honda Generator services module."""

from __future__ import annotations

from custom_components.honda_generator.services import (
    DEFAULT_SERVICE_INTERVALS,
    OIL_CHANGE_BREAKIN_INTERVAL,
    SERVICE_DEFINITIONS,
    ServiceDefinition,
    ServiceInterval,
    ServiceType,
    get_model_services,
    get_service_definition,
)


class TestServiceType:
    """Test ServiceType enum."""

    def test_all_13_members_exist(self) -> None:
        """Test that all 13 service types are defined."""
        assert len(ServiceType) == 13

    def test_user_serviceable_types(self) -> None:
        """Test user-serviceable service types."""
        assert ServiceType.OIL_CHANGE == "oil_change"
        assert ServiceType.AIR_FILTER_CLEAN == "air_filter_clean"
        assert ServiceType.AIR_FILTER_REPLACE == "air_filter_replace"
        assert ServiceType.SPARK_PLUG_CHECK == "spark_plug_check"
        assert ServiceType.SPARK_PLUG_REPLACE == "spark_plug_replace"
        assert ServiceType.SPARK_ARRESTER_CLEAN == "spark_arrester_clean"
        assert ServiceType.SEDIMENT_CUP_CLEAN == "sediment_cup_clean"

    def test_dealer_service_types(self) -> None:
        """Test dealer-service types."""
        assert ServiceType.VALVE_CLEARANCE == "valve_clearance"
        assert ServiceType.TIMING_BELT == "timing_belt"
        assert ServiceType.COMBUSTION_CHAMBER == "combustion_chamber"
        assert ServiceType.FUEL_TANK_CLEAN == "fuel_tank_clean"
        assert ServiceType.FUEL_PUMP_FILTER == "fuel_pump_filter"
        assert ServiceType.FUEL_SYSTEM_CHECK == "fuel_system_check"


class TestServiceDefinitions:
    """Test SERVICE_DEFINITIONS dictionary."""

    def test_all_types_have_definitions(self) -> None:
        """Test that all service types have definitions."""
        for service_type in ServiceType:
            assert service_type in SERVICE_DEFINITIONS

    def test_definition_structure(self) -> None:
        """Test that definitions have valid structure."""
        for service_type, defn in SERVICE_DEFINITIONS.items():
            assert isinstance(defn, ServiceDefinition)
            assert defn.service_type == service_type
            assert isinstance(defn.name, str)
            assert defn.name  # Not empty
            assert defn.icon.startswith("mdi:")
            assert isinstance(defn.interval, ServiceInterval)

    def test_only_oil_change_enabled_by_default(self) -> None:
        """Test that only oil_change is enabled by default."""
        enabled = [st for st, d in SERVICE_DEFINITIONS.items() if d.enabled_by_default]
        assert enabled == [ServiceType.OIL_CHANGE]

    def test_dealer_service_flags(self) -> None:
        """Test that exactly 6 dealer services are flagged."""
        dealer = [st for st, d in SERVICE_DEFINITIONS.items() if d.is_dealer_service]
        assert len(dealer) == 6
        expected_dealer = {
            ServiceType.VALVE_CLEARANCE,
            ServiceType.TIMING_BELT,
            ServiceType.COMBUSTION_CHAMBER,
            ServiceType.FUEL_TANK_CLEAN,
            ServiceType.FUEL_PUMP_FILTER,
            ServiceType.FUEL_SYSTEM_CHECK,
        }
        assert set(dealer) == expected_dealer


class TestGetModelServices:
    """Test get_model_services function."""

    def test_eu2200i_services(self) -> None:
        """Test EU2200i has 9 services."""
        services = get_model_services("EU2200i")
        assert len(services) == 9
        assert ServiceType.SEDIMENT_CUP_CLEAN not in services
        assert ServiceType.TIMING_BELT not in services
        assert ServiceType.FUEL_PUMP_FILTER not in services
        assert ServiceType.AIR_FILTER_REPLACE not in services

    def test_eu3200i_services(self) -> None:
        """Test EU3200i has 12 services including timing_belt and fuel_pump_filter."""
        services = get_model_services("EU3200i")
        assert len(services) == 12
        assert ServiceType.TIMING_BELT in services
        assert ServiceType.FUEL_PUMP_FILTER in services
        assert ServiceType.AIR_FILTER_REPLACE in services

    def test_em5000sx_services(self) -> None:
        """Test EM5000SX has 10 services with sediment_cup."""
        services = get_model_services("EM5000SX")
        assert len(services) == 10
        assert ServiceType.SEDIMENT_CUP_CLEAN in services

    def test_em6500sx_services(self) -> None:
        """Test EM6500SX has 10 services with sediment_cup."""
        services = get_model_services("EM6500SX")
        assert len(services) == 10
        assert ServiceType.SEDIMENT_CUP_CLEAN in services

    def test_eu7000is_services(self) -> None:
        """Test EU7000is has 10 services with sediment_cup."""
        services = get_model_services("EU7000is")
        assert len(services) == 10
        assert ServiceType.SEDIMENT_CUP_CLEAN in services

    def test_unknown_model_returns_defaults(self) -> None:
        """Test unknown model returns default services."""
        services = get_model_services("UnknownModel")
        assert services == DEFAULT_SERVICE_INTERVALS

    def test_none_model_returns_defaults(self) -> None:
        """Test None model returns default services."""
        services = get_model_services(None)
        assert services == DEFAULT_SERVICE_INTERVALS


class TestGetServiceDefinition:
    """Test get_service_definition function."""

    def test_returns_correct_definition(self) -> None:
        """Test that correct definition is returned for each type."""
        for service_type in ServiceType:
            defn = get_service_definition(service_type)
            assert defn.service_type == service_type

    def test_oil_change_definition(self) -> None:
        """Test oil change definition details."""
        defn = get_service_definition(ServiceType.OIL_CHANGE)
        assert defn.name == "Oil Change"
        assert defn.icon == "mdi:oil"
        assert defn.enabled_by_default is True
        assert defn.is_dealer_service is False


class TestBreakInInterval:
    """Test break-in oil change interval."""

    def test_breakin_interval_values(self) -> None:
        """Test break-in interval is 20h/30d."""
        assert OIL_CHANGE_BREAKIN_INTERVAL.hours == 20
        assert OIL_CHANGE_BREAKIN_INTERVAL.days == 30
