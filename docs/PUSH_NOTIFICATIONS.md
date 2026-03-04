# 🔔 Push Notifications Setup Guide

## ✅ IMPLEMENTED - Multi-Channel Notifications!

Your document system can now send push notifications to:
- 📱 **Your iPhone/Android** (via Pushover or ntfy.sh)
- 💬 **Telegram**
- 📧 **Email** (for high-priority alerts)
- 🖥️ **macOS native notifications** (always enabled)

---

## 🎯 **What Gets Notified**

| **Event** | **Priority** | **Example** |
|-----------|--------------|-------------|
| 📥 New files in inbox | Normal | "📥 3 new PDFs in inbox" |
| ✅ Processing complete | Low | "✅ Processed 3 files → Staged" |
| ⚠️ Processing error | **High** | "⚠️ Failed: Invoice.pdf" |
| 📦 Files staged & ready | Normal | "📦 5 files staged, ready to finalize" |
| ✨ Finalization complete | Low | "✨ 5 files moved to permanent location" |
| 🔄 Duplicate detected | Normal | "🔄 Duplicate: Invoice.pdf (deleted)" |

---

## 🚀 **Quick Setup Options**

### **Option 1: Pushover** (Recommended - Simple & Reliable)
- **Cost**: $5 one-time purchase
- **Platforms**: iOS, Android, Desktop
- **Setup**: 2 minutes

### **Option 2: ntfy.sh** (Free & Easy)
- **Cost**: Free, no account needed
- **Platforms**: iOS, Android, Web
- **Setup**: 30 seconds

### **Option 3: Telegram** (Free)
- **Cost**: Free
- **Platforms**: iOS, Android, Desktop, Web
- **Setup**: 5 minutes (need to create bot)

### **Option 4: macOS Only** (Already Working)
- **Cost**: Free
- **Platforms**: macOS only
- **Setup**: None needed!

---

## 📱 **Setup Instructions**

### **1. Pushover Setup** (Recommended)

#### **Step 1: Purchase Pushover**
- Go to: https://pushover.net
- Buy for $5 (one-time, per platform)
- Install app on your phone

#### **Step 2: Get API Credentials**
```bash
1. Log in to pushover.net
2. Create an application:
   - Name: "Document System"
   - Type: "Application"
3. Copy your:
   - User Key (starts with "u...")
   - API Token (starts with "a...")
```

#### **Step 3: Add to Environment**
```bash
# Add to ~/.zshrc or ~/.bash_profile
export PUSHOVER_TOKEN="your_api_token_here"
export PUSHOVER_USER="your_user_key_here"

# Reload
source ~/.zshrc
```

#### **Step 4: Test**
```bash
python3 notification_service.py --test \
  --title "Test from Document System" \
  --message "Pushover is working! 🎉"
```

You should get a push on your phone! 📱

---

### **2. ntfy.sh Setup** (Easiest - No Account!)

#### **Step 1: Pick a Topic Name**
```bash
# Your unique topic (make it hard to guess)
# Example: documents_michaelv_x29j4k
```

#### **Step 2: Add to Environment**
```bash
# Add to ~/.zshrc or ~/.bash_profile
export NTFY_TOPIC="documents_michaelv_x29j4k"

# Optional: Use custom server
# export NTFY_SERVER="https://ntfy.sh"

# Reload
source ~/.zshrc
```

#### **Step 3: Subscribe on Your Phone**
```bash
1. Install ntfy app (iOS/Android)
2. Subscribe to topic: "documents_michaelv_x29j4k"
3. Done! 🎉
```

#### **Step 4: Test**
```bash
python3 notification_service.py --test \
  --title "Test from Document System" \
  --message "ntfy.sh is working! 🎉"
```

---

### **3. Telegram Setup**

#### **Step 1: Create Bot**
```bash
1. Open Telegram
2. Search for: @BotFather
3. Send: /newbot
4. Choose a name: "My Document System"
5. Choose username: "mydocs_bot"
6. Copy the API token (looks like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)
```

#### **Step 2: Get Your Chat ID**
```bash
1. Send a message to your bot
2. Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
3. Find "chat":{"id": 123456789}
4. Copy that ID
```

#### **Step 3: Add to Environment**
```bash
# Add to ~/.zshrc or ~/.bash_profile
export TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
export TELEGRAM_CHAT_ID="123456789"

# Reload
source ~/.zshrc
```

#### **Step 4: Test**
```bash
python3 notification_service.py --test \
  --title "Test from Document System" \
  --message "Telegram is working! 🎉"
```

---

### **4. Email Setup** (Optional - For Critical Alerts Only)

```bash
# Add to ~/.zshrc or ~/.bash_profile
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
export EMAIL_TO="your-email@gmail.com"

# Reload
source ~/.zshrc
```

**Note**: For Gmail, create an "App Password" in your Google Account settings.

---

## 🎮 **Testing Your Setup**

### **Check What's Enabled**
```bash
python3 notification_service.py --status
```

Output:
```
🔔 Notification Service Status

Enabled services: macOS, Pushover, ntfy.sh

Channel Status:
  macOS:    ✅ Enabled
  Pushover: ✅ Enabled
  Telegram: ❌ Disabled (set TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
  ntfy.sh:  ✅ Enabled
  Email:    ❌ Disabled (set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, EMAIL_TO)
```

### **Send Test Notification**
```bash
# Test default priority
python3 notification_service.py --test

# Test high priority
python3 notification_service.py --test \
  --priority high \
  --title "⚠️ Urgent Test" \
  --message "This is a high-priority notification"
```

---

## 🎯 **Real Usage Examples**

### **Example 1: New Files Detected**
```
📱 Push Notification:
   Title: "📥 3 New PDFs"
   Message: "Found 3 new PDF files in inbox"
   Priority: Normal
   Sound: Ping
```

### **Example 2: Processing Complete**
```
📱 Push Notification:
   Title: "✅ Processing Complete"
   Message: "Successfully processed 3 files → staging area"
   Priority: Low
   Sound: Glass
```

### **Example 3: Processing Error** (HIGH Priority)
```
📱 Push Notification:
   Title: "⚠️ Processing Error"
   Message: "Failed to process: Invoice.pdf
            Error: Could not extract text"
   Priority: HIGH
   Sound: Basso
   📧 Also sent via Email (if configured)
```

### **Example 4: Files Ready to Finalize**
```
📱 Push Notification:
   Title: "📦 5 Files Staged"
   Message: "5 processed files in staging, ready to finalize"
   Priority: Normal
   Sound: Pop
```

---

## ⚙️ **Notification Workflow**

```
1. Drop PDFs in inbox
   ↓
2. Processing starts
   ↓ 📱 "📥 3 new PDFs in inbox"
   
3. Processing each file
   ↓ (if error) 📱 "⚠️ Failed: Invoice.pdf"
   
4. Processing complete
   ↓ 📱 "✅ Processed 3 files → Staged"
   ↓ 📱 "📦 3 files staged, ready to finalize"
   
5. Manual review of staged files
   
6. Finalize
   ↓ 📱 "✨ 3 files moved to permanent location"
```

---

## 🔧 **Customization**

### **Disable Notifications for Specific Events**

Edit `inbox_processor.py` and comment out:

```python
# Don't notify about new files
# notify_new_files(len(pdf_files), "In-Box")

# Don't notify about completion
# notify_processing_complete(stats['processed'], staged=self.use_staging)
```

### **Change Notification Sounds**

Edit `notification_service.py`:

```python
def notify_new_files(count: int, location: str = "inbox"):
    # Change sound here
    return notifier.send(title, message, NotificationPriority.NORMAL, sound="Submarine")
```

Available macOS sounds:
- Basso, Blow, Bottle, Frog, Funk, Glass, Hero, Morse, Ping, Pop, Purr, Sosumi, Submarine, Tink

### **Add Custom Notification**

```python
from notification_service import NotificationService, NotificationPriority

notifier = NotificationService()
notifier.send(
    title="Custom Alert",
    message="Something interesting happened!",
    priority=NotificationPriority.HIGH,
    sound="Hero"
)
```

---

## 📊 **Priority Levels**

| **Priority** | **When to Use** | **Email Sent?** |
|--------------|-----------------|-----------------|
| **Low** | Completion, success | No |
| **Normal** | New files, duplicates | No |
| **High** | Errors, warnings | Yes |
| **Urgent** | Critical failures | Yes |

---

## 🎨 **Recommended Setup**

### **For Mobile Access:**
```bash
✅ Pushover ($5) - Best user experience
   OR
✅ ntfy.sh (Free) - No account needed

✅ macOS native - Always works
✅ Email - For critical alerts only
```

### **My Personal Setup:**
```bash
export PUSHOVER_TOKEN="..."      # For iPhone
export PUSHOVER_USER="..."       
export NTFY_TOPIC="..."          # Backup channel
export EMAIL_TO="..."            # Critical only
```

---

## 🐛 **Troubleshooting**

### **"macOS notification failed"**
```bash
# Check notification permissions
System Settings → Notifications → Terminal → Allow Notifications
```

### **"Pushover notification failed"**
```bash
# Verify credentials
echo $PUSHOVER_TOKEN
echo $PUSHOVER_USER

# Test directly
curl -s \
  --form-string "token=$PUSHOVER_TOKEN" \
  --form-string "user=$PUSHOVER_USER" \
  --form-string "message=Test" \
  https://api.pushover.net/1/messages.json
```

### **"ntfy.sh notification failed"**
```bash
# Verify topic
echo $NTFY_TOPIC

# Test directly
curl -d "Test message" ntfy.sh/$NTFY_TOPIC
```

### **"Telegram notification failed"**
```bash
# Verify bot token and chat ID
echo $TELEGRAM_BOT_TOKEN
echo $TELEGRAM_CHAT_ID

# Test directly
curl -X POST \
  "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -d "chat_id=$TELEGRAM_CHAT_ID&text=Test"
```

---

## 🎯 **Quick Start**

### **1. Choose Your Method** (Pick ONE)

**Easiest**: ntfy.sh (30 seconds)
```bash
export NTFY_TOPIC="documents_$(whoami)_$(date +%s)"
python3 notification_service.py --test
# Install ntfy app, subscribe to your topic
```

**Best**: Pushover ($5, 2 minutes)
```bash
# Follow "Pushover Setup" section above
```

### **2. Test It**
```bash
python3 notification_service.py --status
python3 notification_service.py --test
```

### **3. Process Some Files**
```bash
# Drop PDFs in inbox, then:
python3 inbox_processor.py --process

# You'll get notifications at each step! 📱
```

---

## ✅ **Summary**

You now have **push notifications** for:
- ✅ New files detected
- ✅ Processing complete
- ✅ Errors (high priority)
- ✅ Files staged and ready
- ✅ Finalization complete
- ✅ Duplicate detection

**Never miss a document event again!** 🚀📱
