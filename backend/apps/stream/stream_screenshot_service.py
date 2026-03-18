"""
Stream Screenshot Service

Captures periodic screenshots of streams to help identify mismatching
or incorrect streams during live events.
"""

import logging
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from apps.core.logging_config import setup_logging

logger = setup_logging(__name__)

# Configuration
SCREENSHOT_DIR = Path(os.environ.get('CONFIG_DIR', '/app/data')) / 'screenshots'
SCREENSHOT_TIMEOUT = 10  # seconds
SCREENSHOT_QUALITY = 5  # JPEG quality (2-31, lower is better)


# Pre-compiled regexes for stats extraction
_REGEX_BITRATE = re.compile(r'bitrate:\s+(\d+)\s+kb/s')
_REGEX_RESOLUTION = re.compile(r'Video:.*? (\d{3,5})x(\d{3,5})')
_REGEX_FPS = re.compile(r'(\d+(?:\.\d+)?)\s+fps')
_REGEX_COLOR = re.compile(r'(yuv\w+?p?\d{1,2}le)[^,]*,\s*([^,)]+)', re.IGNORECASE)


class StreamScreenshotService:
    """
    Service for capturing stream screenshots.
    
    Uses FFmpeg to capture a single frame from a stream and save it as JPEG.
    Screenshots are saved with stream ID as filename for easy lookup.
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
        self.screenshot_dir = SCREENSHOT_DIR
        
        # Ensure screenshot directory exists
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Screenshot service initialized, saving to {self.screenshot_dir}")
    
    def capture(self, url: str, stream_id: int, timeout: int = SCREENSHOT_TIMEOUT, extract_stats: bool = True, local_udp_port: Optional[int] = None) -> tuple[Optional[str], dict]:
        """
        Capture a screenshot from a stream and optionally extract stats (resolution, fps, bitrate).
        
        Args:
            url: Stream URL
            stream_id: Stream ID (used for filename)
            timeout: Maximum time to wait for capture
            extract_stats: If True, attempts to parse stats from FFmpeg output
            local_udp_port: Optional local UDP port to capture from instead of remote URL
            
        Returns:
            Tuple of (screenshot_path, stats_dict)
            screenshot_path is None if failed
            stats_dict contains 'width', 'height', 'fps', 'bitrate' if found
        """
        try:
            # Filename: stream_id.jpg (overwrite to save space)
            filename = f"{stream_id}.jpg"
            output_path = self.screenshot_dir / filename
            
            # Determine input URL and probe sizes
            input_url = f"udp://127.0.0.1:{local_udp_port}" if local_udp_port else f"{url}{'?' if '?' not in url else '&'}timeout=5000000"
            probe_size = '1000000' if local_udp_port else '3000000'
            analyze_duration = '1000000' if local_udp_port else '3000000'
            
            # Use FFmpeg to capture a single frame
            process = subprocess.Popen(
                [
                    'ffmpeg',
                    '-hide_banner',
                    '-nostdin',   # Disable interactive stdin
                    '-y',         # Overwrite output files
                    '-analyzeduration', analyze_duration,
                    '-probesize', probe_size,
                    '-i', input_url,
                    '-vframes', '1',  # Capture 1 frame immediately
                    '-q:v', str(SCREENSHOT_QUALITY),  # JPEG quality
                    '-f', 'image2',
                    str(output_path)
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL, # Explicitly redirect stdin
                universal_newlines=True
            )
            
            # Wait for completion with timeout
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                logger.warning(f"Screenshot timeout for stream {stream_id}")
                return None, {}
            
            # Check if successful
            stats = {}
            if process.returncode == 0 and output_path.exists():
                # Return relative path
                relative_path = f"screenshots/{filename}"
                size = output_path.stat().st_size
                logger.debug(f"Successfully captured screenshot for stream {stream_id} ({size} bytes): {relative_path}")
                
                # Parse stats if requested
                if extract_stats and stderr:
                    # 1. Bitrate
                    bitrate_match = _REGEX_BITRATE.search(stderr)
                    if bitrate_match:
                        try:
                            stats['bitrate'] = int(bitrate_match.group(1))
                        except ValueError:
                            pass
                    
                    # 2. Resolution
                    res_match = _REGEX_RESOLUTION.search(stderr)
                    if res_match:
                        try:
                            stats['width'] = int(res_match.group(1))
                            stats['height'] = int(res_match.group(2))
                        except ValueError:
                            pass
                            
                    # 3. FPS
                    fps_match = _REGEX_FPS.search(stderr)
                    if fps_match:
                        try:
                            stats['fps'] = float(fps_match.group(1))
                        except ValueError:
                            pass
                            
                    # 4. HDR Detection
                    color_match = _REGEX_COLOR.search(stderr)
                    if color_match:
                        pix_fmt = color_match.group(1).lower()
                        color_info = color_match.group(2).lower()
                        
                        # Check for 10-bit or higher
                        is_10bit_or_higher = '10' in pix_fmt or '12' in pix_fmt or '16' in pix_fmt
                        
                        if is_10bit_or_higher and 'bt2020' in color_info:
                            if 'smpte2084' in color_info:
                                stats['hdr_format'] = 'HDR10'
                            elif 'arib-std-b67' in color_info:
                                stats['hdr_format'] = 'HLG'
                            elif 'dolby' in stderr.lower() or 'dvhe' in stderr.lower():
                                stats['hdr_format'] = 'Dolby Vision'
                            
                    if stats:
                        logger.debug(f"Extracted stats from screenshot probe for stream {stream_id}: {stats}")
                
                return relative_path, stats
            else:
                logger.debug(f"Screenshot failed or stream offline ({stream_id}), exit code: {process.returncode}")
                # Try to parse stats even on failure if we got stderr (might be useful for debugging)
                return None, {}
                
        except Exception as e:
            logger.debug(f"Error capturing screenshot for stream {stream_id}: {e}")
            return None, {}
    
    def get_screenshot_path(self, stream_id: int) -> Optional[str]:
        """
        Get path to existing screenshot for a stream.
        
        Args:
            stream_id: Stream ID
            
        Returns:
            Relative path to screenshot, or None if doesn't exist
        """
        filename = f"{stream_id}.jpg"
        filepath = self.screenshot_dir / filename
        
        if filepath.exists():
            return f"screenshots/{filename}"
        return None
    
    def delete_screenshot(self, stream_id: int) -> bool:
        """
        Delete screenshot for a stream.
        
        Args:
            stream_id: Stream ID
            
        Returns:
            True if deleted, False otherwise
        """
        filename = f"{stream_id}.jpg"
        filepath = self.screenshot_dir / filename
        
        try:
            if filepath.exists():
                filepath.unlink()
                logger.debug(f"Deleted screenshot for stream {stream_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting screenshot for stream {stream_id}: {e}")
            return False
    
    def cleanup_old_screenshots(self, max_age_hours: int = 24):
        """
        Clean up old screenshots.
        
        Args:
            max_age_hours: Maximum age of screenshots to keep
        """
        try:
            now = time.time()
            max_age_seconds = max_age_hours * 3600
            deleted = 0
            
            for filepath in self.screenshot_dir.glob("*.jpg"):
                # Check file age
                age = now - filepath.stat().st_mtime
                if age > max_age_seconds:
                    try:
                        filepath.unlink()
                        deleted += 1
                    except Exception as e:
                        logger.error(f"Error deleting old screenshot {filepath}: {e}")
            
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old screenshots")
                
        except Exception as e:
            logger.error(f"Error during screenshot cleanup: {e}")


# Global instance accessor
_service_instance = None
_service_lock = threading.Lock()


def get_screenshot_service() -> StreamScreenshotService:
    """Get the global StreamScreenshotService instance"""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = StreamScreenshotService()
    return _service_instance
