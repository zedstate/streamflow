# Stream Monitoring

This guide covers the advanced stream monitoring system, including session management, timeline analysis, and reliability scoring.

## Table of Contents
- [Overview](#overview)
- [Creating Sessions](#creating-sessions)
- [Monitoring Dashboard](#monitoring-dashboard)
- [Timeline and History](#timeline-and-history)
- [Reliability Scoring](#reliability-scoring)
- [Smart Stream Protection](#smart-stream-protection)

## Overview

The Stream Monitoring system provides event-based quality tracking and reliability scoring for live streams. It continuously monitors stream health, captures screenshots, and uses a Capped Sliding Window algorithm to calculate reliability scores.

### Key Features

- **Session-Based Monitoring** - Create sessions for specific channels
- **EPG Event Integration** - Link sessions to EPG programs
- **Continuous Quality Assessment** - Real-time metrics collection
- **Reliability Scoring** - Capped Sliding Window algorithm
- **Screenshot Capture** - Visual stream verification
- **Active Stream Detection** - See which streams are being played
- **Browsable Timeline** - Video-editor style timeline for history
- **Smart Stream Protection** - Conditional hysteresis based on user activity

---

## Creating Sessions

### Manual Session Creation

1. Navigate to **Stream Monitoring** in sidebar
2. Click **New Session**
3. Configure the session:
   - **Channel** - Select channel to monitor
   - **Regex Filter** - Filter streams (use `.*` for all)
   - **Pre-Event Timing** - Minutes before event to start
   - **Advanced Settings**:
     - Stagger delay (prevent system overload)
     - Timeout configuration
   - **Auto-Start** - Toggle to start immediately
   - **EPG Event** (optional) - Attach EPG event information
4. Click **Create Session**

### Automatic Session Creation

Sessions can be auto-created from scheduled events:

1. Navigate to Scheduling page
2. Use "Create Session" action on any event
3. Session inherits:
   - EPG event details (title, times, description)
   - Channel's regex filter
   - Pre-event minutes from scheduled event
   - Marked as auto-created with rule ID tracked

See [Automation Profiles](02-automation-profiles.md#epg-based-scheduling) for auto-create rules.

### Session Parameters

| Parameter                     | Default | Description                            |
| ----------------------------- | ------- | -------------------------------------- |
| `pre_event_minutes`           | 30      | Minutes before event to start          |
| `stagger_ms`                  | 200     | Milliseconds between starting monitors |
| `timeout_ms`                  | 30000   | Stream timeout before quarantine (ms)  |
| `probe_interval_ms`           | 300000  | Interval for stream list refresh (ms)  |
| `screenshot_interval_seconds` | 60      | Seconds between screenshots            |
| `window_size`                 | 100     | Size of sliding window for scoring     |

---

## Monitoring Dashboard

### Session View

Active session displays:

**Header:**
- Channel logo (if available)
- EPG event information card (title, description, times)

**Statistics Cards:**
- Total streams discovered
- Active streams being monitored
- Quarantined streams (failed quality)
- Average reliability score

**Screenshot Carousel:**
- Live screenshots from all active streams
- Stream names and reliability scores  
- Navigate with previous/next arrows
- Scrollable container sorted by reliability

**Stream Tables:**
- **Active Streams** - Currently monitored with scores
- **Quarantined Streams** - Failed streams not monitored

### Stream Information

For each active stream:
- **Name** - Stream identifier
- **M3U Account** - Source provider
- **Reliability Score** - 0-100% (with progress bar)
- **Quality Metrics**:
  - Resolution (e.g., 1920×1080)
  - FPS (e.g., 25.0)
  - Bitrate (e.g., 4500 kbps)
- **Play Badge** - Green badge when actively playing
- **FFmpeg Speed Graph** - Real-time performance visualization
- **Screenshot** - Click "View" to see screenshot

### Active Stream Detection

**Play Badge:**
- Green badge with play icon
- Shows which streams currently being played
- Real-time integration with Dispatcharr proxy status
- Updates every 2 seconds

---

## Timeline and History

### Interactive Timeline

**Features:**
- **Video-editor style timeline** - Browse session history
- **Time Travel** - Scrub through past moments
- **Event Markers** - Visual indicators:
  - **Yellow** - Stream Quarantined
  - **Green** - Primary Stream Changed
  - **Blue** - Stream Promoted to Stable
- **Zoom Controls** - Vertical slider with 30s to 1h range
- **Live/History Modes** - Switch between real-time and historical
- **Synchronized Charts** - Speed metrics synced to cursor position
- **Frozen Timeline** - Inactive sessions have static, browsable timeline

### Using the Timeline

**Scrubbing:**
1. Drag timeline cursor to any point in history
2. View stream state at that exact moment
3. FFmpeg speed graphs update to show historical data

**Zoom:**
1. Use vertical zoom slider
2. Range: 30 seconds to 1 hour
3. Fine-tune view for detailed analysis

**Return to Live:**
- Click "Return to Live" button
- Jumps to current time
- Resumes real-time updates

---

## Reliability Scoring

### Capped Sliding Window Algorithm

StreamFlow uses an advanced algorithm to avoid frequent stream changes:

**How It Works:**
1. **Measurement Window** - Maintains last 100 measurements
2. **Health Calculation** - Each measurement scored 0.0-1.0:
   - Stream alive: Yes/No
   - Speed >= 0.9: Full score
   - Speed < 0.9: Partial score (buffering)
   - Dead stream: Zero score
3. **Score Dampening** - Exponential scaling (power 1.5) reduces variance
4. **Range** - Final score clamped to 0-100%

**Benefits:**
- Minor fluctuations don't cause stream changes
- Identifies genuinely unreliable streams
- Stable scoring for decision-making

### Score Interpretation

| Score Range | Quality   | Description                        |
| ----------- | --------- | ---------------------------------- |
| 80-100%     | Excellent | Very reliable, minimal buffering   |
| 60-79%      | Good      | Minor buffering, generally stable  |
| 40-59%      | Fair      | Frequent buffering, usable         |
| 0-39%       | Poor      | Consider quarantine or replacement |

### Manual Quarantine

Quarantine streams manually from UI:
- Useful for streams with mismatched content
- Removes stream from active monitoring
- Stream moved to Quarantined section
- Can be manually re-added if needed

---

## Smart Stream Protection

### Conditional Hysteresis

Intelligent logic based on stream state and user activity:

**States:**
- **Review/Testing** - Never protected (always best candidate wins)
- **Idle Stable** - Weak protection (easy to replace if better found)
- **Active Stable** - Strong protection (hard to replace while watching)

**Dispatcharr Integration:**
- Real-time checking of active playback
- Protects streams users are currently watching
- Allows aggressive replacement of idle streams

**Automatic Fallback:**
- Smart handling of empty channels
- Dead stream replacement
- Ensures channels always have working streams

---

## Continuous Quality Assessment

### Metrics Collected

**Real-time monitoring using lightweight FFmpeg:**
- **Stream Speed** - Buffering detection (< 1.0 = buffering)
- **Bitrate** - Mbps measurement
- **FPS** - Frame rate tracking
- **Resolution** - Width × height
- **Alive Status** - Stream responsive/dead

**Minimal Resource Usage:**
- FFmpeg null muxer (`-c copy -f null -`)
- Copy codec (no re-encoding)
- ~10-20MB per monitored stream

### FFmpeg Speed Graphs

Real-time visualization under each stream:
- **Speed over time** - Shows buffering events
- **Synchronized to timeline** - Updates with timeline cursor
- **Historical data** - Browse past performance
- **Color-coded** - Visual indication of quality

---

## Screenshot Capture

### Features

- **Periodic capture** - Configurable interval (default: 60s)
- **Visual verification** - Identify mismatching streams
- **Efficient storage** - One per stream, overwritten
- **Carousel display** - Scrollable, sorted by reliability

### Using Screenshots

**Quick Visual Check:**
1. View carousel at top of session
2. Browse all alive streams' screenshots
3. Look for:
   - Wrong channel/content
   - Black screens
   - Error messages
   - Quality issues

**Individual Stream:**
- Click "View" on stream row
- Opens screenshot in dialog
- Check for content accuracy

---

## Session Management

### Start/Stop

**Starting:**
- Click "Start" on session card
- Monitoring begins immediately
- Streams discovered and monitored
- Screenshots captured periodically

**Stopping:**
- Click "Stop" on session card
- Monitoring pauses
- Data preserved
- Timeline frozen at current state

### Deleting Sessions

**Delete:**
- Click "Delete" on session card
- Confirmation required
- Session and all data removed
- Screenshots cleaned up

---

## Best Practices

### Regex Filtering

- Use specific patterns to reduce monitored streams
- Examples:
  - `720p|1080p` for specific qualities
  - `.*SPORT.*` for sports streams
- Test regex patterns before creating sessions

### Resource Management

- Start sessions just before events (use pre-event timing)
- Stop sessions when events end
- Use appropriate stagger delays (200ms recommended)
- Monitor system resources when tracking many streams

### Screenshot Review

Check screenshots periodically for:
- Wrong channel/content
- Black screens
- Error messages
- Quality issues

---

## Performance Considerations

### Resource Usage

- **CPU** - Minimal (FFmpeg copy codec, no re-encoding)
- **Memory** - ~10-20MB per monitored stream
- **Disk** - Screenshots ~100KB each, metrics <1MB per session
- **Network** - Continuous stream download (AceStream/HTTP)

### Scaling

- Tested with up to 50 concurrent streams per session
- Multiple sessions can run simultaneously
- Consider system bandwidth when monitoring many streams
- Use stagger delays to prevent startup spikes

---

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

---

**See Also:**
- [Getting Started](01-getting-started.md) - Basic concepts
- [Automation Profiles](02-automation-profiles.md) - EPG-based scheduling
- [Stream Management](04-stream-management.md) - Stream quality checking
- [Stream Monitoring Documentation](../STREAM_MONITORING.md) - Detailed technical reference
