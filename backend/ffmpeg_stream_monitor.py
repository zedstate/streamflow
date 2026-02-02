"""
FFmpeg Stream Monitor

Lightweight stream monitoring using FFmpeg's null muxer for continuous
quality assessment without significant resource usage.
"""

import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional, Callable

from logging_config import setup_logging

logger = setup_logging(__name__)


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
    error_message: Optional[str] = None


class FFmpegStreamMonitor:
    """
    Lightweight FFmpeg stream monitor using null muxer.
    
    Uses `ffmpeg -i <url> -c copy -f null -` to monitor stream health
    without significant CPU/memory overhead.
    """
    
    def __init__(self, url: str, on_stats_update: Optional[Callable[[FFmpegStats], None]] = None):
        """
        Initialize stream monitor.
        
        Args:
            url: Stream URL to monitor
            on_stats_update: Optional callback for stats updates
        """
        self.url = url
        self.on_stats_update = on_stats_update
        self.stats = FFmpegStats(url=url)
        
        self._process: Optional[subprocess.Popen] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
    
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
                
                # Start FFmpeg process
                self._process = subprocess.Popen(
                    [
                        'ffmpeg',
                        '-i', self.url,
                        '-c', 'copy',  # Copy codec (no re-encoding)
                        '-f', 'null',   # Null muxer (no output)
                        '-'
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    bufsize=1
                )
                
                self._running = True
                self.stats.is_alive = True
                self.stats.last_updated = time.time()
                
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
            
            self.stats.is_alive = False
            
            logger.info(f"Stopped monitoring stream: {self.url[:100]}")
    
    def _monitor_output(self):
        """Monitor FFmpeg stderr output for statistics"""
        if not self._process or not self._process.stderr:
            return
        
        try:
            for line in self._process.stderr:
                if not self._running:
                    break
                
                # Parse stats from FFmpeg output
                self._parse_stats(line)
                self._parse_metadata(line)
                
                # Check for errors
                if 'error' in line.lower() or 'failed' in line.lower():
                    logger.warning(f"FFmpeg error for {self.url[:50]}: {line.strip()}")
                    if 'fatal' in line.lower():
                        self.stats.error_message = line.strip()
                
                # Callback if provided
                if self.on_stats_update:
                    try:
                        self.on_stats_update(self.stats)
                    except Exception as e:
                        logger.error(f"Error in stats callback: {e}")
        
        except Exception as e:
            logger.error(f"Error monitoring FFmpeg output: {e}")
        
        finally:
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
                self.stats.fps = float(fps_match.group(1))
    
    def _parse_stats(self, output: str):
        """Parse real-time statistics from FFmpeg output"""
        # Speed (e.g., "speed=1.02x")
        speed_match = re.search(r'speed=\s*(\d+(?:\.\d+)?)x?', output)
        if speed_match:
            self.stats.speed = float(speed_match.group(1))
        
        # Bitrate (e.g., "bitrate= 406.1kbits/s")
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
        
        # FPS (e.g., "fps= 30")
        fps_match = re.search(r'fps=\s*(\d+(?:\.\d+)?)', output)
        if fps_match:
            ffmpeg_fps = float(fps_match.group(1))
            
            # Calculate actual FPS: actual_fps = ffmpeg_fps / speed
            if self.stats.speed > 0:
                self.stats.fps = ffmpeg_fps / self.stats.speed
            elif ffmpeg_fps > 0:
                # Fallback if speed not available yet
                self.stats.fps = ffmpeg_fps
        
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
