from __future__ import annotations

from pathlib import Path


DEFAULT_LOG = Path("/var/log/battery-stat/battery_log.csv")
DEFAULT_REPORT = Path("battery_report.html")
DEFAULT_EXAMPLE_LOG = Path("examples/long_battery_log.csv")
DEFAULT_EXAMPLE_REPORT = Path("examples/long_battery_report.html")
TEMPLATE_NAME = "report_template.html"

POWER_SUPPLY_DIR = Path("/sys/class/power_supply")
BAT_DIR = Path("/sys/class/power_supply/BAT0")
BACKLIGHT_DIR = Path("/sys/class/backlight")
BOOT_ID_FILE = Path("/proc/sys/kernel/random/boot_id")

CSV_FIELDS = [
    "timestamp",
    "session_id",
    "percent",
    "status",
    "ac_adapter_status",
    "power_draw_watts",
    "time_left",
    "estimated_full_runtime",
    "cycle_count",
    "battery_health_percent",
    "voltage_volts",
    "battery_temp_c",
    "brightness_percent",
]
