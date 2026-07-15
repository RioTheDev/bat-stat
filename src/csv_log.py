from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from constants import CSV_FIELDS
from formatting import parse_duration_minutes, parse_float
from models import Sample


def ensure_csv_header(csv_file: Path) -> bool:
    csv_file.parent.mkdir(parents=True, exist_ok=True)

    if not csv_file.exists():
        return True

    with csv_file.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    if not rows:
        return True

    header = rows[0]
    if header == CSV_FIELDS:
        return False

    with csv_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_FIELDS)
        for row in rows[1:]:
            migrated_row = []
            for column in CSV_FIELDS:
                if column in header:
                    index = header.index(column)
                    migrated_row.append(row[index] if index < len(row) else "")
                else:
                    migrated_row.append("")
            writer.writerow(migrated_row)

    return False


def read_samples(path: Path) -> list[Sample]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        samples: list[Sample] = []
        for line_number, row in enumerate(reader, start=2):
            timestamp_text = (row.get("timestamp") or "").strip()
            if not timestamp_text:
                continue
            try:
                timestamp = datetime.fromisoformat(timestamp_text)
            except ValueError as exc:
                raise ValueError(f"Invalid timestamp on line {line_number}: {timestamp_text}") from exc

            samples.append(
                Sample(
                    timestamp=timestamp,
                    session_id=(row.get("session_id") or "").strip() or "unknown",
                    percent=parse_float(row.get("percent")),
                    status=(row.get("status") or "").strip() or "unknown",
                    adapter_status=(row.get("ac_adapter_status") or "").strip() or "unknown",
                    power_draw_watts=parse_float(row.get("power_draw_watts")),
                    time_left_minutes=parse_duration_minutes(row.get("time_left")),
                    estimated_full_runtime_minutes=parse_duration_minutes(row.get("estimated_full_runtime")),
                    cycle_count=parse_float(row.get("cycle_count")),
                    battery_health_percent=parse_float(row.get("battery_health_percent")),
                    voltage_volts=parse_float(row.get("voltage_volts")),
                    battery_temp_c=parse_float(row.get("battery_temp_c")),
                    brightness_percent=parse_float(row.get("brightness_percent")),
                )
            )

    samples.sort(key=lambda sample: sample.timestamp)
    return samples
