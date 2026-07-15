from __future__ import annotations

import csv
import sys
import time
from datetime import datetime
from pathlib import Path

from constants import BACKLIGHT_DIR, BAT_DIR, BOOT_ID_FILE, CSV_FIELDS, POWER_SUPPLY_DIR
from csv_log import ensure_csv_header
from formatting import format_csv_duration


def read_path_value(path: Path) -> str | None:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return None


def read_sysfs_value(filename: str) -> str | None:
    return read_path_value(BAT_DIR / filename)


def read_numeric_value(*filenames: str) -> int | None:
    for filename in filenames:
        value = read_sysfs_value(filename)
        if value is None:
            continue
        try:
            return int(value)
        except ValueError:
            pass
    return None


def read_path_int(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def get_brightness_percent() -> str:
    try:
        backlight_devices = sorted(path for path in BACKLIGHT_DIR.iterdir() if path.is_dir())
    except OSError:
        return ""

    for device in backlight_devices:
        brightness = read_path_int(device / "brightness")
        max_brightness = read_path_int(device / "max_brightness")
        if brightness is None or max_brightness is None or max_brightness <= 0:
            continue
        return str(round((brightness / max_brightness) * 100))

    return ""


def format_duration_from_units(units: int | None, power: int) -> str:
    if units is None or power <= 0:
        return ""
    if units <= 0:
        return "0:00"
    return format_csv_duration((units / power) * 60)


def get_session_id() -> str:
    return read_path_value(BOOT_ID_FILE) or ""


def get_ac_adapter_status() -> str:
    try:
        power_supplies = sorted(path for path in POWER_SUPPLY_DIR.iterdir() if path.is_dir())
    except OSError:
        return ""

    found_adapter = False
    for power_supply in power_supplies:
        supply_type = (read_path_value(power_supply / "type") or "").lower()
        if supply_type not in {"mains", "usb", "usb_c", "usb-c"}:
            continue

        found_adapter = True
        online = read_path_value(power_supply / "online")
        if online == "1":
            return "online"

    return "offline" if found_adapter else ""


def get_battery_health_percent() -> str:
    full = read_numeric_value("energy_full", "charge_full")
    design = read_numeric_value("energy_full_design", "charge_full_design")
    if full is None or design is None or design <= 0:
        return ""
    return str(round((full / design) * 100))


def get_estimated_full_runtime(status: str, power_raw: str) -> str:
    if status.lower() != "discharging":
        return ""
    full = read_numeric_value("energy_full", "charge_full")
    return format_duration_from_units(full, int(power_raw))


def get_voltage_volts() -> str:
    voltage = read_numeric_value("voltage_now")
    if voltage is None:
        return ""
    return f"{voltage / 1_000_000.0:.2f}"


def get_battery_temp_c() -> str:
    temp = read_numeric_value("temp")
    if temp is not None:
        return f"{temp / 10.0:.1f}"

    try:
        hwmon_dirs = sorted(path for path in BAT_DIR.iterdir() if path.name.startswith("hwmon"))
    except OSError:
        return ""

    for hwmon_dir in hwmon_dirs:
        try:
            temp_files = sorted(hwmon_dir.glob("temp*_input"))
        except OSError:
            continue

        for temp_file in temp_files:
            temp_milli_c = read_path_int(temp_file)
            if temp_milli_c is not None:
                return f"{temp_milli_c / 1000.0:.1f}"

    return ""


def format_time_left(status: str, power_raw: str) -> str:
    power = int(power_raw)
    if power <= 0:
        return ""

    battery_status = status.lower()
    current = read_numeric_value("energy_now", "charge_now")
    if current is None:
        return ""

    if battery_status == "discharging":
        remaining_units = current
    elif battery_status == "charging":
        full = read_numeric_value("energy_full", "charge_full")
        if full is None:
            return ""
        remaining_units = full - current
    else:
        return ""

    return format_duration_from_units(remaining_units, power)


def log_battery(csv_file: Path) -> bool:
    if not BAT_DIR.exists():
        print(f"Error: Battery directory {BAT_DIR} not found.", file=sys.stderr)
        return False

    percent_text = read_sysfs_value("capacity")
    status = read_sysfs_value("status")
    power_raw = read_sysfs_value("power_now")
    if not all([percent_text, status, power_raw]):
        print("Error: Could not read all required battery stats.", file=sys.stderr)
        return False

    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    session_id = get_session_id()
    session_label = session_id[:8] if session_id else "N/A"
    percent = int(percent_text)
    watts = int(power_raw) / 1_000_000.0
    time_left = format_time_left(status, power_raw)
    estimated_full_runtime = get_estimated_full_runtime(status, power_raw)
    ac_adapter_status = get_ac_adapter_status()
    brightness_percent = get_brightness_percent()
    cycle_count = read_sysfs_value("cycle_count") or ""
    health_percent = get_battery_health_percent()
    voltage_volts = get_voltage_volts()
    battery_temp_c = get_battery_temp_c()
    signed_watts = -watts if status.lower() == "discharging" else watts

    write_header = ensure_csv_header(csv_file)
    with csv_file.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if write_header:
            writer.writerow(CSV_FIELDS)
        writer.writerow(
            [
                timestamp,
                session_id,
                percent,
                status,
                ac_adapter_status,
                f"{signed_watts:.2f}",
                time_left,
                estimated_full_runtime,
                cycle_count,
                health_percent,
                voltage_volts,
                battery_temp_c,
                brightness_percent,
            ]
        )

    brightness_label = f"{brightness_percent}%" if brightness_percent else "N/A"
    health_label = f"{health_percent}%" if health_percent else "N/A"
    voltage_label = f"{voltage_volts}V" if voltage_volts else "N/A"
    temp_label = f"{battery_temp_c}C" if battery_temp_c else "N/A"
    print(
        f"[{timestamp}] Session: {session_label} | {percent}% | {status} | "
        f"AC: {ac_adapter_status or 'N/A'} | Power: {signed_watts:.2f}W | "
        f"Time left: {time_left or 'N/A'} | Full runtime: {estimated_full_runtime or 'N/A'} | "
        f"Cycles: {cycle_count or 'N/A'} | Health: {health_label} | "
        f"Voltage: {voltage_label} | Temp: {temp_label} | Brightness: {brightness_label}"
    )
    return True


def run_logger(output: Path, watch: bool, interval_seconds: int) -> int:
    if not watch:
        return 0 if log_battery(output) else 1

    print(f"Logging to {output} every {interval_seconds} seconds. Press Ctrl+C to stop.")
    try:
        while True:
            log_battery(output)
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0
