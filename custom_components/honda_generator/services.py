"""Service schedule definitions for Honda generators."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ServiceType(StrEnum):
    """Service types for maintenance tracking."""

    # User-serviceable
    OIL_CHANGE = "oil_change"
    AIR_FILTER_CLEAN = "air_filter_clean"
    AIR_FILTER_REPLACE = "air_filter_replace"
    SPARK_PLUG_CHECK = "spark_plug_check"
    SPARK_PLUG_REPLACE = "spark_plug_replace"
    SPARK_ARRESTER_CLEAN = "spark_arrester_clean"
    SEDIMENT_CUP_CLEAN = "sediment_cup_clean"

    # Dealer-service
    VALVE_CLEARANCE = "valve_clearance"
    TIMING_BELT = "timing_belt"
    COMBUSTION_CHAMBER = "combustion_chamber"
    FUEL_TANK_CLEAN = "fuel_tank_clean"
    FUEL_PUMP_FILTER = "fuel_pump_filter"
    FUEL_SYSTEM_CHECK = "fuel_system_check"


@dataclass(frozen=True)
class ServiceInterval:
    """Service interval definition."""

    hours: int | None  # Runtime hours interval (None = not hour-based)
    days: int | None  # Calendar days interval (None = not time-based)


@dataclass(frozen=True)
class ServiceDefinition:
    """Complete service definition."""

    service_type: ServiceType
    name: str
    icon: str
    interval: ServiceInterval
    enabled_by_default: bool = False
    is_dealer_service: bool = False


# Break-in oil change interval (used before first oil change is recorded)
OIL_CHANGE_BREAKIN_INTERVAL = ServiceInterval(hours=20, days=30)

# Service intervals by model
# Format: {model: {service_type: ServiceInterval}}
MODEL_SERVICE_INTERVALS: dict[str, dict[ServiceType, ServiceInterval]] = {
    "EU2200i": {
        ServiceType.OIL_CHANGE: ServiceInterval(hours=100, days=180),
        ServiceType.AIR_FILTER_CLEAN: ServiceInterval(hours=50, days=90),
        ServiceType.SPARK_PLUG_CHECK: ServiceInterval(hours=100, days=180),
        ServiceType.SPARK_PLUG_REPLACE: ServiceInterval(hours=200, days=365),
        ServiceType.SPARK_ARRESTER_CLEAN: ServiceInterval(hours=100, days=180),
        ServiceType.VALVE_CLEARANCE: ServiceInterval(hours=200, days=365),
        ServiceType.COMBUSTION_CHAMBER: ServiceInterval(hours=300, days=None),
        ServiceType.FUEL_TANK_CLEAN: ServiceInterval(hours=200, days=365),
        ServiceType.FUEL_SYSTEM_CHECK: ServiceInterval(hours=None, days=730),
    },
    "EU3200i": {
        ServiceType.OIL_CHANGE: ServiceInterval(hours=100, days=180),
        ServiceType.AIR_FILTER_CLEAN: ServiceInterval(hours=50, days=90),
        ServiceType.AIR_FILTER_REPLACE: ServiceInterval(hours=300, days=365),
        ServiceType.SPARK_PLUG_CHECK: ServiceInterval(hours=100, days=180),
        ServiceType.SPARK_PLUG_REPLACE: ServiceInterval(hours=300, days=365),
        ServiceType.SPARK_ARRESTER_CLEAN: ServiceInterval(hours=300, days=365),
        ServiceType.VALVE_CLEARANCE: ServiceInterval(hours=300, days=365),
        ServiceType.TIMING_BELT: ServiceInterval(hours=250, days=365),
        ServiceType.COMBUSTION_CHAMBER: ServiceInterval(hours=500, days=None),
        ServiceType.FUEL_TANK_CLEAN: ServiceInterval(hours=1000, days=730),
        ServiceType.FUEL_PUMP_FILTER: ServiceInterval(hours=1000, days=730),
        ServiceType.FUEL_SYSTEM_CHECK: ServiceInterval(hours=None, days=730),
    },
    "EM5000SX": {
        ServiceType.OIL_CHANGE: ServiceInterval(hours=100, days=180),
        ServiceType.AIR_FILTER_CLEAN: ServiceInterval(hours=50, days=90),
        ServiceType.SPARK_PLUG_CHECK: ServiceInterval(hours=100, days=180),
        ServiceType.SPARK_PLUG_REPLACE: ServiceInterval(hours=300, days=365),
        ServiceType.SPARK_ARRESTER_CLEAN: ServiceInterval(hours=300, days=365),
        ServiceType.SEDIMENT_CUP_CLEAN: ServiceInterval(hours=100, days=180),
        ServiceType.VALVE_CLEARANCE: ServiceInterval(hours=300, days=365),
        ServiceType.COMBUSTION_CHAMBER: ServiceInterval(hours=1000, days=None),
        ServiceType.FUEL_TANK_CLEAN: ServiceInterval(hours=300, days=365),
        ServiceType.FUEL_SYSTEM_CHECK: ServiceInterval(hours=None, days=730),
    },
    "EM6500SX": {
        ServiceType.OIL_CHANGE: ServiceInterval(hours=100, days=180),
        ServiceType.AIR_FILTER_CLEAN: ServiceInterval(hours=50, days=90),
        ServiceType.SPARK_PLUG_CHECK: ServiceInterval(hours=100, days=180),
        ServiceType.SPARK_PLUG_REPLACE: ServiceInterval(hours=300, days=365),
        ServiceType.SPARK_ARRESTER_CLEAN: ServiceInterval(hours=300, days=365),
        ServiceType.SEDIMENT_CUP_CLEAN: ServiceInterval(hours=100, days=180),
        ServiceType.VALVE_CLEARANCE: ServiceInterval(hours=300, days=365),
        ServiceType.COMBUSTION_CHAMBER: ServiceInterval(hours=1000, days=None),
        ServiceType.FUEL_TANK_CLEAN: ServiceInterval(hours=300, days=365),
        ServiceType.FUEL_SYSTEM_CHECK: ServiceInterval(hours=None, days=730),
    },
    "EU7000is": {
        ServiceType.OIL_CHANGE: ServiceInterval(hours=100, days=180),
        ServiceType.AIR_FILTER_CLEAN: ServiceInterval(hours=50, days=90),
        ServiceType.SPARK_PLUG_CHECK: ServiceInterval(hours=100, days=180),
        ServiceType.SPARK_PLUG_REPLACE: ServiceInterval(hours=300, days=365),
        ServiceType.SPARK_ARRESTER_CLEAN: ServiceInterval(hours=300, days=365),
        ServiceType.SEDIMENT_CUP_CLEAN: ServiceInterval(hours=100, days=180),
        ServiceType.VALVE_CLEARANCE: ServiceInterval(hours=300, days=365),
        ServiceType.COMBUSTION_CHAMBER: ServiceInterval(hours=500, days=None),
        ServiceType.FUEL_TANK_CLEAN: ServiceInterval(hours=300, days=365),
        ServiceType.FUEL_SYSTEM_CHECK: ServiceInterval(hours=None, days=730),
    },
}

# Default intervals for unknown models (conservative - use shortest intervals)
DEFAULT_SERVICE_INTERVALS: dict[ServiceType, ServiceInterval] = {
    ServiceType.OIL_CHANGE: ServiceInterval(hours=100, days=180),
    ServiceType.AIR_FILTER_CLEAN: ServiceInterval(hours=50, days=90),
    ServiceType.SPARK_PLUG_CHECK: ServiceInterval(hours=100, days=180),
    ServiceType.SPARK_PLUG_REPLACE: ServiceInterval(hours=200, days=365),
    ServiceType.SPARK_ARRESTER_CLEAN: ServiceInterval(hours=100, days=180),
    ServiceType.VALVE_CLEARANCE: ServiceInterval(hours=200, days=365),
    ServiceType.COMBUSTION_CHAMBER: ServiceInterval(hours=300, days=None),
    ServiceType.FUEL_TANK_CLEAN: ServiceInterval(hours=200, days=365),
    ServiceType.FUEL_SYSTEM_CHECK: ServiceInterval(hours=None, days=730),
}

# Service definitions with metadata
SERVICE_DEFINITIONS: dict[ServiceType, ServiceDefinition] = {
    ServiceType.OIL_CHANGE: ServiceDefinition(
        service_type=ServiceType.OIL_CHANGE,
        name="Oil Change",
        icon="mdi:oil",
        interval=ServiceInterval(hours=100, days=180),
        enabled_by_default=True,
    ),
    ServiceType.AIR_FILTER_CLEAN: ServiceDefinition(
        service_type=ServiceType.AIR_FILTER_CLEAN,
        name="Air Filter Clean",
        icon="mdi:air-filter",
        interval=ServiceInterval(hours=50, days=90),
        enabled_by_default=False,
    ),
    ServiceType.AIR_FILTER_REPLACE: ServiceDefinition(
        service_type=ServiceType.AIR_FILTER_REPLACE,
        name="Air Filter Replace",
        icon="mdi:air-filter",
        interval=ServiceInterval(hours=300, days=365),
        enabled_by_default=False,
    ),
    ServiceType.SPARK_PLUG_CHECK: ServiceDefinition(
        service_type=ServiceType.SPARK_PLUG_CHECK,
        name="Spark Plug Check",
        icon="mdi:flash",
        interval=ServiceInterval(hours=100, days=180),
        enabled_by_default=False,
    ),
    ServiceType.SPARK_PLUG_REPLACE: ServiceDefinition(
        service_type=ServiceType.SPARK_PLUG_REPLACE,
        name="Spark Plug Replace",
        icon="mdi:flash",
        interval=ServiceInterval(hours=200, days=365),
        enabled_by_default=False,
    ),
    ServiceType.SPARK_ARRESTER_CLEAN: ServiceDefinition(
        service_type=ServiceType.SPARK_ARRESTER_CLEAN,
        name="Spark Arrester Clean",
        icon="mdi:fire",
        interval=ServiceInterval(hours=100, days=180),
        enabled_by_default=False,
    ),
    ServiceType.SEDIMENT_CUP_CLEAN: ServiceDefinition(
        service_type=ServiceType.SEDIMENT_CUP_CLEAN,
        name="Sediment Cup Clean",
        icon="mdi:cup-water",
        interval=ServiceInterval(hours=100, days=180),
        enabled_by_default=False,
    ),
    ServiceType.VALVE_CLEARANCE: ServiceDefinition(
        service_type=ServiceType.VALVE_CLEARANCE,
        name="Valve Clearance Check",
        icon="mdi:engine",
        interval=ServiceInterval(hours=200, days=365),
        enabled_by_default=False,
        is_dealer_service=True,
    ),
    ServiceType.TIMING_BELT: ServiceDefinition(
        service_type=ServiceType.TIMING_BELT,
        name="Timing Belt Check",
        icon="mdi:tire",
        interval=ServiceInterval(hours=250, days=365),
        enabled_by_default=False,
        is_dealer_service=True,
    ),
    ServiceType.COMBUSTION_CHAMBER: ServiceDefinition(
        service_type=ServiceType.COMBUSTION_CHAMBER,
        name="Combustion Chamber Clean",
        icon="mdi:piston",
        interval=ServiceInterval(hours=300, days=None),
        enabled_by_default=False,
        is_dealer_service=True,
    ),
    ServiceType.FUEL_TANK_CLEAN: ServiceDefinition(
        service_type=ServiceType.FUEL_TANK_CLEAN,
        name="Fuel Tank/Filter Clean",
        icon="mdi:gas-station",
        interval=ServiceInterval(hours=200, days=365),
        enabled_by_default=False,
        is_dealer_service=True,
    ),
    ServiceType.FUEL_PUMP_FILTER: ServiceDefinition(
        service_type=ServiceType.FUEL_PUMP_FILTER,
        name="Fuel Pump Filter Replace",
        icon="mdi:fuel",
        interval=ServiceInterval(hours=1000, days=730),
        enabled_by_default=False,
        is_dealer_service=True,
    ),
    ServiceType.FUEL_SYSTEM_CHECK: ServiceDefinition(
        service_type=ServiceType.FUEL_SYSTEM_CHECK,
        name="Fuel System Check",
        icon="mdi:pipe",
        interval=ServiceInterval(hours=None, days=730),
        enabled_by_default=False,
        is_dealer_service=True,
    ),
}


def get_model_services(model: str | None) -> dict[ServiceType, ServiceInterval]:
    """Get applicable services and intervals for a model.

    Args:
        model: The generator model name (e.g., "EU2200i")

    Returns:
        Dictionary mapping service types to their intervals for this model
    """
    if model and model in MODEL_SERVICE_INTERVALS:
        return MODEL_SERVICE_INTERVALS[model]
    return DEFAULT_SERVICE_INTERVALS


def get_service_definition(service_type: ServiceType) -> ServiceDefinition:
    """Get the service definition for a service type."""
    return SERVICE_DEFINITIONS[service_type]
