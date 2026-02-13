#!/usr/bin/env python3
"""
Dead Streams Tracker for StreamFlow.

This module tracks dead streams in a JSON file using stream URLs as unique keys.
Stream URLs are used instead of names because multiple streams can have the same name.
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple

from logging_config import setup_logging, log_function_call, log_function_return, log_exception

# Setup logging for this module
logger = setup_logging(__name__)

# Configuration directory
CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', '/app/data'))


class DeadStreamsTracker:
    """Tracks dead streams in a JSON file using stream URLs as keys."""
    
    def __init__(self, tracker_file=None):
        """Initialize the dead streams tracker.
        
        Args:
            tracker_file: Path to the JSON file for tracking dead streams.
                         Defaults to CONFIG_DIR/dead_streams.json
        """
        if tracker_file is None:
            tracker_file = CONFIG_DIR / 'dead_streams.json'
        self.tracker_file = Path(tracker_file)
        self.lock = threading.Lock()
        self.dead_streams = self._load_dead_streams()
    
    def _load_dead_streams(self) -> Dict[str, Dict]:
        """Load dead streams data from JSON file.
        
        Returns:
            Dict mapping stream URLs to stream metadata
        """
        if self.tracker_file.exists():
            try:
                with open(self.tracker_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.warning(f"Could not load dead streams from {self.tracker_file}: {e}")
        return {}
    
    def _save_dead_streams(self):
        """Save dead streams data to JSON file.
        
        Note: This method assumes the lock is already held by the caller.
        """
        try:
            self.tracker_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.tracker_file, 'w') as f:
                json.dump(self.dead_streams, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save dead streams: {e}")
    
    def mark_as_dead(self, stream_url: str, stream_id: int, stream_name: str, channel_id: int = None, reason: str = 'unknown') -> bool:
        """Mark a stream as dead.
        
        Args:
            stream_url: The URL of the stream (used as unique key)
            stream_id: The stream ID in Dispatcharr
            stream_name: The name of the stream
            channel_id: The channel ID where this stream was found (optional)
            reason: The reason why the stream is dead (e.g., 'offline', 'low_quality')
            
        Returns:
            bool: True if successful
        """
        try:
            with self.lock:
                self.dead_streams[stream_url] = {
                    'stream_id': stream_id,
                    'stream_name': stream_name,
                    'marked_dead_at': datetime.now().isoformat(),
                    'url': stream_url,
                    'channel_id': channel_id,
                    'reason': reason
                }
                self._save_dead_streams()
            logger.warning(f"🔴 MARKED STREAM AS DEAD: {stream_name} (Reason: {reason}, URL: {stream_url})")
            return True
        except Exception as e:
            logger.error(f"❌ Error marking stream as dead: {e}")
            return False
    
    def mark_as_alive(self, stream_url: str) -> bool:
        """Mark a stream as alive (remove from dead streams).
        
        Args:
            stream_url: The URL of the stream
            
        Returns:
            bool: True if successful
        """
        try:
            with self.lock:
                if stream_url in self.dead_streams:
                    stream_info = self.dead_streams.pop(stream_url)
                    self._save_dead_streams()
                    logger.info(f"🟢 REVIVED STREAM: {stream_info.get('stream_name', 'Unknown')} (URL: {stream_url})")
                    return True
                else:
                    logger.debug(f"Stream not in dead list: {stream_url}")
                    return True
        except Exception as e:
            logger.error(f"❌ Error marking stream as alive: {e}")
            return False
    
    def is_dead(self, stream_url: str) -> bool:
        """Check if a stream is marked as dead.
        
        Args:
            stream_url: The URL of the stream
            
        Returns:
            bool: True if stream is dead
        """
        with self.lock:
            return stream_url in self.dead_streams
    
    def get_dead_reason(self, stream_url: str) -> Optional[str]:
        """Get the reason why a stream was marked as dead.
        
        Args:
            stream_url: The URL of the stream
            
        Returns:
            Optional[str]: The reason ('offline', 'low_quality', etc.) or None if not dead
        """
        with self.lock:
            info = self.dead_streams.get(stream_url)
            return info.get('reason') if info else None

    def is_offline(self, stream_url: str) -> bool:
        """Check if a stream is specifically 'offline' (truly dead).
        
        Args:
            stream_url: The URL of the stream
            
        Returns:
            bool: True if stream is marked as 'offline'
        """
        return self.get_dead_reason(stream_url) == 'offline'
    
    def get_dead_streams(self) -> Dict[str, Dict]:
        """Get all dead streams.
        
        Returns:
            Dict mapping stream URLs to stream metadata
        """
        with self.lock:
            return self.dead_streams.copy()
    
    def get_dead_streams_count_for_channel(self, channel_id: int) -> int:
        """Get count of dead streams for a specific channel.
        
        Args:
            channel_id: The channel ID to count dead streams for
            
        Returns:
            int: Number of dead streams for this channel
        """
        with self.lock:
            count = 0
            for stream_info in self.dead_streams.values():
                if stream_info.get('channel_id') == channel_id:
                    count += 1
            return count
    
    def get_dead_streams_for_channel(self, channel_id: int) -> Dict[str, Dict]:
        """Get dead streams for a specific channel.
        
        Args:
            channel_id: The channel ID to get dead streams for
            
        Returns:
            Dict mapping stream URLs to stream metadata for this channel
        """
        with self.lock:
            channel_dead_streams = {}
            for stream_url, stream_info in self.dead_streams.items():
                if stream_info.get('channel_id') == channel_id:
                    channel_dead_streams[stream_url] = stream_info.copy()
            return channel_dead_streams
    
    def remove_dead_streams_by_channel_id(self, channel_id: int) -> int:
        """Remove all dead streams for a specific channel from tracking.
        
        This is used during single channel checks to clear all dead streams
        for the channel before refreshing the playlist and rematching.
        Unlike remove_dead_streams_for_channel(), this method removes streams
        based on channel_id match, not URL match, which handles cases where
        playlist refresh creates new streams with different URLs.
        
        Args:
            channel_id: The channel ID to remove dead streams for
            
        Returns:
            int: Number of dead streams removed from tracking
        """
        removed_count = 0
        try:
            with self.lock:
                # Find dead streams that belong to this channel by channel_id
                dead_urls_to_remove = []
                for dead_url, stream_info in self.dead_streams.items():
                    if stream_info.get('channel_id') == channel_id:
                        dead_urls_to_remove.append(dead_url)
                
                # Remove them from tracking and collect names for batch logging
                removed_streams = []
                for url in dead_urls_to_remove:
                    stream_info = self.dead_streams.pop(url)
                    removed_count += 1
                    removed_streams.append(stream_info.get('stream_name', 'Unknown'))
                
                # Save if we removed any
                if removed_count > 0:
                    self._save_dead_streams()
                    # Log all removed streams in a single batch message
                    logger.info(f"🗑️ Removed {removed_count} dead stream(s) from channel {channel_id} before refresh: {', '.join(removed_streams)}")
            
            return removed_count
        except Exception as e:
            logger.error(f"❌ Error removing dead streams for channel {channel_id}: {e}")
            return 0
    
    def remove_dead_streams_for_channel(self, channel_stream_urls: set) -> int:
        """Remove dead streams for a specific channel from tracking.
        
        This is used during single channel checks to clear all dead streams
        for the channel before refreshing the playlist and rematching.
        
        Args:
            channel_stream_urls: Set of URLs for streams in the channel
            
        Returns:
            int: Number of dead streams removed from tracking
        """
        removed_count = 0
        try:
            with self.lock:
                # Find dead streams that belong to this channel
                dead_urls_to_remove = []
                for dead_url in self.dead_streams.keys():
                    if dead_url in channel_stream_urls:
                        dead_urls_to_remove.append(dead_url)
                
                # Remove them from tracking
                for url in dead_urls_to_remove:
                    stream_info = self.dead_streams.pop(url)
                    removed_count += 1
                    logger.info(f"🗑️ Removed dead stream from channel tracking: {stream_info.get('stream_name', 'Unknown')} (URL: {url})")
                
                # Save if we removed any
                if removed_count > 0:
                    self._save_dead_streams()
                    logger.info(f"Removed {removed_count} dead stream(s) for channel before refresh")
            
            return removed_count
        except Exception as e:
            logger.error(f"❌ Error removing dead streams for channel: {e}")
            return 0
    
    def cleanup_removed_streams(self, current_stream_urls: set) -> int:
        """Remove dead streams that are no longer in the playlist.
        
        Args:
            current_stream_urls: Set of URLs for streams currently in the playlist
            
        Returns:
            int: Number of dead streams removed from tracking
        """
        removed_count = 0
        try:
            with self.lock:
                # Find dead streams that are no longer in the current playlist
                dead_urls_to_remove = []
                for dead_url in self.dead_streams.keys():
                    if dead_url not in current_stream_urls:
                        dead_urls_to_remove.append(dead_url)
                
                # Remove them from tracking
                for url in dead_urls_to_remove:
                    stream_info = self.dead_streams.pop(url)
                    removed_count += 1
                    logger.info(f"🗑️ Removed dead stream from tracking (no longer in playlist): {stream_info.get('stream_name', 'Unknown')} (URL: {url})")
                
                # Save if we removed any
                if removed_count > 0:
                    self._save_dead_streams()
                    logger.info(f"Cleaned up {removed_count} dead stream(s) that are no longer in playlist")
            
            return removed_count
        except Exception as e:
            logger.error(f"❌ Error cleaning up removed streams: {e}")
            return 0
    
    def clear_all_dead_streams(self) -> int:
        """Clear ALL dead streams from tracking.
        
        This is used during global actions to give all previously dead streams
        a second chance to be re-added and re-checked.
        
        Returns:
            int: Number of dead streams cleared
        """
        try:
            with self.lock:
                count = len(self.dead_streams)
                if count > 0:
                    logger.info(f"🔄 Clearing ALL {count} dead stream(s) from tracker for global action")
                    self.dead_streams.clear()
                    self._save_dead_streams()
                    logger.info(f"✓ Cleared {count} dead stream(s) - they will be given a second chance")
                return count
        except Exception as e:
            logger.error(f"❌ Error clearing all dead streams: {e}")
            return 0
