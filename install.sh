#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-bat-stat}"
SERVICE_NAME="${SERVICE_NAME:-bat-stat-log}"
TIMER_NAME="${TIMER_NAME:-${SERVICE_NAME}.timer}"
INSTALL_DIR="${INSTALL_DIR:-/opt/${APP_NAME}}"
BIN_PATH="${BIN_PATH:-/usr/local/bin/bat-stat}"
LOG_FILE="${LOG_FILE:-/var/log/battery-stat/battery_log.csv}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-300}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
START_TIMER="${START_TIMER:-1}"
RUN_ON_INSTALL="${RUN_ON_INSTALL:-1}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
REPO_URL="${REPO_URL:-https://github.com/riothedev/bat-stat.git}"
BRANCH="${BRANCH:-main}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR"
CLEANUP_DIR=""

cleanup() {
  if [ -n "$CLEANUP_DIR" ]; then
    rm -rf "$CLEANUP_DIR"
  fi
}
trap cleanup EXIT

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this installer as root, for example: sudo ./install.sh" >&2
  exit 1
fi

if [ -z "$PYTHON_BIN" ]; then
  echo "python3 was not found. Set PYTHON_BIN=/path/to/python3 and rerun." >&2
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl was not found. This installer needs systemd." >&2
  exit 1
fi

if [ ! -f "$SOURCE_DIR/bat_stat.py" ] || [ ! -d "$SOURCE_DIR/src" ]; then
  if ! command -v git >/dev/null 2>&1; then
    echo "Local source files were not found and git is not installed." >&2
    echo "Install git or run from a cloned Bat Stat repository." >&2
    exit 1
  fi

  CLEANUP_DIR="$(mktemp -d)"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$CLEANUP_DIR"
  SOURCE_DIR="$CLEANUP_DIR"
fi

case "$INTERVAL_SECONDS" in
  ''|*[!0-9]*)
    echo "INTERVAL_SECONDS must be a positive integer." >&2
    exit 1
    ;;
esac

if [ "$INTERVAL_SECONDS" -lt 1 ]; then
  echo "INTERVAL_SECONDS must be at least 1." >&2
  exit 1
fi

install -d -m 0755 "$INSTALL_DIR"
install -d -m 0755 "$INSTALL_DIR/src"
install -d -m 0755 "$(dirname "$BIN_PATH")"
install -d -m 0755 "$(dirname "$LOG_FILE")"
install -d -m 0755 "$SYSTEMD_DIR"

install -m 0755 "$SOURCE_DIR/bat_stat.py" "$INSTALL_DIR/bat_stat.py"
install -m 0644 "$SOURCE_DIR"/src/*.py "$INSTALL_DIR/src/"
install -m 0644 "$SOURCE_DIR/src/report_template.html" "$INSTALL_DIR/src/report_template.html"

if [ -f "$SOURCE_DIR/README.md" ]; then
  install -m 0644 "$SOURCE_DIR/README.md" "$INSTALL_DIR/README.md"
fi

if [ -f "$SOURCE_DIR/pyproject.toml" ]; then
  install -m 0644 "$SOURCE_DIR/pyproject.toml" "$INSTALL_DIR/pyproject.toml"
fi

if [ -f "$SOURCE_DIR/bat_stat.spec" ]; then
  install -m 0644 "$SOURCE_DIR/bat_stat.spec" "$INSTALL_DIR/bat_stat.spec"
fi

touch "$LOG_FILE"
chmod 0644 "$LOG_FILE"

cat > "$BIN_PATH" <<EOF
#!/usr/bin/env sh
exec "$PYTHON_BIN" "$INSTALL_DIR/bat_stat.py" "\$@"
EOF
chmod 0755 "$BIN_PATH"

cat > "$SYSTEMD_DIR/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Bat Stat CSV log sample

[Service]
Type=oneshot
WorkingDirectory=$INSTALL_DIR
ExecStart=$BIN_PATH log --output $LOG_FILE
Nice=5
NoNewPrivileges=true
EOF

cat > "$SYSTEMD_DIR/$TIMER_NAME" <<EOF
[Unit]
Description=Run Bat Stat CSV logging every $INTERVAL_SECONDS seconds

[Timer]
OnBootSec=1min
OnUnitActiveSec=${INTERVAL_SECONDS}s
AccuracySec=30s
Persistent=true
Unit=${SERVICE_NAME}.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload

if [ "$START_TIMER" = "0" ]; then
  systemctl enable "$TIMER_NAME"
else
  systemctl enable --now "$TIMER_NAME"
fi

if [ "$RUN_ON_INSTALL" != "0" ]; then
  systemctl start "${SERVICE_NAME}.service"
fi

echo "Installed Bat Stat to $INSTALL_DIR"
echo "Command: $BIN_PATH"
echo "Log file: $LOG_FILE"
echo "Service: ${SERVICE_NAME}.service"
echo "Timer: $TIMER_NAME"
echo "Next: systemctl status $TIMER_NAME"
