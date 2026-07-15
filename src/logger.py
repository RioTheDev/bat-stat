from __future__ import annotations

import csv
import sys
import time
from datetime import datetime
from pathlib import Path

from constants import BACKLIGHT_DIR, BOOT_ID_FILE, CSV_FIELDS, POWER_SUPPLY_DIR
from csv_log import ensure_csv_header
from formatting import format_csv_duration


def read_path_value(path: Path) -> str | None:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return None


def read_sysfs_value(battery_dir: Path, filename: str) -> str | None:
    return read_path_value(battery_dir / filename)


def read_numeric_value(battery_dir: Path, *filenames: str) -> int | None:
    for filename in filenames:
        value = read_sysfs_value(battery_dir, filename)
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


def get_battery_dirs() -> list[Path]:
    try:
        power_supplies = sorted(path for path in POWER_SUPPLY_DIR.iterdir() if path.is_dir())
    except OSError:
        return []

    batteries = []
    for power_supply in power_supplies:
        supply_type = (read_path_value(power_supply / "type") or "").lower()
        if supply_type == "battery":
            batteries.append(power_supply)
    return batteries


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


def format_duration_from_units(units: int | None, power: int | None) -> str:
    if units is None or power is None or power <= 0:
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


def get_battery_health_percent(battery_dir: Path) -> str:
    full = read_numeric_value(battery_dir, "energy_full", "charge_full")
    design = read_numeric_value(battery_dir, "energy_full_design", "charge_full_design")
    if full is None or design is None or design <= 0:
        return ""
    return str(round((full / design) * 100))


def get_estimated_full_runtime(battery_dir: Path, status: str, power_raw: int | None) -> str:
    if status.lower() != "discharging":
        return ""
    full = read_numeric_value(battery_dir, "energy_full", "charge_full")
    return format_duration_from_units(full, power_raw)


def get_voltage_volts(battery_dir: Path) -> str:
    voltage = read_numeric_value(battery_dir, "voltage_now")
    if voltage is None:
        return ""
    return f"{voltage / 1_000_000.0:.2f}"


def get_battery_temp_c(battery_dir: Path) -> str:
    temp = read_numeric_value(battery_dir, "temp")
    if temp is not None:
        return f"{temp / 10.0:.1f}"

    try:
        hwmon_dirs = sorted(path for path in battery_dir.iterdir() if path.name.startswith("hwmon"))
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


def format_time_left(battery_dir: Path, status: str, power_raw: int | None) -> str:
    if power_raw is None or power_raw <= 0:
        return ""

    battery_status = status.lower()
    current = read_numeric_value(battery_dir, "energy_now", "charge_now")
    if current is None:
        return ""

    if battery_status == "discharging":
        remaining_units = current
    elif battery_status == "charging":
        full = read_numeric_value(battery_dir, "energy_full", "charge_full")
        if full is None:
            return ""
        remaining_units = full - current
    else:
        return ""

    return format_duration_from_units(remaining_units, power_raw)


def battery_row(
    battery_dir: Path,
    timestamp: str,
    session_id: str,
    ac_adapter_status: str,
    brightness_percent: str,
) -> list[object] | None:
    percent = read_numeric_value(battery_dir, "capacity")
    status = read_sysfs_value(battery_dir, "status") or ""
    if percent is None or not status:
        return None

    power_raw = read_numeric_value(battery_dir, "power_now")
    watts = power_raw / 1_000_000.0 if power_raw is not None else None
    signed_watts = None
    if watts is not None:
        signed_watts = -watts if status.lower() == "discharging" else watts

    return [
        timestamp,
        session_id,
        percent,
        status,
        ac_adapter_status,
        f"{signed_watts:.2f}" if signed_watts is not None else "",
        format_time_left(battery_dir, status, power_raw),
        get_estimated_full_runtime(battery_dir, status, power_raw),
        read_sysfs_value(battery_dir, "cycle_count") or "",
        get_battery_health_percent(battery_dir),
        get_voltage_volts(battery_dir),
        get_battery_temp_c(battery_dir),
        brightness_percent,
        battery_dir.name,
    ]


def log_battery(csv_file: Path) -> bool:
    battery_dirs = get_battery_dirs()
    if not battery_dirs:
        print(f"Error: No batteries found in {POWER_SUPPLY_DIR}.", file=sys.stderr)
        return False

    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    session_id = get_session_id()
    session_label = session_id[:8] if session_id else "N/A"
    ac_adapter_status = get_ac_adapter_status()
    brightness_percent = get_brightness_percent()

    rows = [
        row
        for battery_dir in battery_dirs
        if (row := battery_row(battery_dir, timestamp, session_id, ac_adapter_status, brightness_percent)) is not None
    ]
    if not rows:
        print("Error: Could not read required battery stats.", file=sys.stderr)
        return False

    write_header = ensure_csv_header(csv_file)
    with csv_file.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if write_header:
            writer.writerow(CSV_FIELDS)
        writer.writerows(rows)

    parts = []
    for row in rows:
        battery_name = row[13]
        percent = row[2]
        status = row[3]
        power = row[5] or "N/A"
        time_left = row[6] or "N/A"
        parts.append(f"{battery_name}: {percent}% {status}, {power}W, {time_left}")
    print(f"[{timestamp}] Session: {session_label} | " + " | ".join(parts))
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
