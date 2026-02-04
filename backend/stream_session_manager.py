"""
Advanced Stream Session Manager

Manages event-based stream monitoring sessions with quality testing,
continuous monitoring, and reliability scoring using a Capped Sliding Window algorithm.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from collections import deque
import re

from logging_config import setup_logging
from udi import get_udi_manager

logger = setup_logging(__name__)

# Configuration constants
CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', '/app/data'))
SESSION_CONFIG_FILE = CONFIG_DIR / 'stream_session_config.json'
SESSION_DATA_FILE = CONFIG_DIR / 'stream_session_data.json'

# Session defaults
DEFAULT_PRE_EVENT_MINUTES = 30
DEFAULT_STAGGER_MS = 200
DEFAULT_TIMEOUT_MS = 30000
DEFAULT_PROBE_INTERVAL_MS = 300000
DEFAULT_SCREENSHOT_INTERVAL_SECONDS = 60
DEFAULT_WINDOW_SIZE = 100  # For Capped Sliding Window
DEFAULT_MAX_SCORE = 100.0
DEFAULT_MIN_SCORE = 0.0

# Pre-compiled regex pattern for whitespace conversion (consistent with AutomatedStreamManager)
_WHITESPACE_PATTERN = re.compile(r'(?<!\\) +')


@dataclass
class StreamMetrics:
    """Metrics for a single stream at a point in time"""
    timestamp: float
    speed: float
    bitrate: float
    fps: float
    is_alive: bool
    buffering: bool = False
    

@dataclass
class StreamInfo:
    """Information about a monitored stream"""
    stream_id: int
    url: str
    name: str
    channel_id: int
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    bitrate: Optional[int] = None
    m3u_account: Optional[str] = None
    is_quarantined: bool = False
    reliability_score: float = 50.0  # Start at middle score
    metrics_history: List[StreamMetrics] = None
    last_screenshot_time: float = 0
    screenshot_path: Optional[str] = None
    # Low speed tracking for auto-quarantine
    low_speed_start_time: Optional[float] = None  # When speed first dropped below threshold
    
    def __post_init__(self):
        if self.metrics_history is None:
            self.metrics_history = []


@dataclass
class SessionInfo:
    """Information about a monitoring session"""
    session_id: str
    channel_id: int
    channel_name: str
    regex_filter: str
    created_at: float
    is_active: bool
    pre_event_minutes: int = DEFAULT_PRE_EVENT_MINUTES
    stagger_ms: int = DEFAULT_STAGGER_MS
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    probe_interval_ms: int = DEFAULT_PROBE_INTERVAL_MS
    screenshot_interval_seconds: int = DEFAULT_SCREENSHOT_INTERVAL_SECONDS
    window_size: int = DEFAULT_WINDOW_SIZE
    streams: Dict[int, StreamInfo] = None
    # EPG event attachment
    epg_event_id: Optional[int] = None
    epg_event_title: Optional[str] = None
    epg_event_start: Optional[str] = None
    epg_event_end: Optional[str] = None
    epg_event_description: Optional[str] = None
    # Channel logo
    channel_logo_url: Optional[str] = None
    channel_tvg_id: Optional[str] = None
    # Auto-creation source (for tracking if created by rules)
    auto_created: bool = False
    auto_create_rule_id: Optional[str] = None
    
    def __post_init__(self):
        if self.streams is None:
            self.streams = {}


class CappedSlidingWindow:
    """
    Capped Sliding Window algorithm for stream reliability scoring.
    
    Maintains a fixed-size window of recent measurements and calculates
    a reliability score that avoids large variance to minimize stream
    changes in Dispatcharr.
    """
    
    def __init__(self, window_size: int = DEFAULT_WINDOW_SIZE, 
                 max_score: float = DEFAULT_MAX_SCORE,
                 min_score: float = DEFAULT_MIN_SCORE):
        self.window_size = window_size
        self.max_score = max_score
        self.min_score = min_score
        self.measurements = deque(maxlen=window_size)
        
    def add_measurement(self, is_healthy: bool, speed: float = 1.0):
        """
        Add a measurement to the window.
        
        Args:
            is_healthy: Whether the stream is healthy (alive and not buffering)
            speed: Stream speed (1.0 is normal, <1.0 indicates buffering)
        """
        # Calculate health score for this measurement
        # Healthy stream with good speed = 1.0
        # Unhealthy or buffering = 0.0
        if not is_healthy:
            score = 0.0
        elif speed < 0.9:  # Buffering threshold
            score = 0.3  # Partial score for alive but buffering
        else:
            # Give partial credit based on speed
            score = min(1.0, speed)
            
        self.measurements.append(score)
        
    def get_score(self) -> float:
        """
        Calculate reliability score from the sliding window.
        
        Returns a score between min_score and max_score with limited variance.
        """
        if not self.measurements:
            return (self.max_score + self.min_score) / 2  # Neutral score
            
        # Calculate average health from measurements
        avg_health = sum(self.measurements) / len(self.measurements)
        
        # Apply dampening to reduce variance
        # Use exponential scaling to make changes gradual
        dampened_score = (avg_health ** 1.5) * (self.max_score - self.min_score) + self.min_score
        
        # Clamp to range
        return max(self.min_score, min(self.max_score, dampened_score))


class StreamSessionManager:
    """
    Manages advanced stream monitoring sessions.
    
    This class handles:
    - Session lifecycle (create, start, stop)
    - Stream discovery and testing
    - Continuous monitoring via FFmpeg
    - Reliability scoring with Capped Sliding Window
    - Screenshot capture
    - Metrics persistence
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self.sessions: Dict[str, SessionInfo] = {}
        self.session_locks: Dict[str, threading.Lock] = {}
        self.scoring_windows: Dict[str, Dict[int, CappedSlidingWindow]] = {}  # session_id -> stream_id -> window
        
        # Ensure config directory exists
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load existing sessions if any
        self._load_sessions()
        
        # Track last stream list refresh time
        self._last_streams_refresh = 0
        
        logger.info("StreamSessionManager initialized")
    
    def _load_sessions(self):
        """Load sessions from persistent storage"""
        if SESSION_DATA_FILE.exists():
            try:
                with open(SESSION_DATA_FILE, 'r') as f:
                    data = json.load(f)
                    for session_data in data.get('sessions', []):
                        session = self._deserialize_session(session_data)
                        self.sessions[session.session_id] = session
                        self.session_locks[session.session_id] = threading.Lock()
                        # Don't restart monitoring for loaded sessions
                        # They were stopped when the service shut down
                        session.is_active = False
                logger.info(f"Loaded {len(self.sessions)} sessions from storage")
            except Exception as e:
                logger.error(f"Failed to load sessions: {e}")
    
    def _save_sessions(self):
        """Save sessions to persistent storage"""
        try:
            data = {
                'sessions': [self._serialize_session(s) for s in self.sessions.values()],
                'updated_at': datetime.now().isoformat()
            }
            with open(SESSION_DATA_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sessions: {e}")
    
    def _serialize_session(self, session: SessionInfo) -> Dict[str, Any]:
        """Serialize session to JSON-compatible dict"""
        data = asdict(session)
        # Convert nested dataclasses
        if 'streams' in data:
            streams_dict = {}
            for stream_id, stream_info in data['streams'].items():
                stream_dict = dict(stream_info) if isinstance(stream_info, dict) else asdict(stream_info)
                # Limit metrics history size for storage
                if 'metrics_history' in stream_dict and stream_dict['metrics_history']:
                    stream_dict['metrics_history'] = stream_dict['metrics_history'][-1000:]  # Keep last 1000
                streams_dict[str(stream_id)] = stream_dict
            data['streams'] = streams_dict
        return data
    
    def _deserialize_session(self, data: Dict[str, Any]) -> SessionInfo:
        """Deserialize session from JSON dict"""
        # Convert streams dict back to StreamInfo objects
        if 'streams' in data and data['streams']:
            streams = {}
            for stream_id, stream_data in data['streams'].items():
                # Convert metrics_history back to StreamMetrics objects
                if 'metrics_history' in stream_data and stream_data['metrics_history']:
                    metrics = []
                    for m in stream_data['metrics_history']:
                        if isinstance(m, dict):
                            metrics.append(StreamMetrics(**m))
                        else:
                            metrics.append(m)
                    stream_data['metrics_history'] = metrics
                
                streams[int(stream_id)] = StreamInfo(**stream_data)
            data['streams'] = streams
        
        return SessionInfo(**data)
    
    def create_session(self, channel_id: int, regex_filter: str = ".*",
                      pre_event_minutes: int = DEFAULT_PRE_EVENT_MINUTES,
                      epg_event: Optional[Dict[str, Any]] = None,
                      allow_duplicate_channel: bool = False,
                      skip_stream_refresh: bool = False,
                      **kwargs) -> str:
        """
        Create a new monitoring session.
        
        Args:
            channel_id: Dispatcharr channel ID to monitor
            regex_filter: Regex pattern to filter streams
            pre_event_minutes: Minutes before event to start monitoring
            epg_event: Optional EPG event to attach to this session
            allow_duplicate_channel: Allow creating a session if one already exists for this channel
            skip_stream_refresh: Skip refreshing global stream list (useful for batch operations)
            **kwargs: Additional session parameters (auto_created, auto_create_rule_id, etc.)
            
        Returns:
            Session ID
        """
        # Check for existing active session for this channel
        if not allow_duplicate_channel and self.is_channel_in_active_session(channel_id):
            # Find the existing session ID
            for s in self.sessions.values():
                if s.is_active and s.channel_id == channel_id:
                    logger.info(f"Using existing active session {s.session_id} for channel {channel_id}")
                    return s.session_id

        # Get channel info from UDI
        udi = get_udi_manager()
        
        # Always refresh the specific channel to ensure metadata (name, logo) is up to date
        udi.refresh_channel_by_id(channel_id)
        
        # Refresh global stream list with rate limiting (30s cooldown)
        # This prevents API spam when batch creating sessions while keeping data reasonably fresh
        if not skip_stream_refresh:
            current_time = time.time()
            if current_time - self._last_streams_refresh > 30:
                logger.info("Refreshing global stream list (cooldown passed)")
                if udi.refresh_streams():
                    self._last_streams_refresh = current_time
            else:
                logger.debug(
                    f"Skipping stream list refresh (cooldown active, "
                    f"{30 - (current_time - self._last_streams_refresh):.1f}s remaining)"
                )

        
        channel = udi.get_channel_by_id(channel_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")
        
        # Generate session ID
        session_id = f"session_{channel_id}_{int(time.time())}"
        
        # Extract EPG event info if provided
        epg_event_id = None
        epg_event_title = None
        epg_event_start = None
        epg_event_end = None
        epg_event_description = None
        if epg_event:
            epg_event_id = epg_event.get('id')
            epg_event_title = epg_event.get('title')
            epg_event_start = epg_event.get('start_time')
            epg_event_end = epg_event.get('end_time')
            epg_event_description = epg_event.get('description')
        
        # Get channel logo info
        channel_logo_url = None
        channel_tvg_id = channel.get('tvg_id')
        logo_id = channel.get('logo_id')
        if logo_id:
            # Use cached logo endpoint for better performance
            channel_logo_url = f"/api/channels/logos/{logo_id}/cache"
        
        # Create session
        session = SessionInfo(
            session_id=session_id,
            channel_id=channel_id,
            channel_name=channel.get('name', f'Channel {channel_id}'),
            regex_filter=regex_filter,
            created_at=time.time(),
            is_active=False,
            pre_event_minutes=pre_event_minutes,
            epg_event_id=epg_event_id,
            epg_event_title=epg_event_title,
            epg_event_start=epg_event_start,
            epg_event_end=epg_event_end,
            epg_event_description=epg_event_description,
            channel_logo_url=channel_logo_url,
            channel_tvg_id=channel_tvg_id,
            **kwargs
        )
        
        self.sessions[session_id] = session
        self.session_locks[session_id] = threading.Lock()
        self.scoring_windows[session_id] = {}
        
        self._save_sessions()
        logger.info(f"Created session {session_id} for channel {channel_id}")
        
        return session_id
    
    def start_session(self, session_id: str) -> bool:
        """
        Start monitoring for a session.
        
        This will:
        1. Fetch matching streams from Dispatcharr
        2. Test streams for quality
        3. Start continuous monitoring
        4. Begin reliability scoring
        
        Args:
            session_id: Session to start
            
        Returns:
            True if started successfully
        """
        if session_id not in self.sessions:
            logger.error(f"Session {session_id} not found")
            return False
        
        session = self.sessions[session_id]
        if session.is_active:
            logger.warning(f"Session {session_id} is already active")
            return False
        
        with self.session_locks[session_id]:
            session.is_active = True
            
            # Discover streams
            self._discover_streams(session_id)
            
            self._save_sessions()
        
        logger.info(f"Started session {session_id}")
        return True
    
    def stop_session(self, session_id: str) -> bool:
        """
        Stop monitoring for a session.
        
        Args:
            session_id: Session to stop
            
        Returns:
            True if stopped successfully
        """
        if session_id not in self.sessions:
            logger.error(f"Session {session_id} not found")
            return False
        
        session = self.sessions[session_id]
        
        with self.session_locks[session_id]:
            session.is_active = False
            self._save_sessions()
        
        # Explicitly stop all FFmpeg monitors for this session
        # Import here to avoid circular dependency between session_manager and monitoring_service
        try:
            from stream_monitoring_service import get_monitoring_service
            monitoring_service = get_monitoring_service()
            monitoring_service.stop_session_monitors(session_id)
        except Exception as e:
            logger.error(f"Error stopping monitors for session {session_id}: {e}")
        
        logger.info(f"Stopped session {session_id}")
        return True
    
    def _discover_streams(self, session_id: str):
        """
        Discover streams matching the session's regex filter.
        
        Args:
            session_id: Session ID
        """
        session = self.sessions[session_id]
        udi = get_udi_manager()
        
        # Get all streams
        all_streams = udi.get_streams()
        
        # Filter by regex with safety measures
        try:
            # Validate regex complexity (basic check)
            regex_pattern = session.regex_filter or '.*'
            if len(regex_pattern) > 500:
                logger.error(f"Regex pattern too long ({len(regex_pattern)} chars), max 500")
                return
            
            # Substitute CHANNEL_NAME variable if present (consistent with channel matcher)
            channel_name = session.channel_name or f"Channel {session.channel_id}"
            escaped_channel_name = re.escape(channel_name)
            regex_pattern = regex_pattern.replace('CHANNEL_NAME', escaped_channel_name)
            
            # Convert literal spaces in pattern to flexible whitespace regex (\s+)
            # This matches behavior in RegexChannelMatcher
            regex_pattern = _WHITESPACE_PATTERN.sub(r'\\s+', regex_pattern)
            
            # Compile with timeout protection
            regex = re.compile(regex_pattern, re.IGNORECASE)
            
            # Test regex with empty string to catch catastrophic backtracking
            try:
                regex.search('')
            except Exception as e:
                logger.error(f"Regex pattern failed safety test: {e}")
                return
                
        except re.error as e:
            logger.error(f"Invalid regex filter: {e}")
            return
        except Exception as e:
            logger.error(f"Unexpected error compiling regex: {e}")
            return
        
        # Find matching streams with timeout protection
        matching_streams = []
        for s in all_streams:
            try:
                # Use search with a reasonable timeout approach
                # Python regex doesn't have direct timeout, but we can limit input size
                stream_name = s.get('name', '')[:1000]  # Limit input size
                if regex.search(stream_name):
                    matching_streams.append(s)
            except Exception as e:
                logger.warning(f"Error matching stream {s.get('id')}: {e}")
                continue
        
        logger.info(f"Session {session_id}: Found {len(matching_streams)} matching streams")
        
        # Add all discovered streams to Dispatcharr channel (additive only)
        # This ensures streams matched by regex are actually available in the channel
        stream_ids = [s.get('id') for s in matching_streams]
        if stream_ids:
            try:
                from api_utils import add_streams_to_channel
                added_count = add_streams_to_channel(session.channel_id, stream_ids, allow_dead_streams=True)
                if added_count > 0:
                    logger.info(f"Session {session_id}: Added {added_count} new streams to Dispatcharr channel")
            except Exception as e:
                logger.error(f"Session {session_id}: Failed to sync streams to Dispatcharr: {e}")
        
        # Import stream stats utilities for extracting bitrate and other metadata
        from stream_stats_utils import extract_stream_stats
        
        # Add streams to session
        for stream_data in matching_streams:
            stream_id = stream_data.get('id')
            if stream_id not in session.streams:
                # Extract stream stats (including bitrate from stream_stats)
                stats = extract_stream_stats(stream_data)
                
                # Extract bitrate safely, handling various data types
                bitrate = None
                if stats.get('bitrate_kbps'):
                    try:
                        bitrate = int(stats.get('bitrate_kbps'))
                    except (ValueError, TypeError):
                        bitrate = stream_data.get('bitrate')
                else:
                    bitrate = stream_data.get('bitrate')
                
                stream_info = StreamInfo(
                    stream_id=stream_id,
                    url=stream_data.get('url', ''),
                    name=stream_data.get('name', ''),
                    channel_id=session.channel_id,
                    width=stream_data.get('width'),
                    height=stream_data.get('height'),
                    fps=stats.get('fps') or stream_data.get('fps'),
                    bitrate=bitrate,
                    m3u_account=stream_data.get('m3u_account')
                )
                session.streams[stream_id] = stream_info
                
                # Initialize scoring window
                if session_id not in self.scoring_windows:
                    self.scoring_windows[session_id] = {}
                self.scoring_windows[session_id][stream_id] = CappedSlidingWindow(
                    window_size=session.window_size
                )
    
    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get session by ID"""
        return self.sessions.get(session_id)
    
    def get_all_sessions(self) -> List[SessionInfo]:
        """Get all sessions"""
        return list(self.sessions.values())
    
    def get_active_sessions(self) -> List[SessionInfo]:
        """Get all active sessions"""
        return [s for s in self.sessions.values() if s.is_active]
    
    def is_channel_in_active_session(self, channel_id: int) -> bool:
        """Check if a channel is currently in an active monitoring session.
        
        Args:
            channel_id: Channel ID to check
            
        Returns:
            True if channel is in an active session
        """
        for session in self.sessions.values():
            if session.is_active and session.channel_id == channel_id:
                return True
        return False
    
    def get_channels_in_active_sessions(self) -> Set[int]:
        """Get set of channel IDs that are currently in active monitoring sessions.
        
        Returns:
            Set of channel IDs in active sessions
        """
        channels = set()
        for session in self.sessions.values():
            if session.is_active:
                channels.add(session.channel_id)
        return channels
    
    def add_stream_to_session(self, session_id: str, stream_id: int) -> bool:
        """Add a newly discovered stream to an active session.
        
        This is called when automation discovers new streams for a channel
        that's currently in a monitoring session.
        
        Args:
            session_id: Session ID
            stream_id: Stream ID to add
            
        Returns:
            True if stream was added successfully
        """
        if session_id not in self.sessions:
            logger.error(f"Session {session_id} not found")
            return False
        
        session = self.sessions[session_id]
        if not session.is_active:
            logger.warning(f"Session {session_id} is not active")
            return False
        
        # Check if stream already exists
        if stream_id in session.streams:
            logger.debug(f"Stream {stream_id} already in session {session_id}")
            return True
        
        # Get stream info from UDI
        udi = get_udi_manager()
        stream = udi.get_stream_by_id(stream_id)
        if not stream:
            logger.error(f"Stream {stream_id} not found in UDI")
            return False
        
        # Check if stream matches session's regex filter
        import re
        try:
            # Prepare regex with variable substitution (same as _discover_streams)
            regex_pattern = session.regex_filter or '.*'
            
            # Substitute CHANNEL_NAME variable
            channel_name = session.channel_name or f"Channel {session.channel_id}"
            escaped_channel_name = re.escape(channel_name)
            regex_pattern = regex_pattern.replace('CHANNEL_NAME', escaped_channel_name)
            
            # Convert literal spaces
            regex_pattern = _WHITESPACE_PATTERN.sub(r'\\s+', regex_pattern)
            
            pattern = re.compile(regex_pattern, re.IGNORECASE)
            
            # Limit input size for safety
            stream_name = stream.get('name', '')[:1000]
            if not pattern.search(stream_name):
                logger.debug(f"Stream {stream_id} does not match session regex filter")
                return False
        except re.error:
            logger.warning(f"Invalid regex filter in session {session_id}")
        
        # Add stream to session
        with self.session_locks[session_id]:
            stream_info = StreamInfo(
                stream_id=stream_id,
                url=stream.get('url', ''),
                name=stream.get('name', ''),
                channel_id=session.channel_id,
                m3u_account=stream.get('m3u_account')
            )
            session.streams[stream_id] = stream_info
            self.scoring_windows[session_id][stream_id] = CappedSlidingWindow(session.window_size)
            
            logger.info(f"Added stream {stream_id} to session {session_id}")
            self._save_sessions()
            
            # Also add stream to Dispatcharr channel for real-time sync
            try:
                from api_utils import add_streams_to_channel
                added_count = add_streams_to_channel(session.channel_id, [stream_id], allow_dead_streams=True)
                if added_count > 0:
                    logger.info(
                        f"✓ Successfully added stream {stream_id} to Dispatcharr "
                        f"channel {session.channel_id} (real-time sync)"
                    )
                    # Refresh the channel in UDI to update cache
                    udi.refresh_channel_by_id(session.channel_id)
                else:
                    logger.debug(
                        f"Stream {stream_id} already in Dispatcharr channel {session.channel_id} "
                        f"or filtered out (possibly dead stream)"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to add stream {stream_id} to Dispatcharr channel {session.channel_id}: {e}",
                    exc_info=True
                )
                # Don't fail the entire operation if Dispatcharr sync fails
            
            return True
    
    def quarantine_stream(self, session_id: str, stream_id: int, remove_from_dispatcharr: bool = True) -> bool:
        """
        Manually quarantine a stream and optionally remove it from Dispatcharr.
        
        Args:
            session_id: Session ID
            stream_id: Stream ID to quarantine
            remove_from_dispatcharr: If True, also removes the stream from Dispatcharr channel
            
        Returns:
            True if quarantined successfully
        """
        if session_id not in self.sessions:
            logger.error(f"Session {session_id} not found")
            return False
        
        session = self.sessions[session_id]
        stream_info = session.streams.get(stream_id)
        
        if not stream_info:
            logger.error(f"Stream {stream_id} not found in session {session_id}")
            return False
        
        with self.session_locks[session_id]:
            stream_info.is_quarantined = True
            self._save_sessions()
        
        logger.info(f"Manually quarantined stream {stream_id} in session {session_id}")
        
        # Remove from Dispatcharr channel if requested
        if remove_from_dispatcharr:
            try:
                from udi import get_udi_manager
                udi = get_udi_manager()
                
                # Mark as dead in tracker first
                try:
                    from dead_streams_tracker import DeadStreamsTracker
                    tracker = DeadStreamsTracker()
                    tracker.mark_as_dead(
                        stream_url=stream_info.url,
                        stream_id=stream_id,
                        stream_name=stream_info.name,
                        channel_id=session.channel_id
                    )
                    logger.info(f"Marked quarantined stream {stream_id} as dead in tracker")
                except Exception as e:
                    logger.warning(f"Failed to mark stream {stream_id} as dead: {e}")

                # Remove from channel (but not delete from UDI)
                channel = udi.get_channel_by_id(session.channel_id)
                if channel:
                    current_streams = channel.get('streams', [])
                    if stream_id in current_streams:
                        # Create new list without the quarantined stream
                        new_streams = [sid for sid in current_streams if sid != stream_id]
                        
                        # Update channel with new stream list
                        # use api_utils to ensure proper update
                        from api_utils import update_channel_streams
                        success = update_channel_streams(session.channel_id, new_streams)
                        
                        if success:
                            logger.info(f"Removed quarantined stream {stream_id} from Dispatcharr channel {session.channel_id}")
                            # Refresh channel in UDI
                            udi.refresh_channel_by_id(session.channel_id)
                        else:
                            logger.warning(f"Failed to update channel {session.channel_id} to remove stream {stream_id}")
                    else:
                        logger.info(f"Stream {stream_id} was not in channel {session.channel_id} streams list")
                else:
                    logger.warning(f"Channel {session.channel_id} not found, could not remove stream {stream_id}")

            except Exception as e:
                logger.error(f"Error handling Dispatcharr updates for quarantined stream {stream_id}: {e}", exc_info=True)
         
        return True
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        if session_id not in self.sessions:
            return False
        
        # Stop if active, but ALWAYS try to stop monitors to ensure cleanup
        if self.sessions[session_id].is_active:
            self.stop_session(session_id)
        else:
            # Even if marked inactive, ensure monitors are stopped
            try:
                from stream_monitoring_service import get_monitoring_service
                monitoring_service = get_monitoring_service()
                monitoring_service.stop_session_monitors(session_id)
            except Exception as e:
                logger.error(f"Error checking monitors for deleted session {session_id}: {e}")
        
        # Remove session
        del self.sessions[session_id]
        if session_id in self.session_locks:
            del self.session_locks[session_id]
        if session_id in self.scoring_windows:
            del self.scoring_windows[session_id]
        
        self._save_sessions()
        logger.info(f"Deleted session {session_id}")
        return True


# Global instance accessor
_manager_instance = None
_manager_lock = threading.Lock()


def get_session_manager() -> StreamSessionManager:
    """Get the global StreamSessionManager instance"""
    global _manager_instance
    if _manager_instance is None:
        with _manager_lock:
            if _manager_instance is None:
                _manager_instance = StreamSessionManager()
    return _manager_instance
