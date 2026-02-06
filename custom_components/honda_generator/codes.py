# Copyright 2024-2026 Ken Sanislo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Model-specific warning and fault codes for Honda generators."""

from dataclasses import dataclass


# Alert code to translation key mapping
# Keys are used for HA translations under entity.sensor.*.state.*
CODE_TRANSLATION_KEYS: dict[str, str] = {
    # Warnings (C- codes)
    "C-01": "c_01",
    "C-02": "c_02",
    "C-03": "c_03",
    "C-04": "c_04",
    "C-05": "c_05",
    "C-06": "c_06",
    "C-07": "c_07",
    "C-08": "c_08",
    "C-09": "c_09",
    "C-10": "c_10",
    "C-2A": "c_2a",
    "C-A2": "c_a2",
    # Faults (E- codes)
    "E-00": "e_00",
    "E-01": "e_01",
    "E-02": "e_02",
    "E-03": "e_03",
    "E-04": "e_04",
    "E-05": "e_05",
    "E-06": "e_06",
    "E-07": "e_07",
    "E-0A": "e_0a",
    "E-0B": "e_0b",
    "E-10": "e_10",
    "E-11": "e_11",
    "E-12": "e_12",
    "E-13": "e_13",
    "E-15": "e_15",
    "E-16": "e_16",
    "E-17": "e_17",
    "E-19": "e_19",
    "E-1A": "e_1a",
    "E-1B": "e_1b",
    "E-1C": "e_1c",
    "E-1E": "e_1e",
    "E-20": "e_20",
    "E-21": "e_21",
    "E-22": "e_22",
    "E-23": "e_23",
    "E-25": "e_25",
    "E-26": "e_26",
    "E-27": "e_27",
    "E-29": "e_29",
    "E-2A": "e_2a",
    "E-2B": "e_2b",
    "E-2C": "e_2c",
    "E-2E": "e_2e",
    "E-50": "e_50",
    "E-51": "e_51",
    "E-52": "e_52",
    "E-53": "e_53",
    "E-56": "e_56",
    "E-57": "e_57",
    "E-70": "e_70",
    "E-71": "e_71",
    "E-72": "e_72",
    "E-73": "e_73",
}

# English descriptions (used as fallback and for logging)
CODE_DESCRIPTIONS: dict[str, str] = {
    # Warnings (C- codes)
    "C-01": "Check engine",
    "C-02": "Check fuel",
    "C-03": "Check inverter",
    "C-04": "Check load",
    "C-05": "Output current high",
    "C-06": "Overcurrent detect (slave)",
    "C-07": "Overvoltage detect (slave)",
    "C-08": "Short overcurrent detect (slave)",
    "C-09": "Check CO sensor",
    "C-10": "CO detected",
    "C-2A": "Overspeed",
    "C-A2": "Control unit check",
    # Faults (E- codes)
    "E-00": "Starter fault",
    "E-01": "Starter stuck on",
    "E-02": "Battery voltage fault",
    "E-03": "Low oil",
    "E-04": "Oil sensor fault",
    "E-05": "Overheat",
    "E-06": "Generator pulse fault",
    "E-07": "RPM abnormal",
    "E-0A": "Starter failure",
    "E-0B": "Starter circuit",
    "E-10": "Ignition fault",
    "E-11": "Inverter comm (master)",
    "E-12": "Inverter fault",
    "E-13": "Inverter DC fault",
    "E-15": "Inverter overcurrent",
    "E-16": "Inverter overload",
    "E-17": "Inverter voltage fault",
    "E-19": "Output overvoltage",
    "E-1A": "Overload shutdown",
    "E-1B": "Ground fault",
    "E-1C": "Inverter communication",
    "E-1E": "Inverter overheat",
    "E-20": "Inverter-GCU comm (slave)",
    "E-21": "Inverter comm (slave)",
    "E-22": "Overcurrent shutdown (slave)",
    "E-23": "Overvoltage shutdown (slave)",
    "E-25": "Power module overheat (slave)",
    "E-26": "A/D input fault (slave)",
    "E-27": "FET open circuit (slave)",
    "E-29": "FET short circuit (slave)",
    "E-2A": "Diode short (slave)",
    "E-2B": "SCR short (slave)",
    "E-2C": "Inverter memory fault (slave)",
    "E-2E": "Short-circuit overcurrent (slave)",
    "E-50": "CO alert",
    "E-51": "Atmospheric pressure sensor",
    "E-52": "CO detected high",
    "E-53": "CO sensor error",
    "E-56": "CO calibration error",
    "E-57": "CO shutdown",
    "E-70": "BT unit communication",
    "E-71": "BT connection error",
    "E-72": "BT communication error",
    "E-73": "BT module error",
}


def get_code_description(code: str) -> str | None:
    """Get the English description for an alert code (for logging/fallback)."""
    return CODE_DESCRIPTIONS.get(code)


def get_code_translation_key(code: str) -> str | None:
    """Get the translation key for an alert code."""
    return CODE_TRANSLATION_KEYS.get(code)


@dataclass(frozen=True)
class AlertCode:
    """Represents a warning or fault code."""

    bit: int
    code: str

    @property
    def description(self) -> str | None:
        """Get the human-readable description for this code."""
        return CODE_DESCRIPTIONS.get(self.code)


# EU2200i codes
EU2200I_WARNING_CODES: list[AlertCode] = [
    AlertCode(bit=2, code="C-03"),
    AlertCode(bit=3, code="C-04"),
]

EU2200I_FAULT_CODES: list[AlertCode] = [
    AlertCode(bit=1, code="E-12"),
    AlertCode(bit=3, code="E-13"),
    AlertCode(bit=5, code="E-15"),
    AlertCode(bit=6, code="C-2A"),
    AlertCode(bit=7, code="E-16"),
    AlertCode(bit=10, code="E-17"),
    AlertCode(bit=12, code="E-19"),
    AlertCode(bit=13, code="E-1A"),
    AlertCode(bit=14, code="E-1B"),
]

# EU7000is codes
EU7000IS_WARNING_CODES: list[AlertCode] = [
    AlertCode(bit=0, code="C-01"),
    AlertCode(bit=1, code="C-02"),
    AlertCode(bit=2, code="C-03"),
    AlertCode(bit=3, code="C-04"),
    AlertCode(bit=4, code="C-05"),
    AlertCode(bit=5, code="C-06"),
    AlertCode(bit=6, code="C-07"),
    AlertCode(bit=7, code="C-08"),
    AlertCode(bit=8, code="C-09"),
    AlertCode(bit=9, code="C-10"),  # CO sensor report
]

EU7000IS_FAULT_CODES: list[AlertCode] = [
    AlertCode(bit=0, code="E-00"),
    AlertCode(bit=1, code="E-01"),
    AlertCode(bit=2, code="E-02"),
    AlertCode(bit=8, code="E-03"),
    AlertCode(bit=9, code="E-04"),
    AlertCode(bit=10, code="E-50"),
    AlertCode(bit=11, code="E-51"),
    AlertCode(bit=12, code="E-0A"),
    AlertCode(bit=13, code="E-53"),
    AlertCode(bit=14, code="E-56"),
    AlertCode(bit=16, code="E-05"),
    AlertCode(bit=17, code="E-06"),
    AlertCode(bit=18, code="E-07"),
    AlertCode(bit=20, code="E-10"),
    AlertCode(bit=21, code="E-11"),
    AlertCode(bit=22, code="E-20"),
    AlertCode(bit=23, code="E-21"),
    AlertCode(bit=24, code="E-12"),
    AlertCode(bit=25, code="E-13"),
    AlertCode(bit=26, code="E-1E"),
    AlertCode(bit=27, code="E-15"),
    AlertCode(bit=28, code="E-16"),
    AlertCode(bit=32, code="E-17"),
    AlertCode(bit=33, code="E-19"),
    AlertCode(bit=34, code="E-1A"),
    AlertCode(bit=35, code="E-1B"),
    AlertCode(bit=36, code="E-1C"),
    AlertCode(bit=40, code="E-22"),
    AlertCode(bit=41, code="E-23"),
    AlertCode(bit=42, code="E-2E"),
    AlertCode(bit=43, code="E-25"),
    AlertCode(bit=44, code="E-26"),
    AlertCode(bit=48, code="E-27"),
    AlertCode(bit=49, code="E-29"),
    AlertCode(bit=50, code="E-2A"),
    AlertCode(bit=51, code="E-2B"),
    AlertCode(bit=52, code="E-2C"),
]

# EM5000SX/EM6500SX codes (not documented in protocol - placeholder)
EM5000SX_WARNING_CODES: list[AlertCode] = []
EM5000SX_FAULT_CODES: list[AlertCode] = []
EM6500SX_WARNING_CODES: list[AlertCode] = []
EM6500SX_FAULT_CODES: list[AlertCode] = []

# EU3200i codes (Push architecture - delivered via CAN messages)
# ECU codes (CAN 0x3A2)
EU3200I_ECU_WARNING_CODES: list[AlertCode] = [
    AlertCode(bit=17, code="C-01"),  # Check engine
    AlertCode(bit=18, code="C-A2"),  # Control unit check
    AlertCode(bit=19, code="C-09"),  # Check CO sensor
    AlertCode(bit=21, code="C-10"),  # CO detected
    AlertCode(bit=24, code="C-02"),  # Check fuel
]

EU3200I_ECU_FAULT_CODES: list[AlertCode] = [
    AlertCode(bit=3, code="E-03"),  # Low oil
    AlertCode(bit=4, code="E-04"),  # Oil sensor fault
    AlertCode(bit=5, code="E-05"),  # Overheat
    AlertCode(bit=7, code="E-07"),  # RPM abnormal
    AlertCode(bit=10, code="E-0A"),  # Starter failure
    AlertCode(bit=11, code="E-10"),  # Ignition fault
    AlertCode(bit=12, code="E-70"),  # BT unit communication
    AlertCode(bit=23, code="E-0B"),  # Starter circuit
    AlertCode(bit=40, code="E-50"),  # CO alert
    AlertCode(bit=42, code="E-52"),  # CO detected high
    AlertCode(bit=43, code="E-53"),  # CO sensor error
    AlertCode(bit=46, code="E-56"),  # CO calibration error
]

# INV codes (CAN 0x3B2)
EU3200I_INV_WARNING_CODES: list[AlertCode] = [
    AlertCode(bit=8, code="C-03"),  # Check inverter
    AlertCode(bit=10, code="C-05"),  # Output current high
    AlertCode(bit=12, code="C-04"),  # Check load
]

EU3200I_INV_FAULT_CODES: list[AlertCode] = [
    AlertCode(bit=9, code="E-12"),  # Inverter fault
    AlertCode(bit=11, code="E-1E"),  # Inverter overheat
    AlertCode(bit=13, code="E-13"),  # Inverter DC fault
    AlertCode(bit=14, code="E-15"),  # Inverter overcurrent
    AlertCode(bit=16, code="E-16"),  # Inverter overload
    AlertCode(bit=17, code="E-17"),  # Inverter voltage fault
    AlertCode(bit=19, code="E-19"),  # Output overvoltage
    AlertCode(bit=20, code="E-1A"),  # Overload shutdown
    AlertCode(bit=21, code="E-1B"),  # Ground fault
    AlertCode(bit=22, code="E-1C"),  # Inverter communication
]

# BT codes (CAN 0x3A5)
EU3200I_BT_FAULT_CODES: list[AlertCode] = [
    AlertCode(bit=0, code="E-71"),  # BT connection error
    AlertCode(bit=1, code="E-72"),  # BT communication error
    AlertCode(bit=3, code="E-73"),  # BT module error
]

# Combined EU3200i codes (all sources)
EU3200I_WARNING_CODES: list[AlertCode] = (
    EU3200I_ECU_WARNING_CODES + EU3200I_INV_WARNING_CODES
)
EU3200I_FAULT_CODES: list[AlertCode] = (
    EU3200I_ECU_FAULT_CODES + EU3200I_INV_FAULT_CODES + EU3200I_BT_FAULT_CODES
)

MODEL_WARNING_CODES: dict[str, list[AlertCode]] = {
    "EU2200i": EU2200I_WARNING_CODES,
    "EU3200i": EU3200I_WARNING_CODES,
    "EU7000is": EU7000IS_WARNING_CODES,
    "EM5000SX": EM5000SX_WARNING_CODES,
    "EM6500SX": EM6500SX_WARNING_CODES,
}

MODEL_FAULT_CODES: dict[str, list[AlertCode]] = {
    "EU2200i": EU2200I_FAULT_CODES,
    "EU3200i": EU3200I_FAULT_CODES,
    "EU7000is": EU7000IS_FAULT_CODES,
    "EM5000SX": EM5000SX_FAULT_CODES,
    "EM6500SX": EM6500SX_FAULT_CODES,
}


def get_warning_codes(model: str) -> list[AlertCode]:
    """Get the warning codes defined for a model."""
    return MODEL_WARNING_CODES.get(model, [])


def get_fault_codes(model: str) -> list[AlertCode]:
    """Get the fault codes defined for a model."""
    return MODEL_FAULT_CODES.get(model, [])
