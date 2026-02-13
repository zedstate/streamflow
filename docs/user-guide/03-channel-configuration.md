# Channel Configuration

This guide covers channel management, regex patterns for stream discovery, group-level settings, and channel ordering.

## Table of Contents
- [Overview](#overview)
- [Regex Configuration](#regex-configuration)
- [Group Management](#group-management)
- [Channel Ordering](#channel-ordering)
- [Pattern Matching Rules](#pattern-matching-rules)

## Overview

The Channel Configuration page provides three main tabs for managing channels:

1. **Regex Configuration** - Stream matching patterns for individual channels
2. **Group Management** - Group-level settings for matching and checking
3. **Channel Order** - Drag-and-drop channel organization

## Regex Configuration

### Table-Based Interface

The Regex Configuration tab uses a table layout for efficient pattern management:

**Columns:**
- **Select** - Checkbox for multi-select
- **#** - Channel number
- **Logo** - Channel logo (or first letter if unavailable)
- **Channel Name** - Name of the channel
- **Channel Group** - Group membership
- **Regex Patterns** - Count of configured patterns
- **Actions** - Dropdown menu (⋮) for channel actions

### Multi-Select and Bulk Operations

**Mass Regex Assignment:**
1. Select channels using checkboxes
2. Click "Add Regex to Selected"
3. Enter pattern (use `CHANNEL_NAME` variable for reusable patterns)
4. Pattern added to all selected channels

**Selection Features:**
- Individual selection via row checkboxes
- "Select All" for current page
- "Deselect All" to clear selection
- Selection counter badge

### Filtering and Sorting

**Group Filtering:**
- Filter by specific channel group
- "All Groups" to show all channels
- Focused management of channels by group

**Sort by Group:**
- Organize channels by group name
- Maintains channel number order within groups

**Search:**
- Search by channel name, number, or group
- Real-time filtering as you type
- Case-insensitive

### Pattern Management

**Actions Dropdown (⋮):**
- **View/Edit Regex Rules** - Opens pattern dialog
- **Toggle Stream Matching** - Enable/disable matching for channel
- **Toggle Stream Checking** - Enable/disable checking for channel

**Pattern Dialog:**
- View all patterns for channel
- Add new patterns inline
- Edit existing patterns
- Delete patterns individually
- Test patterns with live preview

### Channel Name Variables

Use `CHANNEL_NAME` in patterns for reusable matching:

**Example:**
```regex
Pattern: .*CHANNEL_NAME.*

For "ESPN" → matches "ESPN HD", "HD ESPN", "ESPN Sports"
For "CNN" → matches "CNN News", "HD CNN", "CNN International"
```

**Benefits:**
- One pattern works for multiple channels
- Reduces duplication
- Easier pattern management
- Automatic escaping of special characters

**Live Preview:**
- `CHANNEL_NAME` automatically substituted
- See matched streams in real-time
- Provider names shown for disambiguation
- Special characters handled automatically

### TVG-ID Matching

StreamFlow also supports automatic stream assignment via TVG-ID matching:

- Enable TVG-ID matching in automation settings
- Streams with matching TVG-IDs automatically assigned to channels
- Works alongside regex patterns
- No manual pattern configuration needed

See [Automation Profiles](02-automation-profiles.md) for TVG-ID configuration.

---

## Group Management

### Overview

Control stream matching and checking behavior for entire channel groups at once.

### Group Settings

Each channel group has two independent settings:

**Stream Matching:**
- **Enabled** - Channels participate in stream matching
- **Disabled** - Channels excluded from stream matching

**Stream Checking:**
- **Enabled** - Streams quality checked and reordered
- **Disabled** - Streams skip quality checking

### Visibility Rules

**Important:** When BOTH settings are disabled for a group:
- Channels from that group are **hidden** from Regex Configuration tab
- Channels from that group are **hidden** from Channel Order tab
- Keeps interface clean by showing only actively managed channels

### Group Card Display

Each group shows:
- Group name and ID
- Channel count
- Settings controls (dropdowns)
- Warning badge when both settings disabled

### Bulk Actions

Quick disable buttons for system-wide operations:

**Disable Matching for All:**
- Sets matching to "Disabled" for all groups
- Stops all stream matching operations
- One-click system-wide control

**Disable Checking for All:**
- Sets checking to "Disabled" for all groups
- Stops all stream quality checking
- Quick way to reduce provider load

### Use Cases

**Example 1: Disable Category**
1. Navigate to Group Management
2. Find group (e.g., "Sports")
3. Disable both matching and checking
4. Channels no longer appear in other tabs

**Example 2: Check Only (No Matching)**
1. Find channel group
2. Set "Stream Matching" to "Disabled"
3. Set "Stream Checking" to "Enabled"
4. Channels checked but won't get new streams via matching

**Example 3: Bulk Management**
1. Review all groups at once
2. Enable/disable settings for multiple groups
3. Changes apply immediately to all channels

---

## Channel Ordering

### Overview

Organize channels using drag-and-drop or sorting options.

### Features

**Drag and Drop:**
- Click and drag channels to reorder
- Visual feedback during drag
- Works with custom order mode

**Sort Options:**
- **Custom Order** - Manual arrangement
- **Channel Number** - Sort by number (1, 2, 3...)
- **Name (A-Z)** - Alphabetical sorting
- **ID** - Sort by internal ID

**Change Detection:**
- Unsaved changes indicator
- Save to persist changes
- Reset to discard changes

### Workflow

1. Switch to Channel Order tab
2. Select sort method from dropdown
3. Optionally drag-and-drop for fine-tuning
4. Click "Save Order" to persist
5. Or click "Reset" to discard

---

## Pattern Matching Rules

### Pattern Variables

**CHANNEL_NAME Variable:**
- Use in patterns to reference channel name
- Automatically substituted during matching
- Makes patterns reusable

**Example:**
```regex
.*CHANNEL_NAME.*HD

Channel "ESPN" → .*ESPN.*HD
Channel "CNN+  " → .*CNN\\+.*HD (special chars escaped)
```

### Whitespace Flexibility

The system automatically handles whitespace variations:

**How It Works:**
- Spaces in patterns converted to `\s+` (one or more whitespace)
- Matches single space, multiple spaces, tabs
- Transparent to users

**Example:**
```regex
User writes:  TVP 1
System converts: TVP\s+1

Matches:
✓ "TVP 1"   (single space)
✓ "TVP  1"  (double space)
✓ "TVP   1" (triple space)
✓ "TVP\t1"  (tab)
✗ "TVP1"    (no space)
```

**Exact Matching (if needed):**
- `TVP\ 1` - exactly one space
- `TVP\s1` - exactly one whitespace character
- `TVP\s{2}1` - exactly two whitespace characters

### Special Characters

Channel names with regex special characters (`+`, `.`, `*`, `[`, `]`, etc.) are automatically escaped:

**Example:**
```
Channel: "ESPN+"
Pattern: CHANNEL_NAME HD
Actual regex: ESPN\+ HD  (+ is escaped)
```

**Benefits:**
- Prevents regex errors
- No unexpected matches
- Transparent to users

### Live Preview

Test patterns against available streams:

**Features:**
- Real-time matching as you type
- `CHANNEL_NAME` automatically substituted
- Provider names shown for disambiguation
- Matched streams highlighted
- Invalid patterns flagged

**Example:**
```
Pattern: CHANNEL_NAME HD
Channel: ESPN+

Preview shows: ESPN\+ HD (escaped)
Matches:
✓ ESPN+ HD (Provider: Sports Plus)
✓ ESPN+ HD Sport (Provider: Premium)
✗ ESPN HD (missing +)
```

---

## Per-Channel Settings

### Matching Mode

Control whether channel participates in stream matching:
- **Enabled** (default) - Automatic stream discovery and assignment
- **Disabled** - Excluded from matching operations

### Checking Mode

Control whether channel participates in quality checking:
- **Enabled** (default) - Streams automatically quality checked
- **Disabled** - Streams excluded from checking

### Use Cases

**Match but Don't Check:**
- Keep channels updated with new streams
- Skip quality checking to reduce provider load

**Check but Don't Match:**
- Only check existing streams
- Don't add new streams automatically

**Disable Both:**
- Fully manual channel management
- No automation for this channel

### Where Settings Are Respected

Channel settings affect:
- Global Actions (checking_mode)
- Single Channel Check (both modes)
- Automated stream discovery (matching_mode)
- Regular automation cycles (both modes)

---

## Pagination

Efficient browsing of large channel lists:

**Features:**
- Configurable items per page (10, 20, 50, 100)
- First/Previous/Next/Last navigation
- Visual page number selection (shows 5 pages at a time)
- Current range indicator (e.g., "Showing 1-20 of 150 channels")
- Auto-reset to first page when search changes

---

## Workflows

### Workflow 1: Add Pattern to Multiple Channels

1. Set "Filter Group" to target group (e.g., "News")
2. Click "Select All"
3. Click "Add Regex to Selected"
4. Enter pattern: `.*CHANNEL_NAME.*`
5. Click "Add to X Channels"
6. Pattern applied to all selected channels

### Workflow 2: Configure Channels Without Patterns

1. Sort by pattern count (ascending)
2. Select channels with "No patterns"
3. Use bulk assignment to add general pattern
4. Refine individual patterns as needed

### Workflow 3: Organize by Group

1. Enable "Sort by Group" checkbox
2. Set "Filter Group" to focus on one group
3. Configure patterns for that group
4. Move to next group

### Workflow 4: Disable Inactive Category

1. Go to Group Management tab
2. Find inactive category (e.g., "International")
3. Set both matching and checking to "Disabled"
4. Channels hidden from Regex Configuration and Channel Order

---

##

 Troubleshooting

### Pattern Not Matching Expected Streams

**Check:**
1. Variable substitution - verify `CHANNEL_NAME` is correct
2. Special characters - ensure proper escaping
3. Whitespace - pattern should handle any whitespace variation
4. Case sensitivity - use `(?i)` flag for case-insensitive

**Use Live Preview:**
- Add pattern in regex editor
- View matched streams in real-time
- Check provider names if streams look identical

### CHANNEL_NAME Not Working

**Solutions:**
- Use `CHANNEL_NAME` (not `{CHANNEL_NAME}`)
- Verify channel has a name set
- Check pattern syntax
- Use live preview to see actual substitution

### Whitespace Matching Issues

- System automatically handles multiple spaces
- Verify stream name has at least one space
- For exact matching, use explicit `\  ` or `\s{1}`

---

**See Also:**
- [Getting Started](01-getting-started.md) - Basic concepts and setup
- [Automation Profiles](02-automation-profiles.md) - Pipeline modes and automation
- [Stream Management](04-stream-management.md) - Stream checking and scoring
- [Mass Regex Assignment](../MASS_REGEX_ASSIGNMENT.md) - Detailed bulk operations guide
