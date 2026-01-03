# Automation System Documentation

## Overview

The StreamFlow application provides flexible automation controls that allow you to customize which automation features are enabled. You can independently control M3U playlist updates, stream matching, quality checking, and scheduled global actions. Additionally, you can configure the system to automatically remove streams from channels if they no longer match configured regex patterns.

## Automation Controls

StreamFlow uses individual automation controls instead of predefined pipeline modes. This gives you fine-grained control over each automation feature:

### Available Controls

1. **Automatic M3U Updates** (`auto_m3u_updates`)
   - Automatically refresh M3U playlists from configured sources
   - Frequency configured via `playlist_update_interval_minutes` or `playlist_update_cron`

2. **Automatic Stream Matching** (`auto_stream_matching`)
   - Automatically match streams to channels using regex patterns
   - Runs after M3U playlist updates

3. **Automatic Quality Checking** (`auto_quality_checking`)
   - Automatically analyze stream quality (bitrate, resolution, FPS)
   - Reorder streams based on quality scores
   - Includes 2-hour immunity to prevent excessive checking

4. **Scheduled Global Action** (`scheduled_global_action`)
   - Run complete automation cycle on a schedule
   - Updates all M3U playlists, matches all streams, checks ALL channels
   - Bypasses 2-hour immunity
   - Schedule configured via `global_check_schedule.cron_expression`

5. **Remove Non-Matching Streams** (`remove_non_matching_streams`)
   - Automatically remove streams from channels if they no longer match regex patterns
   - Useful when providers change stream names but keep same URLs
   - Runs during automation cycles, global actions, and single channel checks

### Configuration Example

```json
{
  "automation_controls": {
    "auto_m3u_updates": true,
    "auto_stream_matching": true,
    "auto_quality_checking": true,
    "scheduled_global_action": true,
    "remove_non_matching_streams": false
  },
  "global_check_schedule": {
    "enabled": true,
    "cron_expression": "0 3 * * *"
  }
}
```

## Common Configuration Patterns

### Pattern 1: Full Automation with Quality Checking

**Use Case:** Users without connection limits who want continuous updates and quality checking

```json
{
  "automation_controls": {
    "auto_m3u_updates": true,
    "auto_stream_matching": true,
    "auto_quality_checking": true,
    "scheduled_global_action": true,
    "remove_non_matching_streams": false
  }
}
```

**Behavior:**
- Updates M3U playlists at configured interval
- Matches new streams to channels via regex patterns
- Checks channels that received new streams (respects 2-hour immunity)
- Runs scheduled global action to check ALL channels (bypasses immunity)

---

### Pattern 2: Updates and Matching Only

**Use Case:** Users with strict connection limits who only want stream discovery

```json
{
  "automation_controls": {
    "auto_m3u_updates": true,
    "auto_stream_matching": true,
    "auto_quality_checking": false,
    "scheduled_global_action": false,
    "remove_non_matching_streams": false
  }
}
```

**Behavior:**
- Updates M3U playlists at configured interval
- Matches new streams to channels via regex patterns
- NO automatic stream checking

---

### Pattern 3: Scheduled Actions Only

**Use Case:** Users who want complete control with scheduled maintenance

```json
{
  "automation_controls": {
    "auto_m3u_updates": false,
    "auto_stream_matching": false,
    "auto_quality_checking": false,
    "scheduled_global_action": true,
    "remove_non_matching_streams": false
  },
  "global_check_schedule": {
    "enabled": true,
    "cron_expression": "0 3 * * *"
  }
}
```

**Behavior:**
- NO automatic updates or matching between scheduled actions
- ONLY scheduled global action runs at specified time
- Updates all M3U playlists, matches all streams, checks ALL channels

---

## Migration from Legacy Pipeline Modes

If you were using the old `pipeline_mode` configuration, it will be automatically migrated to `automation_controls` when the system starts:

| Old Pipeline Mode | New Automation Controls |
|------------------|-------------------------|
| `pipeline_1` | `auto_m3u_updates: true`, `auto_stream_matching: true`, `auto_quality_checking: true`, `scheduled_global_action: false` |
| `pipeline_1_5` | `auto_m3u_updates: true`, `auto_stream_matching: true`, `auto_quality_checking: true`, `scheduled_global_action: true` |
| `pipeline_2` | `auto_m3u_updates: true`, `auto_stream_matching: true`, `auto_quality_checking: false`, `scheduled_global_action: false` |
| `pipeline_2_5` | `auto_m3u_updates: true`, `auto_stream_matching: true`, `auto_quality_checking: false`, `scheduled_global_action: true` |
| `pipeline_3` | `auto_m3u_updates: false`, `auto_stream_matching: false`, `auto_quality_checking: false`, `scheduled_global_action: true` |

The migration happens automatically and the old `pipeline_mode` key is removed from the configuration file.

---

## Global Action

### What is a Global Action?

A Global Action is a comprehensive operation that:
1. **Updates** all enabled M3U playlists
2. **Matches** all streams to channels via regex patterns
3. **Checks** ALL channels, bypassing the 2-hour immunity period

### When Does it Run?

Global Actions run:
- **Automatically:** When `scheduled_global_action` is enabled and the cron schedule triggers
- **Manually:** Via the "Global Action" button in the UI or API call

### Exclusive Execution

**Important:** During a global action, all regular automation is paused to prevent concurrent operations:
- Regular M3U update cycles are skipped
- Automated stream matching is paused
- Regular channel queueing for checking is suspended
- Once the global action completes, regular automation automatically resumes

This ensures that global actions run cleanly without interference from regular operations, and prevents resource contention.

### Force Check Behavior

During a Global Action, all channels are marked for "force check" which:
- Bypasses the 2-hour immunity period
- Analyzes ALL streams in every channel (not just new ones)
- Updates all stream quality scores
- Re-ranks all channels based on fresh analysis

---

## API Endpoints

### Trigger Manual Global Action

```
POST /api/stream-checker/global-action
```

**Response:**
```json
{
  "message": "Global action triggered successfully",
  "status": "in_progress",
  "description": "Update, Match, and Check all channels in progress"
}
```

### Get Stream Checker Status

```
GET /api/stream-checker/status
```

**Response includes:**
```json
{
  "running": true,
  "global_action_in_progress": false,
  "config": {
    "automation_controls": {
      "auto_m3u_updates": true,
      "auto_stream_matching": true,
      "auto_quality_checking": true,
      "scheduled_global_action": true,
      "remove_non_matching_streams": false
    },
    "global_check_schedule": {
      "enabled": true,
      "cron_expression": "0 3 * * *"
    }
  },
  "last_global_check": "2025-10-13T03:00:15.123Z"
}
```

---

## Technical Implementation

### Key Classes and Methods

#### StreamCheckerService

**New Methods:**
- `_perform_global_action()`: Executes complete Update→Match→Check cycle
- `trigger_global_action()`: Manually triggers a global action
- `_queue_updated_channels()`: Now respects pipeline mode

**Updated Methods:**
- `_check_global_schedule()`: Checks automation_controls before running
- `_queue_all_channels(force_check=False)`: Supports force checking
- `is_auto_m3u_updates_enabled()`: Checks if M3U updates are enabled
- `is_auto_stream_matching_enabled()`: Checks if stream matching is enabled
- `is_auto_quality_checking_enabled()`: Checks if quality checking is enabled
- `is_scheduled_global_action_enabled()`: Checks if scheduled actions are enabled

#### ChannelUpdateTracker

**New Methods:**
- `mark_channel_for_force_check(channel_id)`: Sets force check flag
- `should_force_check(channel_id)`: Checks if channel should be force checked
- `clear_force_check(channel_id)`: Clears force check flag

### Queue Management

The queue system prevents:
- Duplicate channel checking
- Race conditions during M3U updates
- Checking channels that are already queued or in progress
- Global actions from stacking up

### 2-Hour Immunity System

Streams are tracked per channel:
- Each stream's last check timestamp is stored
- When checking a channel, only unchecked streams (or those not checked in 2 hours) are analyzed
- Recently checked streams use cached quality scores
- Force check bypasses this immunity

---

## UI Configuration

### Setup Wizard

The **Setup Wizard** allows you to configure automation during initial setup:
- Step 1: Dispatcharr Connection
- Step 2: Channel Patterns Configuration
- Step 3: **Automation Settings**
  - Enable/disable individual automation features
  - Configure update intervals and schedules
  - Set concurrent stream limits
  - Configure stream removal options
- Step 4: Setup Complete

### Automation Settings Page

The web interface provides an **Automation Settings** page where you can:

1. **Configure Automation Features**: Enable or disable each automation feature independently
   - Automatic M3U Updates
   - Automatic Stream Matching
   - Automatic Quality Checking
   - Scheduled Global Action
   - Remove Non-Matching Streams

2. **Configure Schedules**: Set update intervals and global action schedules
   - Playlist update interval (minutes) or cron expression
   - Global action cron expression
   - Concurrent stream limits

3. **Queue Settings**: Configure channel checking queue
   - Maximum queue size
   - Max channels per run
   - Check on update behavior

---

## Stream Validation and Removal

### Remove Non-Matching Streams Feature

The `remove_non_matching_streams` automation control enables automatic cleanup of streams that no longer match their channel's regex patterns. This is useful when:

- Providers change stream names but keep the same URLs
- You update regex patterns and want to remove streams that no longer match
- You want to keep channels clean and up-to-date

**Important:** This feature **only affects channels that meet ALL of the following criteria**:
1. Have automatic stream matching **enabled** (channel-level or group-level setting)
2. Have regex patterns **configured and enabled**

Channels that don't meet these criteria will not be validated or have their streams removed, ensuring that manually managed channels and channels with matching disabled are not affected.

**When it runs:**
- During automation cycles (after M3U updates and before matching new streams)
- During global actions
- During single channel checks

**How it works:**
1. For each channel, checks if matching is enabled AND regex patterns are configured
2. Validates existing streams against those regex patterns
3. Removes streams that don't match any pattern for that channel
4. Skips channels with matching disabled or without regex patterns entirely
5. Logs the removals in the changelog
6. Updates the channel via Dispatcharr API

**Configuration:**
```json
{
  "automation_controls": {
    "remove_non_matching_streams": true
  }
}
```

---

## Configuration Examples (Updated)

### For Users Without Connection Limits
```json
{
  "automation_controls": {
    "auto_m3u_updates": true,
    "auto_stream_matching": true,
    "auto_quality_checking": true,
    "scheduled_global_action": true,
    "remove_non_matching_streams": false
  },
  "queue": {
    "check_on_update": true,
    "max_channels_per_run": 50
  }
}
```

### For Users With Moderate Limits
```json
{
  "automation_controls": {
    "auto_m3u_updates": true,
    "auto_stream_matching": true,
    "auto_quality_checking": true,
    "scheduled_global_action": true,
    "remove_non_matching_streams": false
  },
  "queue": {
    "check_on_update": true,
    "max_channels_per_run": 20
  },
  "global_check_schedule": {
    "enabled": true,
    "cron_expression": "0 3 * * *"
  }
}
```

### For Users With Strict Limits
```json
{
  "automation_controls": {
    "auto_m3u_updates": false,
    "auto_stream_matching": false,
    "auto_quality_checking": false,
    "scheduled_global_action": true,
    "remove_non_matching_streams": false
  },
  "global_check_schedule": {
    "enabled": true,
    "cron_expression": "0 3 * * *"
  }
}
```

---

## Configuration Guide

To configure automation:

1. **Via Web UI** (Recommended):
   - Navigate to **Automation Settings** page
   - Toggle individual automation features
   - Configure schedules and intervals
   - Click **Save Settings**

2. Via API:
```bash
curl -X PUT http://localhost:5000/api/stream-checker/config \
  -H "Content-Type: application/json" \
  -d '{
    "automation_controls": {
      "auto_m3u_updates": true,
      "auto_stream_matching": true,
      "auto_quality_checking": true,
      "scheduled_global_action": true,
      "remove_non_matching_streams": false
    }
  }'
```

3. Via Configuration File:
Edit `/app/data/stream_checker_config.json`:
```json
{
  "automation_controls": {
    "auto_m3u_updates": true,
    "auto_stream_matching": true,
    "auto_quality_checking": true,
    "scheduled_global_action": true,
    "remove_non_matching_streams": false
  }
}
```

Note: Changes via web UI or API take effect immediately without restart.

---

## Dead Stream Detection and Management

StreamFlow automatically detects and manages non-functional streams to maintain channel quality.

### How Dead Stream Detection Works

**Detection Criteria:**
A stream is considered "dead" if during quality analysis:
- Resolution is `0x0` or contains a 0 dimension (e.g., `1920x0` or `0x1080`)
- Bitrate is 0 kbps or null

**Tagging:**
When a dead stream is detected, it is automatically tagged with a `[DEAD]` prefix in Dispatcharr:
- Original: `"CNN HD"`
- Tagged: `"[DEAD] CNN HD"`

### Automation-Specific Behavior

#### With Auto Quality Checking Enabled
- Dead streams detected during regular channel checks
- Immediately tagged with `[DEAD]` prefix
- **Removed from channels** to maintain quality
- Will not be re-added during subsequent stream matching

#### Without Auto Quality Checking
- No regular stream checking, so no dead stream detection during normal operations
- Dead streams only detected during scheduled global actions (if enabled)

### Revival During Global Actions

During global actions (force check), dead streams are given a chance to revive:
1. All streams (including dead ones) are re-analyzed
2. If a dead stream is found to be working:
   - The `[DEAD]` prefix is removed
   - Stream is restored to normal status
   - Stream can be matched to channels again
3. If still dead, the tag remains

**Example Revival:**
```
Before global check: "[DEAD] CNN HD" (resolution: 0x0, bitrate: 0)
After global check:  "CNN HD" (resolution: 1920x1080, bitrate: 5000)
```

### Stream Matching Exclusion

Dead streams are automatically excluded from stream discovery:
- When regex patterns are matched, streams with `[DEAD]` prefix are skipped
- Prevents dead streams from being added to new channels
- Ensures only functional streams are assigned

### Benefits

1. **Automatic Cleanup**: Channels stay clean without manual intervention
2. **Quality Maintenance**: Only working streams remain in channels
3. **Efficient Checking**: Dead streams don't waste resources during regular checks
4. **Revival Opportunity**: Streams can recover during global actions
5. **Clear Identification**: `[DEAD]` tag makes status immediately visible

### Configuration

No special configuration required. Dead stream detection is:
- **Enabled by default** when auto quality checking or scheduled global actions are enabled
- **Automatic** - no manual intervention needed
- **Transparent** - all actions logged in changelog

### Monitoring

Dead stream activity is logged in the changelog:
- Detection and tagging events
- Removal from channels
- Revival events during global actions

You can monitor dead streams via:
- Changelog page in web UI
- Dispatcharr stream list (search for `[DEAD]`)
- Stream checker logs

---

## Future Enhancements

Potential future improvements:
- Per-channel automation control overrides
- Custom schedules per channel group
- Analytics dashboard showing automation statistics and patterns
- Dynamic automation adjustment based on connection speed
- Dead stream statistics and reporting dashboard
- Enhanced stream removal rules and filters
