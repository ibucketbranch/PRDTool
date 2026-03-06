import Cocoa
import WebKit

class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate {

    // MARK: - Properties

    private var statusItem: NSStatusItem!
    private var window: NSWindow!
    private var webView: WKWebView!
    private var errorView: NSView!
    private var retryButton: NSButton!

    private let dashboardURL = URL(string: "http://localhost:3100")!
    private let windowWidth: CGFloat = 1280
    private let windowHeight: CGFloat = 820

    // MARK: - Application Lifecycle

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupStatusItem()
        setupWindow()
        setupWebView()
        setupErrorView()
        loadDashboard()
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag {
            showWindow()
        }
        return true
    }

    // MARK: - Status Item Setup

    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)

        if let button = statusItem.button {
            // Use SF Symbol for menu bar icon
            if let image = NSImage(systemSymbolName: "folder.badge.gearshape", accessibilityDescription: "PRD Dashboard") {
                image.isTemplate = true
                button.image = image
            } else {
                // Fallback to text if SF Symbol unavailable
                button.title = "PRD"
            }
            button.action = #selector(statusItemClicked)
            button.target = self
            button.sendAction(on: [.leftMouseUp, .rightMouseUp])
        }
    }

    @objc private func statusItemClicked(_ sender: NSStatusBarButton) {
        let event = NSApp.currentEvent!

        if event.type == .rightMouseUp {
            showContextMenu()
        } else {
            toggleWindow()
        }
    }

    private func showContextMenu() {
        let menu = NSMenu()

        menu.addItem(NSMenuItem(title: "Open Dashboard", action: #selector(showWindow), keyEquivalent: "o"))
        menu.addItem(NSMenuItem(title: "Refresh", action: #selector(refreshDashboard), keyEquivalent: "r"))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Quit PRD Dashboard", action: #selector(quitApp), keyEquivalent: "q"))

        statusItem.menu = menu
        statusItem.button?.performClick(nil)
        statusItem.menu = nil // Reset to allow left-click toggle
    }

    // MARK: - Window Setup

    private func setupWindow() {
        let contentRect = NSRect(x: 0, y: 0, width: windowWidth, height: windowHeight)

        window = NSWindow(
            contentRect: contentRect,
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )

        window.title = "PRD Dashboard"
        window.center()
        window.setFrameAutosaveName("PRDDashboardWindow")
        window.isReleasedWhenClosed = false
        window.minSize = NSSize(width: 800, height: 600)

        // Override close button to hide instead of quit
        window.delegate = self
    }

    // MARK: - WebView Setup

    private func setupWebView() {
        let configuration = WKWebViewConfiguration()

        // Enable developer tools for right-click inspect
        configuration.preferences.setValue(true, forKey: "developerExtrasEnabled")

        webView = WKWebView(frame: window.contentView!.bounds, configuration: configuration)
        webView.autoresizingMask = [.width, .height]
        webView.navigationDelegate = self

        // Allow local network access
        webView.configuration.preferences.setValue(true, forKey: "allowFileAccessFromFileURLs")

        window.contentView?.addSubview(webView)
    }

    // MARK: - Error View Setup

    private func setupErrorView() {
        errorView = NSView(frame: window.contentView!.bounds)
        errorView.autoresizingMask = [.width, .height]
        errorView.isHidden = true

        // Background color
        errorView.wantsLayer = true
        errorView.layer?.backgroundColor = NSColor(white: 0.12, alpha: 1.0).cgColor

        // Container stack
        let stackView = NSStackView()
        stackView.orientation = .vertical
        stackView.alignment = .centerX
        stackView.spacing = 16
        stackView.translatesAutoresizingMaskIntoConstraints = false

        // Icon
        let iconLabel = NSTextField(labelWithString: "⚠️")
        iconLabel.font = NSFont.systemFont(ofSize: 48)
        iconLabel.alignment = .center

        // Title
        let titleLabel = NSTextField(labelWithString: "Dashboard Not Running")
        titleLabel.font = NSFont.boldSystemFont(ofSize: 24)
        titleLabel.textColor = .white
        titleLabel.alignment = .center
        titleLabel.isBordered = false
        titleLabel.isEditable = false
        titleLabel.drawsBackground = false

        // Message
        let messageLabel = NSTextField(labelWithString: "The dashboard server is not running at localhost:3100.\nStart the server with: cd dashboard && npm run dev")
        messageLabel.font = NSFont.systemFont(ofSize: 14)
        messageLabel.textColor = NSColor(white: 0.7, alpha: 1.0)
        messageLabel.alignment = .center
        messageLabel.isBordered = false
        messageLabel.isEditable = false
        messageLabel.drawsBackground = false
        messageLabel.maximumNumberOfLines = 3

        // Retry button
        retryButton = NSButton(title: "Retry", target: self, action: #selector(retryConnection))
        retryButton.bezelStyle = .rounded
        retryButton.controlSize = .large

        stackView.addArrangedSubview(iconLabel)
        stackView.addArrangedSubview(titleLabel)
        stackView.addArrangedSubview(messageLabel)
        stackView.addArrangedSubview(retryButton)

        errorView.addSubview(stackView)

        // Center the stack view
        NSLayoutConstraint.activate([
            stackView.centerXAnchor.constraint(equalTo: errorView.centerXAnchor),
            stackView.centerYAnchor.constraint(equalTo: errorView.centerYAnchor),
            stackView.widthAnchor.constraint(lessThanOrEqualTo: errorView.widthAnchor, multiplier: 0.8)
        ])

        window.contentView?.addSubview(errorView)
    }

    // MARK: - Dashboard Loading

    private func loadDashboard() {
        let request = URLRequest(url: dashboardURL)
        webView.load(request)
    }

    @objc private func retryConnection() {
        hideError()
        loadDashboard()
    }

    private func showError() {
        webView.isHidden = true
        errorView.isHidden = false
    }

    private func hideError() {
        webView.isHidden = false
        errorView.isHidden = true
    }

    // MARK: - Window Actions

    private func toggleWindow() {
        if window.isVisible {
            window.orderOut(nil)
        } else {
            showWindow()
        }
    }

    @objc private func showWindow() {
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc private func refreshDashboard() {
        hideError()
        webView.reload()
    }

    @objc private func quitApp() {
        NSApp.terminate(nil)
    }

    // MARK: - WKNavigationDelegate

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        // Connection failed - show error view
        showError()
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        // Navigation failed - show error view
        showError()
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        // Successfully loaded - ensure error view is hidden
        hideError()
    }
}

// MARK: - NSWindowDelegate

extension AppDelegate: NSWindowDelegate {
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        // Hide window instead of closing (standard menu bar app behavior)
        window.orderOut(nil)
        return false
    }
}
