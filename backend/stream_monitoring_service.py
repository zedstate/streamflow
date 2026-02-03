"""
Stream Monitoring Service

Orchestrates continuous stream monitoring, reliability scoring, and screenshot capture
for active monitoring sessions.
"""

import logging
import threading
import time
from typing import Dict, Optional

from logging_config import setup_logging
from stream_session_manager import get_session_manager, StreamMetrics
from ffmpeg_stream_monitor import FFmpegStreamMonitor
from stream_screenshot_service import get_screenshot_service
from dead_streams_tracker import DeadStreamsTracker
from udi import get_udi_manager

logger = setup_logging(__name__)

# Monitoring intervals
MONITOR_INTERVAL = 1.0  # seconds - how often to evaluate streams
REFRESH_INTERVAL = 60.0  # seconds - how often to refresh stream list
SCREENSHOT_CHECK_INTERVAL = 5.0  # seconds - how often to check for screenshot needs


# Auto-quarantine thresholds
SLOW_SPEED_THRESHOLD = 0.3  # Speed below this is considered too slow
SLOW_SPEED_DURATION = 60.0  # seconds - how long to tolerate slow speed before quarantine

# Stream switching thresholds
SCORE_SWITCH_THRESHOLD = 10.0  # Points diff required to switch primary stream
SWITCH_COOLDOWN = 60.0  # Seconds between switches to prevent flapping


class StreamMonitoringService:
    """
    Service that manages continuous monitoring of streams.
    
    For each active session:
    - Monitors all non-quarantined streams with FFmpeg
    - Updates reliability scores using Capped Sliding Window
    - Captures periodic screenshots
    - Persists metrics to database
    - Reorders streams in Dispatcharr if a better stream is found
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
        self.session_manager = get_session_manager()
        self.screenshot_service = get_screenshot_service()
        self.dead_streams_tracker = DeadStreamsTracker()
        
        # Active monitors: session_id -> stream_id -> FFmpegStreamMonitor
        self.monitors: Dict[str, Dict[int, FFmpegStreamMonitor]] = {}
        
        # Track last switch times for cooldown: session_id -> timestamp
        self.last_switch_times: Dict[str, float] = {}
        
        # Worker threads
        self._monitor_thread: Optional[threading.Thread] = None
        self._refresh_thread: Optional[threading.Thread] = None
        self._screenshot_thread: Optional[threading.Thread] = None
        self._running = False
        
        logger.info("StreamMonitoringService initialized")

    # [Skipped methods unchanged]

    def _evaluate_session_streams(self, session_id: str):
        """Evaluate and score all streams in a session"""
        session = self.session_manager.get_session(session_id)
        if not session:
            return
        
        current_time = time.time()
        
        # Create a copy of the monitors dict items to avoid "dictionary changed size during iteration" error
        monitors_snapshot = list(self.monitors.get(session_id, {}).items())
        
        # Check each monitor
        for stream_id, monitor in monitors_snapshot:
            stream_info = session.streams.get(stream_id)
            if not stream_info:
                continue
            
            stats = monitor.get_stats()
            
            # Update stream info with latest stats
            if stats.width > 0:
                stream_info.width = stats.width
                stream_info.height = stats.height
            if stats.fps > 0:
                stream_info.fps = stats.fps
            if stats.bitrate > 0:
                stream_info.bitrate = int(stats.bitrate)
            
            # Create metrics entry
            metrics = StreamMetrics(
                timestamp=current_time,
                speed=stats.speed,
                bitrate=stats.bitrate,
                fps=stats.fps,
                is_alive=stats.is_alive,
                buffering=monitor.is_buffering()
            )
            
            # Add to history (limit size)
            stream_info.metrics_history.append(metrics)
            if len(stream_info.metrics_history) > 1000:
                stream_info.metrics_history = stream_info.metrics_history[-1000:]
            
            # Update reliability score
            scoring_window = self.session_manager.scoring_windows.get(session_id, {}).get(stream_id)
            if scoring_window:
                is_healthy = stats.is_alive and not monitor.is_buffering()
                scoring_window.add_measurement(is_healthy, stats.speed)
                stream_info.reliability_score = scoring_window.get_score()
            
            # Check if stream is dead or timed out
            if not stats.is_alive:
                # Stream has died - quarantine it and remove from Dispatcharr
                logger.warning(f"Stream {stream_id} is dead in session {session_id}, quarantining")
                monitor.stop()
                # Safe to delete since we're iterating over a snapshot
                del self.monitors[session_id][stream_id]
                stream_info.is_quarantined = True
                # Remove dead stream from Dispatcharr channel
                self._remove_stream_from_dispatcharr(session_id, stream_id, "dead")
            else:
                # Check for timeout/stall on alive streams
                time_since_update = current_time - stats.last_updated
                if time_since_update > (session.timeout_ms / 1000.0):
                    logger.warning(f"Stream {stream_id} timed out in session {session_id} (no updates for {time_since_update:.1f}s)")
                    monitor.stop()
                    # Safe to delete since we're iterating over a snapshot
                    del self.monitors[session_id][stream_id]
                    stream_info.is_quarantined = True
                    # Remove timed-out stream from Dispatcharr channel
                    self._remove_stream_from_dispatcharr(session_id, stream_id, "timed-out")
                else:
                    # Check for persistently slow speed (auto-quarantine)
                    # Handle None speed values gracefully
                    current_speed = stats.speed if stats.speed is not None else 0.0
                    if current_speed < SLOW_SPEED_THRESHOLD:
                        # Speed is too slow
                        if stream_info.low_speed_start_time is None:
                            # First time below threshold, start tracking
                            stream_info.low_speed_start_time = current_time
                            logger.debug(f"Stream {stream_id} speed dropped below {SLOW_SPEED_THRESHOLD} (current: {current_speed:.2f}x)")
                        else:
                            # Check how long it's been slow
                            slow_duration = current_time - stream_info.low_speed_start_time
                            if slow_duration >= SLOW_SPEED_DURATION:
                                # Been slow for too long, quarantine
                                logger.warning(
                                    f"Stream {stream_id} has been below {SLOW_SPEED_THRESHOLD}x speed for "
                                    f"{slow_duration:.1f}s (current: {current_speed:.2f}x), auto-quarantining"
                                )
                                monitor.stop()
                                # Safe to delete since we're iterating over a snapshot
                                del self.monitors[session_id][stream_id]
                                stream_info.is_quarantined = True
                                # Remove slow stream from Dispatcharr channel
                                self._remove_stream_from_dispatcharr(session_id, stream_id, "slow-speed")
                    else:
                        # Speed is acceptable, reset tracking
                        if stream_info.low_speed_start_time is not None:
                            logger.debug(f"Stream {stream_id} speed recovered (current: {current_speed:.2f}x)")
                            stream_info.low_speed_start_time = None
        
        # ---------------------------------------------------------
        # Logic to reorder streams based on score (with hysteresis)
        # ---------------------------------------------------------
        
        # Check cooldown
        last_switch = self.last_switch_times.get(session_id, 0)
        if current_time - last_switch < SWITCH_COOLDOWN:
            return

        # Get current channel order from UDI
        udi = get_udi_manager()
        channel = udi.get_channel_by_id(session.channel_id)
        if not channel:
            return

        current_stream_ids = channel.get('streams', [])
        if not current_stream_ids:
            return

        # Identify current primary (active) stream
        primary_stream_id = current_stream_ids[0]
        primary_info = session.streams.get(primary_stream_id)
        
        if not primary_info:
            # Primary stream in channel is not in our session? Weird.
            return

        # Find best candidate stream in our session
        best_stream_id = None
        best_score = -1.0
        
        for stream_id, info in session.streams.items():
            if info.is_quarantined:
                continue
            # Skip if we don't have enough history to decide? (Optional, but CappedSlidingWindow handles low data)
            if info.reliability_score > best_score:
                best_score = info.reliability_score
                best_stream_id = stream_id

        if best_stream_id and best_stream_id != primary_stream_id:
            # Calculate difference
            score_diff = best_score - primary_info.reliability_score
            
            if score_diff >= SCORE_SWITCH_THRESHOLD:
                logger.info(
                    f"Switching primary stream for session {session_id}. "
                    f"New: {best_stream_id} (Score: {best_score:.1f}), "
                    f"Old: {primary_stream_id} (Score: {primary_info.reliability_score:.1f}), "
                    f"Diff: {score_diff:.1f}"
                )
                
                # Construct new order: Best first, then others
                new_order = [best_stream_id] + [sid for sid in current_stream_ids if sid != best_stream_id]
                
                from api_utils import update_channel_streams
                if update_channel_streams(session.channel_id, new_order):
                    logger.info(f"Updated Dispatcharr channel {session.channel_id} with new stream order")
                    udi.refresh_channel_by_id(session.channel_id)
                    self.last_switch_times[session_id] = current_time
                else:
                    logger.error(f"Failed to update stream order for channel {session.channel_id}")
    
    def _refresh_session_streams(self, session_id: str):
        """Refresh the list of streams for a session"""
        # Re-discover streams (will add new ones if they appear)
        self.session_manager._discover_streams(session_id)
        
        session = self.session_manager.get_session(session_id)
        if session:
            logger.info(f"Refreshed streams for session {session_id}, now tracking {len(session.streams)} streams")
    
    def _check_screenshots(self, session_id: str):
        """Check if any streams need screenshots"""
        session = self.session_manager.get_session(session_id)
        if not session:
            return
        
        current_time = time.time()
        interval = session.screenshot_interval_seconds
        
        for stream_id, stream_info in session.streams.items():
            if stream_info.is_quarantined:
                continue
            
            # Check if we need a screenshot
            time_since_screenshot = current_time - stream_info.last_screenshot_time
            if time_since_screenshot >= interval:
                # Capture screenshot in background
                threading.Thread(
                    target=self._capture_screenshot,
                    args=(session_id, stream_id),
                    daemon=True,
                    name=f"Screenshot-{stream_id}"
                ).start()
                
                # Update timestamp to avoid duplicate attempts
                stream_info.last_screenshot_time = current_time
    
    def _capture_screenshot(self, session_id: str, stream_id: int):
        """Capture a screenshot for a stream"""
        session = self.session_manager.get_session(session_id)
        if not session:
            return
        
        stream_info = session.streams.get(stream_id)
        if not stream_info:
            return
        
        try:
            path = self.screenshot_service.capture(stream_info.url, stream_id)
            if path:
                stream_info.screenshot_path = path
                logger.debug(f"Captured screenshot for stream {stream_id}: {path}")
        except Exception as e:
            logger.error(f"Error capturing screenshot for stream {stream_id}: {e}")


# Global instance accessor
_monitoring_instance = None
_monitoring_lock = threading.Lock()


def get_monitoring_service() -> StreamMonitoringService:
    """Get the global StreamMonitoringService instance"""
    global _monitoring_instance
    if _monitoring_instance is None:
        with _monitoring_lock:
            if _monitoring_instance is None:
                _monitoring_instance = StreamMonitoringService()
    return _monitoring_instance
