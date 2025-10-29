#!/bin/bash
# DNS Block List Checker - Service Control Script
# Updated for Ubuntu 22.04+ with systemd support
#
# Usage: ./main.sh {start|stop|restart|status|enable|disable}

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# CONFIGURATION
# ============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SERVICE_NAME="dnsblchk"
readonly MAIN_PY="${SCRIPT_DIR}/main.py"
readonly PYTHON_CMD="python3"
readonly PIDFILE="/var/run/${SERVICE_NAME}.pid"
readonly LOGFILE="/var/log/${SERVICE_NAME}.log"
readonly USER="${SERVICE_USER:-nobody}"
readonly GROUP="${SERVICE_GROUP:-nogroup}"

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m'  # No Color

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOGFILE}"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
    log "INFO: $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
    log "ERROR: $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
    log "WARN: $*"
}

# Check if running as root
check_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# Check if main.py exists
check_main_py() {
    if [[ ! -f "${MAIN_PY}" ]]; then
        log_error "main.py not found at ${MAIN_PY}"
        exit 1
    fi
}

# Check if Python 3 is available
check_python() {
    if ! command -v "${PYTHON_CMD}" &> /dev/null; then
        log_error "Python 3 is not installed or not in PATH"
        exit 1
    fi
    log_info "Using Python: $(${PYTHON_CMD} --version)"
}

# Get PID from pidfile or process
get_pid() {
    if [[ -f "${PIDFILE}" ]]; then
        local pid
        pid=$(cat "${PIDFILE}" 2>/dev/null || echo "0")
        # Verify PID is still running
        if kill -0 "${pid}" 2>/dev/null; then
            echo "${pid}"
        else
            rm -f "${PIDFILE}"
            echo "0"
        fi
    else
        # Try to find by process name as fallback
        pgrep -f "python3.*${MAIN_PY}" || echo "0"
    fi
}

# Check if service is running
is_running() {
    local pid
    pid=$(get_pid)
    [[ "${pid}" -ne 0 ]]
}

# ============================================================================
# SERVICE FUNCTIONS
# ============================================================================

start_service() {
    log_info "Starting ${SERVICE_NAME}..."

    # Check prerequisites
    check_python
    check_main_py

    # Check if already running
    if is_running; then
        local pid
        pid=$(get_pid)
        log_warn "${SERVICE_NAME} is already running (PID: ${pid})"
        return 0
    fi

    # Create log directory if needed
    mkdir -p "$(dirname "${LOGFILE}")"
    touch "${LOGFILE}"

    # Create pidfile directory if needed
    mkdir -p "$(dirname "${PIDFILE}")"

    # Start the service
    log_info "Executing: ${PYTHON_CMD} ${MAIN_PY}"

    # Start in background and capture PID
    if nohup "${PYTHON_CMD}" "${MAIN_PY}" >> "${LOGFILE}" 2>&1 &
        PID=$!
    then
        # Write PID to file
        echo "${PID}" > "${PIDFILE}"
        sleep 1

        # Verify it's still running
        if kill -0 "${PID}" 2>/dev/null; then
            log_info "✓ ${SERVICE_NAME} started successfully (PID: ${PID})"
            return 0
        else
            log_error "✗ ${SERVICE_NAME} exited immediately"
            rm -f "${PIDFILE}"
            return 1
        fi
    else
        log_error "✗ Failed to start ${SERVICE_NAME}"
        return 1
    fi
}

stop_service() {
    log_info "Stopping ${SERVICE_NAME}..."

    local pid
    pid=$(get_pid)

    if [[ "${pid}" -eq 0 ]]; then
        log_warn "${SERVICE_NAME} is not running"
        return 0
    fi

    log_info "Sending SIGTERM to PID ${pid}..."

    # Send SIGTERM and wait for graceful shutdown
    if kill -TERM "${pid}" 2>/dev/null; then
        local timeout=30
        local elapsed=0

        while kill -0 "${pid}" 2>/dev/null && [[ ${elapsed} -lt ${timeout} ]]; do
            sleep 1
            ((elapsed++))
            printf "."
        done
        echo ""

        # Check if still running
        if kill -0 "${pid}" 2>/dev/null; then
            log_warn "Process did not stop gracefully, sending SIGKILL..."
            kill -9 "${pid}" 2>/dev/null || true
        fi
    else
        log_warn "Process ${pid} not found"
    fi

    # Clean up pidfile
    rm -f "${PIDFILE}"
    log_info "✓ ${SERVICE_NAME} stopped"
    return 0
}

restart_service() {
    log_info "Restarting ${SERVICE_NAME}..."
    stop_service
    sleep 2
    start_service
}

status_service() {
    local pid
    pid=$(get_pid)

    if [[ "${pid}" -eq 0 ]]; then
        echo -e "${RED}✗ ${SERVICE_NAME} is stopped${NC}"
        [[ -f "${LOGFILE}" ]] && echo "Last log entries:" && tail -5 "${LOGFILE}"
        return 1
    else
        echo -e "${GREEN}✓ ${SERVICE_NAME} is running${NC}"
        echo "  PID: ${pid}"
        echo "  Log file: ${LOGFILE}"

        # Show process info
        if ps -p "${pid}" -o cmd= | head -1; then
            true
        fi

        return 0
    fi
}

# ============================================================================
# SYSTEMD INTEGRATION
# ============================================================================

enable_systemd() {
    log_info "Creating systemd unit file..."

    local systemd_file="/etc/systemd/system/${SERVICE_NAME}.service"

    cat > "${systemd_file}" << 'EOF'
[Unit]
Description=DNS Block List Checker
After=network.target syslog.target

[Service]
Type=simple
User=nobody
Group=nogroup
WorkingDirectory={WORK_DIR}
ExecStart={PYTHON_CMD} {MAIN_PY}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=dnsblchk

[Install]
WantedBy=multi-user.target
EOF

    # Replace placeholders
    sed -i "s|{WORK_DIR}|${SCRIPT_DIR}|g" "${systemd_file}"
    sed -i "s|{PYTHON_CMD}|${PYTHON_CMD}|g" "${systemd_file}"
    sed -i "s|{MAIN_PY}|${MAIN_PY}|g" "${systemd_file}"

    # Reload systemd
    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}.service"

    log_info "✓ Systemd service created: ${systemd_file}"
    log_info "Enable with: systemctl start ${SERVICE_NAME}"
}

disable_systemd() {
    log_info "Removing systemd unit file..."

    local systemd_file="/etc/systemd/system/${SERVICE_NAME}.service"

    if [[ -f "${systemd_file}" ]]; then
        systemctl disable "${SERVICE_NAME}.service" || true
        systemctl stop "${SERVICE_NAME}.service" || true
        rm -f "${systemd_file}"
        systemctl daemon-reload
        log_info "✓ Systemd service removed"
    fi
}

# ============================================================================
# HELP & USAGE
# ============================================================================

show_help() {
    cat << EOF
Usage: $0 {start|stop|restart|status|enable|disable|help}

COMMANDS:
  start       Start the ${SERVICE_NAME} service
  stop        Stop the ${SERVICE_NAME} service
  restart     Restart the ${SERVICE_NAME} service
  status      Show service status
  enable      Create and enable systemd service (requires root)
  disable     Remove systemd service (requires root)
  help        Show this help message

EXAMPLES:
  # Manual management
  sudo $0 start
  sudo $0 stop
  sudo $0 status

  # Systemd management (recommended)
  sudo $0 enable
  sudo systemctl start ${SERVICE_NAME}
  sudo systemctl status ${SERVICE_NAME}

CONFIGURATION:
  Service name:    ${SERVICE_NAME}
  Main script:     ${MAIN_PY}
  PID file:        ${PIDFILE}
  Log file:        ${LOGFILE}
  Python command:  ${PYTHON_CMD}

EOF
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    local command="${1:-help}"

    # Shift to get remaining args
    shift 2>/dev/null || true

    case "${command}" in
        start)
            check_root
            start_service
            ;;
        stop)
            check_root
            stop_service
            ;;
        restart)
            check_root
            restart_service
            ;;
        status)
            status_service
            ;;
        enable)
            check_root
            enable_systemd
            ;;
        disable)
            check_root
            disable_systemd
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: ${command}"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"

