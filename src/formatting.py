from __future__ import annotations

import html
import math
from typing import Callable, Iterable, TypeVar


T = TypeVar("T")


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value.lower() in {"unknown", "n/a", "na", "none", "--"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_duration_minutes(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value.lower() in {"unknown", "n/a", "na", "none", "--"}:
        return None

    parts = value.split(":")
    try:
        if len(parts) == 2:
            hours, minutes = (int(part) for part in parts)
            return hours * 60 + minutes
        if len(parts) == 3:
            hours, minutes, seconds = (int(part) for part in parts)
            return hours * 60 + minutes + seconds / 60
    except ValueError:
        return None
    return None


def format_csv_duration(minutes: float | None) -> str:
    if minutes is None or not math.isfinite(minutes) or minutes <= 0:
        return ""
    total_minutes = int(round(minutes))
    hours, mins = divmod(total_minutes, 60)
    return f"{hours}:{mins:02d}"


def format_minutes(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    total = max(0, round(value))
    hours, minutes = divmod(total, 60)
    return f"{hours}h {minutes:02d}m"


def format_runtime(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "Calculating..."
    return format_minutes(value)


def format_number(value: float | None, suffix: str = "", decimals: int = 1) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    if decimals == 0:
        return f"{value:.0f}{suffix}"
    return f"{value:.{decimals}f}{suffix}"


def html_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def values(items: Iterable[T], getter: Callable[[T], float | None]) -> list[float]:
    return [value for item in items if (value := getter(item)) is not None and math.isfinite(value)]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
