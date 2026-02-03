# Advanced Stream Monitoring System

## Overview

The Advanced Stream Monitoring System provides event-based quality tracking and reliability scoring for live streams. It continuously monitors stream health, captures screenshots, and uses a Capped Sliding Window algorithm to calculate reliability scores while minimizing unnecessary stream changes in Dispatcharr.

## Key Features

### 1. Session-Based Monitoring
- Create monitoring sessions for specific channels
- Configure regex filters to select which streams to monitor
- Set pre-event timing to start monitoring before events begin
- Independent session management with start/stop controls
- **EPG Event Integration**: Sessions can be attached to EPG events for context-aware monitoring
- **Automatic Creation**: Sessions can be auto-created from scheduled events via regex/group rules

### 2. EPG Event Attachment
- Sessions can be linked to specific EPG program events
- Displays event information including:
  - Program title and description
  - Event start and end times
  - Event metadata
- Enables event-context monitoring for live broadcasts
- Automatic session creation when scheduled events trigger

### 3. Continuous Quality Assessment
- Lightweight FFmpeg-based monitoring using null muxer (`-c copy -f null -`)
- Real-time metrics collection:
  - Stream speed (buffering detection)
  - Bitrate measurement
  - FPS tracking
  - Resolution detection
- Minimal resource usage through copy codec (no re-encoding)
- **FFmpeg Speed Stats Storage**: Historical speed metrics stored for graphing

### 4. Reliability Scoring
- **Capped Sliding Window Algorithm**
  - Maintains a fixed-size window of recent measurements (default: 100)
  - Calculates reliability scores with limited variance
  - Prevents frequent stream changes due to minor fluctuations
  - Score range: 0-100%
- Automatic stream quarantine for failed streams
- **Manual Quarantine**: Ability to manually quarantine streams from the UI
- Continuous re-evaluation of stream health

### 5. Screenshot Capture & Carousel
- Periodic screenshot capture for visual stream verification
- Configurable interval (default: 60 seconds)
- Helps identify mismatching or incorrect streams
- Screenshots stored efficiently (one per stream, overwritten)
- **Scrollable Screenshot Display**: All alive streams' screenshots displayed in scrollable container
- Screenshots sorted by reliability score for quick quality assessment
- Accessible via web UI for quick visual checks

### 6. Active Stream Detection
- **Play Badge**: Green badge with play icon shows which streams are currently being played
- Real-time integration with Dispatcharr proxy status
- Updates every 2 seconds to show current playback state
- Helps identify which streams are actively in use

### 7. Metrics Persistence & Visualization
- Historical metrics stored for each stream
- Session data persisted to JSON files
- **Speed Stat Graphs**: FFmpeg speed metrics visualized in line charts under each stream
- **Improved Timeline**: Graph timestamps show HH:MM:SS format for better precision
- Real-time graph updates showing stream performance trends
- Stats refresh automatically without page reload
- Viewable in real-time dashboard
- Exportable for analysis

## Architecture

### Backend Components

#### 1. StreamSessionManager (`stream_session_manager.py`)
- **Purpose**: Core session lifecycle management
- **Features**:
  - Session CRUD operations
  - Stream discovery via UDI
  - Regex-based stream filtering
  - Metrics persistence
  - Capped Sliding Window scoring implementation

#### 2. FFmpegStreamMonitor (`ffmpeg_stream_monitor.py`)
- **Purpose**: Lightweight stream quality monitoring
- **Features**:
  - FFmpeg null muxer integration
  - Real-time stats parsing
  - Buffering detection
  - Metadata extraction (resolution, FPS, bitrate)

#### 3. StreamScreenshotService (`stream_screenshot_service.py`)
- **Purpose**: Screenshot capture and management
- **Features**:
  - FFmpeg-based screenshot capture
  - Automatic cleanup of old screenshots
  - Efficient storage (overwrite mode)

#### 4. StreamMonitoringService (`stream_monitoring_service.py`)
- **Purpose**: Orchestration of all monitoring activities
- **Features**:
  - Worker threads for:
    - Stream monitoring (1s interval)
    - Stream list refresh (60s interval)
    - Screenshot capture (5s check interval)
  - Reliability score updates
  - Stream quarantine management

### Frontend Components

#### 1. StreamMonitoring Page
- **Location**: `/stream-monitoring`
- **Features**:
  - Session list with active/all filtering
  - Session creation dialog
  - Real-time updates (5s polling for list, 2s for active sessions)
  - Session controls (start, stop, delete)

#### 2. SessionMonitorView Component
- **Features**:
  - **Channel Logo Display**: Shows channel logo at top of session view
  - **EPG Event Info Card**: Displays attached EPG event details (title, description, times)
  - Live monitoring dashboard
  - Stats cards (total, active, quarantined, avg reliability)
  - **Screenshot Carousel**: Carousel of all alive streams' screenshots above stream list
  - Stream tables with:
    - Reliability scores (with progress bars)
    - Quality metrics (resolution, FPS, bitrate)
    - **FFmpeg Speed Graphs**: Real-time speed metrics visualization under each stream
    - Screenshot viewing
  - Active/quarantined stream separation

#### 3. CreateSessionDialog Component
- **Features**:
  - Channel selection
  - Regex filter configuration
  - Advanced settings:
    - Stagger delay (prevent system overload)
    - Timeout configuration
    - Pre-event timing
  - Auto-start option

## API Endpoints

### Session Management

#### GET `/api/stream-sessions`
List all monitoring sessions or filter by status.

**Query Parameters:**
- `status` (optional): Filter by status (`active` or omit for all)

**Response:**
```json
[
  {
    "session_id": "session_123_1706834567",
    "channel_id": 123,
    "channel_name": "Sports Channel",
    "regex_filter": ".*",
    "created_at": 1706834567.123,
    "is_active": true,
    "pre_event_minutes": 30,
    "stagger_ms": 200,
    "timeout_ms": 30000,
    "stream_count": 15,
    "active_streams": 12,
    "epg_event_id": 456,
    "epg_event_title": "Live Sports Event",
    "epg_event_start": "2024-01-01T20:00:00Z",
    "epg_event_end": "2024-01-01T22:00:00Z",
    "epg_event_description": "Championship game",
    "channel_logo_url": "http://localhost:9191/api/channels/logos/789/",
    "channel_tvg_id": "sports-channel",
    "auto_created": true,
    "auto_create_rule_id": "rule-uuid-123"
  }
]
```

#### POST `/api/stream-sessions`
Create a new monitoring session.

**Request Body:**
```json
{
  "channel_id": 123,
  "regex_filter": ".*",
  "pre_event_minutes": 30,
  "stagger_ms": 200,
  "timeout_ms": 30000,
  "epg_event": {
    "id": 456,
    "title": "Live Sports Event",
    "start_time": "2024-01-01T20:00:00Z",
    "end_time": "2024-01-01T22:00:00Z",
    "description": "Championship game"
  },
  "auto_created": false,
  "auto_create_rule_id": null
}
```

**Response:**
```json
{
  "session_id": "session_123_1706834567",
  "message": "Session created successfully"
}
```

#### GET `/api/stream-sessions/<session_id>`
Get detailed information about a specific session.

**Response:**
```json
{
  "session_id": "session_123_1706834567",
  "channel_id": 123,
  "channel_name": "Sports Channel",
  "is_active": true,
  "streams": [
    {
      "stream_id": 789,
      "name": "Stream Name",
      "url": "acestream://...",
      "width": 1920,
      "height": 1080,
      "fps": 25.0,
      "bitrate": 4500,
      "reliability_score": 87.3,
      "is_quarantined": false,
      "screenshot_path": "screenshots/789.jpg",
      "metrics_count": 245
    }
  ]
}
```

#### POST `/api/stream-sessions/<session_id>/start`
Start monitoring for a session.

**Response:**
```json
{
  "message": "Session started successfully"
}
```

#### POST `/api/stream-sessions/<session_id>/stop`
Stop monitoring for a session.

**Response:**
```json
{
  "message": "Session stopped successfully"
}
```

#### DELETE `/api/stream-sessions/<session_id>`
Delete a session (stops monitoring first if active).

**Response:**
```json
{
  "message": "Session deleted successfully"
}
```

#### GET `/api/stream-sessions/<session_id>/streams/<stream_id>/metrics`
Get historical metrics for a stream.

**Response:**
```json
{
  "stream_id": 789,
  "metrics": [
    {
      "timestamp": 1706834567.123,
      "speed": 1.02,
      "bitrate": 4500.5,
      "fps": 25.0,
      "is_alive": true,
      "buffering": false
    }
  ]
}
```

#### GET `/api/stream-sessions/<session_id>/alive-screenshots`
Get screenshots and info for all alive (non-quarantined) streams in a session.

**Response:**
```json
{
  "session_id": "session_123_1706834567",
  "screenshots": [
    {
      "stream_id": 789,
      "stream_name": "Stream Name",
      "screenshot_url": "/data/screenshots/789.jpg",
      "reliability_score": 87.3,
      "m3u_account": "premium-account"
    }
  ]
}
```

#### POST `/api/stream-sessions/<session_id>/streams/<stream_id>/quarantine`
Manually quarantine a stream in a session. Useful for streams with mismatched content.

**Response:**
```json
{
  "message": "Stream quarantined successfully",
  "session_id": "session_123_1706834567",
  "stream_id": 789
}
```

#### GET `/api/proxy/status`
Get current proxy status showing which streams are actively being played.

**Response:**
```json
{
  "channels": [
    {
      "channel_id": "uuid-123",
      "state": "active",
      "stream_id": 789,
      "stream_name": "Stream Name",
      "client_count": 1,
      "uptime": 199.12,
      "avg_bitrate_kbps": 7377.21,
      "avg_bitrate": "7.38 Mbps",
      "resolution": "1920x1080",
      "source_fps": 25.0,
      "ffmpeg_speed": 1.45,
      "clients": [...]
    }
  ],
  "count": 2
}
```

#### GET `/api/proxy/playing-streams`
Get list of stream IDs that are currently being played.

**Response:**
```json
{
  "playing_stream_ids": [789, 790, 791],
  "count": 3
}
```

#### POST `/api/scheduled-events/<event_id>/create-session`
Create a monitoring session from a scheduled event.

**Response:**
```json
{
  "session_id": "session_123_1706834567",
  "message": "Session created successfully from event"
}
```

#### GET `/data/screenshots/<filename>`
Serve screenshot files.

**Example:** `/data/screenshots/789.jpg?t=1706834567`

## Automatic Session Creation

### Via Scheduled Events

Sessions can be automatically created from scheduled events using the existing auto-create rules system in the scheduling service. When an EPG event matches an auto-create rule:

1. A scheduled event is created for the channel check
2. The event can be manually converted to a monitoring session via the API endpoint:
   - `POST /api/scheduled-events/<event_id>/create-session`
3. The session will:
   - Inherit the channel's configured regex filter from channel settings
   - Attach the EPG event information (title, times, description)
   - Use the pre-event minutes specified in the scheduled event
   - Be marked as auto-created with the rule ID tracked

### Auto-Create Rules Integration

The existing auto-create rules in the scheduling service support:
- **Channel-based rules**: Monitor specific channels
- **Group-based rules**: Monitor all channels in a group
- **Regex pattern matching**: Filter EPG programs by title
- **Time-based scheduling**: Configure when monitoring should start (minutes before event)

These rules automatically create scheduled events which can then be converted to monitoring sessions, providing seamless integration between EPG-based scheduling and stream quality monitoring.

## Usage Guide

### Creating a Monitoring Session

1. Navigate to **Stream Monitoring** in the sidebar
2. Click **New Session**
3. Configure the session:
   - Select a channel to monitor
   - Set regex filter (use `.*` for all streams)
   - Configure pre-event timing
   - Adjust advanced settings if needed
   - Toggle auto-start if desired
   - Optionally attach EPG event information
4. Click **Create Session**

Alternatively, create sessions from scheduled events:
- Navigate to the scheduled events page
- Use the "Create Session" action on any event
- The session will automatically inherit EPG event details and channel regex

### Monitoring Active Sessions

1. Session will appear in the "Active Sessions" tab once started
2. Click on a session to view the live monitoring dashboard
3. **Session Header** displays:
   - Channel logo (if available)
   - EPG event information card with program details
4. **Screenshot Carousel** shows:
   - Live screenshots from all active streams
   - Stream names and reliability scores
   - Navigate with previous/next arrows
5. View real-time statistics:
   - Total streams discovered
   - Active streams being monitored
   - Quarantined streams (failed quality checks)
   - Average reliability score
6. Browse stream tables:
   - **Active Streams**: Currently monitored with reliability scores
   - **FFmpeg Speed Graphs**: Real-time performance visualization under each stream
   - **Quarantined**: Failed streams not being monitored
7. Click **View** on any stream to see its screenshot

### Managing Sessions

- **Start/Stop**: Use the buttons to control monitoring
- **Delete**: Remove a session and all its data
- **View Details**: Click on a session card to see the monitoring dashboard

## Configuration

### Session Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pre_event_minutes` | 30 | Minutes before event to start monitoring |
| `stagger_ms` | 200 | Milliseconds between starting stream monitors |
| `timeout_ms` | 30000 | Stream timeout before quarantine (ms) |
| `probe_interval_ms` | 300000 | Interval for stream list refresh (ms) |
| `screenshot_interval_seconds` | 60 | Seconds between screenshot captures |
| `window_size` | 100 | Size of sliding window for scoring |

### Capped Sliding Window Algorithm

The reliability scoring uses a Capped Sliding Window algorithm to avoid frequent stream changes:

1. **Measurement Window**: Maintains last 100 measurements
2. **Health Calculation**: Each measurement scored 0.0-1.0 based on:
   - Stream alive: Yes/No
   - Speed >= 0.9: Full score
   - Speed < 0.9: Partial score (buffering)
   - Dead stream: Zero score
3. **Score Dampening**: Uses exponential scaling (power 1.5) to reduce variance
4. **Range**: Final score clamped to 0-100%

This approach ensures that minor fluctuations don't cause stream changes while still identifying genuinely unreliable streams.

## Best Practices

### 1. Regex Filtering
- Use specific patterns to reduce monitored streams
- Example: `720p|1080p` for specific qualities
- Example: `.*SPORT.*` for sports streams
- Test regex patterns before creating sessions

### 2. Resource Management
- Start sessions just before events (use pre-event timing)
- Stop sessions when events end
- Use appropriate stagger delays (200ms recommended)
- Monitor system resources when tracking many streams

### 3. Screenshot Review
- Check screenshots periodically to verify stream content
- Look for:
  - Wrong channel/content
  - Black screens
  - Error messages
  - Quality issues

### 4. Reliability Interpretation
- Scores 80-100%: Excellent, very reliable
- Scores 60-79%: Good, minor buffering
- Scores 40-59%: Fair, frequent buffering
- Scores 0-39%: Poor, consider quarantine

## Troubleshooting

### Streams Not Appearing
- Verify regex filter matches stream names
- Check UDI has loaded streams from Dispatcharr
- Ensure channel ID is correct

### Monitoring Not Starting
- Check backend logs for errors
- Verify FFmpeg is installed and accessible
- Ensure sufficient system resources

### Screenshots Not Capturing
- Verify stream URLs are accessible
- Check `/app/data/screenshots` directory permissions
- Review screenshot service logs

### High Resource Usage
- Reduce number of monitored streams
- Increase stagger delay
- Stop unused sessions
- Check for memory leaks in long-running sessions

## Integration with Dispatcharr

The monitoring system integrates with Dispatcharr through:

1. **UDI (Universal Data Index)**: Fetches stream data
2. **Channel Information**: Links sessions to Dispatcharr channels
3. **Stream URLs**: Monitors AceStream/HTTP streams from Dispatcharr
4. **Independent Operation**: Doesn't modify Dispatcharr directly (read-only)

Future enhancements may include:
- Automatic stream reordering in Dispatcharr based on reliability
- Integration with scheduling system for EPG-based session creation
- Alerts/notifications for stream failures

## Data Storage

### Files
- **Session Data**: `/app/data/stream_session_data.json`
- **Configuration**: `/app/data/stream_session_config.json`
- **Screenshots**: `/app/data/screenshots/`

### Data Retention
- Sessions: Persisted indefinitely until deleted
- Metrics: Last 1000 measurements per stream
- Screenshots: One per stream (overwritten)

### Cleanup
- Delete old sessions manually via UI
- Screenshots auto-cleaned after 24 hours (configurable)

## Performance Considerations

### Resource Usage
- **CPU**: Minimal (FFmpeg copy codec, no re-encoding)
- **Memory**: ~10-20MB per monitored stream
- **Disk**: Screenshots ~100KB each, metrics <1MB per session
- **Network**: Continuous stream download (AceStream/HTTP)

### Scaling
- Tested with up to 50 concurrent streams per session
- Multiple sessions can run simultaneously
- Consider system bandwidth when monitoring many streams
- Use stagger delays to prevent startup spikes

## Security

### Access Control
- No authentication currently (uses same auth as main app)
- Sessions accessible to all users
- Consider implementing session ownership in future

### Data Privacy
- Stream URLs stored in session data
- Screenshots may contain copyrighted content
- Metrics data stored locally only

## Future Enhancements

Planned improvements:
1. **WebSocket Updates**: Replace polling with real-time updates
2. **Graphs and Charts**: Visualize metrics over time
3. **Preset Management**: Save and reuse session configurations
4. **EPG Integration**: Auto-create sessions based on EPG schedule
5. **Dispatcharr Integration**: Auto-reorder streams by reliability
6. **Alerts**: Notifications for stream failures
7. **Export**: Download metrics as CSV/JSON
8. **Multi-channel Sessions**: Monitor multiple channels in one session

## Support

For issues or questions:
- Check backend logs: `docker logs streamflow`
- Review frontend console for errors
- Check GitHub issues: https://github.com/krinkuto11/streamflow/issues
- See existing documentation in `/docs`
