"""
Stream Screenshot Service

Captures periodic screenshots of streams to help identify mismatching
or incorrect streams during live events.
"""

import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from logging_config import setup_logging

logger = setup_logging(__name__)

# Configuration
SCREENSHOT_DIR = Path(os.environ.get('CONFIG_DIR', '/app/data')) / 'screenshots'
SCREENSHOT_TIMEOUT = 10  # seconds
SCREENSHOT_QUALITY = 5  # JPEG quality (2-31, lower is better)


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
    
    def capture(self, url: str, stream_id: int, timeout: int = SCREENSHOT_TIMEOUT, extract_stats: bool = True) -> tuple[Optional[str], dict]:
        """
        Capture a screenshot from a stream and optionally extract stats (resolution, fps, bitrate).
        
        Args:
            url: Stream URL
            stream_id: Stream ID (used for filename)
            timeout: Maximum time to wait for capture
            extract_stats: If True, attempts to parse stats from FFmpeg output
            
        Returns:
            Tuple of (screenshot_path, stats_dict)
            screenshot_path is None if failed
            stats_dict contains 'width', 'height', 'fps', 'bitrate' if found
        """
        try:
            # Filename: stream_id.jpg (overwrite to save space)
            filename = f"{stream_id}.jpg"
            output_path = self.screenshot_dir / filename
            
            # Use FFmpeg to capture a single frame
            # Add -analyzeduration and -probesize to help with stream info detection
            process = subprocess.Popen(
                [
                    'ffmpeg',
                    '-y',  # Overwrite output files
                    '-analyzeduration', '10000000', # 10s of analysis for better probe
                    '-probesize', '10000000',      # 10MB probe size
                    '-i', url,
                    '-ss', '00:00:01',  # Seek 1 second in (avoid black frames)
                    '-vframes', '1',  # Capture 1 frame
                    '-q:v', str(SCREENSHOT_QUALITY),  # JPEG quality
                    '-f', 'image2',
                    str(output_path)
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
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
                logger.debug(f"Captured screenshot for stream {stream_id}: {relative_path}")
                
                # Parse stats if requested
                if extract_stats and stderr:
                    import re
                    
                    # 1. Bitrate
                    # Look for "bitrate: 1234 kb/s" in stderr
                    bitrate_match = re.search(r'bitrate:\s+(\d+)\s+kb/s', stderr)
                    if bitrate_match:
                        try:
                            stats['bitrate'] = int(bitrate_match.group(1))
                        except ValueError:
                            pass
                    
                    # 2. Resolution (look for "Video: ... 1920x1080 ...")
                    # Use a robust regex that requires at least 3 digits for width/height to avoid aspect ratios
                    res_match = re.search(r'Video:.*? (\d{3,5})x(\d{3,5})', stderr)
                    if res_match:
                        try:
                            stats['width'] = int(res_match.group(1))
                            stats['height'] = int(res_match.group(2))
                        except ValueError:
                            pass
                            
                    # 3. FPS
                    fps_match = re.search(r'(\d+(?:\.\d+)?)\s*fps', stderr)
                    if fps_match:
                        try:
                            stats['fps'] = float(fps_match.group(1))
                        except ValueError:
                            pass
                            
                    if stats:
                        logger.info(f"Extracted stats from screenshot probe for stream {stream_id}: {stats}")
                
                return relative_path, stats
            else:
                logger.warning(f"Screenshot failed for stream {stream_id}, exit code: {process.returncode}")
                # Try to parse stats even on failure if we got stderr (might be useful for debugging)
                return None, {}
                
        except Exception as e:
            logger.error(f"Error capturing screenshot for stream {stream_id}: {e}")
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
