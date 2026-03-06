#!/bin/bash
#
# Install/uninstall the PRD Dashboard launchd service for auto-start on login.
#
# Usage:
#   ./install-launchd.sh install   - Install and enable auto-start
#   ./install-launchd.sh uninstall - Remove auto-start service
#   ./install-launchd.sh status    - Check if service is loaded
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.prdtool.dashboard"
PLIST_SOURCE="${SCRIPT_DIR}/com.prdtool.dashboard.plist"
PLIST_DEST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"
SERVICE_TARGET="${DOMAIN}/${LABEL}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_app_exists() {
    local app_path="${SCRIPT_DIR}/build/PRDDashboard.app"
    if [[ ! -d "$app_path" ]]; then
        print_error "PRDDashboard.app not found at: $app_path"
        echo "Please run ./build.sh first to build the app."
        exit 1
    fi
}

check_plist_exists() {
    if [[ ! -f "$PLIST_SOURCE" ]]; then
        print_error "Plist file not found: $PLIST_SOURCE"
        exit 1
    fi
}

do_install() {
    echo "Installing PRD Dashboard launchd service..."

    check_app_exists
    check_plist_exists

    # Create LaunchAgents directory if it doesn't exist
    mkdir -p "${HOME}/Library/LaunchAgents"

    # If service is already loaded, unload it first
    if launchctl print "$SERVICE_TARGET" &>/dev/null; then
        print_warning "Service already loaded, reloading..."
        launchctl bootout "$DOMAIN" "$PLIST_DEST" 2>/dev/null || true
    fi

    # Copy plist to LaunchAgents
    cp "$PLIST_SOURCE" "$PLIST_DEST"
    print_status "Copied plist to $PLIST_DEST"

    # Bootstrap the service
    if launchctl bootstrap "$DOMAIN" "$PLIST_DEST"; then
        print_status "Service bootstrapped successfully"
    else
        print_error "Failed to bootstrap service"
        exit 1
    fi

    # Enable the service
    launchctl enable "$SERVICE_TARGET"
    print_status "Service enabled"

    echo ""
    echo -e "${GREEN}Installation complete!${NC}"
    echo "The PRD Dashboard menu bar app will now start automatically on login."
    echo ""
    echo "To start it immediately, run:"
    echo "  open '${SCRIPT_DIR}/build/PRDDashboard.app'"
    echo ""
    echo "To uninstall, run:"
    echo "  ./install-launchd.sh uninstall"
}

do_uninstall() {
    echo "Uninstalling PRD Dashboard launchd service..."

    # Bootout/disable the service
    if launchctl print "$SERVICE_TARGET" &>/dev/null; then
        launchctl bootout "$DOMAIN" "$PLIST_DEST" 2>/dev/null || true
        print_status "Service unloaded"
    else
        print_warning "Service was not loaded"
    fi

    # Disable the service target
    launchctl disable "$SERVICE_TARGET" 2>/dev/null || true

    # Remove the plist
    if [[ -f "$PLIST_DEST" ]]; then
        rm "$PLIST_DEST"
        print_status "Removed plist from $PLIST_DEST"
    else
        print_warning "Plist was not installed"
    fi

    echo ""
    echo -e "${GREEN}Uninstallation complete!${NC}"
    echo "The PRD Dashboard menu bar app will no longer start automatically on login."
}

do_status() {
    echo "Checking PRD Dashboard launchd service status..."
    echo ""

    if [[ -f "$PLIST_DEST" ]]; then
        print_status "Plist installed at: $PLIST_DEST"
    else
        print_warning "Plist not installed"
    fi

    if launchctl print "$SERVICE_TARGET" &>/dev/null; then
        print_status "Service is loaded"
        echo ""
        echo "Service details:"
        launchctl print "$SERVICE_TARGET" 2>&1 | head -20
    else
        print_warning "Service is not loaded"
    fi
}

# Main
case "${1:-}" in
    install)
        do_install
        ;;
    uninstall)
        do_uninstall
        ;;
    status)
        do_status
        ;;
    *)
        echo "PRD Dashboard Launchd Service Installer"
        echo ""
        echo "Usage: $0 {install|uninstall|status}"
        echo ""
        echo "Commands:"
        echo "  install   - Install and enable auto-start on login"
        echo "  uninstall - Remove the launchd service"
        echo "  status    - Check if the service is installed and running"
        exit 1
        ;;
esac
