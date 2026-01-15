# Mass Regex Edit Feature

## Overview

The Mass Regex Edit feature allows you to perform find and replace operations on regex patterns across multiple channels simultaneously. This is useful for bulk pattern updates, such as:
- Changing quality indicators (HD → 4K, SD → HD)
- Updating provider names
- Standardizing pattern formats
- Applying regex transformations to multiple patterns at once

**Note:** This feature includes automatic duplicate prevention - when editing existing patterns, the system updates them in place rather than creating duplicates. See [CHANGELOG.md](CHANGELOG.md) for details on bug fixes and improvements.

## Accessing the Feature

1. Navigate to the **Channel Configuration** page
2. Select multiple channels using the checkboxes
3. Click the **"Bulk/Common Patterns"** button
4. Select one or more patterns using the checkboxes
5. Click **"Edit Selected"** button (next to "Delete Selected")

## Using Mass Edit

### 1. Find and Replace Fields

**Find Pattern**: Enter the text or regex pattern you want to find
- Example (text): `_HD`
- Example (regex): `\.\*(\w+)_HD\.\*`

**Replace With**: Enter the replacement text or regex substitution
- Example (text): `_4K`
- Example (regex): `.*\1_UHD.*`
- **Backreferences**: Use `\1`, `\2`, etc. for capture groups, or `\g<0>` for the full match (equivalent to $0 in JavaScript)

### 2. Options

**Use Regular Expression**: When checked, enables regex-based find and replace
- Find: Uses regex patterns with capture groups
- Replace: Can use backreferences like `\1`, `\2`, etc. for capture groups
- Replace: Use `\g<0>` to reference the full match (equivalent to $0 in JavaScript)

**Update Playlists**: Optionally update M3U account filters for affected patterns
- **Keep Existing Playlists**: Preserves current playlist settings (default)
- **All Playlists**: Sets patterns to apply to all M3U accounts
- **Specific Playlists**: Select which M3U accounts the patterns should apply to

### 3. Preview Changes

Click **"Preview Changes"** to see what will be affected:
- Shows all channels that will be modified
- Displays before/after comparison for each pattern
- Shows total number of channels and patterns affected

### 4. Apply Changes

Click **"Apply Changes"** to execute the mass edit operation:
- Only enabled after a successful preview
- Applies the find/replace to all selected patterns
- Shows success message with counts

## Examples

### Example 1: Simple Text Replacement

**Scenario**: Change all `_HD` suffixes to `_4K`

1. Find Pattern: `_HD`
2. Replace With: `_4K`
3. Use Regular Expression: ❌ (unchecked)

**Result**:
- `.*ESPN_HD.*` → `.*ESPN_4K.*`
- `.*CNN_HD.*` → `.*CNN_4K.*`

### Example 2: Regex-Based Transformation

**Scenario**: Change `.*CHANNEL_HD.*` to `.*CHANNEL_UHD.*` while preserving channel name

1. Find Pattern: `\.\*(\w+)_HD\.\*`
2. Replace With: `.*\1_UHD.*`
3. Use Regular Expression: ✅ (checked)

**Result**:
- `.*ESPN_HD.*` → `.*ESPN_UHD.*`
- `.*CNN_HD.*` → `.*CNN_UHD.*`
- `.*HBO_HD.*` → `.*HBO_UHD.*`

### Example 3: Pattern Standardization

**Scenario**: Add consistent prefix to all patterns

1. Find Pattern: `^`
2. Replace With: `US_`
3. Use Regular Expression: ✅ (checked)

**Result**:
- `.*ESPN.*` → `US_.*ESPN.*`
- `.*CNN.*` → `US_.*CNN.*`

### Example 4: Using Full Match Reference

**Scenario**: Wrap all patterns with additional pattern markers

1. Find Pattern: `(.*)`
2. Replace With: `^(\g<0>)$`
3. Use Regular Expression: ✅ (checked)

**Result**:
- `.*ESPN.*` → `^(.*ESPN.*)$`
- `.*CNN.*` → `^(.*CNN.*)$`

Note: `\g<0>` references the full match (equivalent to $0 in JavaScript)

### Example 5: Update Playlists

**Scenario**: Change all HD patterns to 4K and limit to Premium playlist

1. Find Pattern: `_HD`
2. Replace With: `_4K`
3. Use Regular Expression: ❌
4. Update Playlists: ✅ Select "Premium" playlist only

**Result**:
- Pattern text updated from `_HD` to `_4K`
- M3U accounts updated to only use Premium playlist

## Features

### Duplicate Prevention
The mass edit feature automatically prevents duplicate patterns:
- If the new pattern already exists in a channel, duplicates are automatically removed
- Only unique patterns are saved

### Validation
- All resulting patterns are validated before being saved
- Invalid regex patterns are rejected with error messages
- Changes are atomic per channel (all or nothing)

### Logging
- Batch operations use reduced logging to avoid spam
- Summary log message shows total channels and patterns affected
- Individual channel updates logged at DEBUG level

## API Endpoints

### Preview Mass Edit
```
POST /api/regex-patterns/mass-edit-preview
```

**Request Body**:
```json
{
  "channel_ids": [1, 2, 3],
  "find_pattern": "_HD",
  "replace_pattern": "_4K",
  "use_regex": false
}
```

**Response**:
```json
{
  "affected_channels": [
    {
      "channel_id": 1,
      "channel_name": "ESPN",
      "affected_patterns": [
        {
          "old_pattern": ".*ESPN_HD.*",
          "new_pattern": ".*ESPN_4K.*",
          "m3u_accounts": null
        }
      ],
      "total_affected": 1
    }
  ],
  "total_channels_affected": 1,
  "total_patterns_affected": 1,
  "find_pattern": "_HD",
  "replace_pattern": "_4K",
  "use_regex": false
}
```

### Apply Mass Edit
```
POST /api/regex-patterns/mass-edit
```

**Request Body**:
```json
{
  "channel_ids": [1, 2, 3],
  "find_pattern": "_HD",
  "replace_pattern": "_4K",
  "use_regex": false,
  "new_m3u_accounts": null
}
```

**Response**:
```json
{
  "message": "Successfully updated 3 channel(s)",
  "success_count": 3,
  "total_channels": 3,
  "total_patterns_updated": 5
}
```

## Troubleshooting

### No Patterns Affected
- Ensure the find pattern exactly matches existing patterns
- Check if "Use Regular Expression" is toggled correctly
- Verify selected channels actually have the patterns you're looking for

### Invalid Regex Error
- Check your regex syntax in the find pattern
- Test the regex separately before using in mass edit
- Ensure backreferences in replace pattern match capture groups in find pattern

### Some Channels Failed
- Check the error messages in the response
- Verify resulting patterns are valid regex
- Ensure channels exist and are accessible

## Best Practices

1. **Always Preview First**: Use the preview feature before applying changes
2. **Test on Few Channels**: Start with a small subset to verify the operation works as expected
3. **Backup Patterns**: Export your regex patterns before major changes
4. **Use Specific Patterns**: Make find patterns as specific as possible to avoid unintended changes
5. **Check Results**: After applying, verify the changes in the channel list

## Related Features

- **Bulk Add Patterns**: Add the same pattern to multiple channels
- **Bulk Delete Patterns**: Remove patterns from multiple channels
- **Common Patterns**: View and edit patterns that appear across channels
- **Pattern Import/Export**: Backup and restore regex configurations
