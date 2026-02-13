# Getting Started with StreamFlow

StreamFlow is an automated stream management system for Dispatcharr IPTV services, providing intelligent quality checking, automatic stream discovery, and smart stream reordering.

## Table of Contents
- [Quick Deployment](#quick-deployment)
- [Requirements](#requirements)
- [Installation](#installation)
- [First-Time Configuration](#first-time-configuration)
- [Basic Concepts](#basic-concepts)
- [Next Steps](#next-steps)

## Quick Deployment

The fastest way to get StreamFlow running:

```bash
git clone https://github.com/krinkuto11/streamflow.git
cd streamflow
cp .env.template .env
# Edit .env with your Dispatcharr instance details
docker compose up -d
```

**Access**: http://localhost:5000

## Requirements

- **Docker and Docker Compose** - Required for deployment
- **Dispatcharr Instance** - StreamFlow connects to your Dispatcharr API
- **System Resources** (recommended):
  - 2 CPU cores minimum
  - 2GB RAM minimum
  - Sufficient disk space for configuration and logs

## Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/krinkuto11/streamflow.git
cd streamflow
```

### Step 2: Configure Environment

Create your `.env` file from the template:

```bash
cp .env.template .env
```

Edit `.env` with your Dispatcharr connection details:

```env
DISPATCHARR_BASE_URL=http://your-dispatcharr-instance:9191
DISPATCHARR_USER=your-username
DISPATCHARR_PASS=your-password
DEBUG_MODE=false
API_HOST=0.0.0.0
API_PORT=5000
CONFIG_DIR=/app/data
```

**Environment Variables:**
- `DISPATCHARR_BASE_URL` - Full URL to your Dispatcharr instance (including port)
- `DISPATCHARR_USER` - Your Dispatcharr username
- `DISPATCHARR_PASS` - Your Dispatcharr password
- `DISPATCHARR_TOKEN` - Auto-populated JWT token (leave empty)
- `DEBUG_MODE` - Enable verbose logging (`true`/`false`)
- `API_HOST` - API bind address (default: `0.0.0.0`)
- `API_PORT` - API port (default: `5000`)
- `CONFIG_DIR` - Configuration directory (default: `/app/data`)

### Step 3: Deploy Container

```bash
docker compose up -d
```

### Step 4: Verify Deployment

Check that the container is running:

```bash
docker compose ps
```

View logs to confirm startup:

```bash
docker compose logs -f
```

Test the API health endpoint:

```bash
curl http://localhost:5000/api/health
```

## First-Time Configuration

### Setup Wizard

On first launch, StreamFlow presents a setup wizard to guide you through initial configuration:

1. **Dispatcharr Connection**
   - Enter your Dispatcharr URL, username, and password
   - Test the connection to verify credentials
   
2. **Channel Configuration** (optional)
   - Import regex patterns from JSON file
   - Configure channel regex patterns manually
   
3. **Automation Configuration**
   - Configure individual automation controls (see [Automation Profiles](02-automation-profiles.md))
   
4. **Schedule Configuration** (if applicable)
   - Set timing for global actions
   - Daily or monthly frequency

The wizard automatically saves settings as you proceed.

### Manual Configuration

Alternatively, configure StreamFlow via the **Configuration** page after deployment:

- Navigate to http://localhost:5000
- Go to **Configuration** in the navigation
- Adjust automation configuration, schedules, and analysis parameters

## Basic Concepts

### Channels and Streams

- **Channel**: A TV channel in Dispatcharr (e.g., ESPN, CNN)
- **Stream**: A specific stream URL providing content for a channel
- StreamFlow manages which streams are assigned to channels and their quality/order

### Stream Operations

StreamFlow performs three core operations:

1. **Playlist Updates**: Refreshes M3U playlists to discover new streams
2. **Stream Matching**: Assigns streams to channels using regex patterns or TVG-ID matching
3. **Stream Checking**: Analyzes stream quality (bitrate, resolution, FPS, codec) and reorders

### Automation Profiles

StreamFlow uses **automation profiles** to control:
- Which M3U playlists are active
- When playlists are refreshed
- Stream quality scoring weights
- Concurrent stream limits per M3U account

See [Automation Profiles](02-automation-profiles.md) for details.

### Data Storage

All configuration is stored in JSON files in the Docker volume at `/app/data`:

- `automation_config.json` - Automation settings (intervals, profiles)
- `stream_checker_config.json` - Automation configuration, scheduling, checking parameters
- `channel_regex_config.json` - Regex patterns for stream assignment
- `profile_config.json` - Channel profile configuration
- `channel_updates.json` - Channel update tracking
- `changelog.json` - Activity history
- `udi/` - Universal Data Index (channel, stream, and M3U account cache)

### Universal Data Index (UDI)

The **UDI** is StreamFlow's internal cache system:
- Reduces API calls to Dispatcharr
- Stores channel, stream, and M3U account data locally
- Automatically refreshes when playlists update
- Provides fast data access for UI and automation logic

## Next Steps

### Configure Automation

1. **Set up M3U Accounts** - Configure priorities and concurrent limits in [Automation Profiles](02-automation-profiles.md)
2. **Configure Channels** - Add regex patterns or enable TVG-ID matching in [Channel Configuration](03-channel-configuration.md)
3. **Configure Automation** - Set up automation controls in [Automation Profiles](02-automation-profiles.md)

### Monitor Streams

- **Stream Checker Dashboard**: Real-time checking status and queue monitoring
- **Changelog**: View automation history and stream changes
- **Stream Monitoring**: Create sessions to track stream quality over time (see [Monitoring](05-monitoring.md))

### Advanced Features

- **EPG-Based Scheduling**: Schedule checks before programs (see [Automation Profiles](02-automation-profiles.md#epg-based-scheduling))
- **Stream Monitoring**: Timeline-based quality tracking with screenshots (see [Monitoring](05-monitoring.md))
- **Performance Tuning**: Optimize concurrent limits and analysis params (see [Troubleshooting](06-troubleshooting.md))

## Architecture Overview

StreamFlow uses a **single-container architecture**:

- **Single Docker Container** - All services in one container
- **Flask Backend** - Python REST API (port 5000)
- **React Frontend** - Web interface served by Flask
- **Thread-Based Parallelism** - Multi-threaded stream checking
- **Persistent Storage** - Docker volume for configuration data
- **Single Port** - Everything accessible at port 5000

See [Architecture](../technical/architecture.md) for detailed technical information.

## Getting Help

- **Troubleshooting**: See [Troubleshooting Guide](06-troubleshooting.md)
- **API Reference**: See [REST API](../api/rest-api.md)
- **Debug Mode**: Enable in `.env` for verbose logging
- **Logs**: `docker compose logs -f` to view application logs

---

**See Also:**
- [Automation Profiles](02-automation-profiles.md) - Profile system and automation controls
- [Channel Configuration](03-channel-configuration.md) - Regex patterns and channel settings
- [Stream Management](04-stream-management.md) - Stream checking and quality scoring
- [Technical Architecture](../technical/architecture.md) - System design and components
