# Stream Management

This guide covers stream quality checking, scoring, reordering, dead stream handling, and concurrent stream limits.

## Table of Contents
- [Stream Quality Checking](#stream-quality-checking)
- [Quality Scoring](#quality-scoring)
- [Stream Reordering](#stream-reordering)
- [Dead Stream Management](#dead-stream-management)
- [Stream Limits](#stream-limits)

## Stream Quality Checking

StreamFlow analyzes stream quality using FFmpeg to measure technical characteristics and identify the best streams.

### What Gets Analyzed

**Multi-factor analysis using a single optimized FFmpeg call:**
- **Bitrate** - Average kbps measurement
- **Resolution** - Width × height detection  
- **Frame Rate** - FPS analysis
- **Video Codec** - H.265/H.264 identification with automatic sanitization
- **Audio Codec** - Detection and validation (input stream codecs only)
- **Error Detection** - Decode errors, discontinuities, timeouts
- **HDR Format** - HDR10, HLG, Dolby Vision detection

### Checking Modes

**Parallel Mode** (default):
- Thread-based concurrent analysis
- Configurable worker pool (default: 10)
- Per-account stream limits respected
- Stagger delay to prevent simultaneous starts
- Robust pipeline: stats gathered in parallel, pushed after ALL checks complete

**Sequential Mode**:
- One stream at a time
- Minimal provider load
- Queue-based processing
- Real-time progress tracking

### 2-Hour Immunity System

Streams are tracked per channel to prevent excessive checking:
- Each stream's last check timestamp stored
- Only unchecked streams (or those not checked in 2 hours) analyzed
- Recently checked streams use cached quality scores
- **Force check bypasses immunity** (used in Global Actions)

### Per-Account Stream Limits

StreamFlow respects maximum concurrent streams for each M3U account:

**Smart Scheduler:**
- Account A (limit: 1), Account B (limit: 2) with streams A1, A2, B1, B2, B3
- **Concurrently checks**: A1, B1, B2 (3 total, respecting limits)
- When A1 completes, A2 starts
- When B1/B2 completes, B3 starts

See [Automation Profiles](02-automation-profiles.md#m3u-accounts-and-profiles) for M3U account configuration.

---

## Quality Scoring

Stream quality scores determine stream order in channels.

### Scoring Formula

```
Total Score = (Bitrate × W1) + (Resolution × W2) + (FPS × W3) + (Codec × W4) + (HDR × W5)
```

### Default Weights

```json
{
  "weights": {
    "bitrate": 0.35,      // 35%
    "resolution": 0.30,   // 30%
    "fps": 0.15,          // 15%
    "codec": 0.10,        // 10%
    "hdr": 0.10           // 10%
  }
}
```

### Per-Profile Weights

Automation profiles can override global scoring weights:
- Configure custom weights for each profile
- Different priorities for different use cases
- Example: Sports profile prioritizes FPS, Movies profile prioritizes bitrate

### Component Scores

**Bitrate Score** (0-1):
- Normalized to typical range 1000-8000 kbps
- Higher bitrate = higher score
- Capped at 1.0 for 8000+ kbps

**Resolution Score** (0-1):
- Based on vertical resolution
- 2160p (4K): 1.0
- 1080p (FHD): 0.75
- 720p (HD): 0.50
- 576p (SD): 0.35
- 480p: 0.25

**FPS Score** (0-1):
- Based on frame rate
- 60 FPS: 1.0
- 50 FPS: 0.90
- 30 FPS: 0.70
- 25 FPS: 0.65
- 24 FPS: 0.60

**Codec Score** (0-1):
- H.265/HEVC: 1.0 (if prefer_h265 enabled)
- H.264/AVC: 0.8
- Other codecs: 0.5
- Interlaced penalty: -0.2

**HDR Score** (0-1):
- HDR10: 1.0
- HLG: 0.9
- Dolby Vision: 1.0
- SDR: 0.0

### Codec Preferences

**H.265 Preference:**
- Configurable via `prefer_h265` setting
- When enabled: H.265 scores higher than H.264
- When disabled: H.265 and H.264 score equally

**Interlaced Penalty:**
- Interlaced content scores lower
- Encourages progressive scan streams

### M3U Priority Integration

StreamFlow considers M3U account priority when scoring:

**Priority Modes:**
- **Disabled** - Priority ignored, pure quality scoring
- **Same Resolution Only** - Priority within resolution groups
- **All Streams** - Priority always considered

**How It Works:**
- Higher priority accounts get score boost
- Ensures preferred sources selected when quality similar
- Configurable per account or globally

See [Automation Profiles](02-automation-profiles.md#m3u-priority-system) for priority configuration.

---

## Stream Reordering

Best quality streams automatically moved to top based on scores.

### Automatic Reordering

**When It Happens:**
- After stream quality checking
- During global actions
- After single channel checks

**How It Works:**
1. All streams in channel scored
2. Streams sorted by score (descending)
3. Dead streams removed
4. Top N streams kept (if stream limit configured)
5. Channel updated in Dispatcharr with new order

### Manual Reordering

Streams can also be manually reordered in Dispatcharr:
- Manual order preserved until next quality check
- Quality checking will reorder based on scores
- Disable checking for channel to preserve manual order

### Stream Limit per Channel

Limit the number of streams kept per channel:

**Configuration:**
- Set `stream_limit` in profile settings
- `0` = Unlimited (keep all streams)
- `N` = Keep top N streams only

**How It Works:**
1. All streams (cached + newly analyzed) scored
2. Combined list sorted by score
3. Top N streams kept
4. Lower-scoring streams removed

**Benefits:**
- Reduces clutter in channels
- Improves performance (fewer streams to check)
- Focuses on best quality streams

---

## Dead Stream Management

StreamFlow automatically detects and manages non-functional streams.

### Detection Criteria

A stream is "dead" if:
- Resolution is 0×0 or contains a 0 dimension (e.g., 1920×0)
- Bitrate is 0 kbps or null

### Tagging

Dead streams are tagged with `[DEAD]` prefix:
- Original: "CNN HD"
- Tagged: "[DEAD] CNN HD"

### Automation Behavior

**With Auto Quality Checking Enabled:**
- Dead streams detected during regular checks
- Immediately tagged with `[DEAD]`
- **Removed from channels** to maintain quality
- Won't be re-added during stream matching

**Without Auto Quality Checking:**
- No regular detection
- Dead streams only detected during global actions (if enabled)

### Revival During Global Actions

During global actions, dead streams get a second chance:

1. All streams (including dead) re-analyzed
2. If dead stream is now working:
   - `[DEAD]` prefix removed
   - Stream restored to normal status
   - Can be matched to channels again
3. If still dead, tag remains

**Example:**
```
Before: "[DEAD] CNN HD" (resolution: 0×0, bitrate: 0)
After:  "CNN HD" (resolution: 1920×1080, bitrate: 5000)
```

### Stream Matching Exclusion

Dead streams excluded from discovery:
- Regex patterns skip streams with `[DEAD]` prefix
- Prevents dead streams from being added to new channels
- Ensures only functional streams assigned

### Monitoring

Dead stream activity logged in changelog:
- Detection and tagging events
- Removal from channels
- Revival events during global actions

View dead streams via:
- Changelog page in web UI
- Dispatcharr stream list (search for `[DEAD]`)
- Stream checker logs

---

## Stream Limits

### Concurrent Stream Limits

**Per-Account Limits:**
- Set maximum concurrent streams for each M3U account
- System ensures limits never exceeded
- Multiple accounts can check streams in parallel

**Per-Profile Limits:**
- Each profile within an account has its own limit
- System tracks usage per profile
- Selects available profile for new streams

See [Automation Profiles](02-automation-profiles.md#concurrent-stream-limiting) for detailed concurrent limit information.

### Stream Limit per Channel

**Purpose:**
- Limit number of streams kept per channel
- Keep only top N highest-quality streams

**Configuration:**
```json
{
  "stream_limit": 5  // Keep top 5 streams per channel, 0 = unlimited
}
```

**UI Text:**
- "0 = Unlimited (Keep All Streams)"

**Behavior:**
1. All streams scored (cached + newly analyzed)
2. Combined list sorted by score
3. Top N streams retained
4. Lower-scoring streams removed
5. HDR data persisted for accurate cached stream scoring

---

## Configuration

### Via Web UI

1. Navigate to **Configuration** page
2. Adjust **Stream Analysis Parameters**:
   - FFmpeg duration (seconds to analyze)
   - Base timeout
   - Stream startup buffer (5-120s, default: 10s)
   - Retry attempts and delay
   - User agent string
3. Configure **Concurrent Stream Checking**:
   - Maximum parallel workers (default: 10)
   - Stagger delay between dispatches
4. Set **Scoring Weights** in automation profile
5. Click **Save Settings**

###

 Via Configuration File

Edit `/app/data/stream_checker_config.json`:
```json
{
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
    "retry_delay_seconds": 5
  }
}
```

Edit `/app/data/automation_config.json` for scoring weights:
```json
{
  "profiles": [
    {
      "scoring_weights": {
        "bitrate": 0.35,
        "resolution": 0.30,
        "fps": 0.15,
        "codec": 0.10,
        "hdr": 0.10,
        "prefer_h265": true
      }
    }
  ]
}
```

---

**See Also:**
- [Getting Started](01-getting-started.md) - Basic concepts
- [Automation Profiles](02-automation-profiles.md) - M3U accounts, profiles, pipelines
- [Channel Configuration](03-channel-configuration.md) - Channel and pattern setup
- [Monitoring](05-monitoring.md) - Advanced stream quality monitoring
- [Troubleshooting](06-troubleshooting.md) - Performance optimization
