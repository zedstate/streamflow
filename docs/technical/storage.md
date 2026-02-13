# Storage

This document describes StreamFlow's data storage layer, including file structure, JSON schemas, and data models.

## Table of Contents
- [Directory Structure](#directory-structure)
- [Configuration Files](#configuration-files)
- [Data Files](#data-files)
- [Data Models](#data-models)
- [Persistence Strategy](#persistence-strategy)

## Directory Structure

### Container Layout

```
/app/
├── backend/           # Python backend code
├── frontend/          # React frontend (built)
├── data/              # Persistent data directory
│   ├── *.json        # Configuration and data files
│   ├── screenshots/   # Stream screenshots
│   └── logs/          # Application logs (if configured)
└── logs/              # FFmpeg and processing logs
```

### Data Directory (`/app/data/`)

**Mounted as Docker Volume:**
- Persists across container restarts
- Recommended: Named volume or bind mount
- Example: `./data:/app/data`

**Contents:**
- Configuration files (`.json`)
- Stream statistics
- Session data
- Screenshots

---

## Configuration Files

### stream_checker_config.json

**Purpose:** Main StreamFlow configuration

**Schema:**
```json
{
  "enabled": true,
  "check_interval_minutes": 120,
  "concurrent_streams": {
    "enabled": true,
    "max_workers": 10,
    "stagger_delay_ms": 200
  },
  "stream_analysis": {
    "duration_seconds": 10,
    "base_timeout_seconds": 30,
    "startup_buffer_seconds": 10,
    "retry_attempts": 2,
    "retry_delay_seconds": 5,
    "user_agent": "Mozilla/5.0..."
  },
  "debug_mode": false
}
```

**Key Fields:**
- `enabled` - Master toggle for stream checking
- `check_interval_minutes` - Immunity period (default: 120 = 2 hours)
- `concurrent_streams.max_workers` - Parallel checking pool size
- `stream_analysis.duration_seconds` - FFmpeg analysis duration

### automation_config.json

**Purpose:** Automation pipeline configuration

**Schema:**
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
  "profiles": [
    {
      "id": "default",
      "name": "Default Profile",
      "scoring_weights": {
        "bitrate": 0.35,
        "resolution": 0.30,
        "fps": 0.15,
        "codec": 0.10,
        "hdr": 0.10,
        "prefer_h265": true
      },
      "stream_limit": 0
    }
  ]
}
```

### m3u_accounts.json

**Purpose:** M3U accounts and profiles

**Schema:**
```json
{
  "accounts": [
    {
      "id": 1,
      "name": "Premium IPTV",
      "server_url": "http://provider.com/playlist.m3u8",
      "max_streams": 2,
      "account_type": "premium",
      "priority": 100,
      "is_active": true,
      "profiles": [
        {
          "id": 1,
          "name": "Profile 1",
          "max_streams": 1,
          "is_active": true,
          "search_pattern": "user1/pass1",
          "replace_pattern": "user1/pass1",
          "account_id": 1
        }
      ]
    }
  ]
}
```

### group_settings.json

**Purpose:** Channel group automation settings

**Schema:**
```json
{
  "5":  {
    "matching_mode": "enabled",
    "checking_mode": "enabled"
  },
  "12": {
    "matching_mode": "disabled",
    "checking_mode": "disabled"
  }
}
```

**Keys:** Channel group IDs (as strings)
**Values:** Settings objects with matching_mode and checking_mode

---

## Data Files

### stream_stats.json

**Purpose:** Stream quality statistics and scores

**Schema:**
```json
{
  "stream_123": {
    "stream_id": 123,
    "channel_id": "uuid",
    "last_check": 1706834567.123,
    "bitrate": 5000,
    "width": 1920,
    "height": 1080,
    "fps": 25.0,
    "codec": "h264",
    "hdr_format": null,
    "score": 0.85,
    "is_dead": false
  }
}
```

**Key Fields:**
- `last_check` - Unix timestamp of last analysis
- `score` - Calculated quality score (0.0-1.0)
- `is_dead` - Whether stream is marked dead
- `hdr_format` - HDR type (null, "hdr10", "hlg", "dolby_vision")

### channel_update_tracking.json

**Purpose:** 2-hour immunity tracking

**Schema:**
```json
{
  "channel_uuid_1": {
    "last_check_timestamp": 1706834567.123,
    "streams_checked": [123, 456, 789]
  }
}
```

**Keys:** Channel UUIDs
**Values:** Last check timestamp and stream IDs checked

### stream_session_data.json

**Purpose:** Stream monitoring sessions

**Schema:**
```json
{
  "session_123_1706834567": {
    "session_id": "session_123_1706834567",
    "channel_id": 123,
    "channel_name": "ESPN",
    "regex_filter": ".*",
    "created_at": 1706834567.123,
    "is_active": true,
    "pre_event_minutes": 30,
    "stagger_ms": 200,
    "timeout_ms": 30000,
    "epg_event": {
      "id": 456,
      "title": "Live Game",
      "start_time": "2024-01-01T20:00:00Z",
      "end_time": "2024-01-01T22:00:00Z"
    },
    "streams": {
      "789": {
        "stream_id": 789,
        "name": "ESPN HD",
        "url": "acestream://...",
        "width": 1920,
        "height": 1080,
        "fps": 25.0,
        "bitrate": 5000,
        "reliability_score": 87.3,
        "is_quarantined": false,
        "metrics": [...],
        "screenshot_path": "/app/data/screenshots/789.jpg"
      }
    }
  }
}
```

---

## Data Models

### Channel Model

```python
{
    "id": str,  # UUID
    "channel_number": int,
    "name": str,
    "channel_group_id": int,
    "tvg_id": str,
    "logo_url": str,
    "streams": List[Stream]
}
```

###Stream Model

```python
{
    "id": int,
    "name": str,
    "url": str,
    "channel_id": str,  # UUID
    "m3u_account_id": int,
    "m3u_profile_id": int,
    "quality_stats": {
        "bitrate": int,
        "width": int,
        "height": int,
        "fps": float,
        "codec": str,
        "hdr_format": Optional[str],
        "score": float,
        "is_dead": bool
    }
}
```

### M3U Account Model

```python
{
    "id": int,
    "name": str,
    "server_url": str,
    "max_streams": int,
    "account_type": str,
    "priority": int,
    "is_active": bool,
    "profiles": List[Profile]
}
```

### Profile Model

```python
{
    "id": int,
    "name": str,
    "max_streams": int,
    "is_active": bool,
    "search_pattern": Optional[str],
    "replace_pattern": Optional[str],
    "account_id": int
}
```

### Automation Profile Model

```python
{
    "id": str,
    "name": str,
    "scoring_weights": {
        "bitrate": float,  # 0.0-1.0
        "resolution": float,
        "fps": float,
        "codec": float,
        "hdr": float,
        "prefer_h265": bool
    },
    "stream_limit": int  # 0 = unlimited
}
```

---

## Persistence Strategy

### Write-Through Cache

**Pattern:**
```python
def update_config(self, key, value):
    # Update in-memory cache
    self._config[key] = value
    
    # Write to disk
    self._save_config_to_disk()
```

**Benefits:**
- Fast reads (from memory)
- Durable writes (to disk)
- Consistent state

### Atomic Writes

**Implementation:**
```python
def _save_to_disk(self, data, filepath):
    temp_path = filepath + '.tmp'
    
    # Write to temporary file
    with open(temp_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Atomic rename
    os.rename(temp_path, filepath)
```

**Benefits:**
- Prevents corruption on crash
- Never leaves partial writes
- Safe concurrent reads

### Backup and Recovery

**Manual Backup:**
```bash
# Backup all data
docker cp streamflow:/app/data ./backup-$(date +%Y%m%d)

# Backup specific file
docker cp streamflow:/app/data/stream_checker_config.json ./config-backup.json
```

**Restore:**
```bash
# Restore all data
docker cp ./backup-20240101/. streamflow:/app/data/
docker restart streamflow

# Restore specific file
docker cp ./config-backup.json streamflow:/app/data/stream_checker_config.json
docker restart streamflow
```

**Recommended Strategy:**
- Daily automated backups
- Keep 7 days of backups
- Test restore procedure periodically

---

**See Also:**
- [Architecture](architecture.md) - System components
- [Automation System](automation-system.md) - Automation details
- [Performance](performance.md) - Performance considerations
