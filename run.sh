#!/bin/bash
# DNS Block List Checker local runner for macOS, Linux, and WSL.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_PY="${SCRIPT_DIR}/main.py"
DEFAULT_CONFIG="${SCRIPT_DIR}/config/config-local.yaml"
EXTENDED_CONFIG="${SCRIPT_DIR}/config/config-local-extended.yaml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_section() { echo -e "\n${BLUE}>>> $*${NC}"; }

detect_os() {
    case "$(uname -s)" in
        Linux*) echo "Linux" ;;
        Darwin*) echo "macOS" ;;
        MINGW*|MSYS*|CYGWIN*) echo "Windows" ;;
        *) echo "Unknown" ;;
    esac
}

detect_python_env() {
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        echo "venv (${VIRTUAL_ENV})"
    elif [[ -n "${CONDA_DEFAULT_ENV:-}" ]]; then
        echo "conda (${CONDA_DEFAULT_ENV})"
    elif [[ -d "${SCRIPT_DIR}/.venv" ]]; then
        echo "local .venv"
    elif [[ -d "${SCRIPT_DIR}/venv" ]]; then
        echo "local venv"
    else
        echo "system Python"
    fi
}

find_python() {
    local candidates=(
        "${VIRTUAL_ENV:-}/bin/python"
        "${VIRTUAL_ENV:-}/bin/python3"
        "${SCRIPT_DIR}/.venv/bin/python"
        "${SCRIPT_DIR}/.venv/bin/python3"
        "${SCRIPT_DIR}/venv/bin/python"
        "${SCRIPT_DIR}/venv/bin/python3"
        "python3"
        "python"
    )

    local candidate
    for candidate in "${candidates[@]}"; do
        if [[ -n "${candidate}" ]] && command -v "${candidate}" >/dev/null 2>&1; then
            echo "${candidate}"
            return 0
        fi
    done
}

check_python_version() {
    local python_exe="$1"
    local version major minor
    version=$("${python_exe}" --version 2>&1 | awk '{print $2}')
    major=$(echo "${version}" | cut -d. -f1)
    minor=$(echo "${version}" | cut -d. -f2)
    [[ "${major}" -gt 3 || ( "${major}" -eq 3 && "${minor}" -ge 10 ) ]]
}

show_help() {
    cat <<EOF
DNS Block List Checker - Local Runner

USAGE:
  ./run.sh [OPTIONS]

OPTIONS:
  -e, --extended       Use config/config-local-extended.yaml
  -c, --config PATH    Use a custom config file
  -v, --verbose        Show verbose runner output
  -h, --help           Show this help message

EXAMPLES:
  ./run.sh
  ./run.sh --config config/config-local.yaml
  ./run.sh -e

REQUIREMENTS:
  - Python 3.14 or higher
  - Dependencies from requirements.txt installed
EOF
}

USE_EXTENDED=false
VERBOSE=false
CUSTOM_CONFIG=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -e|--extended) USE_EXTENDED=true; shift ;;
        -v|--verbose) VERBOSE=true; shift ;;
        -c|--config)
            CUSTOM_CONFIG="${2:-}"
            if [[ -z "${CUSTOM_CONFIG}" ]]; then
                log_error "--config requires a path"
                exit 1
            fi
            shift 2
            ;;
        -h|--help) show_help; exit 0 ;;
        *) log_error "Unknown option: $1"; show_help; exit 1 ;;
    esac
done

log_section "Starting dnsblchk Local Runner"
log_info "Operating System: $(detect_os)"
log_info "Python Environment: $(detect_python_env)"

if [[ -n "${CUSTOM_CONFIG}" ]]; then
    CONFIG_FILE="${CUSTOM_CONFIG}"
    [[ "${CONFIG_FILE}" = /* ]] || CONFIG_FILE="${SCRIPT_DIR}/${CONFIG_FILE}"
elif [[ "${USE_EXTENDED}" == "true" ]]; then
    CONFIG_FILE="${EXTENDED_CONFIG}"
else
    CONFIG_FILE="${DEFAULT_CONFIG}"
fi

log_section "Validating configuration"
if [[ ! -f "${MAIN_PY}" ]]; then
    log_error "main.py not found: ${MAIN_PY}"
    exit 1
fi
if [[ ! -f "${CONFIG_FILE}" ]]; then
    log_error "Config file not found: ${CONFIG_FILE}"
    log_error "Restore config/config-local.yaml or pass --config PATH."
    exit 1
fi
log_info "Configuration file validated"

log_section "Locating Python"
PYTHON_EXE="$(find_python || true)"
if [[ -z "${PYTHON_EXE}" ]]; then
    log_error "Python 3.14+ not found in PATH or virtual environments"
    exit 1
fi
if ! check_python_version "${PYTHON_EXE}"; then
    log_error "Python version too old: $("${PYTHON_EXE}" --version 2>&1) (required: 3.14+)"
    exit 1
fi
log_info "Found Python: ${PYTHON_EXE}"

if [[ "${VERBOSE}" == "true" ]]; then
    log_info "Verbose runner output enabled"
fi

log_section "Ready to start dnsblchk"
echo "  Python:      ${PYTHON_EXE}"
echo "  Config file: ${CONFIG_FILE}"
echo "  Main script: ${MAIN_PY}"

cd "${SCRIPT_DIR}"
exec "${PYTHON_EXE}" "${MAIN_PY}" "${CONFIG_FILE}"
