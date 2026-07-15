#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-bat-stat}"
SERVICE_NAME="${SERVICE_NAME:-bat-stat-log}"
TIMER_NAME="${TIMER_NAME:-${SERVICE_NAME}.timer}"
INSTALL_DIR="${INSTALL_DIR:-/opt/${APP_NAME}}"
BIN_PATH="${BIN_PATH:-/usr/local/bin/bat-stat}"
LOG_FILE="${LOG_FILE:-/var/log/battery-stat/battery_log.csv}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
REMOVE_LOG="${REMOVE_LOG:-0}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this uninstaller as root, for example: sudo ./uninstall.sh" >&2
  exit 1
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl disable --now "$TIMER_NAME" >/dev/null 2>&1 || true
  systemctl stop "${SERVICE_NAME}.service" >/dev/null 2>&1 || true
fi

rm -f "$SYSTEMD_DIR/$TIMER_NAME"
rm -f "$SYSTEMD_DIR/${SERVICE_NAME}.service"
rm -f "$BIN_PATH"
rm -rf "$INSTALL_DIR"

if [ "$REMOVE_LOG" = "1" ]; then
  rm -f "$LOG_FILE"
  rmdir "$(dirname "$LOG_FILE")" >/dev/null 2>&1 || true
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload
  systemctl reset-failed "$TIMER_NAME" "${SERVICE_NAME}.service" >/dev/null 2>&1 || true
fi

echo "Removed Bat Stat app files, command, service, and timer."
if [ "$REMOVE_LOG" = "1" ]; then
  echo "Removed log file: $LOG_FILE"
else
  echo "Kept log file: $LOG_FILE"
  echo "Run with REMOVE_LOG=1 to delete it too."
fi
