# Photos Duplicate Cleanup Guide

## Using Photos' Built-in Duplicate Detection

Photos has a built-in duplicate detection feature that is the most reliable way to find and remove duplicates in large libraries (37k+ items).

### Step-by-Step Instructions

1. **Open Photos App**
   - Make sure Photos is running and your library is loaded

2. **Access Duplicate Detection**
   - Go to **View → Show Duplicates** (or press `Cmd+Shift+D`)
   - Photos will scan your library and show all duplicate groups

3. **Review Duplicates**
   - Photos groups duplicates together
   - Each group shows:
     - Number of duplicates
     - File sizes
     - Dates
     - Thumbnails

4. **Handle Each Duplicate Group**

   **Option A: Merge (Recommended)**
   - Click "Merge" on a duplicate group
   - Photos combines metadata from all versions
   - Keeps the highest quality version
   - This is usually the best option

   **Option B: Manual Selection (If you want to keep largest only)**
   - Select the duplicate group
   - Review each version
   - Manually delete the smaller ones:
     - Select the smaller duplicate(s)
     - Press `Delete` or right-click → Delete
     - Confirm deletion

5. **Bulk Operations**
   - You can select multiple duplicate groups at once
   - Use `Cmd+Click` to select multiple groups
   - Then merge or delete in bulk

### Tips

- **Start with Merge**: Photos' merge feature is smart - it usually keeps the best quality version automatically
- **Review Before Deleting**: Check thumbnails to make sure you're not deleting important variations
- **Work in Batches**: For large libraries, work through duplicates in batches to avoid fatigue
- **Check Recently Deleted**: Deleted items go to "Recently Deleted" album where they stay for 30 days before permanent deletion

### Keyboard Shortcuts

- `Cmd+Shift+D` - Show/Hide Duplicates
- `Delete` - Delete selected items
- `Cmd+A` - Select all (in duplicate view)
- `Cmd+Click` - Multi-select duplicate groups

### What Photos Considers Duplicates

Photos uses visual similarity and metadata to detect duplicates:
- Same or very similar images
- Same filename (even if sizes differ)
- Similar content (Photos uses AI to detect similar images)

### After Cleanup

Once you've cleaned up duplicates:
- Check your library size (should be smaller)
- Review "Recently Deleted" to make sure nothing important was removed
- Empty "Recently Deleted" after 30 days if you're sure

## Alternative: Automated Script (If Needed)

If you need to automate this process, we can create a script that:
1. Finds duplicates by filename and size
2. Identifies the largest version
3. Deletes smaller duplicates automatically

However, Photos' built-in duplicate finder is more reliable and safer for large libraries.
