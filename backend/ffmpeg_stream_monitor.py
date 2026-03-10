"""
FFmpeg Stream Monitor

Lightweight stream monitoring using FFmpeg's null muxer for continuous
quality assessment without significant resource usage.
"""

import logging
import os
import re
import shutil
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Callable

from logging_config import setup_logging

logger = setup_logging(__name__)

# Constants for HLS
HLS_ROOT = "/tmp/streamflow_hls"

# Constants for bitrate calculation
BITS_PER_BYTE = 8
BYTES_TO_KBPS = 1000


@dataclass
class FFmpegStats:
    """Statistics from FFmpeg monitoring"""
    url: str
    speed: float = 0.0
    bitrate: float = 0.0  # kbps
    fps: float = 0.0
    width: int = 0
    height: int = 0
    time: float = 0.0  # seconds
    last_updated: float = 0.0
    is_alive: bool = False
    is_fatal: bool = False
    error_message: Optional[str] = None
    audio_language: Optional[str] = None
    # Additional fields for bitrate calculation
    total_size: int = 0  # bytes
    start_time: float = 0.0


class FFmpegStreamMonitor:
    """
    Lightweight FFmpeg stream monitor using null muxer.
    
    Uses `ffmpeg -i <url> -c copy -f null -` to monitor stream health
    without significant CPU/memory overhead.
    """
    
    def __init__(self, url: str, stream_id: Optional[int] = None, on_stats_update: Optional[Callable[[FFmpegStats], None]] = None):
        """
        Initialize stream monitor.
        
        Args:
            url: Stream URL to monitor
            stream_id: Optional stream ID for unique UDP port assignment
            on_stats_update: Optional callback for stats updates
        """
        self.url = url
        self.stream_id = stream_id
        self.on_stats_update = on_stats_update
        self.stats = FFmpegStats(url=url)
        
        # UDP ports for Primary-Sidecar routing and Live Preview
        self.port_a = None
        self.port_b = None
        self.port_viewer = None
        if stream_id is not None:
            self.port_a = 10000 + stream_id
            self.port_b = 20000 + stream_id
        # HLS Configuration
        self.hls_dir = None
        if stream_id is not None:
            self.hls_dir = os.path.join(HLS_ROOT, f"stream_{stream_id}")
        
        self._process: Optional[subprocess.Popen] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        
        # Error tracking for auto-restart
        self._error_history = deque(maxlen=100)
    
    def start(self) -> bool:
        """
        Start monitoring the stream.
        
        Returns:
            True if started successfully
        """
        with self._lock:
            if self._running:
                logger.warning(f"Monitor already running for {self.url}")
                return False
            
            try:
                # Validate URL to prevent command injection
                if not self._validate_url(self.url):
                    logger.error(f"Invalid or unsafe URL: {self.url}")
                    self.stats.error_message = "Invalid URL"
                    return False
                
                # Prepare FFmpeg command
                cmd = [
                    'ffmpeg',
                    '-hide_banner', # Reduce log spam
                    '-err_detect', 'ignore_err', # Ignore minor errors to prevent player stalling
                    '-fflags', '+genpts', # Regenerate timestamps (keep as input flag)
                    '-nostdin',     # Disable interactive stdin
                    '-i', self.url,
                ]
                
                if self.port_a and self.port_b and self.hls_dir:
                    # 1. Ensure HLS directory exists and is clean
                    if os.path.exists(self.hls_dir):
                        shutil.rmtree(self.hls_dir)
                    os.makedirs(self.hls_dir, exist_ok=True)
                    
                    hls_playlist = os.path.join(self.hls_dir, "playlist.m3u8")
                    
                    # Duplicate to:
                    # - two local UDP ports (port_a & port_b) for sidecar processes
                    # - HLS output for stable web preview
                    # - null output for stats
                    cmd.extend([
                        '-map', '0', '-c', 'copy', '-f', 'fifo', '-fifo_format', 'mpegts', '-drop_pkts_on_overflow', '1', '-attempt_recovery', '1', f'udp://127.0.0.1:{self.port_a}',
                        '-map', '0', '-c', 'copy', '-f', 'fifo', '-fifo_format', 'mpegts', '-drop_pkts_on_overflow', '1', '-attempt_recovery', '1', f'udp://127.0.0.1:{self.port_b}',
                        
                        # HLS Output for Web Preview
                        '-map', '0:v', '-map', '0:a:0?', 
                        '-c:v', 'copy', 
                        '-c:a', 'aac', '-ac', '2', '-ar', '44100', '-af', 'aresample=async=1',
                        '-avoid_negative_ts', 'make_zero',
                        '-f', 'hls',
                        '-hls_time', '2',          # 2-second segments for stability
                        '-hls_list_size', '6',     # Keep 6 segments in playlist
                        '-hls_flags', 'delete_segments+append_list+independent_segments',
                        '-hls_segment_type', 'fmp4',
                        '-hls_segment_filename', os.path.join(self.hls_dir, "seg_%d.m4s"),
                        hls_playlist,
                        
                        '-map', '0', '-c', 'copy', '-f', 'null', '-'
                    ])
                else:
                    cmd.extend(['-f', 'null', '-'])
                
                # Start FFmpeg process
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL, # Explicitly redirect stdin to prevent terminal-related issues
                    universal_newlines=True,
                    bufsize=1
                )
                
                self._running = True
                self.stats.is_alive = True
                self.stats.last_updated = time.time()
                self.stats.start_time = time.time()
                
                # Start monitoring thread
                self._monitor_thread = threading.Thread(
                    target=self._monitor_output,
                    daemon=True,
                    name=f"FFmpegMonitor-{id(self)}"
                )
                self._monitor_thread.start()
                
                logger.info(f"Started monitoring stream: {self.url[:100]}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start FFmpeg monitor: {e}")
                self._running = False
                self.stats.is_alive = False
                self.stats.error_message = str(e)
                return False
    
    def _validate_url(self, url: str) -> bool:
        """
        Validate URL to prevent command injection and ensure it's a supported protocol.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid and safe
        """
        if not url or not isinstance(url, str):
            return False
        
        # Check for command injection attempts
        dangerous_chars = ['`', '$', ';', '|', '&', '\n', '\r']
        if any(char in url for char in dangerous_chars):
            logger.warning(f"Rejected URL with dangerous characters: {url[:50]}")
            return False
        
        # Check for supported protocols
        import re
        # Allow http(s), acestream, rtmp(s), etc.
        protocol_pattern = r'^(https?|acestream|rtmp|rtmps|rtp|rtsp|udp|tcp)://'
        if not re.match(protocol_pattern, url, re.IGNORECASE):
            logger.warning(f"Rejected URL with unsupported protocol: {url[:50]}")
            return False
        
        # Basic length check
        if len(url) > 2000:
            logger.warning(f"Rejected URL that is too long: {len(url)} chars")
            return False
        
        return True
    
    def stop(self):
        """Stop monitoring the stream"""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            # Terminate FFmpeg process
            if self._process:
                try:
                    self._process.terminate()
                    # Give it a moment to terminate gracefully
                    try:
                        self._process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                except Exception as e:
                    logger.error(f"Error stopping FFmpeg process: {e}")
                finally:
                    self._process = None
            
            # Cleanup HLS directory
            if self.hls_dir and os.path.exists(self.hls_dir):
                try:
                    shutil.rmtree(self.hls_dir)
                except Exception as e:
                    logger.error(f"Error cleaning up HLS directory {self.hls_dir}: {e}")
            
            self.stats.is_alive = False
            
            logger.info(f"Stopped monitoring stream: {self.url[:100]}")
    
    def _monitor_output(self):
        """Monitor FFmpeg stderr output for statistics"""
        if not self._process or not self._process.stderr:
            return
        
        # Pre-lowercase fatal error patterns for performance
        fatal_error_patterns = [
            'error opening input:',
            'error opening input file',
            'error opening input files:',
            'server returned 4',  # HTTP errors
            'server returned 5',  # HTTP errors
            'connection refused',
            'no route to host',
            'connection timed out',
            'end of file',
            'i/o error',
            'protocol not found',
            'no such file or directory',
        ]
        
        # Non-fatal error patterns that should be logged at debug level only
        # These are common codec errors that don't indicate stream failure
        non_fatal_error_patterns = [
            'decode_slice_header error',
            'concealing',
            'error while decoding mb',
            'missing picture in access unit',
            'error decoding the audio block',
            'invalid data found when processing input',
            'non-existing pps 0 referenced',
            'no frame!',
            'reference picture missing',
        ]
        
        try:
            for line in self._process.stderr:
                if not self._running:
                    break
                
                # Parse stats from FFmpeg output
                self._parse_stats(line)
                self._parse_metadata(line)
                
                # Check for fatal errors that should stop the monitor
                line_lower = line.lower()
                is_fatal = any(pattern in line_lower for pattern in fatal_error_patterns)
                
                # Check if this is a non-fatal error that should be logged at debug level
                is_non_fatal_error = any(pattern in line_lower for pattern in non_fatal_error_patterns)
                
                # Check for errors
                if 'error' in line_lower or 'failed' in line_lower:
                    if is_non_fatal_error:
                        # Log non-fatal errors at debug level to avoid spam
                        logger.debug(f"FFmpeg non-fatal error for {self.url[:50]}: {line.strip()}")
                        
                        # Track non-fatal error frequency for health checks
                        current_time = time.time()
                        self._error_history.append(current_time)
                        
                        # If more than 50 errors in 30 seconds, consider it a stalled stream that needs restart
                        # Increased from 20 to 50 to be less sensitive to transient audio glitches
                        recent_errors = [t for t in self._error_history if current_time - t < 30]
                        if len(recent_errors) > 50:
                            logger.warning(f"Excessive decoding errors ({len(recent_errors)} in 30s) for {self.url[:50]}. Triggering restart.")
                            self.stats.error_message = "Excessive decoding errors"
                            self.stats.is_alive = False
                            self.stats.is_fatal = False # Explicitly non-fatal, just needs restart
                            self._running = False
                            break
                    else:
                        # Log other errors at warning level
                        logger.warning(f"FFmpeg error for {self.url[:50]}: {line.strip()}")
                    
                    if is_fatal or 'fatal' in line_lower:
                        self.stats.error_message = line.strip()
                        self.stats.is_alive = False
                        self.stats.is_fatal = True # Fatal error, stop and quarantine
                        # Stop monitoring on fatal error
                        logger.error(f"Fatal FFmpeg error detected, stopping monitor for {self.url[:50]}")
                        self._running = False
                        break
                
                # Callback if provided
                if self.on_stats_update:
                    try:
                        self.on_stats_update(self.stats)
                    except Exception as e:
                        logger.error(f"Error in stats callback: {e}")
        
        except Exception as e:
            logger.error(f"Error monitoring FFmpeg output: {e}")
        
        finally:
            # Check if process exited unexpectedly
            if self._process:
                try:
                    exit_code = self._process.poll()
                    if exit_code is not None and exit_code != 0:
                        logger.warning(f"FFmpeg process exited with code {exit_code} for {self.url[:50]}")
                        self.stats.error_message = f"FFmpeg exited with code {exit_code}"
                except Exception as e:
                    logger.error(f"Error checking FFmpeg exit code: {e}")
            
            with self._lock:
                self._running = False
                self.stats.is_alive = False
    
    def _parse_metadata(self, output: str):
        """Parse stream metadata from FFmpeg output"""
        # Look for video stream info: "Stream #0:0: Video: h264... 1920x1080 ..."
        if 'Video:' in output:
            # Extract resolution
            res_match = re.search(r'(\d{3,5})x(\d{3,5})', output)
            if res_match:
                self.stats.width = int(res_match.group(1))
                self.stats.height = int(res_match.group(2))
            
            # Extract FPS from metadata line
            fps_match = re.search(r'(\d+(?:\.\d+)?)\s*fps', output)
            if fps_match:
                self.stats.fps = round(float(fps_match.group(1)), 0)
        
        # Extract audio language: "Stream #0:1(eng): Audio: ..."
        if 'Audio:' in output:
            lang_match = re.search(r'Stream #\d+:\d+\((\w+)\):', output)
            if lang_match:
                self.stats.audio_language = lang_match.group(1)
                logger.debug(f"Detected audio language for {self.url[:50]}: {self.stats.audio_language}")
    
    def _parse_stats(self, output: str):
        """Parse real-time statistics from FFmpeg output"""
        # Speed (e.g., "speed=1.02x")
        speed_match = re.search(r'speed=\s*(\d+(?:\.\d+)?)x?', output)
        if speed_match:
            self.stats.speed = float(speed_match.group(1))
        
        # Bitrate (e.g., "bitrate= 406.1kbits/s")
        bitrate_found = False
        bitrate_match = re.search(r'bitrate=\s*([0-9.]+)\s*([kmg]?)bits/s', output, re.IGNORECASE)
        if bitrate_match:
            value = float(bitrate_match.group(1))
            unit = bitrate_match.group(2).lower()
            
            # Convert to kbps
            if unit == 'm':
                value *= 1000
            elif unit == 'g':
                value *= 1000000
            # 'k' or empty defaults to kbps
            
            self.stats.bitrate = value
            bitrate_found = True
        
        # Size (e.g., "size= 12345kB") - for calculating bitrate if not provided
        size_match = re.search(r'size=\s*([0-9.]+)\s*([kmg]?)B', output, re.IGNORECASE)
        if size_match:
            value = float(size_match.group(1))
            unit = size_match.group(2).lower()
            
            # Convert to bytes
            if unit == 'k':
                value *= 1024
            elif unit == 'm':
                value *= 1024 * 1024
            elif unit == 'g':
                value *= 1024 * 1024 * 1024
            
            self.stats.total_size = int(value)
            
            # Calculate bitrate from size and time if explicit bitrate not available
            # We check !bitrate_found rather than stats.bitrate == 0 to allow updates 
            # if the stream stays in "bitrate=N/A" state but size/time keep growing.
            if not bitrate_found and self.stats.time > 0:
                # bitrate = (total_size * BITS_PER_BYTE) / time / BYTES_TO_KBPS (to get kbps)
                self.stats.bitrate = (self.stats.total_size * BITS_PER_BYTE) / self.stats.time / BYTES_TO_KBPS
        
        # FPS (e.g., "fps= 30")
        fps_match = re.search(r'fps=\s*(\d+(?:\.\d+)?)', output)
        if fps_match:
            ffmpeg_fps = float(fps_match.group(1))
            
            # Calculate actual FPS: actual_fps = ffmpeg_fps / speed
            if self.stats.speed > 0:
                self.stats.fps = round(ffmpeg_fps / self.stats.speed, 0)
            elif ffmpeg_fps > 0:
                # Fallback if speed not available yet
                self.stats.fps = round(ffmpeg_fps, 0)
        
        # Time (e.g., "time=00:01:23.45")
        time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', output)
        if time_match:
            hours = float(time_match.group(1))
            minutes = float(time_match.group(2))
            seconds = float(time_match.group(3))
            self.stats.time = hours * 3600 + minutes * 60 + seconds
        
        # Update timestamp
        self.stats.last_updated = time.time()
    
    def get_stats(self) -> FFmpegStats:
        """Get current statistics"""
        return self.stats
    
    def is_running(self) -> bool:
        """Check if monitor is running"""
        return self._running
    
    def is_alive(self) -> bool:
        """Check if stream is alive"""
        return self.stats.is_alive
    
    def is_buffering(self) -> bool:
        """
        Check if stream is buffering.
        
        Stream is considered buffering if:
        - Speed is significantly less than 1.0
        - No recent updates
        """
        if not self.stats.is_alive:
            return False
        
        # Check for low speed (buffering indicator)
        if self.stats.speed > 0 and self.stats.speed < 0.9:
            return True
        
        # Check for stale data (no updates recently)
        time_since_update = time.time() - self.stats.last_updated
        if time_since_update > 10:  # 10 seconds without update
            return True
        
        return False
