# StreamFlow for Dispatcharr
![Docker Pulls](https://ghcr-badge.elias.eu.org/shield/krinkuto11/streamflow/streamflow)

Automated stream management system for Dispatcharr IPTV services with intelligent quality checking and automatic stream reordering.
1. Updates playlists.
2. Adds Streams to channels via Regex
3. Checks streams
4. Reorders the streams to ensure the best ones are first

## Quick Deployment

```bash
git clone https://github.com/krinkuto11/streamflow.git
cd streamflow
cp .env.template .env
# Edit .env with your Dispatcharr instance details
docker compose up -d
```

**Access**: http://localhost:5000

For **local development** with hot-reload, see [DEVELOPMENT.md](DEVELOPMENT.md).

See [Deployment Guide](docs/DEPLOYMENT.md) for detailed instructions.

## Features

- **Flexible Automation Profiles**: Fine-grained control with individual automation controls, or choose from 5 convenience presets
- **Advanced Stream Monitoring**: Event-based quality tracking with reliability scoring and screenshot capture
- **Browsable Timeline**: Interactive video-editor style timeline to scrub through stream history with synchronized metrics
- **Smart Stream Protection**: Intelligent hysteresis to protect active streams while aggressively replacing idle ones
- **Parallel Stream Checking**: Thread-based parallel stream analysis with configurable worker pool
- **Per-Account Stream Limits**: Intelligent concurrent stream limiting respects M3U provider limits while maximizing parallelism
- **Channel Profile Management**: Select specific Dispatcharr profiles, manage dead streams, and use snapshots for automatic re-enabling
- **Automated M3U Playlist Management**: Refresh playlists every 5 minutes (configurable)
- **Stream Quality Checking**: Analyze streams for bitrate, resolution, FPS, codec quality, and errors
- **Automatic Stream Reordering**: Best quality streams moved to the top
- **Stream Discovery**: Regex patterns for automatic stream-to-channel assignment
- **Mass Regex Assignment**: Add a single regex pattern to multiple channels at once with support for channel name variables
- **Global Action**: Manual or scheduled complete update cycles (Update → Match → Check all channels)
- **Channel-Specific Settings**: Exclude individual channels from matching and/or checking operations
- **EPG-Based Scheduling**: Schedule channel checks based on EPG program data
- **JSON-backed Storage**: Fast, file-based data access with UDI (Universal Data Index)
- **Web Interface**: React-based UI with unified configuration page and real-time monitoring
- **REST API**: Full API access for all operations

## Architecture

**Single Docker container** with:
- Flask backend (Python) serving REST API
- React frontend for web interface
- Persistent configuration storage via Docker volumes
- Single port (5000) for all web access
- Multi-platform support: linux/amd64, linux/arm64

The Flask API runs directly as PID 1 in the container for simplified deployment.

## Configuration

All configuration stored in JSON files in `/app/data` (Docker volume):
- `automation_config.json` - Automation settings (intervals, features)
- `stream_checker_config.json` - Pipeline mode, scheduling, and stream checking parameters
- `channel_regex_config.json` - Regex patterns for stream assignment
- `profile_config.json` - Channel profile configuration and snapshots
- `channel_updates.json` - Channel update tracking
- `changelog.json` - Activity history

**Web UI**: Navigate to the **Configuration** page (formerly "Automation Settings") to:
- Configure individual automation controls or select a preset pattern (determines when and how streams are checked)
- Configure scheduled global actions
- Adjust update intervals and analysis settings

**Stream Checker**: View real-time statistics, progress, and manually trigger global actions

## Project Structure

```
backend/
  ├── automated_stream_manager.py    # Core automation engine
  ├── stream_checker_service.py      # Stream quality checking
  ├── web_api.py                      # Flask REST API
  ├── api_utils.py                    # Dispatcharr API utilities
  └── ...
frontend/
  └── src/
      ├── components/                 # React components
      └── services/                   # API client
docs/
  ├── DEPLOYMENT.md                   # Detailed deployment guide
  ├── API.md                          # API documentation
  └── FEATURES.md                     # Feature details
```

## Documentation

### User Guides
- [Getting Started](docs/user-guide/01-getting-started.md) - Installation and first-time configuration
- [Automation Profiles](docs/user-guide/02-automation-profiles.md) - M3U accounts, automation configuration, and scheduling
- [Channel Configuration](docs/CHANNEL_CONFIGURATION_FEATURES.md) - Channel management and regex patterns
- [Stream Management](docs/FEATURES.md) - Stream checking and quality scoring
- [Stream Monitoring](docs/STREAM_MONITORING.md) - Advanced stream quality monitoring
- [Channel Profiles](docs/CHANNEL_PROFILES_FEATURE.md) - Profile management and dead stream handling

### Technical Documentation
- [Deployment Guide](docs/DEPLOYMENT.md) - Installation and deployment instructions
- [Pipeline System](docs/PIPELINE_SYSTEM.md) - Automation configuration and controls
- [Concurrent Stream Limits](docs/CONCURRENT_STREAM_LIMITS.md) - Per-account stream limiting
- [Debug Mode Guide](docs/DEBUG_MODE.md) - Troubleshooting with enhanced logging

### API Reference
- [REST API Documentation](docs/API.md) - Complete API reference
- [Changelog](docs/CHANGELOG.md) - Version history and updates

For the full documentation index, see [docs/README.md](docs/README.md).

## Requirements

- Docker and Docker Compose
- Dispatcharr instance with API access
- Sufficient resources for parallel stream checking (recommended: 2 CPU cores, 2GB RAM minimum)

## Performance Notes

### Stream Matching Performance

If you experience slow performance during **stream matching and assignment** (e.g., during manual health checks or global actions):

- **This is normal for large M3U playlists** (thousands of streams) with many regex patterns
- **GPU acceleration will NOT help** - Stream matching performs regex pattern matching which is a CPU-bound text processing task, not video processing
- **Progress is logged** - Check the logs to see processing status (progress updates shown periodically during processing)
- **To improve performance:**
  - Reduce the number of enabled M3U accounts in your configuration
  - Simplify or reduce the number of regex patterns
  - Disable matching for channels that don't need it (channel-level or group-level settings)
  
### Stream Quality Checking Performance

Stream quality checking uses ffmpeg to analyze video streams. Hardware acceleration is NOT currently implemented but could be added in future versions.

### M3U Priority

The priority system uses values from 0-100:
- **Higher numbers = Higher priority** (e.g., priority=100 for your preferred source, priority=1 for fallbacks)
- See [FEATURES.md](docs/FEATURES.md) for detailed priority mode documentation

## License

See [LICENSE](LICENSE) file for details.
