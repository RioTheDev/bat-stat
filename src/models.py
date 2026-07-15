from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Sample:
    timestamp: datetime
    session_id: str
    percent: float | None
    status: str
    adapter_status: str
    power_draw_watts: float | None
    time_left_minutes: float | None
    estimated_full_runtime_minutes: float | None
    cycle_count: float | None
    battery_health_percent: float | None
    voltage_volts: float | None
    battery_temp_c: float | None
    brightness_percent: float | None
    battery_name: str
