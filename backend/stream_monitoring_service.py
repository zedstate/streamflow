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
from stream_session_manager import (
    StreamInfo,
    SessionInfo,
    REVIEW_DURATION,
    QUARANTINE_DURATION,
    get_session_manager,
    StreamMetrics
)
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

# Stream switching thresholds
SCORE_SWITCH_THRESHOLD = 10.0  # Points diff required to switch primary stream
SWITCH_COOLDOWN = 60.0  # Seconds between switches to prevent flapping
RESOLUTION_SCORE_TOLERANCE = 5.0  # Points to sacrifice for better resolution

# Quarantine & Review Lifecycle
# Imported from stream_session_manager
pass
PASS_SCORE_THRESHOLD = 70.0  # Score needed to pass review
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
        
        # Track last evaluation times: session_id -> timestamp
        self.last_evaluation_times: Dict[str, float] = {}
        
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
    
    def _remove_stream_from_dispatcharr(self, session_id: str, stream_id: int, reason: str):
        """
        Remove a stream from Dispatcharr channel (without deleting it from UDI).
        
        Args:
            session_id: Session ID
            stream_id: Stream ID to remove
            reason: Reason for removal (for logging)
        """
        try:
            session = self.session_manager.get_session(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found when removing stream {stream_id}")
                return
            
            stream_info = session.streams.get(stream_id)
            if not stream_info:
                logger.warning(f"Stream info {stream_id} not found when removing stream")
                return

            # Mark as dead in tracker
            self.dead_streams_tracker.mark_as_dead(
                stream_url=stream_info.url,
                stream_id=stream_id,
                stream_name=stream_info.name,
                channel_id=session.channel_id
            )
            
            # Remove from channel (but not delete from UDI)
            udi = get_udi_manager()
            channel = udi.get_channel_by_id(session.channel_id)
            
            if channel:
                current_streams = channel.get('streams', [])
                if stream_id in current_streams:
                    new_streams = [sid for sid in current_streams if sid != stream_id]
                    from api_utils import update_channel_streams
                    success = update_channel_streams(session.channel_id, new_streams)
                    
                    if success:
                        logger.info(f"Removed {reason} stream {stream_id} from Dispatcharr channel {session.channel_id}")
                        udi.refresh_channel_by_id(session.channel_id)
                    else:
                        logger.warning(f"Failed to update channel {session.channel_id} to remove {reason} stream {stream_id}")
                else:
                    logger.info(f"{reason} stream {stream_id} was not in channel {session.channel_id} streams list")
            else:
                logger.warning(f"Channel {session.channel_id} not found, could not remove {reason} stream {stream_id}")

        except Exception as e:
            logger.error(f"Error removing {reason} stream from Dispatcharr: {e}", exc_info=True)
    
    def _manage_quarantine_lifecycle(self, session) -> bool:
        """
        Manage lifecycle of streams:
        - Quarantined -> Review (after cooldown)
        - Review -> Stable (after passing probation)
        
        Returns:
            bool: True if any stream transitioned to 'stable' (requiring immediate update)
        """
        current_time = time.time()
        updates_needed = False
        transitioned_to_stable = False
        
        for stream_id, info in session.streams.items():
            time_in_state = current_time - info.last_status_change
            
            if info.status == 'quarantined':
                # Check if it's time to give another chance
                if time_in_state > QUARANTINE_DURATION:
                    logger.info(f"Stream {stream_id} passed quarantine period ({time_in_state:.0f}s), moving to Review")
                    # Use session manager to revive (handles locking and saving)
                    self.session_manager.revive_stream(session.session_id, stream_id)
            
            elif info.status == 'review':
                # Check if it passed review
                if time_in_state > self.session_manager.get_review_duration():
                    if info.reliability_score >= PASS_SCORE_THRESHOLD:
                        logger.info(f"Stream {stream_id} passed review (Score: {info.reliability_score:.1f}), moving to Stable")
                        with self.session_manager.session_locks[session.session_id]:
                            info.status = 'stable'
                            info.last_status_change = current_time
                            updates_needed = True
                            transitioned_to_stable = True
                    # Else: stay in review until score improves or it dies (monitored by standard logic)
        
        if updates_needed:
            self.session_manager._save_sessions()
            
        return transitioned_to_stable
    
    def _check_sync_enforcement(self, session) -> bool:
        """
        Check if we need to enforce synchronization for this session.
        
        This ensures that the Dispatcharr channel state matches the session state,
        reverting any external changes (manual edits, other apps) and enforcing
        exclusive ownership.
        
        Returns:
            bool: True if sync enforcement was triggered
        """
        current_time = time.time()
        
        # Check if ownership is lost (shouldn't happen if locking logic works, but good for safety)
        owner = self.session_manager.get_session_owner(session.channel_id)
        if owner and owner != session.session_id:
            logger.warning(f"Session {session.session_id} lost ownership of channel {session.channel_id} to {owner}")
            return False
            
        # Check if it's time to enforce sync
        # Default 1000ms (1s) interval
        interval = getattr(session, 'enforce_sync_interval_ms', 1000) / 1000.0
        last_sync = getattr(session, 'last_sync_time', 0.0)
        
        if current_time - last_sync >= interval:
            # Trigger evaluation with force_update=True to enforce state
            self._evaluate_session_streams(session.session_id, force_update=True)
            session.last_sync_time = current_time
            return True
            
        return False
    
    def _monitor_worker(self):
        """Worker thread for monitoring streams"""
        logger.info("Monitor worker started")
        
        while self._running:
            try:
                # Process each active session
                active_sessions = self.session_manager.get_active_sessions()
                current_time = time.time()
                
                for session in active_sessions:
                    self._check_session_auto_stop(session)
                    
                    # Check lifecycle updates
                    became_stable = self._manage_quarantine_lifecycle(session)
                    
                    # Enforce synchronization (exclusive ownership)
                    # This runs frequently (e.g. 1s) to revert external changes
                    sync_triggered = self._check_sync_enforcement(session)
                    
                    # Always monitor (collect stats) - this is fast and non-blocking usually
                    self._monitor_session(session.session_id)
                    
                    # Check if it's time to Evaluate (reorder streams) - this is the adjustable part
                    last_eval = self.last_evaluation_times.get(session.session_id, 0)
                    eval_interval_sec = getattr(session, 'evaluation_interval_ms', 1000) / 1000.0
                    
                    # Force update if a stream just became stable, OR if interval passed
                    # Note: if sync_triggered is True, we already evaluated, so skip to avoid double work
                    if not sync_triggered and (became_stable or (current_time - last_eval >= eval_interval_sec)):
                        self._evaluate_session_streams(session.session_id, force_update=became_stable)
                        self.last_evaluation_times[session.session_id] = current_time
                
                # Sleep briefly to avoid CPU spin, but fast enough to catch 100ms intervals if needed
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in monitor worker: {e}", exc_info=True)
                time.sleep(1)
        
        logger.info("Monitor worker stopped")
    
    def _check_session_auto_stop(self, session):
        """Check if session should automatically stop based on EPG event end time"""
        if not session.epg_event_end:
            return
        
        try:
            from datetime import datetime, timezone
            end_time = datetime.fromisoformat(session.epg_event_end.replace('Z', '+00:00'))
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            if now >= end_time:
                logger.info(f"EPG event ended for session {session.session_id}, auto-stopping session")
                self.session_manager.stop_session(session.session_id)
        except Exception as e:
            logger.error(f"Error checking auto-stop for session {session.session_id}: {e}")
    
    def _refresh_worker(self):
        """Worker thread for refreshing stream lists and updating stats"""
        logger.info("Refresh worker started")
        
        while self._running:
            try:
                active_sessions = self.session_manager.get_active_sessions()
                
                # Refresh streams (discover new ones)
                for session in active_sessions:
                    try:
                        self._refresh_session_streams(session.session_id)
                    except Exception as e:
                        logger.error(f"Error refreshing streams for session {session.session_id}: {e}")
                
                # Sync stream stats to Dispatcharr
                try:
                    self._sync_stream_stats(active_sessions)
                except Exception as e:
                    logger.error(f"Error syncing stream stats: {e}")
                    
                time.sleep(REFRESH_INTERVAL)
            except Exception as e:
                logger.error(f"Error in refresh worker: {e}", exc_info=True)
                time.sleep(5)
        
        logger.info("Refresh worker stopped")
    
    def _sync_stream_stats(self, active_sessions):
        """Sync stream metadata (res, fps, bitrate) to Dispatcharr"""
        stats_to_update = []
        
        for session in active_sessions:
            for stream_id, stream_info in session.streams.items():
                if stream_info.is_quarantined:
                    continue
                
                # Build stats payload for Dispatcharr
                stats = {}
                
                # Resolution
                if stream_info.width and stream_info.height:
                    stats['resolution'] = f"{stream_info.width}x{stream_info.height}"
                
                if stream_info.fps:
                    try:
                        # Round to nearest integer (standard FPS e.g. 23.97 -> 24, 29.97 -> 30)
                        stats['source_fps'] = int(round(float(stream_info.fps)))
                    except (ValueError, TypeError):
                        pass
                
                # Bitrate
                if stream_info.bitrate:
                    try:
                        stats['ffmpeg_output_bitrate'] = int(stream_info.bitrate)
                    except (ValueError, TypeError):
                        pass
                
                # Only update if we have meaningful stats
                if stats:
                    stats_to_update.append({
                        'stream_id': stream_id,
                        'stream_stats': stats
                    })
        
        if stats_to_update:
            try:
                from api_utils import batch_update_stream_stats
                success, failed = batch_update_stream_stats(stats_to_update)
                if success > 0:
                    logger.info(f"Synced stats for {success} streams to Dispatcharr")
                if failed > 0:
                    logger.warning(f"Failed to sync stats for {failed} streams")
            except Exception as e:
                logger.error(f"Failed to execute batch update: {e}")
    
    def _screenshot_worker(self):
        """Worker thread for capturing screenshots"""
        logger.info("Screenshot worker started")
        
        while self._running:
            try:
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
            if session_id in self.monitors:
                for monitor in self.monitors[session_id].values():
                    monitor.stop()
                del self.monitors[session_id]
            return
        
        if session_id not in self.monitors:
            self.monitors[session_id] = {}
        
        for stream_id, stream_info in session.streams.items():
            if stream_info.is_quarantined:
                continue
            
            if stream_id not in self.monitors[session_id]:
                monitor = FFmpegStreamMonitor(
                    url=stream_info.url,
                    on_stats_update=lambda stats, sid=session_id, stid=stream_id: 
                        self._on_stats_update(sid, stid, stats)
                )
                
                if monitor.start():
                    self.monitors[session_id][stream_id] = monitor
                    logger.info(f"Started monitor for stream {stream_id} in session {session_id}")
                    time.sleep(session.stagger_ms / 1000.0)
                else:
                    logger.error(f"Failed to start monitor for stream {stream_id} in session {session_id}")
                    # Monitor failed to start (e.g. invalid URL), quarantine immediately
                    self.session_manager.quarantine_stream(session_id, stream_id)
                    self._remove_stream_from_dispatcharr(session_id, stream_id, "monitor-start-failed")

    
    def _on_stats_update(self, session_id: str, stream_id: int, stats):
        """Callback for when FFmpeg stats are updated"""
        session = self.session_manager.get_session(session_id)
        if not session:
            return
        
        stream_info = session.streams.get(stream_id)
        if not stream_info:
            return
        
        if not stats.is_alive and stats.error_message:
            logger.warning(f"Stream {stream_id} marked as dead in session {session_id}: {stats.error_message}")
            self.dead_streams_tracker.mark_as_dead(
                stream_url=stream_info.url,
                stream_id=stream_id,
                stream_name=stream_info.name,
                channel_id=session.channel_id
            )
            if session_id in self.monitors and stream_id in self.monitors[session_id]:
                monitor = self.monitors[session_id][stream_id]
                monitor.stop()
                del self.monitors[session_id][stream_id]
            
            # Quarantine via session manager to update blocklist
            self.session_manager.quarantine_stream(session_id, stream_id)
            self._remove_stream_from_dispatcharr(session_id, stream_id, "dead")
            return
        
        if stats.width > 0:
            stream_info.width = stats.width
            stream_info.height = stats.height
        if stats.fps > 0:
            stream_info.fps = stats.fps
        if stats.bitrate > 0:
            stream_info.bitrate = int(stats.bitrate)

    def _evaluate_session_streams(self, session_id: str, force_update: bool = False):
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
            
            # Update reliability score first so it's included in metrics
            scoring_window = self.session_manager.scoring_windows.get(session_id, {}).get(stream_id)
            current_score = stream_info.reliability_score
            if scoring_window:
                is_healthy = stats.is_alive and not monitor.is_buffering()
                scoring_window.add_measurement(is_healthy, stats.speed)
                current_score = scoring_window.get_score()
                stream_info.reliability_score = current_score

            # Create metrics entry
            # Use stream_info.bitrate/fps which are "sticky" (hold last known good value)
            # This prevents 0/N/A in history if a single probe fails to get metadata but stream is alive
            metrics_bitrate = stream_info.bitrate if (stream_info.bitrate and stream_info.bitrate > 0) else stats.bitrate
            metrics_fps = stream_info.fps if (stream_info.fps and stream_info.fps > 0) else stats.fps
            
            metrics = StreamMetrics(
                timestamp=current_time,
                speed=stats.speed,
                bitrate=metrics_bitrate,
                fps=metrics_fps,
                is_alive=stats.is_alive,
                buffering=monitor.is_buffering(),
                reliability_score=current_score,
                status=stream_info.status
            )
            
            # Add to history (limit size)
            stream_info.metrics_history.append(metrics)
            # Use configurable window size from session manager
            window_size = getattr(self.session_manager, 'DEFAULT_WINDOW_SIZE', 3600)
            if len(stream_info.metrics_history) > window_size:
                stream_info.metrics_history = stream_info.metrics_history[-window_size:]
            
            # Check if stream is dead or timed out
            if not stats.is_alive:
                # Stream has died - quarantine it and remove from Dispatcharr
                logger.warning(f"Stream {stream_id} is dead in session {session_id}, quarantining")
                monitor.stop()
                # Safe to delete since we're iterating over a snapshot
                del self.monitors[session_id][stream_id]
                self.session_manager.quarantine_stream(session_id, stream_id)
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
                    self.session_manager.quarantine_stream(session_id, stream_id)
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
                                self.session_manager.quarantine_stream(session_id, stream_id)
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
        
        # Check cooldown (bypass if force_update is True)
        last_switch = self.last_switch_times.get(session_id, 0)
        if not force_update and (current_time - last_switch < SWITCH_COOLDOWN):
            return

        # Get current channel order from UDI
        udi = get_udi_manager()
        channel = udi.get_channel_by_id(session.channel_id)
        if not channel:
            return

        current_stream_ids = channel.get('streams', [])
        # Note: We do NOT return if current_stream_ids is empty, because we want to FILL it.

        # Identify current primary (active) stream
        primary_stream_id = current_stream_ids[0] if current_stream_ids else None
        primary_info = session.streams.get(primary_stream_id) if primary_stream_id else None
        
        # If primary_info is None, it means either:
        # 1. Channel is empty (we need to populate it)
        # 2. Primary stream is not in our session (maybe manual override or old stream)
        # In either case, we proceed to find the best candidate from our session.

        # Find best candidate stream in our session
        candidates = []
        for stream_id, info in session.streams.items():
            if info.is_quarantined:
                # Still check resolution for quarantined logic? No, skip dead/bad streams
                continue
            candidates.append(info)
            
        if not candidates:
            return

        # Sort candidates to find the best one
        # Logic: 
        # 1. Primary stream gets hysterisis bonus (SCORE_SWITCH_THRESHOLD) - ONLY for deciding the top spot
        # 2. Prefer Higher Resolution if scores are close (RESOLUTION_SCORE_TOLERANCE)
        # 3. Prefer Higher Score
        
        # Primary stream ID from Dispatcharr (source of truth for "current state")
        current_primary_id = primary_stream_id

        # -------------------------------------------------------------------------
        # 1. Sort Candidates Globally
        # Hierarchy:
        # A. Status: Stable (2) > Review (1)
        # B. Score: Higher is better
        # C. Resolution: Higher is better (width * height)
        # -------------------------------------------------------------------------
        
        def calculate_sort_key(info):
            # Status Priority: Stable (2) > Review (1) > Quarantined (0)
            status_priority = 2 if info.status == 'stable' else 1
            
            # Score
            score = info.reliability_score
            
            # Resolution Score
            res_score = (info.width or 0) * (info.height or 0)
            
            # FPS
            fps = info.fps or 0
            
            return (status_priority, score, res_score, fps)

        # Initial sort by Status and Score and Resolution and FPS (unique stable sort)
        candidates.sort(key=calculate_sort_key, reverse=True)
        
        # -------------------------------------------------------------------------
        # 2. Refine Sort with Resolution Tiers (within same Status)
        # This handles cases where scores are very close but resolution is different.
        # -------------------------------------------------------------------------
        final_sorted_streams = []
        
        # Helper to process a group of candidates (same status)
        def process_group(group):
            if not group: return []
            res_sorted = []
            while group:
                current = group.pop(0)
                tier = [current]
                i = 0
                while i < len(group):
                    # Check difference between current top of tier and next candidate
                    diff = current.reliability_score - group[i].reliability_score
                    if diff <= RESOLUTION_SCORE_TOLERANCE:
                        tier.append(group.pop(i))
                    else:
                        break
                # Sort tier by resolution AND FPS
                tier.sort(key=lambda x: ((x.width or 0) * (x.height or 0), (x.fps or 0)), reverse=True)
                res_sorted.extend(tier)
            return res_sorted

        # Split into status groups to ensure we don't mix them during tier processing
        stable_streams = [s for s in candidates if s.status == 'stable']
        review_streams = [s for s in candidates if s.status == 'review']
        
        # Process each group independently and concatenate
        # Stable streams always come first
        final_sorted_streams.extend(process_group(stable_streams))
        final_sorted_streams.extend(process_group(review_streams))

        # -------------------------------------------------------------------------
        # 3. Apply Hysteresis for the *Primary* position only
        # -------------------------------------------------------------------------
        if final_sorted_streams:
            proposed_primary = final_sorted_streams[0]
            
            if proposed_primary.stream_id != current_primary_id:
                # Find current primary stream info (if it exists and is valid)
                curr_prim_info = next((s for s in session.streams.values() if s.stream_id == current_primary_id), None)
                
                # Only consider hysteresis if current primary is still valid (not dead/quarantined)
                if curr_prim_info and not curr_prim_info.is_quarantined:
                    
                    # Determine if we should protect the current primary stream
                    should_protect = False
                    
                    # 1. Review streams are NEVER protected (Testing Phase)
                    # 2. Stable streams are protected ONLY if they are currently playing
                    if curr_prim_info.status == 'stable':
                        try:
                            # Note: udi variable is defined earlier in this function
                            playing_ids = udi.get_playing_stream_ids()
                            if curr_prim_info.stream_id in playing_ids:
                                should_protect = True
                        except Exception as e:
                            logger.error(f"Failed to check playing status for protection logic: {e}")
                            # Fail-safe: Protect if we can't check
                            should_protect = True
                    
                    if should_protect:
                        # Protected -> Apply Hysteresis
                        # Only switch if Proposed is SIGNIFICANTLY better
                        
                        score_diff = proposed_primary.reliability_score - curr_prim_info.reliability_score
                        
                        # Resolution
                        prop_res = (proposed_primary.width or 0) * (proposed_primary.height or 0)
                        curr_res = (curr_prim_info.width or 0) * (curr_prim_info.height or 0)
                        
                        # FPS
                        prop_fps = proposed_primary.fps or 0
                        curr_fps = curr_prim_info.fps or 0
                        
                        # Revert swap if improvement is not significant enough
                        revert_swap = False
                        
                        if score_diff < SCORE_SWITCH_THRESHOLD:
                            # Strict Hysteresis:
                            # If score improvement is small, only allow switch if resolution is significantly BETTER.
                            if prop_res < curr_res:
                                # Proposed has WORSE resolution -> Keep current
                                revert_swap = True
                            elif prop_res == curr_res:
                                # Resolution is SAME, check FPS
                                if prop_fps <= curr_fps:
                                    # Proposed has SAME/WORSE FPS -> Keep current
                                    revert_swap = True
                        
                        if revert_swap:
                             if curr_prim_info in final_sorted_streams:
                                 final_sorted_streams.remove(curr_prim_info)
                                 final_sorted_streams.insert(0, curr_prim_info)
                    
                    # If NOT protected (should_protect == False):
                    # We simply allow proposed_primary (which is better sorted) to take over.
                    # No hysteresis applied.
                    # Else: Proposed HAS better resolution, so let it stay at top (Swap happens)

        # -------------------------------------------------------------------------
        # 3.5 Update StreamMetrics with Rank
        # -------------------------------------------------------------------------
        for rank, stream_info in enumerate(final_sorted_streams, start=1):
            # Update top-level rank for API/UI
            stream_info.rank = rank
            
            if stream_info.metrics_history:
                # Update the most recent metric
                stream_info.metrics_history[-1].rank = rank


        # 4. Enforce this order in Dispatcharr
        # Prefer STABLE streams, but fallback to REVIEW streams if no stable streams exist
        # This prevents the channel from appearing empty during testing/initial phase
        public_streams = [s for s in final_sorted_streams if s.status == 'stable']
        
        if not public_streams and final_sorted_streams:
             # Fallback: If no stable streams, show ALL available streams (including Review)
             # but check if we should allow this (user might want strict hiding)
             # Assuming we should show *something* rather than nothing
             public_streams = final_sorted_streams
             msg = f"No stable streams found for session {session_id}. Falling back to all streams."
             logger.warning(msg)

        new_order_ids = [s.stream_id for s in public_streams]
        
        # Append any other streams that might be in current_stream_ids but not in our active list
        # We only exclude QUARANTINED streams now
        monitored_ids_set = set(new_order_ids)
        for sid in current_stream_ids:
            if sid not in monitored_ids_set:
                known_stream = session.streams.get(sid)
                if known_stream and known_stream.status == 'quarantined':
                     continue # Explicitly exclude quarantined
                if known_stream and known_stream.status == 'review' and public_streams != final_sorted_streams:
                     # If we are in "Stable Only" mode, exclude review streams from tail too
                     continue

                # Append at the end (ONLY if in session or explicit ownership not enforced)
                # Ensure exclusive ownership: Drop "alien" streams that are not in our session
                if known_stream:
                    new_order_ids.append(sid)
                else:
                    logger.debug(f"Dropping alien stream {sid} from channel {session.channel_id} (Exclusive Ownership)")

        # Check if order changed
        # If force_update is True, we proceed even if order looks same (to handle desync or status updates)
        if new_order_ids != current_stream_ids or force_update:
            msg = f"Enforcing new stream order for session {session_id}. "
            if force_update:
                msg += "[FORCE UPDATE] "
            
            if new_order_ids:
                primary_id = new_order_ids[0]
                score_str = "N/A"
                if primary_id in session.streams:
                        score_str = f"{session.streams[primary_id].reliability_score:.1f}"
                status_str = "Unknown"
                if primary_id in session.streams:
                    status_str = session.streams[primary_id].status
                msg += f"Primary: {primary_id} (Score: {score_str}, Status: {status_str})"
            else:
                msg += "Emptying channel (no valid streams)."
            
            logger.info(msg)
            
            from api_utils import update_channel_streams
            if update_channel_streams(session.channel_id, new_order_ids):
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
            # Capture screenshot and probe all stats (resolution, fps, bitrate)
            # This merges screenshot capture and stats probing into one FFmpeg call
            path, stats = self.screenshot_service.capture(
                stream_info.url, 
                stream_id, 
                extract_stats=True
            )
            
            if path:
                stream_info.screenshot_path = path
                logger.debug(f"Captured screenshot for stream {stream_id}: {path}")
            
            # Update stream info with probed stats
            if stats:
                updated_fields = []
                if 'bitrate' in stats:
                    stream_info.bitrate = stats['bitrate']
                    updated_fields.append('bitrate')
                if 'width' in stats and 'height' in stats:
                    stream_info.width = stats['width']
                    stream_info.height = stats['height']
                    updated_fields.append('resolution')
                    stream_info.fps = stats['fps']
                    updated_fields.append('fps')
                if 'hdr_format' in stats:
                    stream_info.hdr_format = stats['hdr_format']
                    updated_fields.append('hdr_format')
                
                if updated_fields:
                    logger.info(f"Updated stream {stream_id} stats from screenshot probe: {', '.join(updated_fields)}")
                
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
