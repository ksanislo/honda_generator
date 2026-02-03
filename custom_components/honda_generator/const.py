"""Constants for the Honda Generator integration."""

DOMAIN = "honda_generator"

DEFAULT_SCAN_INTERVAL = 10
MIN_SCAN_INTERVAL = 1

# Number of consecutive failed updates before forcing a reconnect
DEFAULT_RECONNECT_AFTER_FAILURES = 3

# Grace period at startup before showing offline defaults (seconds)
DEFAULT_STARTUP_GRACE_PERIOD = 60

CONF_SERIAL = "serial"
CONF_MODEL = "model"
CONF_ARCHITECTURE = "architecture"
CONF_RECONNECT_AFTER_FAILURES = "reconnect_after_failures"
CONF_STARTUP_GRACE_PERIOD = "startup_grace_period"
