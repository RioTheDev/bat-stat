from __future__ import annotations

import argparse
from pathlib import Path

from constants import DEFAULT_EXAMPLE_LOG, DEFAULT_EXAMPLE_REPORT, DEFAULT_LOG, DEFAULT_REPORT, TEMPLATE_NAME
from example import write_example_csv
from logger import run_logger
from report import build_report


def add_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-i", "--input", type=Path, default=DEFAULT_LOG, help=f"CSV input path (default: {DEFAULT_LOG})")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_REPORT, help=f"HTML output path (default: {DEFAULT_REPORT})")
    parser.add_argument("--template", type=Path, default=None, help=f"HTML template path (default: bundled {TEMPLATE_NAME})")
    parser.add_argument("--recent-limit", type=int, default=60, help="Number of recent samples to show in the table")
    parser.add_argument("--no-open", action="store_true", help="Do not open the generated report in a browser.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Battery logging and HTML reporting app.")
    subparsers = parser.add_subparsers(dest="command")

    report_parser = subparsers.add_parser("report", help="Generate an HTML report from a battery CSV log.")
    add_report_args(report_parser)

    log_parser = subparsers.add_parser("log", help="Append one battery sample to the CSV log, or keep logging.")
    log_parser.add_argument("-o", "--output", type=Path, default=DEFAULT_LOG, help=f"CSV file to append to (default: {DEFAULT_LOG})")
    log_parser.add_argument("--watch", action="store_true", help="Keep logging until interrupted.")
    log_parser.add_argument("--interval-seconds", type=int, default=300, help="Watch-mode interval in seconds (default: 300).")

    example_parser = subparsers.add_parser("example", help="Generate a long synthetic CSV log.")
    example_parser.add_argument("-o", "--output", type=Path, default=DEFAULT_EXAMPLE_LOG)
    example_parser.add_argument("--days", type=int, default=45)
    example_parser.add_argument("--interval-minutes", type=int, default=5)
    example_parser.add_argument("--seed", type=int, default=1729)
    example_parser.add_argument("--battery-names", default="BAT0")

    demo_parser = subparsers.add_parser("demo", help="Generate a synthetic CSV and render its HTML report.")
    demo_parser.add_argument("--csv-output", type=Path, default=DEFAULT_EXAMPLE_LOG)
    demo_parser.add_argument("--report-output", type=Path, default=DEFAULT_EXAMPLE_REPORT)
    demo_parser.add_argument("--days", type=int, default=45)
    demo_parser.add_argument("--interval-minutes", type=int, default=5)
    demo_parser.add_argument("--seed", type=int, default=1729)
    demo_parser.add_argument("--battery-names", default="BAT0")
    demo_parser.add_argument("--template", type=Path, default=None, help=f"HTML template path (default: bundled {TEMPLATE_NAME})")
    demo_parser.add_argument("--recent-limit", type=int, default=120)
    demo_parser.add_argument("--no-open", action="store_true", help="Do not open the generated report in a browser.")

    add_report_args(parser)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.command == "log":
        return run_logger(args.output, args.watch, max(1, args.interval_seconds))

    if args.command == "example":
        write_example_csv(args.output, args.days, max(1, args.interval_minutes), args.seed, args.battery_names)
        return 0

    if args.command == "demo":
        write_example_csv(args.csv_output, args.days, max(1, args.interval_minutes), args.seed, args.battery_names)
        return build_report(args.csv_output, args.report_output, args.recent_limit, args.template, not args.no_open)

    return build_report(args.input, args.output, args.recent_limit, args.template, not args.no_open)
