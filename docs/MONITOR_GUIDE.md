# Document Monitor - Automatic PDF Detection & Processing

## Overview

The Document Monitor automatically watches specified directories for new PDF files, processes them on detection, and sends macOS notifications with reports.

## Features

✅ **Runs on Mac Login** - Automatically starts when you log in
✅ **Internet-Aware** - Only runs when connected to internet
✅ **Smart Notifications** - Shows "No new files" or details about processed files
✅ **Automatic Processing** - Detects bin, categorizes, and stores in database
✅ **Report Generation** - Creates detailed reports saved to Documents folder
✅ **State Tracking** - Remembers which files have been seen
✅ **Multiple Directory Support** - Monitors iCloud, Downloads, Documents, etc.

## Installation

### Quick Install
```bash
cd /Users/michaelvalderrama/Websites/TheConversation
./install_monitor.sh
```

The installer will:
1. Ask for your Groq API key (if not already set)
2. Create LaunchAgent configuration
3. Set up automatic startup
4. Send a test notification

### Manual Installation

1. **Edit the plist file** with your paths:
```bash
nano com.user.document-monitor.plist
```

2. **Set your Groq API key** in the plist:
```xml
<key>GROQ_API_KEY</key>
<string>YOUR_ACTUAL_KEY_HERE</string>
```

3. **Copy to LaunchAgents**:
```bash
cp com.user.document-monitor.plist ~/Library/LaunchAgents/
```

4. **Load the agent**:
```bash
launchctl load ~/Library/LaunchAgents/com.user.document-monitor.plist
```

## Usage

### Test the Monitor
```bash
# Test notifications
python document_monitor.py --test

# Run once manually
python document_monitor.py --once

# Run as daemon (continuous)
python document_monitor.py --daemon
```

### Monitor Specific Paths
```bash
python document_monitor.py --once --paths ~/Downloads ~/Documents/Scans
```

### Custom Check Interval
```bash
# Check every 10 minutes (600 seconds)
python document_monitor.py --daemon --interval 600
```

## How It Works

1. **On Login / Every 5 Minutes**:
   - Checks if connected to internet
   - Checks if Supabase is running
   - Scans watched directories for PDFs

2. **When New PDFs Found**:
   - Sends notification: "📄 Found X new PDF files. Processing..."
   - Processes each file (extracts, categorizes, detects bin)
   - Generates detailed report
   - Saves report to ~/Documents/pdf_report_YYYYMMDD_HHMMSS.txt
   - Sends final notification with results

3. **When No New Files**:
   - Sends quick notification: "✅ No new PDF files"
   - Silent mode (no sound)

## Notifications

### No New Files
```
Document Monitor
✅ No new PDF files
```

### New Files Found
```
Document Monitor
📄 Found 3 new PDF files. Processing...
```

### Processing Complete
```
Document Monitor
✅ Processed 3 new documents.
Report saved to Documents folder.
```

### Error Notification
```
Document Monitor
⚠️ Database not running.
Start Supabase with: supabase start
```

## Reports

Reports are saved to `~/Documents/pdf_report_YYYYMMDD_HHMMSS.txt`

Example report:
```
📊 NEW PDF FILES REPORT
==================================================

Total New Files: 3
✅ Processed: 3
⏭️  Skipped: 0
❌ Failed: 0

Files by Bin:

📂 Personal Bin: 2 documents
   • Tesla_Registration_2024.pdf (vehicle_registration)
   • Health_Insurance_Card.pdf (medical_insurance)

📂 Work Bin: 1 documents
   • Project_Contract.pdf (contract)
```

## Monitored Directories (Default)

- `~/Library/Mobile Documents/com~apple~CloudDocs` (iCloud Drive)
- `~/Downloads`
- `~/Documents`

To change, edit the plist file or use `--paths` argument.

## Log Files

- **Monitor Log**: `~/.document_monitor.log` - Detailed activity log
- **State File**: `~/.document_monitor_state.json` - Tracks processed files
- **System Stdout**: `~/.document_monitor_stdout.log` - System output
- **System Stderr**: `~/.document_monitor_stderr.log` - Error output

## Management Commands

### Check Status
```bash
launchctl list | grep document-monitor
```

### View Recent Logs
```bash
tail -f ~/.document_monitor.log
```

### Stop Monitor
```bash
launchctl unload ~/Library/LaunchAgents/com.user.document-monitor.plist
```

### Start Monitor
```bash
launchctl load ~/Library/LaunchAgents/com.user.document-monitor.plist
```

### Restart Monitor
```bash
launchctl unload ~/Library/LaunchAgents/com.user.document-monitor.plist
launchctl load ~/Library/LaunchAgents/com.user.document-monitor.plist
```

## Uninstallation

```bash
./uninstall_monitor.sh
```

Or manually:
```bash
launchctl unload ~/Library/LaunchAgents/com.user.document-monitor.plist
rm ~/Library/LaunchAgents/com.user.document-monitor.plist
```

## Customization

### Change Check Interval

Edit `com.user.document-monitor.plist`:
```xml
<key>StartInterval</key>
<integer>600</integer>  <!-- 600 = 10 minutes -->
```

### Add More Watched Paths

Edit the plist and add to `ProgramArguments`:
```xml
<key>ProgramArguments</key>
<array>
    <string>/path/to/python3</string>
    <string>/path/to/document_monitor.py</string>
    <string>--once</string>
    <string>--paths</string>
    <string>/path/to/watch1</string>
    <string>/path/to/watch2</string>
</array>
```

### Disable Notifications

Edit `document_monitor.py` and modify `send_notification()` calls.

## Troubleshooting

### Notifications Not Working
```bash
# Test notifications
python document_monitor.py --test

# Check System Preferences > Notifications
# Make sure Python/Terminal has notification permission
```

### Monitor Not Running
```bash
# Check if loaded
launchctl list | grep document-monitor

# Check logs
tail ~/.document_monitor_stderr.log

# Try manual run
python document_monitor.py --once
```

### Supabase Not Detected
```bash
# Make sure Supabase is running
supabase status

# Start if needed
supabase start
```

### Files Not Being Processed
```bash
# Check state file
cat ~/.document_monitor_state.json

# Reset state (will reprocess all files)
rm ~/.document_monitor_state.json

# Run manually to see errors
python document_monitor.py --once
```

### Internet Check Fails
The monitor checks for internet connectivity before running. If you're on a restricted network, you may need to modify the `check_internet_connection()` method in `document_monitor.py`.

## Performance Notes

- **Check Interval**: Default 5 minutes (300 seconds)
- **Processing Speed**: ~2-5 seconds per PDF
- **Resource Usage**: Minimal when idle, moderate during processing
- **Network**: Only requires connection for AI processing (Groq API)

## Security & Privacy

- ✅ All processing is local (except AI categorization via Groq)
- ✅ No data is uploaded except to your local Supabase database
- ✅ State and logs are stored in your home directory
- ✅ File paths are tracked but contents are not logged

## Integration with Document Management System

The monitor uses the same processing pipeline as the main system:
- Same categorization logic
- Same bin detection
- Same database schema
- Fully searchable via `search_engine.py`

## Advanced Usage

### Run Only During Business Hours

Edit plist and add:
```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>9</integer>
    <key>Minute</key>
    <integer>0</integer>
</dict>
<!-- Add more dict entries for other times -->
```

### Email Reports Instead of Notifications

Modify `document_monitor.py` to send email via `smtplib` instead of macOS notifications.

### Webhook Integration

Add webhook call in `run_check()` to notify external services.

---

## Summary

The Document Monitor provides **set-it-and-forget-it** automatic PDF management:

1. ✅ **Install once** with `./install_monitor.sh`
2. ✅ **Runs automatically** on login and every 5 minutes
3. ✅ **Smart notifications** - no noise when no files
4. ✅ **Detailed reports** saved to Documents
5. ✅ **Fully integrated** with your document management system

**Never manually import PDFs again!** 🎉
