import Cocoa

// PRD Dashboard Menu Bar App
// A lightweight native macOS wrapper for the Next.js dashboard

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate

// Run the application
app.run()
