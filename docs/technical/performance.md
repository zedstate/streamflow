# Performance

This document covers performance considerations, optimization techniques, resource management, and scaling strategies for StreamFlow.

## Table of Contents
- [Resource Requirements](#resource-requirements)
- [Optimization Techniques](#optimization-techniques)
- [Concurrent Checking](#concurrent-checking)
- [Memory Management](#memory-management)
- [Scaling Strategies](#scaling-strategies)

## Resource Requirements

### Minimum Requirements

**System:**
- CPU: 2 cores
- RAM: 2GB
- Disk: 10GB available
- Network: Stable broadband connection

**For Basic Usage:**
- Up to 50 channels
- Up to 500 streams
- Sequential checking mode
- Minimal monitoring sessions

### Recommended Requirements

**System:**
- CPU: 4+ cores
- RAM: 4GB+
- Disk: 20GB+ SSD
- Network: 100+ Mbps

**For Production Use:**
- 100+ channels
- 1000+ streams
- Concurrent checking mode (10+ workers)
- Multiple monitoring sessions

### Resource Usage by Feature

| Feature                         | CPU     | Memory   | Disk             | Network |
| ------------------------------- | ------- | -------- | ---------------- | ------- |
| Stream Checking (per stream)    | Low     | 10-20MB  | Minimal          | High    |
| M3U Updates                     | Low     | <50MB    | Minimal          | Medium  |
| Stream Monitoring (per session) | Low     | 50-100MB | 100KB/screenshot | High    |
| Screenshot Capture              | Medium  | <50MB    | 100KB/image      | Low     |
| Web UI                          | Minimal | <100MB   | Minimal          | Low     |

---

## Optimization Techniques

### Stream Analysis Duration

**Configuration:**
```json
{
  "stream_analysis": {
    "duration_seconds": 10  // Reduce to 5-8 for faster checking
  }
}
```

**Trade-offs:**
- **Lower** (5-8s): Faster checks, less accurate
- **Higher** (10-15s): Slower checks, more accurate

**Recommendation:**
- Development/testing: 5s
- Production: 10s
- High-accuracy needs: 15s

### Concurrent Workers

**Configuration:**
```json
{
  "concurrent_streams": {
    "max_workers": 10,  // Adjust based on CPU cores
    "stagger_delay_ms": 200
  }
}
```

**Sizing Guidelines:**
- **Weak systems** (2 cores): 3-5 workers
- **Medium systems** (4 cores): 8-10 workers
- **Strong systems** (8+ cores): 15-20 workers

**Formula:**
```
max_workers = (CPU_cores × 2) - 2
```

### Stream Limits

**Per-Channel Limit:**
```json
{
  "profiles": [{
    "stream_limit": 5  // Keep only top 5 streams
  }]
}
```

**Benefits:**
- Fewer streams = less checking needed
- Reduced memory usage
- Faster automation cycles
- Lower provider load

**Recommendation:**
- Sports/News: 5-10 streams
- Movies/Shows: 3-5 streams
- Low-priority channels: 1-3 streams

### Update Intervals

**Configuration:**
```json
{
  "playlist_update_interval_minutes": 60,
  "check_interval_minutes": 120,
  "automation_check_interval": 60
}
```

**Optimization:**
- Increase intervals for stable providers
- Decrease intervals for dynamic content
- Disable unused automation features

---

## Concurrent Checking

### Architecture

**Thread Pool:**
```python
class StreamCheckerService:
    def __init__(self):
        self.max_workers = 10
        self.worker_threads = []
        self.channel_queue = Queue()
```

**Worker Lifecycle:**
1. Wait for channel from queue
2. Fetch channel streams from UDI
3. Analyze streams (respecting account limits)
4. Calculate scores and reorder
5. Update Dispatcharr
6. Return to step 1

### Account-Based Limiting

**Smart Scheduling:**
```python
# Account A: limit 1, Account B: limit 2
# Streams: A1, A2, B1, B2, B3

# Concurrent checks:
# - A1 (Account A: 1/1)
# - B1 (Account B: 1/2)
# - B2 (Account B: 2/2)

# When A1 completes:
# - A2 starts (Account A: 1/1)

# When B1 completes:
# - B3 starts (Account B: 2/2)
```

**Implementation:**
```python
def _get_available_profile(self, m3u_account_id):
    # Get account and profiles
    # Check concurrent usage per profile
    # Return first profile with available slots
    # If none available, wait/queue
```

### Stagger Delay

**Purpose:** Prevent simultaneous FFmpeg process starts

**Configuration:**
```json
{
  "concurrent_streams": {
    "stagger_delay_ms": 200  // Delay between dispatches
  }
}
```

**Impact:**
- **Lower** (50-100ms): Faster dispatch, higher CPU spike
- **Higher** (500-1000ms): Slower dispatch, smoother CPU usage

**Recommendation:**
- Fast systems: 100-200ms
- Weak systems: 500-1000ms

---

## Memory Management

### FFmpeg Process Management

**Memory per Stream:**
- FFmpeg process: ~10-20MB
- Stream buffers: ~5-10MB
- Total per stream: ~15-30MB

**With 10 workers:**
- Memory usage: ~150-300MB

**Optimization:**
- Use copy codec (`-c copy`) - no re-encoding
- Null muxer (`-f null`) - no file output
- Timeout enforcement - kill hung processes

### UDI Caching

**Memory Usage:**
- Channels: ~1KB per channel
- Streams: ~500B per stream
- Groups: ~200B per group

**Example:**
- 100 channels × 10 streams = 1000 streams
- Memory: 100KB + 500KB + 20KB = ~620KB

**Benefits:**
- Minimal memory footprint
- Fast data access
- Reduced API calls

### Screenshot Storage

**Disk Usage:**
- One screenshot per stream (overwritten)
- Average size: ~100KB per screenshot
- Example: 50 streams = 5MB

**Cleanup:**
- Old screenshots auto-deleted after 24 hours
- Configurable retention period

---

## Scaling Strategies

### Horizontal Scaling

**Multi-Instance Deployment:**
- Run multiple StreamFlow instances
- Each managing subset of channels
- Load balancer for web UI

**Benefits:**
- Distribute load across servers
- Improved fault tolerance
- Higher throughput

**Considerations:**
- Shared Dispatcharr instance
- No shared state between instances
- Coordinate to avoid duplicate checking

### Vertical Scaling

**Resource Upgrades:**
- More CPU cores → more concurrent workers
- More RAM → more monitoring sessions
- Faster disk → better I/O performance

**Guidelines:**
```
| Channels | Workers | CPU | RAM   |
| -------- | ------- | --- | ----- |
| <50      | 5       | 2   | 2GB   |
| 50-100   | 10      | 4   | 4GB   |
| 100-200  | 15      | 6   | 6GB   |
| 200-500  | 20      | 8   | 8GB   |
| 500+     | 25+     | 12+ | 12GB+ |
```

### Database Migration (Future)

**Current:** JSON file persistence
**Consideration:** PostgreSQL/MySQL for large deployments

**Benefits:**
- Better concurrency
- ACID transactions
- Query optimization
- Horizontal scaling support

**When to Consider:**
- 500+ channels
- Multiple instances
- High write frequency
- Complex queries needed

---

## Performance Monitoring

### Docker Stats

**Command:**
```bash
docker stats streamflow
```

**Metrics:**
- CPU % - Should average <50%, spikes OK during checking
- Memory - Should stay within limits (2-8GB typical)
- Network I/O - High during stream checking
- Disk I/O - Low except during M3U updates

### Application Logs

**Performance Indicators:**
```bash
# Check cycle times
docker logs streamflow | grep "Channel check completed"

# Find slow streams
docker logs streamflow | grep "timeout"

# Memory warnings
docker logs streamflow | grep -i "memory"
```

### Health Endpoints

**API Health:**
```bash
curl http://localhost:5000/api/health
```

**Response:**
```json
{
  "status": "healthy",
  "uptime_seconds": 86400,
  "active_workers": 8,
  "queued_channels": 5
}
```

---

## Troubleshooting Performance Issues

### High CPU Usage

**Symptoms:**
- CPU consistently >80%
- System slowdown
- Lag in web UI

**Solutions:**
1. Reduce concurrent workers
2. Increase stagger delay
3. Reduce stream analysis duration
4. Disable unused automation features

### High Memory Usage

**Symptoms:**
- Memory consistently near limit
- OOM errors
- Container restarts

**Solutions:**
1. Reduce monitoring sessions
2. Limit streams per channel
3. Reduce concurrent workers
4. Increase Docker memory limit

### Slow Stream Checking

**Symptoms:**
- Checks taking too long
- Queues building up
- Timeouts

**Solutions:**
1. Increase concurrent workers
2. Reduce stream analysis duration
3. Check network bandwidth
4. Review provider response times

### Disk Space Issues

**Symptoms:**
- Disk full errors
- Failed log writes
- Screenshot errors

**Solutions:**
1. Clean up old screenshots
2. Rotate/archive logs
3. Increase disk allocation
4. Move data to larger volume

---

**See Also:**
- [Architecture](architecture..md) - System components
- [Automation System](automation-system.md) - Automation implementation
- [Storage](storage.md) - Data persistence
- [User Guide: Troubleshooting](../user-guide/06-troubleshooting.md) - User-facing troubleshooting
