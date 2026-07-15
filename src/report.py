from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Iterable

from csv_log import read_samples
from formatting import format_minutes, format_number, format_runtime, html_escape, values
from models import Sample
from templates import default_template_path


def is_discharging(sample: Sample) -> bool:
    return (
        sample.status.lower() == "discharging"
        or sample.adapter_status.lower() == "offline"
        or (sample.power_draw_watts is not None and sample.power_draw_watts <= 0)
    )


def drain_power_watts(sample: Sample) -> float | None:
    if sample.power_draw_watts is None or not math.isfinite(sample.power_draw_watts):
        return None
    if sample.adapter_status.lower() == "online" or sample.status.lower() in {"charging", "full"}:
        return None
    return sample.power_draw_watts if sample.power_draw_watts <= 0 else None


def charging_power_watts(sample: Sample) -> float | None:
    if sample.power_draw_watts is None or not math.isfinite(sample.power_draw_watts):
        return None
    return sample.power_draw_watts if sample.power_draw_watts > 0 else None


def discharge_power_values(samples: Iterable[Sample]) -> list[float]:
    return [
        sample.power_draw_watts
        for sample in samples
        if sample.power_draw_watts is not None
        and math.isfinite(sample.power_draw_watts)
        and sample.power_draw_watts <= 0
    ]


def observed_duration(samples: list[Sample]) -> str:
    if len(samples) < 2:
        return "n/a"
    delta = samples[-1].timestamp - samples[0].timestamp
    minutes = delta.total_seconds() / 60
    if minutes < 60:
        return f"{minutes:.0f} min"
    hours = minutes / 60
    if hours < 48:
        return f"{hours:.1f} hr"
    return f"{hours / 24:.1f} days"


def average_discharge_rate(samples: list[Sample]) -> float | None:
    total_percent_change = 0.0
    total_hours = 0.0
    for current, next_sample in zip(samples, samples[1:]):
        if current.percent is None or next_sample.percent is None:
            continue
        if not is_discharging(current):
            continue
        elapsed_hours = (next_sample.timestamp - current.timestamp).total_seconds() / 3600
        if elapsed_hours <= 0:
            continue
        percent_change = next_sample.percent - current.percent
        if percent_change > 0:
            continue
        total_percent_change += percent_change
        total_hours += elapsed_hours
    if total_hours <= 0:
        return None
    return total_percent_change / total_hours


def summary_cards(samples: list[Sample]) -> str:
    latest = samples[-1]
    drain_values = discharge_power_values(samples)
    brightness_values = values(samples, lambda sample: sample.brightness_percent)
    rate_value = average_discharge_rate(samples)

    cards = [
        ("Charge Status", format_number(latest.percent, "%", 0), latest.status),
        ("Runtime", format_runtime(latest.time_left_minutes), f"Est. full: {format_runtime(latest.estimated_full_runtime_minutes)}"),
        ("Power Draw", format_number(mean(drain_values) if drain_values else None, " W", 2), f"current {format_number(drain_power_watts(latest), ' W', 2)} | {format_number(latest.voltage_volts, ' V', 2)}"),
        ("Discharge Rate", format_number(rate_value, "%/hr", 1), "avg over logged discharging intervals"),
        ("Battery Health", format_number(latest.battery_health_percent, "%", 0), f"{format_number(latest.cycle_count, '', 0)} cycles"),
        ("Brightness", format_number(latest.brightness_percent, "%", 0), f"avg {format_number(mean(brightness_values) if brightness_values else None, '%', 0)}"),
    ]
    if latest.battery_temp_c is not None and math.isfinite(latest.battery_temp_c):
        cards.append(("Temperature", format_number(latest.battery_temp_c, " C", 1), "latest sensor reading"))

    return "\n".join(
        f"""
        <article class="stat">
          <span>{html_escape(title)}</span>
          <strong>{html_escape(value)}</strong>
          <small>{html_escape(detail)}</small>
        </article>
        """
        for title, value, detail in cards
    )


def distribution_list(title: str, counter: Counter[str]) -> str:
    total = sum(counter.values()) or 1
    rows = []
    for name, count in counter.most_common():
        pct = count / total * 100
        rows.append(
            f"""
            <div class="bar-row">
              <span>{html_escape(name)}</span>
              <div><i style="width:{pct:.1f}%"></i></div>
              <b>{count}</b>
            </div>
            """
        )
    return f'<section class="panel"><h2>{html_escape(title)}</h2>{"".join(rows)}</section>'


def session_table(samples: list[Sample]) -> str:
    sessions: dict[str, list[Sample]] = defaultdict(list)
    for sample in samples:
        sessions[sample.session_id].append(sample)

    rows = []
    for session_id, session_samples in sorted(sessions.items(), key=lambda item: item[1][0].timestamp):
        first, last = session_samples[0], session_samples[-1]
        percent_values = values(session_samples, lambda sample: sample.percent)
        drain_values = discharge_power_values(session_samples)
        avg_discharge = average_discharge_rate(session_samples)
        duration = observed_duration(session_samples)
        change = "n/a"
        if first.percent is not None and last.percent is not None:
            change = f"{last.percent - first.percent:+.0f}%"
        rows.append(
            f"""
            <tr>
              <td><code>{html_escape(session_id[:8])}</code></td>
              <td>{html_escape(first.timestamp.strftime("%Y-%m-%d %H:%M"))}</td>
              <td>{html_escape(last.timestamp.strftime("%Y-%m-%d %H:%M"))}</td>
              <td>{html_escape(duration)}</td>
              <td>{html_escape(format_number(min(percent_values) if percent_values else None, "%", 0))}</td>
              <td>{html_escape(format_number(max(percent_values) if percent_values else None, "%", 0))}</td>
              <td>{html_escape(change)}</td>
              <td>{html_escape(format_number(avg_discharge, "%/hr", 1))}</td>
              <td>{html_escape(format_number(mean(drain_values) if drain_values else None, " W", 2))}</td>
              <td>{html_escape(last.status)}</td>
            </tr>
            """
        )

    return f"""
    <section class="panel wide">
      <h2>Sessions</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Session</th><th>Start</th><th>End</th><th>Duration</th>
              <th>Min</th><th>Max</th><th>Change</th><th>Discharge avg</th>
              <th>Avg drain</th><th>Latest status</th>
            </tr>
          </thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </section>
    """


def recent_table(samples: list[Sample], limit: int) -> str:
    rows = []
    for sample in samples[-limit:]:
        rows.append(
            f"""
            <tr>
              <td>{html_escape(sample.timestamp.strftime("%Y-%m-%d %H:%M:%S"))}</td>
              <td>{html_escape(format_number(sample.percent, "%", 0))}</td>
              <td>{html_escape(sample.status)}</td>
              <td>{html_escape(sample.adapter_status)}</td>
              <td>{html_escape(format_number(drain_power_watts(sample), " W", 2))}</td>
              <td>{html_escape(format_minutes(sample.time_left_minutes))}</td>
              <td>{html_escape(format_number(sample.voltage_volts, " V", 2))}</td>
              <td>{html_escape(format_number(sample.brightness_percent, "%", 0))}</td>
            </tr>
            """
        )

    return f"""
    <section class="panel wide">
      <h2>Recent samples</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th><th>Charge</th><th>Status</th><th>Adapter</th>
              <th>Drain</th><th>Time left</th><th>Voltage</th><th>Brightness</th>
            </tr>
          </thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </section>
    """


def json_for_html(data: object) -> str:
    return json.dumps(data, separators=(",", ":")).replace("</", "<\\/")


def sample_payload(samples: list[Sample]) -> list[list[object]]:
    return [
        [
            int(sample.timestamp.timestamp() * 1000),
            sample.percent,
            drain_power_watts(sample),
            sample.time_left_minutes,
            sample.estimated_full_runtime_minutes,
            sample.voltage_volts,
            sample.brightness_percent,
            sample.battery_temp_c,
            charging_power_watts(sample),
            sample.battery_health_percent,
            sample.cycle_count,
            sample.status,
            sample.adapter_status,
        ]
        for sample in samples
    ]


def chart_panel(config: dict[str, object]) -> str:
    key = html_escape(config["key"])
    label = html_escape(config["label"])
    return f"""
        <section class="panel chart-panel">
          <div class="panel-title-row">
            <h2>{label}</h2>
            <span id="chart-note-{key}" class="panel-note"></span>
          </div>
          <div id="chart-{key}" class="chart-host"></div>
        </section>
        """


def chart_configs_for(samples: list[Sample]) -> list[dict[str, object]]:
    configs: list[dict[str, object]] = [
        {"label": "Charge percent", "key": "charge", "index": 1, "color": "#6bb6ff", "unit": "%", "decimals": 0, "axisMin": 0, "axisMax": 100},
        {"label": "Power draw (drain only)", "key": "drain", "index": 2, "color": "#ff9369", "unit": " W", "decimals": 2, "axisMin": 0, "axisMax": None, "display": "negativeMagnitude"},
        {"label": "Charging power", "key": "charging-power", "index": 8, "color": "#67d6a3", "unit": " W", "decimals": 2, "axisMin": 0, "axisMax": None},
        {
            "label": "Runtime estimates",
            "key": "runtime",
            "singleAxis": True,
            "series": [
                {"label": "Time left", "key": "time-left", "index": 3, "color": "#67d6a3", "unit": " min", "decimals": 0, "axisMin": None, "axisMax": None, "format": "duration", "side": "left"},
                {"label": "Full runtime", "key": "full-runtime", "index": 4, "color": "#c0a2ff", "unit": " min", "decimals": 0, "axisMin": None, "axisMax": None, "format": "duration", "side": "left"},
            ],
        },
        {"label": "Voltage", "key": "voltage", "index": 5, "color": "#f1d36b", "unit": " V", "decimals": 2, "axisMin": None, "axisMax": None},
        {"label": "Brightness", "key": "brightness", "index": 6, "color": "#f5b85f", "unit": "%", "decimals": 0, "axisMin": 0, "axisMax": 100},
        {
            "label": "Battery health & cycles",
            "key": "battery-aging",
            "series": [
                {"label": "Health", "key": "health", "index": 9, "color": "#7dd3fc", "unit": "%", "decimals": 1, "axisMin": 0, "axisMax": 100, "side": "left"},
                {"label": "Cycles", "key": "cycles", "index": 10, "color": "#fbbf24", "unit": "", "decimals": 0, "axisMin": None, "axisMax": None, "side": "right"},
            ],
        },
    ]
    if values(samples, lambda sample: sample.battery_temp_c):
        configs.append({"label": "Battery temperature", "key": "temperature", "index": 7, "color": "#ff7ab6", "unit": " C", "decimals": 1, "axisMin": None, "axisMax": None})
    return configs


def render_template(template_path: Path, context: dict[str, object]) -> str:
    rendered = template_path.read_text(encoding="utf-8")
    for key, value in context.items():
        rendered = rendered.replace(f"${key}", str(value))
    return rendered


def render_report(
    samples: list[Sample],
    source: Path,
    generated_at: datetime,
    recent_limit: int,
    template_path: Path | None = None,
) -> str:
    if not samples:
        raise ValueError(f"No samples found in {source}")
    template_path = template_path or default_template_path()

    status_counts = Counter(sample.status for sample in samples)
    adapter_counts = Counter(sample.adapter_status for sample in samples)
    latest = samples[-1]
    chart_configs = chart_configs_for(samples)
    chart_sections = "\n".join(chart_panel(config) for config in chart_configs)

    context = {
        "title": html_escape(f"Battery report - {latest.timestamp.strftime('%Y-%m-%d %H:%M')}"),
        "source": html_escape(source),
        "generated_at": html_escape(generated_at.strftime("%Y-%m-%d %H:%M:%S %z")),
        "range_start": html_escape(samples[0].timestamp.strftime("%Y-%m-%d %H:%M")),
        "range_end": html_escape(samples[-1].timestamp.strftime("%Y-%m-%d %H:%M")),
        "observed_duration": html_escape(observed_duration(samples)),
        "sample_count": len(samples),
        "summary_cards": summary_cards(samples),
        "chart_sections": chart_sections,
        "status_distribution": distribution_list("Status distribution", status_counts),
        "adapter_distribution": distribution_list("Adapter distribution", adapter_counts),
        "session_table": session_table(samples),
        "recent_table": recent_table(samples, recent_limit),
        "samples_json": json_for_html(sample_payload(samples)),
        "charts_json": json_for_html(chart_configs),
    }
    return render_template(template_path, context)


def build_report(input_path: Path, output_path: Path, recent_limit: int, template_path: Path | None = None) -> int:
    samples = read_samples(input_path)
    generated_at = datetime.now().astimezone()
    report = render_report(samples, input_path, generated_at, max(1, recent_limit), template_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"Wrote {output_path} with {len(samples)} samples from {input_path}")
    return 0
