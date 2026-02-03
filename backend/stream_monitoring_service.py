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

logger = setup_logging(__name__)

# Monitoring intervals
MONITOR_INTERVAL = 1.0  # seconds - how often to evaluate streams
REFRESH_INTERVAL = 60.0  # seconds - how often to refresh stream list
SCREENSHOT_CHECK_INTERVAL = 5.0  # seconds - how often to check for screenshot needs


class StreamMonitoringService:
    """
    Service that manages continuous monitoring of streams.
    
    For each active session:
    - Monitors all non-quarantined streams with FFmpeg
    - Updates reliability scores using Capped Sliding Window
    - Captures periodic screenshots
    - Persists metrics to database
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
        
        # Worker threads
        self._monitor_thread: Optional[threading.Thread] = None
        self._refresh_thread: Optional[threading.Thread] = None
        self._screenshot_thread: Optional[threading.Thread] = None
        self._running = False
        
        logger.info("StreamMonitoringService initialized")
    
    def start(self):
        """Start the monitoring service"""
        if self._running:
            logger.warning("Monitoring service already running")
            return
        
        self._running = True
        
        # Start worker threads
        self._monitor_thread = threading.Thread(
            target=self._monitor_worker,
            daemon=True,
            name="StreamMonitor-Worker"
        )
        self._monitor_thread.start()
        
        self._refresh_thread = threading.Thread(
            target=self._refresh_worker,
            daemon=True,
            name="StreamMonitor-Refresh"
        )
        self._refresh_thread.start()
        
        self._screenshot_thread = threading.Thread(
            target=self._screenshot_worker,
            daemon=True,
            name="StreamMonitor-Screenshot"
        )
        self._screenshot_thread.start()
        
        logger.info("StreamMonitoringService started")
    
    def stop(self):
        """Stop the monitoring service"""
        if not self._running:
            return
        
        self._running = False
        
        # Stop all monitors
        for session_monitors in self.monitors.values():
            for monitor in session_monitors.values():
                monitor.stop()
        
        self.monitors.clear()
        
        logger.info("StreamMonitoringService stopped")
    
    def stop_session_monitors(self, session_id: str):
        """
        Stop all FFmpeg monitors for a specific session.
        
        This is called when a session is stopped or deleted to ensure
        all FFmpeg processes are terminated immediately.
        
        Args:
            session_id: Session ID to stop monitors for
        """
        if session_id in self.monitors:
            logger.info(f"Stopping all monitors for session {session_id}")
            for stream_id, monitor in list(self.monitors[session_id].items()):
                try:
                    monitor.stop()
                    logger.debug(f"Stopped monitor for stream {stream_id}")
                except Exception as e:
                    logger.error(f"Error stopping monitor for stream {stream_id}: {e}")
            
            # Remove session from monitors
            del self.monitors[session_id]
            logger.info(f"All monitors stopped for session {session_id}")
    
    def _monitor_worker(self):
        """Worker thread for monitoring streams"""
        logger.info("Monitor worker started")
        
        while self._running:
            try:
                # Process each active session
                active_sessions = self.session_manager.get_active_sessions()
                
                for session in active_sessions:
                    # Check if session should auto-stop based on EPG event end time
                    self._check_session_auto_stop(session)
                    
                    # Monitor the session
                    self._monitor_session(session.session_id)
                
                time.sleep(MONITOR_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in monitor worker: {e}", exc_info=True)
                time.sleep(1)
        
        logger.info("Monitor worker stopped")
    
    def _check_session_auto_stop(self, session):
        """Check if session should automatically stop based on EPG event end time"""
        if not session.epg_event_end:
            # No EPG event attached, don't auto-stop
            return
        
        try:
            from datetime import datetime, timezone
            
            # Parse EPG event end time
            end_time = datetime.fromisoformat(session.epg_event_end.replace('Z', '+00:00'))
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
            
            # Check if event has ended
            now = datetime.now(timezone.utc)
            if now >= end_time:
                logger.info(f"EPG event ended for session {session.session_id}, auto-stopping session")
                self.session_manager.stop_session(session.session_id)
        except Exception as e:
            logger.error(f"Error checking auto-stop for session {session.session_id}: {e}")
    
    def _refresh_worker(self):
        """Worker thread for refreshing stream lists"""
        logger.info("Refresh worker started")
        
        while self._running:
            try:
                # Refresh streams for each active session
                active_sessions = self.session_manager.get_active_sessions()
                
                for session in active_sessions:
                    self._refresh_session_streams(session.session_id)
                
                time.sleep(REFRESH_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in refresh worker: {e}", exc_info=True)
                time.sleep(5)
        
        logger.info("Refresh worker stopped")
    
    def _screenshot_worker(self):
        """Worker thread for capturing screenshots"""
        logger.info("Screenshot worker started")
        
        while self._running:
            try:
                # Check each active session for screenshot needs
                active_sessions = self.session_manager.get_active_sessions()
                
                for session in active_sessions:
                    self._check_screenshots(session.session_id)
                
                time.sleep(SCREENSHOT_CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in screenshot worker: {e}", exc_info=True)
                time.sleep(5)
        
        logger.info("Screenshot worker stopped")
    
    def _monitor_session(self, session_id: str):
        """Monitor all streams in a session"""
        session = self.session_manager.get_session(session_id)
        if not session or not session.is_active:
            # Clean up monitors for inactive session
            if session_id in self.monitors:
                for monitor in self.monitors[session_id].values():
                    monitor.stop()
                del self.monitors[session_id]
            return
        
        # Ensure monitors dict exists for this session
        if session_id not in self.monitors:
            self.monitors[session_id] = {}
        
        # Start monitors for streams that don't have one
        for stream_id, stream_info in session.streams.items():
            if stream_info.is_quarantined:
                continue
            
            if stream_id not in self.monitors[session_id]:
                # Create monitor
                monitor = FFmpegStreamMonitor(
                    url=stream_info.url,
                    on_stats_update=lambda stats, sid=session_id, stid=stream_id: 
                        self._on_stats_update(sid, stid, stats)
                )
                
                if monitor.start():
                    self.monitors[session_id][stream_id] = monitor
                    logger.info(f"Started monitor for stream {stream_id} in session {session_id}")
                    
                    # Stagger stream starts to avoid overwhelming the system
                    time.sleep(session.stagger_ms / 1000.0)
        
        # Update metrics and scores
        self._evaluate_session_streams(session_id)
    
    def _on_stats_update(self, session_id: str, stream_id: int, stats):
        """Callback for when FFmpeg stats are updated"""
        session = self.session_manager.get_session(session_id)
        if not session:
            return
        
        stream_info = session.streams.get(stream_id)
        if not stream_info:
            return
        
        # Check if stream has died (fatal error)
        if not stats.is_alive and stats.error_message:
            logger.warning(f"Stream {stream_id} marked as dead in session {session_id}: {stats.error_message}")
            # Mark stream as dead in the tracker
            self.dead_streams_tracker.mark_as_dead(
                stream_url=stream_info.url,
                stream_id=stream_id,
                stream_name=stream_info.name,
                channel_id=session.channel_id
            )
            # Stop the monitor
            if session_id in self.monitors and stream_id in self.monitors[session_id]:
                monitor = self.monitors[session_id][stream_id]
                monitor.stop()
                del self.monitors[session_id][stream_id]
            # Quarantine the stream
            stream_info.is_quarantined = True
            # Remove dead stream from Dispatcharr channel
            try:
                from udi import get_udi_manager
                udi = get_udi_manager()
                success = udi.bulk_delete_streams([stream_id])
                if success:
                    logger.info(f"Removed dead stream {stream_id} from Dispatcharr channel")
                    # Refresh the channel in UDI to update cache after deletion
                    session = self.session_manager.get_session(session_id)
                    if session:
                        udi.refresh_channel_by_id(session.channel_id)
                        logger.debug(f"Refreshed channel {session.channel_id} in UDI after dead stream removal")
                else:
                    logger.warning(f"Failed to remove dead stream {stream_id} from Dispatcharr")
            except Exception as e:
                logger.error(f"Error removing dead stream from Dispatcharr: {e}", exc_info=True)
            return
        
        # Update stream metadata if we got better info
        if stats.width > 0:
            stream_info.width = stats.width
            stream_info.height = stats.height
        if stats.fps > 0:
            stream_info.fps = stats.fps
        if stats.bitrate > 0:
            stream_info.bitrate = int(stats.bitrate)
    
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
                try:
                    from udi import get_udi_manager
                    udi = get_udi_manager()
                    success = udi.bulk_delete_streams([stream_id])
                    if success:
                        logger.info(f"Removed dead stream {stream_id} from Dispatcharr channel")
                        # Refresh the channel in UDI to update cache after deletion
                        udi.refresh_channel_by_id(session.channel_id)
                        logger.debug(f"Refreshed channel {session.channel_id} in UDI after dead stream removal")
                    else:
                        logger.warning(f"Failed to remove dead stream {stream_id} from Dispatcharr")
                except Exception as e:
                    logger.error(f"Error removing dead stream from Dispatcharr: {e}", exc_info=True)
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
                    try:
                        from udi import get_udi_manager
                        udi = get_udi_manager()
                        success = udi.bulk_delete_streams([stream_id])
                        if success:
                            logger.info(f"Removed timed-out stream {stream_id} from Dispatcharr channel")
                            # Refresh the channel in UDI to update cache after deletion
                            udi.refresh_channel_by_id(session.channel_id)
                            logger.debug(f"Refreshed channel {session.channel_id} in UDI after timed-out stream removal")
                        else:
                            logger.warning(f"Failed to remove timed-out stream {stream_id} from Dispatcharr")
                    except Exception as e:
                        logger.error(f"Error removing timed-out stream from Dispatcharr: {e}", exc_info=True)
    
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
