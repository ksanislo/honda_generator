# Honda Generator Service Schedule

This document outlines the maintenance schedule for supported Honda generators, based on official Honda manuals.

## User-Serviceable Items

| Service Item | Runtime Interval | Time Interval | Models | Notes |
|--------------|------------------|---------------|--------|-------|
| **Oil Change (First)** | 20 hrs | 1 month | All | One-time break-in service |
| **Oil Change** | 100 hrs | 6 months | All | Regular interval after break-in |
| **Air Filter Clean** | 50 hrs | 3 months | All | |
| **Air Filter Replace** | 300 hrs | 1 year | EU3200i | Other models: clean only |
| **Spark Plug Check** | 100 hrs | 6 months | All | |
| **Spark Plug Replace** | 200 hrs | 1 year | EU2200i | |
| **Spark Plug Replace** | 300 hrs | 1 year | EU3200i, EM5000/6500, EU7000is | |
| **Spark Arrester Clean** | 100 hrs | 6 months | EU2200i | |
| **Spark Arrester Clean** | 300 hrs | 1 year | EU3200i, EM5000/6500, EU7000is | |
| **Sediment Cup Clean** | 100 hrs | 6 months | EM5000SX, EM6500SX, EU7000is | Not on EU2200i/EU3200i |

## Dealer-Service Items

| Service Item | Runtime Interval | Time Interval | Models | Notes |
|--------------|------------------|---------------|--------|-------|
| **Valve Clearance Check** | 200 hrs | 1 year | EU2200i | |
| **Valve Clearance Check** | 300 hrs | 1 year | EU3200i, EM5000/6500, EU7000is | |
| **Timing Belt Check** | 250 hrs | 1 year | EU3200i | EU3200i only |
| **Combustion Chamber Clean** | 300 hrs | - | EU2200i | |
| **Combustion Chamber Clean** | 500 hrs | - | EU3200i, EU7000is | |
| **Combustion Chamber Clean** | 1000 hrs | - | EM5000SX, EM6500SX | |
| **Fuel Tank/Filter Clean** | 200 hrs | 1 year | EU2200i | |
| **Fuel Tank/Filter Clean** | 300 hrs | 1 year | EM5000/6500, EU7000is | |
| **Fuel Tank Clean** | 1000 hrs | 2 years | EU3200i | |
| **Fuel Pump Filter Replace** | 1000 hrs | 2 years | EU3200i | EU3200i only |
| **Fuel System Check** | - | 2 years | All | Tubes, canister, etc. |

## Notes

1. Service more frequently when used in dusty areas.
2. Dealer-service items should be serviced by your servicing dealer, unless you have the proper tools and are mechanically proficient.
3. For commercial use, log hours of operation to determine proper maintenance intervals.
4. Failure to follow this maintenance schedule could result in non-warrantable failures.
5. EU3200i is equipped with a catalytic converter. If the engine is not properly maintained, the catalyst in the muffler may lose effectiveness.

## Implementation

The integration tracks both runtime hours and calendar time for each service item. A notification is triggered when **either** threshold is reached (whichever comes first).

### Binary Sensors

- `binary_sensor.generator_oil_change_due`
- `binary_sensor.generator_air_filter_service_due`
- `binary_sensor.generator_spark_plug_service_due`
- `binary_sensor.generator_spark_arrester_service_due`
- `binary_sensor.generator_sediment_cup_service_due` (EM models only)
- `binary_sensor.generator_valve_clearance_due`
- `binary_sensor.generator_timing_belt_due` (EU3200i only)
- `binary_sensor.generator_combustion_chamber_due`
- `binary_sensor.generator_fuel_tank_service_due`
- `binary_sensor.generator_fuel_pump_filter_due` (EU3200i only)
- `binary_sensor.generator_fuel_system_due`

### Buttons (Mark Service Complete)

Each service item has a corresponding button to mark it as complete. Pressing the button records the current runtime hours and date.
