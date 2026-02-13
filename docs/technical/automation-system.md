# Automation System

This document provides technical details on StreamFlow's automation system, including automation profiles, scheduling, and implementation details.

## Table of Contents
- [Automation Profiles](#automation-profiles)
- [Automation Controls](#automation-controls)
- [Scheduling System](#scheduling-system)
- [Global Actions](#global-actions)
- [Implementation Details](#implementation-details)

## Automation Profiles

StreamFlow uses automation profiles to configure automation behavior. For legacy compatibility, 5 pre-configured modes are supported that map to automation control settings.

### Mode Definitions

| Mode    | Updates | Matching | Checking | Scheduled |
| ------- | ------- | -------- | -------- | --------- |
| **1**   | ✓       | ✓        | ✓        | ✗         |
| **1.5** | ✓       | ✓        | ✓        | ✓         |
| **2**   | ✓       | ✓        | ✗        | ✗         |
| **2.5** | ✓       | ✓        | ✗        | ✓         |
| **3**   | ✗       | ✗        | ✗        | ✓         |

### Pipeline Mode Implementation

**Configuration Mapping:**
```python
PIPELINE_MODES = {
    "pipeline_1": {
        "auto_m3u_updates": True,
        "auto_stream_matching": True,
        "auto_quality_checking": True,
        "scheduled_global_action": False,
    },
    "pipeline_1_5": {
        "auto_m3u_updates": True,
        "auto_stream_matching": True,
        "auto_quality_checking": True,
        "scheduled_global_action": True,
    },
    # ... etc
}
```

**Legacy Migration:**
- Old `pipeline_mode` config migrated to `automation_controls` on startup
- Backward compatibility maintained
- New installations use `automation_controls` directly

---

## Automation Controls

### Individual Controls

Each control toggles a specific automation feature:

**auto_m3u_updates:**
- Automatically refresh M3U playlists
- Frequency: `playlist_update_interval_minutes`
- Default: 60 minutes

**auto_stream_matching:**
- Automatically match streams to channels
- Uses regex patterns
- Runs after M3U updates

**auto_quality_checking:**
- Automatically analyze stream quality
- Respects 2-hour immunity
- Queues channels with new streams

**scheduled_global_action:**
- Run complete automation cycle on schedule
- Bypasses 2-hour immunity
- Updates all, matches all, checks ALL

**remove_non_matching_streams:**
- Remove streams no longer matching regex
- Only affects channels with matching enabled
- Keeps channels clean

###Implementation

**Configuration Structure:**
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

**Runtime Checking:**
```python
def is_auto_quality_checking_enabled(self):
    return self.config.get('automation_controls.auto_quality_checking', False)

def is_scheduled_global_action_enabled(self):
    return (
        self.config.get('automation_controls.scheduled_global_action', False) and
        self.config.get('global_check_schedule.enabled', False)
    )
```

---

## Scheduling System

### Cron-Based Scheduling

**Global Check Schedule:**
```json
{
  "global_check_schedule": {
    "enabled": true,
    "cron_expression": "0 3 * * *"  // 3 AM daily
  }
}
```

**Cron Expression Format:**
```
* * * * *
│ │ │ │ │
│ │ │ │ └─── Day of week (0-6, Sunday=0)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

**Common Examples:**
- `0 3 * * *` - Daily at 3:00 AM
- `0 */6 * * *` - Every 6 hours
- `30 2 * * 0` - Sundays at 2:30 AM
- `0 0 1 * *` - First day of month at midnight

### Scheduler Thread

**Implementation:**
```python
class AutomatedStreamManager:
    def _scheduler_worker(self):
        while self._scheduler_running:
            # Check if scheduled global action is due
            if self.is_scheduled_global_action_enabled():
                cron_expr = self.config.get('global_check_schedule.cron_expression')
                if self.cron_scheduler.is_due(cron_expr):
                    self._perform_global_action()
            
            # Sleep and check again
            time.sleep(60)  # Check every minute
```

**Thread Lifecycle:**
- Starts with service initialization
- Runs continuously in background
- Stops gracefully on service shutdown

---

## Global Actions

### What Is a Global Action?

A comprehensive operation that:
1. Updates all enabled M3U playlists
2. Matches all streams to channels
3. Checks ALL channels (bypassing immunity)

### Implementation

**Exclusive Execution:**
```python
def _perform_global_action(self):
    # Pause regular automation
    self._pause_regular_automation()
    
    try:
        # 1. Update M3U playlists
        self._update_all_m3u_playlists()
        
        # 2. Match all streams
        self._match_all_streams()
        
        # 3. Force check all channels
        self._check_all_channels(force_check=True)
    finally:
        # Resume regular automation
        self._resume_regular_automation()
```

**Force Check Mechanism:**
```python
def _queue_all_channels(self, force_check=False):
    for channel in self.udi.get_all_channels():
        if force_check:
            # Bypass 2-hour immunity
            self.stream_checker.queue_channel(
                channel_id=channel['id'],
                force_check=True
            )
        else:
            # Respect immunity
            if self._should_check_channel(channel):
                self.stream_checker.queue_channel(channel['id'])
```

### Trigger Methods

**Scheduled:**
- Cron expression triggers automatically
- Runs at configured time
- Logged with timestamp

**Manual:**
- API endpoint: `POST /api/global-action`
- UI button: "Global Action"
- Immediately queued

**Status Tracking:**
```python
def trigger_global_action(self):
    if self._is_global_action_running():
        return {"status": "in_progress"}
    
    self._perform_global_action()
    return {
        "status": "completed",
        "description": "Update, Match, and Check all channels"
    }
```

---

## Implementation Details

### 2-Hour Immunity System

**Purpose:** Prevent excessive checking of recently analyzed channels

**Data Structure:**
```python
{
    "channel_id": {
        "last_check_timestamp": 1706834567.123,
        "streams_checked": ["stream_1", "stream_2", "stream_3"]
    }
}
```

**Implementation:**
```python
def should_check_channel(self, channel_id):
    last_check = self.tracker.get_last_check_time(channel_id)
    if last_check is None:
        return True  # Never checked
    
    elapsed = time.time() - last_check
    return elapsed >= 7200  # 2 hours = 7200 seconds
```

**Force Check Bypass:**
```python
def queue_channel(self, channel_id, force_check=False):
    if force_check or self.should_check_channel(channel_id):
        self._add_to_queue(channel_id)
    else:
        logger.info(f"Channel {channel_id} immune, skipping")
```

### Channel Update Tracking

**Purpose:** Track which channels received new streams and need checking

**Implementation:**
```python
class ChannelUpdateTracker:
    def __init__(self):
        self.updated_channels = set()
        self.force_check_channels = set()
    
    def mark_channel_updated(self, channel_id):
        self.updated_channels.add(channel_id)
    
    def mark_channel_for_force_check(self, channel_id):
        self.force_check_channels.add(channel_id)
    
    def clear_force_check(self, channel_id):
        self.force_check_channels.discard(channel_id)
```

**Usage:**
```python
# After stream matching
for channel_id in matched_channels:
    self.tracker.mark_channel_updated(channel_id)

# During global action
for channel_id in all_channels:
    self.tracker.mark_channel_for_force_check(channel_id)
```

### Regular Automation Cycle

**Main Loop:**
```python
def _automation_loop(self):
    while self._running:
        # M3U Updates
        if self.is_auto_m3u_updates_enabled():
            if self._should_update_m3u():
                self._update_all_m3u_playlists()
        
        # Stream Matching
        if self.is_auto_stream_matching_enabled():
            if self._should_match_streams():
                self._match_streams_for_updated_channels()
        
        # Quality Checking
        if self.is_auto_quality_checking_enabled():
            self._queue_updated_channels()
        
        # Sleep interval
        time.sleep(self.config.get('automation_check_interval', 60))
```

**Interval Configuration:**
```json
{
  "playlist_update_interval_minutes": 60,
  "stream_matching_interval_minutes": 15,
  "automation_check_interval": 60
}
```

### Pause/Resume Mechanism

**Implementation:**
```python
def _pause_regular_automation(self):
    self._automation_paused = True
    logger.info("Regular automation paused")

def _resume_regular_automation(self):
    self._automation_paused = False
    logger.info("Regular automation resumed")

def _automation_loop(self):
    while self._running:
        if self._automation_paused:
            time.sleep(5)
            continue
        
        # Regular automation logic...
```

**Purpose:**
- Prevents concurrent M3U updates during global actions
- Avoids race conditions
- Ensures clean execution of global actions

---

## Configuration File Structure

**automation_config.json:**
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
  },
  "playlist_update_interval_minutes": 60,
  "stream_matching_interval_minutes": 15,
  "automation_check_interval": 60
}
```

---

**See Also:**
- [Architecture](architecture.md) - System components and data flow
- [Storage](storage.md) - Data models and file formats
- [Performance](performance.md) - Optimization considerations
- [User Guide: Automation Profiles](../user-guide/02-automation-profiles.md) - User-facing pipeline documentation
