# Architecture

This document provides a technical overview of StreamFlow's architecture, core components, data flow, and the Universal Data Index (UDI) system.

## Table of Contents
- [System Overview](#system-overview)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Universal Data Index (UDI)](#universal-data-index-udi)
- [Storage Layer](#storage-layer)

## System Overview

StreamFlow is a Python/Flask backend with a React frontend that integrates with Dispatcharr to provide automated IPTV stream management.

### Technology Stack

**Backend:**
- Python 3.x
- Flask (web framework)
- Threading for concurrent operations
- FFmpeg for stream analysis
- JSON for data persistence

**Frontend:**
- React
- ShadCN UI components
- React Router for navigation
- Axios for API calls

**External Dependencies:**
- Dispatcharr (channel and stream management)
- FFmpeg (stream quality analysis)
- AceStream/HTTP streams

---

## Core Components

### 1. Web API (`web_api.py`)

**Purpose:** REST API server providing all backend functionality

**Key Endpoints:**
- `/api/channels/*` - Channel management
- `/api/stream-checker/*` - Stream quality checking
- `/api/automation/*` - Automation control
- `/api/m3u-accounts/*` - M3U account management
- `/api/stream-sessions/*` - Stream monitoring sessions

**Features:**
- Request/response logging
- Error handling
- CORS configuration
- Static file serving

### 2. Stream Checker Service (`stream_checker_service.py`)

**Purpose:** Core stream quality analysis and automation orchestration

**Responsibilities:**
- Queue-based channel processing
- FFmpeg stream analysis
- Quality scoring and ranking
- Concurrent/sequential checking modes
- 2-hour immunity tracking
- Dead stream detection

**Key Methods:**
- `queue_channel()` - Add channel to checking queue
- `_check_channel()` - Analyze streams for a channel
- `_analyze_stream()` - FFmpeg-based stream analysis
- `_score_stream()` - Calculate quality scores
- `_reorder_streams()` - Sort streams by score

### 3. Automated Stream Manager (`automated_stream_manager.py`)

**Purpose:** Automation pipeline orchestration

**Responsibilities:**
- M3U playlist updates
- Automatic stream matching
- Scheduled operations
- Global action coordination
- Pipeline mode management

**Key Features:**
- Cron-based scheduling
- Channel update tracking
- Force check mechanisms
- Pipeline modes (1, 1.5, 2, 2.5, 3)

### 4. Universal Data Index (UDI) (`udi/manager.py`)

**Purpose:** Centralized data layer for Dispatcharr integration

**Responsibilities:**
- Channel data caching
- Stream information indexing
- Group management
- Logo caching
- Data synchronization

**Benefits:**
- Single source of truth
- Reduced Dispatcharr API calls
- Faster data access
- Consistent data structure

See [Universal Data Index](#universal-data-index-udi) section for details.

### 5. M3U Account Manager (`m3u_account_manager.py`)

**Purpose:** M3U playlist and account management

**Responsibilities:**
- Playlist fetching and parsing
- Profile URL transformation
- Concurrent stream limiting
- Account/profile management

**Key Features:**
- Search/replace patterns
- Per-profile stream limits
- Provider priority system

### 6. Stream Session Manager (`stream_session_manager.py`)

**Purpose:** Advanced stream monitoring system

**Responsibilities:**
- Monitoring session management
- Reliability scoring (Capped Sliding Window)
- Screenshot capture coordination
- Timeline and history tracking

**Key Features:**
- EPG event integration
- Real-time metrics collection
- Smart stream protection
- Historical analysis

### 7. Configuration Managers

**channel_settings_manager.py:**
- Per-channel settings
- Group settings
- Regex pattern management

**automation_config_manager.py:**
- Pipeline modes
- Automation controls
- Scoring weights
- Profile management

### 8. Frontend Application

**Main Components:**
- `StreamChecker.jsx` - Stream checking interface
- `ChannelConfiguration.jsx` - Channel/regex management
- `Configuration.jsx` - System configuration
- `AutomationProfileStudio.jsx` - Profile management
- `StreamMonitoring.jsx` - Session monitoring
- `Scheduling.jsx` - EPG-based scheduling

---

## Data Flow

### Channel Quality Checking Flow

```
1. User/Automation triggers check
   ↓
2. StreamCheckerService.queue_channel()
   ↓
3.Worker thread picks up channel
   ↓
4. UDI fetches channel streams
   ↓
5. FFmpeg analyzes each stream
   ↓
6. Quality scores calculated
   ↓
7. Streams reordered by score
   ↓
8. Dead streams removed
   ↓
9. Channel updated in Dispatcharr
   ↓
10. Statistics persisted
```

### Automation Pipeline Flow

```
1. Scheduler checks cron expressions
   ↓
2. Pipeline mode determines actions
   ↓
3. M3U playlists updated (if enabled)
   ↓
4. Streams matched to channels (if enabled)
   ↓
5. Quality checking triggered (if enabled)
   ↓
6. Global action runs (if scheduled)
```

### M3U Stream Matching Flow

```
1. M3U playlist fetched
   ↓
2. Streams parsed from playlist
   ↓
3. For each channel with regex patterns:
   ↓
4. UDI provides available streams
   ↓
5. Regex patterns tested against streams
   ↓
6. Matched streams added to channel
   ↓
7. Non-matching streams removed (if enabled)
   ↓
8. Dispatcharr updated
```

---

## Universal Data Index (UDI)

### Purpose

Centralized data layer that:
- Caches Dispatcharr data locally
- Provides fast, consistent data access
- Reduces external API calls
- Enables offline operations

### Architecture

**UDI Manager (`udi/manager.py`):**
- Main interface for all UDI operations
- Handles data synchronization
- Manages cache lifecycle

**Data Categories:**
1. **Channels** - Channel metadata, groups, settings
2. **Streams** - Stream URLs, metadata, quality stats
3. **Groups** - Channel groups and membership
4. **Logos** - Channel logo URLs and caching

### Synchronization

**Auto-Sync:**
- Periodic background sync (configurable interval)
- Triggered by user actions (manual refresh)
- Lazy loading for missing data

**Sync Process:**
1. Fetch data from Dispatcharr API
2. Update local cache
3. Merge with existing data
4. Notify components of updates

### Data Structure

**Channel Index:**
```json
{
  "channel_id": {
    "id": "uuid",
    "channel_number": 101,
    "name": "ESPN",
    "channel_group_id": 5,
    "tvg_id": "espn.us",
    "logo_url": "http://...",
    "streams": [...]
  }
}
```

**Stream Index:**
```json
{
  "stream_id": {
    "id": 123,
    "name": "ESPN HD",
    "url": "acestream://...",
    "channel_id": "uuid",
    "m3u_account_id": 1,
    "m3u_profile_id": 2
  }
}
```

### Benefits

1. **Performance** - Cached data = faster access
2. **Reliability** - Works during Dispatcharr outages
3. **Consistency** - Single data source for all components
4. **Efficiency** - Reduced network I/O

---

## Storage Layer

### File-Based Persistence

StreamFlow uses JSON files for data persistence:

**Configuration Files:**
- `stream_checker_config.json` - Main configuration
- `automation_config.json` - Automation profiles
- `group_settings.json` - Group settings
- `m3u_accounts.json` - M3U accounts and profiles

**Data Files:**
- `stream_stats.json` - Stream quality statistics
- `channel_update_tracking.json` - 2-hour immunity tracking
- `stream_session_data.json` - Monitoring sessions

**Location:**
- Container: `/app/data/`
- Host: Configured via Docker volume

### Data Persistence Strategy

**Write-Through Cache:**
- Changes written immediately to disk
- In-memory cache updated simultaneously
- Ensures durability

**Atomic Writes:**
- Write to temporary file
- Rename to target file
- Prevents corruption on crash

**Backup:**
- Regular backups recommended
- Export via API or file copy
- Docker volume snapshots

---

## Concurrency Model

### Threading

**Worker Threads:**
- Stream checking workers (pool-based)
- Automation scheduler thread
- Monitoring session threads
- Screenshot capture workers

**Thread Safety:**
- Locks for shared state
- Queue-based communication
- Thread-safe data structures

### Async Operations

**Background Tasks:**
- M3U playlist updates
- UDI synchronization
- Dead stream cleanup
- Screenshot capture

**Event-Driven:**
- Channel update events
- Stream status changes
- Session lifecycle events

---

## Integration Points

### Dispatcharr API

**Read Operations:**
- Get channels and streams
- Get channel groups
- Get proxy status

**Write Operations:**
- Update channel streams
- Reorder streams
- Update stream metadata

**Error Handling:**
- Retry logic for transient failures
- Fallback to cached data
- Error logging and reporting

### FFmpeg

**Stream Analysis:**
- Quality metrics extraction
- Codec detection
- Error detection

**Screenshot Capture:**
- Periodic image capture
- Format conversion
- File management

---

**See Also:**
- [Automation System](automation-system.md) - Automation pipeline details
- [Storage](storage.md) - Data models and schemas
- [Performance](performance.md) - Performance considerations
