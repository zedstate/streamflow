# Troubleshooting

This guide covers common issues, debug mode, performance optimization, and helpful troubleshooting tips.

## Table of Contents
- [Debug Mode](#debug-mode)
- [Common Issues](#common-issues)
- [Performance Optimization](#performance-optimization)
- [Logs and Diagnostics](#logs-and-diagnostics)

## Debug Mode

Enable enhanced logging for troubleshooting.

### Enabling Debug Mode

**Via Web UI:**
1. Navigate to **Configuration** page
2. Toggle **Enable Debug Mode**
3. Click **Save Settings**
4. Debug logging activates immediately

**Via Configuration File:**
```json
{
  "debug_mode": true
}
```

### What Debug Mode Logs

**Enhanced Logging:**
- FFmpeg command execution details
- Stream analysis parameters
- Codec detection process
- Error stack traces
- API request/response details
- Regex pattern matching details

### Viewing Debug Logs

**Docker Logs:**
```bash
docker logs streamflow
docker logs streamflow -f  # follow mode
docker logs streamflow --tail 100  # last 100 lines
```

**Logs Location:**
- Container: `/app/logs/`
- Host (if volume mounted): Configured volume path

---

## Common Issues

### Setup Wizard Not Advancing

**Symptoms:**
- Complete setup wizard but stay on wizard page
- Main application doesn't load

**Solutions:**
1. Check backend logs for API errors
2. Clear browser cache and reload
3. Verify setup completion via API:
   ```bash
   curl http://localhost:5000/api/setup/status
   ```
4. Manually mark setup complete:
   ```bash
   curl -X POST http://localhost:5000/api/setup/complete
   ```

### Streams Not Being Matched

**Symptoms:**
- M3U playlist loaded but streams not appearing in channels
- No streams matched despite regex patterns

**Check:**
1. **Auto Stream Matching Enabled:**
   - Configuration → Automation Controls
   - Ensure "Automatic Stream Matching" is enabled

2. **Channel Has Matching Enabled:**
   - Channel Configuration → Regex Configuration
   - Check dropdown menu (⋮) for channel
   - Verify "Stream Matching" toggle is ON

3. **Regex Patterns Correct:**
   - View/Edit Regex Rules for channel
   - Use live preview to test patterns
   - Check for typos or incorrect regex syntax

4. **Channel Group Not Disabled:**
   - Channel Configuration → Group Management
   - Verify group has "Stream Matching" enabled

### Streams Not Being Checked

**Symptoms:**
- Streams matched but never analyzed for quality
- No quality scores appearing

**Check:**
1. **Auto Quality Checking Enabled:**
   - Configuration → Automation Controls
   - Ensure "Automatic Quality Checking" is enabled

2. **Channel Has Checking Enabled:**
   - Channel Configuration → Regex Configuration
   - Check channel's dropdown menu
   - Verify "Stream Checking" toggle is ON

3. **Channel Group Not Disabled:**
   - Channel Configuration → Group Management
   - Verify group has "Stream Checking" enabled

4. **2-Hour Immunity:**
   - Streams only checked every 2 hours by default
   - Use "Check Single Channel" for immediate check
   - Or trigger Global Action to force check all

### Channels Not Appearing in UI

**Symptoms:**
- Channels exist in Dispatcharr but don't show in StreamFlow
- Channel list empty or incomplete

**Solutions:**
1. **UDI Sync:** Wait for UDI to sync from Dispatcharr (happens automatically)
2. **Group Settings:** Check if channel's group has both matching AND checking disabled
3. **Refresh:** Reload page or restart StreamFlow container

### M3U Playlist Not Updating

**Symptoms:**
- New streams not appearing from M3U source
- Playlist update time not changing

**Check:**
1. **Auto M3U Updates Enabled:**
   - Configuration → Automation Controls
   - Ensure "Automatic M3U Updates" is enabled

2. **Update Interval:**
   - Check `playlist_update_interval_minutes`
   - Default is 60 minutes, verify it's not too long

3. **M3U URL Accessible:**
   - Test URL in browser
   - Check for authentication issues
   - Verify URL format is correct

4. **Manual Update:**
   - Trigger manual M3U update via UI
   - Check logs for error messages

### Regex Patterns Not Matching

**Symptoms:**
- Patterns configured but no streams matched
- Live preview shows no matches

**Solutions:**
1. **Test with Live Preview:**
   - Open regex editor for channel
   - Add pattern
   - Check matched streams in real-time

2. **Check Special Characters:**
   - Channel names with `+`, `.`, `*` are auto-escaped
   - Verify CHANNEL_NAME substitution working

3. **Whitespace:**
   - System auto-converts spaces to `\s+`
   - Try pattern without strict whitespace

4. **Case Sensitivity:**
   - Patterns are case-sensitive by default
   - Use `(?i)` flag for case-insensitive: `(?i).*espn.*`

### Dead Streams Multiplying

**Symptoms:**
- Many streams tagged with `[DEAD]`
- Dead count increasing

**Causes:**
- Providers removing or changing streams
- Temporary provider outages
- Network connectivity issues

**Solutions:**
1. **Global Action:** Run Global Action to:
   - Re-analyze all streams
   - Remove confirmed dead streams
   - Revive working streams

2. **Disable Auto Checking:**
   - For channels with unreliable providers
   - Prevents excessive dead stream detection

3. **Manual Cleanup:**
   - Remove dead streams via Dispatcharr
   - Or wait for next global action to clean up

### High CPU or Memory Usage

See [Performance Optimization](#performance-optimization) below.

---

## Performance Optimization

### Concurrent Stream Checking

**Reduce Workers:**
- Default: 10 concurrent workers
- Lower for weak systems: 5-8 workers
- Configuration → Concurrent Stream Checking

**Increase Stagger Delay:**
- Default: 200ms between stream dispatches
- Increase to 500-1000ms for weak systems
- Reduces simultaneous FFmpeg processes

### Stream Analysis Duration

**Reduce Analysis Time:**
- Default: 10 seconds per stream
- Lower to 5-8 seconds for faster checking
- Trade-off: less accurate quality metrics

**Configuration:**
```json
{
  "stream_analysis": {
    "duration_seconds": 5  // Faster but less accurate
  }
}
```

### Stream Limits

**Per-Channel Limit:**
- Set `stream_limit` in automation profile
- Example: Keep top 5 streams only
- Reduces total streams to check

**Benefits:**
- Fewer streams = less checking needed
- Lower resource usage
- Faster automation cycles

### Disable Unused Features

**If Not Needed:**
- Disable Auto Quality Checking (manual checks only)
- Disable Auto Stream Matching (manual matching only)
- Set longer playlist update intervals

**Configuration:**
```json
{
  "automation_controls": {
    "auto_quality_checking": false,  // Disable if not needed
    "auto_stream_matching": false    // Disable if not needed
  },
  "playlist_update_interval_minutes": 180  // 3 hours instead of 1
}
```

### Monitor Resource Usage

**Docker Stats:**
```bash
docker stats streamflow
```

**Output shows:**
- CPU usage percentage
- Memory usage and limit
- Network I/O
- Disk I/O

**Healthy Ranges:**
- CPU: <50% average (spikes during checking normal)
- Memory: <512MB (depends on stream count)

---

## Logs and Diagnostics

### Backend Logs

**View Logs:**
```bash
# All logs
docker logs streamflow

# Follow logs (real-time)
docker logs streamflow -f

# Last 100 lines
docker logs streamflow --tail 100

# Logs since timestamp
docker logs streamflow --since 2024-01-01T00:00:00
```

**Key Log Sections:**
- `[STREAM_CHECKER]` - Quality checking activity
- `[AUTOMATION]` - Automation pipeline events
- `[M3U_MANAGER]` - Playlist updates
- `[UDI]` - Dispatcharr sync
- `[API]` - API request/response
- `[ERROR]` - Error messages

### Frontend Logs

**Browser Console:**
1. Open browser DevTools (F12)
2. Go to Console tab
3. Look for errors or warnings

**Common Errors:**
- API connection failures
- CORS issues
- JavaScript errors

### Configuration Files

**Location:**
- `/app/data/stream_checker_config.json` - Main configuration
- `/app/data/automation_config.json` - Automation profiles
- `/app/data/group_settings.json` - Group settings
- `/app/data/m3u_accounts.json` - M3U accounts

**Backup:**
```bash
# Backup all configs
docker cp streamflow:/app/data ./streamflow-backup
```

**Restore:**
```bash
# Restore configs
docker cp ./streamflow-backup/. streamflow:/app/data/
docker restart streamflow
```

### Health Checks

**API Health:**
```bash
curl http://localhost:5000/api/health
```

**Dispatcharr Connectivity:**
```bash
curl http://localhost:5000/api/dispatcharr/status
```

**UDI Status:**
```bash
curl http://localhost:5000/api/udi/status
```

---

## Getting Help

### Before Reporting Issues

1. **Enable Debug Mode** and reproduce issue
2. **Collect logs** (last 100-200 lines)
3. **Note exact error messages**
4. **Document steps to reproduce**
5. **Check configuration** for typos

### Information to Provide

When reporting issues, include:
- StreamFlow version
- Docker/host OS version
- Configuration (redact sensitive data)
- Error logs
- Steps to reproduce
- Expected vs actual behavior

### Resources

- **GitHub Issues**: https://github.com/krinkuto11/streamflow/issues
- **Documentation**: See other user guides and technical docs
- **Logs**: `docker logs streamflow`

---

**See Also:**
- [Getting Started](01-getting-started.md) - Basic concepts and setup
- [Automation Profiles](02-automation-profiles.md) - Pipeline configuration
- [Stream Management](04-stream-management.md) - Quality checking details
- [Debug Mode Documentation](../DEBUG_MODE.md) - Detailed debug mode reference
