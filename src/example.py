from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_DNS, uuid5

from constants import CSV_FIELDS
from formatting import clamp, format_csv_duration


def plugged_in_at(timestamp: datetime) -> bool:
    hour = timestamp.hour + timestamp.minute / 60
    weekday = timestamp.weekday()

    if 0 <= hour < 6.5:
        return True
    if weekday < 5 and 9 <= hour < 12:
        return True
    if weekday < 5 and 14 <= hour < 16:
        return timestamp.day % 3 != 0
    if 19.5 <= hour < 22 and timestamp.day % 2 == 0:
        return True
    return False


def session_id_for(timestamp: datetime) -> str:
    day = timestamp.strftime("%Y-%m-%d")
    hour = timestamp.hour
    if hour < 8:
        block = "overnight"
    elif hour < 18:
        block = "work"
    else:
        block = "evening"
    return str(uuid5(NAMESPACE_DNS, f"battery-example-{day}-{block}"))


def brightness_for(timestamp: datetime, rng: random.Random) -> int:
    hour = timestamp.hour + timestamp.minute / 60
    if 0 <= hour < 7:
        base = 28
    elif 7 <= hour < 18:
        base = 64
    else:
        base = 44
    return round(clamp(base + rng.uniform(-10, 12), 12, 96))


def generate_rows(days: int, interval_minutes: int, seed: int, battery_names: str = "BAT0") -> list[dict[str, object]]:
    rng = random.Random(seed)
    names = [name for name in battery_names.split("+") if name] or ["BAT0"]
    tz = timezone(timedelta(hours=4))
    start = datetime(2026, 6, 1, 0, 0, tzinfo=tz)
    sample_count = int(days * 24 * 60 / interval_minutes)
    percent = 91.0
    starting_cycle_count = 37
    discharged_percent_total = 0.0
    health = 96.0
    rows: list[dict[str, object]] = []

    for index in range(sample_count):
        timestamp = start + timedelta(minutes=index * interval_minutes)
        plugged = plugged_in_at(timestamp)
        brightness = brightness_for(timestamp, rng)

        if plugged:
            status = "Full" if percent >= 99.4 else "Charging"
            adapter = "online"
            watts = 0.8 + rng.uniform(0.0, 3.0) if status == "Full" else 24 + rng.uniform(-7, 11)
            percent_delta = 0.0 if status == "Full" else rng.uniform(0.8, 1.9)
        else:
            status = "Discharging"
            adapter = "offline"
            workload = 0.65 + (brightness / 100) * 0.45 + rng.uniform(-0.1, 0.35)
            if 10 <= timestamp.hour < 17 and timestamp.weekday() < 5:
                workload += 0.35
            watts = -(5.5 + workload * 8.8 + rng.uniform(-1.2, 2.0))
            percent_delta = watts / 60 * interval_minutes / 5.4

        previous_percent = percent
        percent = clamp(percent + percent_delta, 4, 100)
        if not plugged and previous_percent > percent:
            discharged_percent_total += previous_percent - percent
        cycle_count = starting_cycle_count + int(discharged_percent_total / 100)
        if percent <= 7 and not plugged:
            percent = 7
        if plugged and percent >= 99.4:
            percent = 100

        if not plugged and watts < 0:
            runtime_minutes = percent / max(0.1, -percent_delta) * interval_minutes
            full_runtime_minutes = 100 / max(0.1, -percent_delta) * interval_minutes
        else:
            runtime_minutes = None
            full_runtime_minutes = None

        health = clamp(health - 0.00035 + rng.uniform(-0.0008, 0.0004), 92.5, 100)
        voltage = 11.3 + (percent / 100) * 1.45 + (0.25 if plugged else 0) + rng.uniform(-0.06, 0.06)
        temp = 31 + (abs(watts) * 0.18) + (4 if plugged and watts > 15 else 0) + rng.uniform(-2.5, 2.5)
        if timestamp.hour < 7:
            temp -= 3.2

        split_total = sum(range(1, len(names) + 1))
        for battery_index, battery_name in enumerate(names):
            share = (battery_index + 1) / split_total
            offset = (battery_index - (len(names) - 1) / 2) * 8
            battery_percent = clamp(percent + offset, 4, 100)
            battery_watts = watts * share
            battery_runtime = runtime_minutes * (0.8 + share) if runtime_minutes else None
            battery_full_runtime = full_runtime_minutes * (0.8 + share) if full_runtime_minutes else None
            rows.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "session_id": session_id_for(timestamp),
                    "percent": round(battery_percent),
                    "status": status,
                    "ac_adapter_status": adapter,
                    "power_draw_watts": f"{battery_watts:.2f}",
                    "time_left": format_csv_duration(battery_runtime),
                    "estimated_full_runtime": format_csv_duration(battery_full_runtime),
                    "cycle_count": cycle_count + battery_index * 3,
                    "battery_health_percent": f"{clamp(health - battery_index * 1.4, 0, 100):.1f}",
                    "voltage_volts": f"{voltage + (battery_index - 0.5) * 0.12:.2f}",
                    "battery_temp_c": f"{temp + battery_index * 1.1:.1f}",
                    "brightness_percent": brightness,
                    "battery_name": battery_name,
                }
            )

    return rows


def write_example_csv(output: Path, days: int, interval_minutes: int, seed: int, battery_names: str = "BAT0") -> int:
    rows = generate_rows(days, interval_minutes, seed, battery_names)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {output} with {len(rows)} samples")
    return len(rows)
