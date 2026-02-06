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

"""Constants for the Honda Generator integration."""

DOMAIN = "honda_generator"

DEFAULT_SCAN_INTERVAL = 10
MIN_SCAN_INTERVAL = 1

# Number of consecutive failed updates before forcing a reconnect
DEFAULT_RECONNECT_AFTER_FAILURES = 3

# Grace period at startup before showing offline defaults (seconds)
DEFAULT_STARTUP_GRACE_PERIOD = 60

# Grace period after disconnect before showing offline defaults (seconds)
DEFAULT_RECONNECT_GRACE_PERIOD = 30

# Number of stop command attempts before giving up
DEFAULT_STOP_ATTEMPTS = 3

CONF_SERIAL = "serial"
CONF_MODEL = "model"
CONF_ARCHITECTURE = "architecture"
CONF_RECONNECT_AFTER_FAILURES = "reconnect_after_failures"
CONF_STARTUP_GRACE_PERIOD = "startup_grace_period"
CONF_RECONNECT_GRACE_PERIOD = "reconnect_grace_period"
CONF_STOP_ATTEMPTS = "stop_attempts"
