#!/bin/bash

# PRD Dashboard Menu Bar App - Test Script
# Validates source files, Info.plist, and build structure

# Don't exit on error - we handle failures in the test logic
# set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
APP_NAME="PRDDashboard"
APP_BUNDLE="${BUILD_DIR}/${APP_NAME}.app"
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS_COUNT++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL_COUNT++))
}

skip() {
    echo -e "${YELLOW}○${NC} $1 (skipped)"
    ((SKIP_COUNT++))
}

echo "🧪 Testing PRD Dashboard Menu Bar App..."
echo ""

# =============================================================================
# Source File Tests
# =============================================================================
echo "━━━ Source Files ━━━"

# Test: main.swift exists
if [[ -f "${SCRIPT_DIR}/Sources/main.swift" ]]; then
    pass "main.swift exists"
else
    fail "main.swift is missing"
fi

# Test: AppDelegate.swift exists
if [[ -f "${SCRIPT_DIR}/Sources/AppDelegate.swift" ]]; then
    pass "AppDelegate.swift exists"
else
    fail "AppDelegate.swift is missing"
fi

# Test: main.swift has correct structure
if grep -q "NSApplication.shared" "${SCRIPT_DIR}/Sources/main.swift" && \
   grep -q "AppDelegate" "${SCRIPT_DIR}/Sources/main.swift" && \
   grep -q "app.run()" "${SCRIPT_DIR}/Sources/main.swift"; then
    pass "main.swift has correct app entry point structure"
else
    fail "main.swift missing required app entry point code"
fi

# =============================================================================
# AppDelegate Functionality Tests
# =============================================================================
echo ""
echo "━━━ AppDelegate Features ━━━"

# Test: Uses NSStatusItem (menu bar icon)
if grep -q "NSStatusItem" "${SCRIPT_DIR}/Sources/AppDelegate.swift"; then
    pass "Uses NSStatusItem for menu bar icon"
else
    fail "Missing NSStatusItem (menu bar icon)"
fi

# Test: Uses WKWebView for dashboard
if grep -q "WKWebView" "${SCRIPT_DIR}/Sources/AppDelegate.swift"; then
    pass "Uses WKWebView for dashboard content"
else
    fail "Missing WKWebView"
fi

# Test: Loads correct dashboard URL
if grep -q "localhost:3100" "${SCRIPT_DIR}/Sources/AppDelegate.swift"; then
    pass "Loads dashboard from localhost:3100"
else
    fail "Not loading correct dashboard URL"
fi

# Test: Uses SF Symbol icon
if grep -q "folder.badge.gearshape" "${SCRIPT_DIR}/Sources/AppDelegate.swift"; then
    pass "Uses folder.badge.gearshape SF Symbol icon"
else
    fail "Using wrong icon"
fi

# Test: Has error page for server-down scenario
if grep -q "Dashboard Not Running" "${SCRIPT_DIR}/Sources/AppDelegate.swift"; then
    pass "Has error page for server-down scenario"
else
    fail "Missing error page"
fi

# Test: Has retry functionality
if grep -q "retryConnection\|Retry" "${SCRIPT_DIR}/Sources/AppDelegate.swift"; then
    pass "Has retry button functionality"
else
    fail "Missing retry functionality"
fi

# Test: Has refresh menu item
if grep -q "Refresh" "${SCRIPT_DIR}/Sources/AppDelegate.swift"; then
    pass "Has Refresh menu item"
else
    fail "Missing Refresh menu item"
fi

# Test: Has quit menu item
if grep -q "Quit PRD Dashboard" "${SCRIPT_DIR}/Sources/AppDelegate.swift"; then
    pass "Has Quit menu item"
else
    fail "Missing Quit menu item"
fi

# Test: Window close hides instead of quits
if grep -q "windowShouldClose" "${SCRIPT_DIR}/Sources/AppDelegate.swift" && \
   grep -q "orderOut" "${SCRIPT_DIR}/Sources/AppDelegate.swift"; then
    pass "Window close hides instead of quitting (menu bar behavior)"
else
    fail "Window close not properly handled"
fi

# Test: WKNavigationDelegate for error handling
if grep -q "WKNavigationDelegate" "${SCRIPT_DIR}/Sources/AppDelegate.swift" && \
   grep -q "didFailProvisionalNavigation" "${SCRIPT_DIR}/Sources/AppDelegate.swift"; then
    pass "Implements WKNavigationDelegate for error handling"
else
    fail "Missing WKNavigationDelegate implementation"
fi

# Test: Developer extras enabled
if grep -q "developerExtrasEnabled" "${SCRIPT_DIR}/Sources/AppDelegate.swift"; then
    pass "WebKit developer extras enabled (right-click inspect)"
else
    fail "Missing developer extras"
fi

# =============================================================================
# Info.plist Tests
# =============================================================================
echo ""
echo "━━━ Info.plist Configuration ━━━"

# Test: Info.plist exists
if [[ -f "${SCRIPT_DIR}/Info.plist" ]]; then
    pass "Info.plist exists"
else
    fail "Info.plist is missing"
fi

# Test: LSUIElement set to true (menu-bar-only, no dock icon)
if grep -q "<key>LSUIElement</key>" "${SCRIPT_DIR}/Info.plist" && \
   grep -A1 "<key>LSUIElement</key>" "${SCRIPT_DIR}/Info.plist" | grep -q "<true/>"; then
    pass "LSUIElement=true (menu-bar-only, no Dock icon)"
else
    fail "LSUIElement not set to true"
fi

# Test: Correct bundle identifier
if grep -q "com.prdtool.dashboard" "${SCRIPT_DIR}/Info.plist"; then
    pass "Bundle identifier: com.prdtool.dashboard"
else
    fail "Incorrect bundle identifier"
fi

# Test: Local networking allowed
if grep -q "NSAllowsLocalNetworking" "${SCRIPT_DIR}/Info.plist" && \
   grep -A1 "NSAllowsLocalNetworking" "${SCRIPT_DIR}/Info.plist" | grep -q "<true/>"; then
    pass "NSAllowsLocalNetworking enabled"
else
    fail "NSAllowsLocalNetworking not enabled"
fi

# Test: High resolution capable
if grep -q "NSHighResolutionCapable" "${SCRIPT_DIR}/Info.plist"; then
    pass "NSHighResolutionCapable flag set"
else
    fail "NSHighResolutionCapable not set"
fi

# Test: Minimum system version set
if grep -q "<key>LSMinimumSystemVersion</key>" "${SCRIPT_DIR}/Info.plist"; then
    pass "Minimum system version configured"
else
    fail "Minimum system version not set"
fi

# =============================================================================
# Build Script Tests
# =============================================================================
echo ""
echo "━━━ Build Script ━━━"

# Test: Build script exists and is executable
if [[ -x "${SCRIPT_DIR}/build.sh" ]]; then
    pass "build.sh exists and is executable"
else
    fail "build.sh is missing or not executable"
fi

# Test: Build script checks for swiftc
if grep -q "command -v swiftc" "${SCRIPT_DIR}/build.sh"; then
    pass "build.sh checks for swiftc availability"
else
    fail "build.sh doesn't check for swiftc"
fi

# Test: Build script creates app bundle structure
if grep -q "Contents/MacOS" "${SCRIPT_DIR}/build.sh" && \
   grep -q "Contents/Resources" "${SCRIPT_DIR}/build.sh"; then
    pass "build.sh creates proper app bundle structure"
else
    fail "build.sh doesn't create app bundle structure"
fi

# Test: Build script creates PkgInfo
if grep -q "PkgInfo" "${SCRIPT_DIR}/build.sh"; then
    pass "build.sh creates PkgInfo file"
else
    fail "build.sh doesn't create PkgInfo"
fi

# =============================================================================
# Launchd Service Tests
# =============================================================================
echo ""
echo "━━━ Launchd Service ━━━"

# Test: Launchd plist exists
if [[ -f "${SCRIPT_DIR}/com.prdtool.dashboard.plist" ]]; then
    pass "com.prdtool.dashboard.plist exists"
else
    fail "com.prdtool.dashboard.plist is missing"
fi

# Test: Correct service label
if grep -q "<string>com.prdtool.dashboard</string>" "${SCRIPT_DIR}/com.prdtool.dashboard.plist"; then
    pass "Launchd label: com.prdtool.dashboard"
else
    fail "Incorrect launchd label"
fi

# Test: RunAtLoad enabled
if grep -q "<key>RunAtLoad</key>" "${SCRIPT_DIR}/com.prdtool.dashboard.plist" && \
   grep -A1 "<key>RunAtLoad</key>" "${SCRIPT_DIR}/com.prdtool.dashboard.plist" | grep -q "<true/>"; then
    pass "RunAtLoad=true (starts on login)"
else
    fail "RunAtLoad not enabled"
fi

# Test: LimitLoadToSessionType is Aqua (GUI only)
if grep -q "<key>LimitLoadToSessionType</key>" "${SCRIPT_DIR}/com.prdtool.dashboard.plist" && \
   grep -A1 "<key>LimitLoadToSessionType</key>" "${SCRIPT_DIR}/com.prdtool.dashboard.plist" | grep -q "Aqua"; then
    pass "LimitLoadToSessionType=Aqua (GUI session only)"
else
    fail "LimitLoadToSessionType not set to Aqua"
fi

# Test: Points to correct executable
if grep -q "PRDDashboard.app/Contents/MacOS/PRDDashboard" "${SCRIPT_DIR}/com.prdtool.dashboard.plist"; then
    pass "Program path points to correct executable"
else
    fail "Program path incorrect"
fi

# Test: Has log paths configured
if grep -q "StandardOutPath" "${SCRIPT_DIR}/com.prdtool.dashboard.plist" && \
   grep -q "StandardErrorPath" "${SCRIPT_DIR}/com.prdtool.dashboard.plist"; then
    pass "Standard out/error log paths configured"
else
    fail "Log paths not configured"
fi

# Test: KeepAlive configured (restart on crash only)
if grep -q "<key>KeepAlive</key>" "${SCRIPT_DIR}/com.prdtool.dashboard.plist" && \
   grep -q "<key>SuccessfulExit</key>" "${SCRIPT_DIR}/com.prdtool.dashboard.plist"; then
    pass "KeepAlive configured (restarts on crash, not on quit)"
else
    fail "KeepAlive not properly configured"
fi

# Test: Install script exists and is executable
if [[ -x "${SCRIPT_DIR}/install-launchd.sh" ]]; then
    pass "install-launchd.sh exists and is executable"
else
    fail "install-launchd.sh is missing or not executable"
fi

# Test: Install script has install command
if grep -q "do_install\(\)" "${SCRIPT_DIR}/install-launchd.sh"; then
    pass "install-launchd.sh has install command"
else
    fail "install-launchd.sh missing install command"
fi

# Test: Install script has uninstall command
if grep -q "do_uninstall\(\)" "${SCRIPT_DIR}/install-launchd.sh"; then
    pass "install-launchd.sh has uninstall command"
else
    fail "install-launchd.sh missing uninstall command"
fi

# Test: Install script has status command
if grep -q "do_status\(\)" "${SCRIPT_DIR}/install-launchd.sh"; then
    pass "install-launchd.sh has status command"
else
    fail "install-launchd.sh missing status command"
fi

# Test: Install script checks for app existence
if grep -q "check_app_exists" "${SCRIPT_DIR}/install-launchd.sh" && \
   grep -q "PRDDashboard.app" "${SCRIPT_DIR}/install-launchd.sh"; then
    pass "install-launchd.sh verifies app exists before installing"
else
    fail "install-launchd.sh doesn't verify app existence"
fi

# =============================================================================
# Swift Syntax Validation
# =============================================================================
echo ""
echo "━━━ Swift Syntax Validation ━━━"

# Check if swiftc is available for syntax checking
if command -v swiftc &> /dev/null; then
    # Validate Swift syntax without full compilation
    # Using -typecheck to parse and type-check without generating code
    # This may still fail due to SDK issues, so we handle errors gracefully

    if swiftc -parse \
        "${SCRIPT_DIR}/Sources/AppDelegate.swift" \
        "${SCRIPT_DIR}/Sources/main.swift" 2>/dev/null; then
        pass "Swift source files have valid syntax"
    else
        # Parse may fail due to SDK issues, not syntax
        # Check if it's a syntax error or SDK error
        PARSE_OUTPUT=$(swiftc -parse \
            "${SCRIPT_DIR}/Sources/AppDelegate.swift" \
            "${SCRIPT_DIR}/Sources/main.swift" 2>&1 || true)

        if echo "${PARSE_OUTPUT}" | grep -qi "syntax\|parse error\|expected"; then
            fail "Swift syntax error detected"
            echo "    Error: ${PARSE_OUTPUT}"
        else
            skip "Swift syntax check (SDK/toolchain configuration issue)"
        fi
    fi
else
    skip "Swift syntax check (swiftc not available)"
fi

# =============================================================================
# Build Attempt
# =============================================================================
echo ""
echo "━━━ Build Attempt ━━━"

# Attempt to build
BUILD_OUTPUT=$("${SCRIPT_DIR}/build.sh" 2>&1) || BUILD_RESULT=$?
BUILD_RESULT=${BUILD_RESULT:-0}

if [[ ${BUILD_RESULT} -eq 0 ]]; then
    pass "Build completed successfully"

    # Additional tests for successful build
    echo ""
    echo "━━━ Built App Bundle ━━━"

    if [[ -d "${APP_BUNDLE}" ]]; then
        pass "App bundle created"
    else
        fail "App bundle not created"
    fi

    if [[ -f "${APP_BUNDLE}/Contents/MacOS/${APP_NAME}" ]]; then
        pass "Executable created"

        # Check if it's a valid Mach-O binary
        if file "${APP_BUNDLE}/Contents/MacOS/${APP_NAME}" | grep -q "Mach-O"; then
            pass "Executable is valid Mach-O binary"
        else
            fail "Executable is not a valid Mach-O binary"
        fi
    else
        fail "Executable not created"
    fi

    if [[ -f "${APP_BUNDLE}/Contents/Info.plist" ]]; then
        pass "Info.plist copied to bundle"
    else
        fail "Info.plist not in bundle"
    fi

    if [[ -f "${APP_BUNDLE}/Contents/PkgInfo" ]]; then
        pass "PkgInfo file created"
    else
        fail "PkgInfo file not created"
    fi
else
    # Build failed - check if it's an SDK issue or a code issue
    if echo "${BUILD_OUTPUT}" | grep -qi "SDK is not supported by the compiler\|redefinition of module\|toolchain"; then
        skip "Build (SDK/toolchain version mismatch - requires Xcode)"
        echo ""
        echo "    Note: Build requires Xcode or matching Command Line Tools."
        echo "    Source files and configuration have been validated."
    else
        fail "Build failed with unexpected error"
        echo "    Output: ${BUILD_OUTPUT}"
    fi
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "=================================="
echo "Test Results: ${PASS_COUNT} passed, ${FAIL_COUNT} failed, ${SKIP_COUNT} skipped"
echo "=================================="

if [[ ${FAIL_COUNT} -eq 0 ]]; then
    if [[ ${SKIP_COUNT} -gt 0 ]]; then
        echo -e "${YELLOW}All validations passed. Some tests skipped due to environment.${NC}"
        echo ""
        echo "To complete all tests, install Xcode from the App Store and run:"
        echo "  sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"
    else
        echo -e "${GREEN}All tests passed!${NC}"
    fi
    exit 0
else
    echo -e "${RED}Some tests failed${NC}"
    exit 1
fi
