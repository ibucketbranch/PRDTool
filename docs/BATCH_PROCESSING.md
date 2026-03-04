# 📦 Batch Folder Processing Guide

## ✅ IMPLEMENTED - Safe Batch Processing!

Process your existing PDF collection in **controlled batches**, starting with the **oldest-modified folders first**.

---

## 🎯 **What It Does**

1. **Scans recursively** for all PDFs in a folder structure
2. **Sorts folders by age** (oldest-modified first = "backward search")
3. **Processes in batches** (default: 10 files at a time)
4. **Tracks progress** (resume where you left off)
5. **Notifies you** after each batch
6. **Safe by default** (dry-run mode)

---

## 🚀 **Quick Start**

### **Step 1: Preview First Batch** (Dry-run)

```bash
python3 batch_processor.py ~/Documents/Personal --dry-run
```

This shows you:
- How many folders have PDFs
- Total PDFs found
- Oldest/newest folder dates
- Which 10 files would be processed
- No actual processing happens

### **Step 2: Process the Batch**

```bash
python3 batch_processor.py ~/Documents/Personal --process
```

This actually processes the 10 oldest files and saves them to your database.

### **Step 3: Repeat Until Done**

```bash
# Run again for next batch
python3 batch_processor.py ~/Documents/Personal --process

# Keep running until all files processed
```

---

## 📋 **Commands**

### **Preview Next Batch** (Safe, no changes)
```bash
python3 batch_processor.py ~/Documents/Personal --dry-run
```

### **Process Next Batch** (10 files)
```bash
python3 batch_processor.py ~/Documents/Personal --process
```

### **Process Larger Batch** (25 files)
```bash
python3 batch_processor.py ~/Documents/Personal --process --batch-size 25
```

### **Check Progress**
```bash
python3 batch_processor.py ~/Documents/Personal --status
```

Output:
```
📊 PROGRESS STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Started: 2026-01-05T10:30:00
   Last batch: 2026-01-05T10:45:00
   Total processed: 50
   Total errors: 2
   Files tracked: 50
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### **Reset Progress** (Start over)
```bash
python3 batch_processor.py ~/Documents/Personal --reset
```

---

## 🎨 **Example Workflow**

### **Day 1: Process Your Personal Bin**

```bash
# 1. Preview what would be processed
python3 batch_processor.py ~/Library/Mobile\ Documents/com~apple~CloudDocs/Personal\ Bin --dry-run

# Output:
# 🔍 Scanning folder structure: Personal Bin
#    ✅ Found 42 folders with PDFs
#    ✅ Total PDFs: 387
#    📅 Oldest folder: 2019-03-15
#    📅 Newest folder: 2026-01-04
#
# 📊 Progress Status:
#    ✅ Already processed: 0 files
#    📋 Remaining: 387 files
#    🎯 This batch: 10 files

# 2. Looks good! Process first batch
python3 batch_processor.py ~/Library/Mobile\ Documents/com~apple~CloudDocs/Personal\ Bin --process

# 📱 Notification: "Starting batch: 10 files (377 remaining)"
# ... processing ...
# 📱 Notification: "✅ Processed 10 files"
# 📱 Notification: "Batch complete! 377 files remaining"

# 3. Check progress
python3 batch_processor.py ~/Library/Mobile\ Documents/com~apple~CloudDocs/Personal\ Bin --status

# 4. Continue with next batch
python3 batch_processor.py ~/Library/Mobile\ Documents/com~apple~CloudDocs/Personal\ Bin --process

# 5. Keep repeating until done!
```

### **Day 2: Process Your Work Bin**

```bash
# Start on Work Bin
python3 batch_processor.py ~/Library/Mobile\ Documents/com~apple~CloudDocs/Work\ Bin --process
```

---

## 🎯 **Why Oldest Folders First?**

| **Approach** | **Why?** |
|--------------|----------|
| **Oldest folders first** | ✅ Historical documents likely more stable |
| | ✅ Less likely to change while processing |
| | ✅ Archive older stuff first |
| | ✅ Most important docs often older |
| **Newest folders first** | ❌ May still be actively adding files |
| | ❌ Might miss new files |

---

## ⚙️ **Batch Sizes**

| **Batch Size** | **When to Use** |
|----------------|-----------------|
| **5 files** | Testing, first time, very cautious |
| **10 files** | Default, good balance (RECOMMENDED) |
| **25 files** | Confident, faster processing |
| **50 files** | Very confident, bulk processing |

```bash
# Conservative (5 files)
python3 batch_processor.py ~/Documents/Personal --process --batch-size 5

# Default (10 files)
python3 batch_processor.py ~/Documents/Personal --process

# Aggressive (50 files)
python3 batch_processor.py ~/Documents/Personal --process --batch-size 50
```

---

## 📊 **Progress Tracking**

### **How It Works**

Progress is saved in:
```
~/.document_system/batch_progress.json
```

Contains:
- List of processed files
- Total processed count
- Total errors
- Last batch timestamp

### **Resume Processing**

Just run the same command again:
```bash
# First run: processes files 1-10
python3 batch_processor.py ~/Documents/Personal --process

# Second run: processes files 11-20 (automatically resumes)
python3 batch_processor.py ~/Documents/Personal --process

# Third run: processes files 21-30
python3 batch_processor.py ~/Documents/Personal --process
```

The system **remembers what you've already processed!**

---

## 🎨 **Sample Output**

```bash
python3 batch_processor.py ~/Documents/Personal --process
```

```
🔍 Scanning folder structure: /Users/you/Documents/Personal
   This may take a moment...

   ✅ Found 42 folders with PDFs
   ✅ Total PDFs: 387
   📅 Oldest folder: 2019-03-15
   📅 Newest folder: 2026-01-04

📊 Progress Status:
   ✅ Already processed: 0 files
   📋 Remaining: 387 files
   🎯 This batch: 10 files
   ⏭️  After this batch: 377 files remaining

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 BATCH PROCESSING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Files in batch: 10
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[1/10] Processing: Invoice_2019.pdf
   📁 Folder: /Users/you/Documents/Personal/old_docs
   📅 Modified: 2019-03-15 10:23
   ✅ Success

[2/10] Processing: Receipt_Amazon.pdf
   📁 Folder: /Users/you/Documents/Personal/old_docs
   📅 Modified: 2019-03-20 14:55
   ✅ Success

... (8 more files) ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 BATCH SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Processed: 10
   ❌ Errors: 0
   📋 Remaining: 377
   📈 Total processed (all time): 10
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 Notification: "✅ Processed 10 files"
📱 Notification: "Batch complete! 377 files remaining. Run again to continue."
```

---

## 🔄 **Processing Multiple Bins**

```bash
# Personal Bin - 10 at a time
python3 batch_processor.py ~/Library/Mobile\ Documents/com~apple~CloudDocs/Personal\ Bin --process

# Work Bin - 10 at a time
python3 batch_processor.py ~/Library/Mobile\ Documents/com~apple~CloudDocs/Work\ Bin --process

# Each bin tracks its own progress!
```

**Note**: Each root path has its own progress tracking file.

---

## 🐛 **Troubleshooting**

### **"All PDFs already processed!"**

You've finished! Check progress:
```bash
python3 batch_processor.py ~/Documents/Personal --status
```

To start over:
```bash
python3 batch_processor.py ~/Documents/Personal --reset
```

### **Want to Skip Some Files?**

Edit the progress file manually:
```bash
# View progress file
cat ~/.document_system/batch_progress.json

# Edit to add files to skip
nano ~/.document_system/batch_progress.json
```

Add file paths to `processed_files` array to skip them.

### **Processing Seems Slow?**

Increase batch size:
```bash
python3 batch_processor.py ~/Documents/Personal --process --batch-size 25
```

---

## 🎯 **Best Practices**

### **First Time Using System?**

1. Start with **5 files** per batch
2. Check each batch result carefully
3. Increase to 10 once confident
4. Increase to 25 for bulk processing

```bash
# Week 1: Very cautious
python3 batch_processor.py ~/Documents/Personal --process --batch-size 5

# Week 2: Normal pace
python3 batch_processor.py ~/Documents/Personal --process --batch-size 10

# Week 3+: Bulk processing
python3 batch_processor.py ~/Documents/Personal --process --batch-size 25
```

### **Large Collections (1000+ PDFs)?**

Create a shell script to automate:

```bash
#!/bin/bash
# process_all.sh

ROOT_PATH="$1"
BATCH_SIZE="${2:-10}"

echo "Processing all PDFs in: $ROOT_PATH"
echo "Batch size: $BATCH_SIZE"
echo ""

while true; do
    echo "Running batch..."
    python3 batch_processor.py "$ROOT_PATH" --process --batch-size "$BATCH_SIZE"
    
    # Wait 5 seconds between batches
    sleep 5
    
    # Check if done (optional: parse output to detect completion)
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        break
    fi
done

echo "✅ Processing complete!"
```

Usage:
```bash
chmod +x process_all.sh
./process_all.sh ~/Documents/Personal 10
```

---

## 🎊 **Integration with Other Tools**

### **After Batch Processing**

Files are added to database but NOT moved. To organize:

```bash
# 1. Batch process to catalog files
python3 batch_processor.py ~/Documents/Personal --process

# 2. Search for specific documents
python3 search_engine.py "tesla registration"

# 3. Analyze folder organization
python3 folder_analyzer.py ~/Documents/Personal

# 4. Get reorganization suggestions
python3 folder_analyzer.py ~/Documents/Personal --suggest-reorg
```

### **With Inbox Processor**

Batch processor is for **existing files**, inbox is for **new files**:

```bash
# Process existing collection
python3 batch_processor.py ~/Documents/Personal --process

# Then set up inbox for new files
python3 inbox_processor.py --setup-only
python3 inbox_processor.py --process
```

---

## 📋 **Quick Reference**

```bash
# Preview next batch
python3 batch_processor.py <folder> --dry-run

# Process next batch (10 files)
python3 batch_processor.py <folder> --process

# Process larger batch (25 files)
python3 batch_processor.py <folder> --process --batch-size 25

# Check progress
python3 batch_processor.py <folder> --status

# Reset and start over
python3 batch_processor.py <folder> --reset
```

---

## ✅ **Summary**

The batch processor gives you:
- ✅ **Safe processing** - Small batches, dry-run by default
- ✅ **Resumable** - Track progress, continue where you left off
- ✅ **Systematic** - Oldest folders first (backward search)
- ✅ **Flexible** - Configurable batch sizes
- ✅ **Transparent** - See exactly what's being processed
- ✅ **Notified** - Push notifications for each batch

**Perfect for processing your existing PDF collection!** 🚀📦
