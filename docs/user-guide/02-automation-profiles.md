# Automation Profiles

This guide covers StreamFlow's automation system, including M3U account management, profile configuration, and scheduling.

## Table of Contents
- [M3U Accounts and Profiles](#m3u-accounts-and-profiles)
- [Automation Controls](#automation-controls)
- [Global Actions](#global-actions)
- [EPG-Based Scheduling](#epg-based-scheduling)

## M3U Accounts and Profiles

### Overview

M3U accounts represent connections to IPTV playlist sources. Each account can have multiple profiles, allowing you to maximize concurrent stream usage from a single M3U source.

### Account vs Profile

**M3U Account**:
- Represents a connection to an M3U playlist source (e.g., IPTV provider)
- Has properties: `name`, `server_url`, `max_streams`, `account_type`, `profiles`

**M3U Account Profile**:
- A variant way to access streams from the same account using different credentials or URL patterns
- Has properties: `name`, `max_streams`, `is_active`, `search_pattern`, `replace_pattern`, `account_id`

### Common Use Cases

**Multiple Credentials**: Provider gives you 2 logins, each with 1 concurrent stream
- Account: max_streams = 1
- Profile 1 (user1/pass1): max_streams = 1  
- Profile 2 (user2/pass2): max_streams = 1
- **Total capacity**: 2 concurrent streams

**Free + Premium**: Provider offers free streams alongside premium
- Account: max_streams = 2
- Profile 1 (Premium): max_streams = 2
- Profile 2 (Free): max_streams = 1
- **Total capacity**: 3 concurrent streams

### How Profile Selection Works

When checking streams, StreamFlow:

1. **Finds Available Profile**: Looks for a profile with available slots
   - Checks each profile's `max_streams` limit
   - Counts currently active streams using that profile
   - Selects first profile with available capacity

2. **Applies URL Transformation**: If profile has `search_pattern` and `replace_pattern`
   - Example: Transform `user1/pass1` to `user2/pass2` in URL

3. **Tracks Profile Usage**: During playback
   - Proxy tracks which profile is being used via `m3u_profile_id`
   - System counts active streams per profile
   - Respects per-profile `max_streams` limits

### Concurrent Stream Limiting

StreamFlow enforces limits at two levels:

1. **Account Level**: Total capacity = sum of all active profile limits
2. **Profile Level**: Each profile has its own limit

Example:
- Profile 1: 0/1 used → available
- Profile 2: 1/1 used → at capacity  
- System will use Profile 1 for next stream

### M3U Priority System

Configure stream selection priority for M3U accounts:

**Global Priority Mode** (applied to all accounts unless overridden):
- **Disabled**: Priority ignored, streams selected by quality only
- **Same Resolution Only**: Priority applied within same resolution groups
- **All Streams**: Always prefer higher priority accounts regardless of quality

**Priority Values** (0-100):
- **Higher numbers = Higher priority**
- Example: 100 = highest priority, 1 = lowest priority
- Use higher values (e.g., 100) for preferred sources
- Use lower values (e.g., 1) for fallback sources

**Per-Account Override**: Each account can override global priority mode

See [Stream Management](04-stream-management.md) for how priority affects stream scoring.

---

## Automation Controls

StreamFlow uses individual automation controls for fine-grained control over each feature:

### Available Controls

1. **Automatic M3U Updates** (`auto_m3u_updates`)
   - Automatically refresh M3U playlists from configured sources
   - Frequency configured via `playlist_update_interval_minutes`

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

5. **Remove Non-Matching Streams** (`remove_non_matching_streams`)
   - Automatically remove streams that no longer match regex patterns
   - Useful when providers change stream names
   - Only affects channels with matching enabled and regex patterns configured

### Configuration Example

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

---


## Global Actions

### What is a Global Action?

A comprehensive operation that:
1. **Updates** all enabled M3U playlists
2. **Matches** all streams to channels via regex patterns
3. **Checks** ALL channels, bypassing the 2-hour immunity period

### When Does it Run?

- **Automatically**: When `scheduled_global_action` is enabled and schedule triggers
- **Manually**: Via \"Global Action\" button in UI or API call

### Exclusive Execution

During a global action, all regular automation is paused:
- Regular M3U update cycles are skipped
- Automated stream matching is paused
- Regular channel queueing is suspended
- Once complete, regular automation automatically resumes

This prevents concurrent operations and resource contention.

### Force Check Behavior

During a Global Action, all channels are \"force checked\":
- Bypasses 2-hour immunity
- Analyzes ALL streams in every channel (not just new ones)
- Updates all stream quality scores
- Re-ranks all channels based on fresh analysis

### Dead Stream Revival

Global actions give dead streams a chance to revive:
1. All streams (including dead) are re-analyzed
2. If a dead stream is working: `[DEAD]` prefix removed, restored to normal
3. If still dead, tag remains

---

## EPG-Based Scheduling

Schedule channel checks to run before EPG program events for optimal stream quality.

### Manual Scheduled Events

- **Browse EPG programs** from Dispatcharr
- **Select channel and program**
- **Set check timing** (minutes before program starts)
- **Playlist refresh included** with each scheduled check

**Workflow**:
1. Navigate to Scheduling page
2. Click \"Add Event Check\"
3. Select channel from dropdown
4. View and select upcoming program
5. Specify minutes before program start
6. Save scheduled event

### Auto-Create Rules (Regex-Based)

Automatically create scheduled events based on program name patterns.

**Configuration**:
- Rule name for identification
- Channel selection (individual channels or channel groups)
- Regex pattern to match program names
- Minutes before setting

**Live Regex Testing**:
- Test patterns against real EPG data
- See matching programs before creating rule
- Case-insensitive matching

**Import/Export Rules**:
- **Export**: Download all rules as JSON for backup or transfer
- **Import**: Load rules from JSON file
  - Main Import: Bulk import all rules
  - Wizard Import: Load single rule into form
- **Use Cases**: Backup, transfer between environments, share configurations

**Automatic Event Creation**:
- Background processor fetches EPG data periodically
- Configurable refresh interval (default: 60 minutes, minimum: 5 minutes)
- Rules scan EPG automatically on every refresh
- Creates events for matching programs without manual intervention
- **Smart Filtering**:
  - Skips programs in the past
  - Prevents re-creation of executed events
  - Tracks executed events for 7 days
- **Duplicate Prevention**: Same channel/date/time within 5 minutes treated as duplicate

**Channel Groups Support**:
- Apply rules to entire channel groups
- New channels added to groups automatically included
- Perfect for dynamic groups (e.g., sports event channels created by Teamarr)

**Example Use Cases**:
- Breaking news: `^Breaking News|^Special Report`
- Live sports: `^Live:|Championship|Finals`
- Show-specific: `^Game of Thrones|^The Mandalorian`
- NBA games on Teamarr group: `(?i)^(?:coming up:\\s*)?NBA Basketball`

---

## Configuration

### Via Web UI (Recommended)

1. Navigate to **Configuration** page
2. Toggle individual automation controls
3. Configure schedules and intervals
4. Click **Save Settings**

### Via API

```bash
curl -X PUT http://localhost:5000/api/stream-checker/config \
  -H "Content-Type: application/json" \
  -d '{
    "automation_controls": {
      "auto_m3u_updates": true,
      "auto_stream_matching": true,
      "auto_quality_checking": true,
      "scheduled_global_action": true
    }
  }'
```

### Via Configuration File

Edit `/app/data/stream_checker_config.json`:
```json
{
  "automation_controls": {
    "auto_m3u_updates": true,
    "auto_stream_matching": true,
    "auto_quality_checking": true,
    "scheduled_global_action": true
  },
  "global_check_schedule": {
    "enabled": true,
    "cron_expression": "0 3 * * *"
  }
}
```

Changes via web UI or API take effect immediately without restart.

---

**See Also:**
- [Getting Started](01-getting-started.md) - Basic concepts and first-time setup
- [Channel Configuration](03-channel-configuration.md) - Regex patterns and channel settings
- [Stream Management](04-stream-management.md) - Stream checking and quality scoring
- [Technical: Pipeline System](../technical/pipeline-system.md) - Technical implementation details
