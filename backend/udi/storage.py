"""
Storage layer for the Universal Data Index (UDI) system.

Provides JSON file-based persistence for cached data with thread-safe operations.
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from logging_config import setup_logging

logger = setup_logging(__name__)

# Configuration directory - persisted via Docker volume
# Use current directory as fallback if CONFIG_DIR is not set or not accessible
CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', str(Path(__file__).parent.parent / 'data')))


class UDIStorage:
    """JSON file-based storage for UDI data with thread-safe operations."""
    
    def __init__(self, storage_dir: Optional[Path] = None):
        """Initialize the UDI storage.
        
        Args:
            storage_dir: Directory for storing UDI data files.
                        Defaults to CONFIG_DIR/udi/
        """
        if storage_dir is None:
            storage_dir = CONFIG_DIR / 'udi'
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # File paths for each entity type
        self.channels_file = self.storage_dir / 'channels.json'
        self.streams_file = self.storage_dir / 'streams.json'
        self.channel_groups_file = self.storage_dir / 'channel_groups.json'
        self.logos_file = self.storage_dir / 'logos.json'
        self.m3u_accounts_file = self.storage_dir / 'm3u_accounts.json'
        self.channel_profiles_file = self.storage_dir / 'channel_profiles.json'
        self.profile_channels_file = self.storage_dir / 'profile_channels.json'
        self.metadata_file = self.storage_dir / 'metadata.json'
        
        # Thread locks for each data type
        self._channels_lock = threading.Lock()
        self._streams_lock = threading.Lock()
        self._channel_groups_lock = threading.Lock()
        self._logos_lock = threading.Lock()
        self._m3u_accounts_lock = threading.Lock()
        self._channel_profiles_lock = threading.Lock()
        self._profile_channels_lock = threading.Lock()
        self._metadata_lock = threading.Lock()
        
        logger.info(f"UDI storage initialized at {self.storage_dir}")
    
    def _load_json(self, file_path: Path) -> Optional[Any]:
        """Load JSON data from a file.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            Parsed JSON data or None if file doesn't exist or is invalid
        """
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning(f"Could not load {file_path}: {e}")
            return None
    
    def _save_json(self, file_path: Path, data: Any) -> bool:
        """Save data to a JSON file.
        
        Args:
            file_path: Path to the JSON file
            data: Data to save (must be JSON-serializable)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save {file_path}: {e}")
            return False
    
    # Channels
    def load_channels(self) -> List[Dict[str, Any]]:
        """Load all channels from storage.
        
        Returns:
            List of channel dictionaries
        """
        with self._channels_lock:
            data = self._load_json(self.channels_file)
            return data if isinstance(data, list) else []
    
    def save_channels(self, channels: List[Dict[str, Any]]) -> bool:
        """Save channels to storage.
        
        Args:
            channels: List of channel dictionaries
            
        Returns:
            True if successful
        """
        with self._channels_lock:
            success = self._save_json(self.channels_file, channels)
            if success:
                self._update_metadata('channels_last_updated')
            return success
    
    def get_channel_by_id(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific channel by ID.
        
        Args:
            channel_id: The channel ID
            
        Returns:
            Channel dictionary or None if not found
        """
        channels = self.load_channels()
        for channel in channels:
            if channel.get('id') == channel_id:
                return channel
        return None
    
    def update_channel(self, channel_id: int, channel_data: Dict[str, Any]) -> bool:
        """Update a specific channel in storage.
        
        This method writes the entire channels file for each update to maintain
        data consistency. For high-frequency batch updates, use save_channels()
        instead to write all changes at once.
        
        Args:
            channel_id: The channel ID
            channel_data: Updated channel data
            
        Returns:
            True if successful
        """
        with self._channels_lock:
            channels = self._load_json(self.channels_file) or []
            updated = False
            for i, channel in enumerate(channels):
                if channel.get('id') == channel_id:
                    channels[i] = channel_data
                    updated = True
                    break
            
            if not updated:
                channels.append(channel_data)
            
            return self._save_json(self.channels_file, channels)
    
    # Streams
    def load_streams(self) -> List[Dict[str, Any]]:
        """Load all streams from storage.
        
        Returns:
            List of stream dictionaries
        """
        with self._streams_lock:
            data = self._load_json(self.streams_file)
            return data if isinstance(data, list) else []
    
    def save_streams(self, streams: List[Dict[str, Any]]) -> bool:
        """Save streams to storage.
        
        Args:
            streams: List of stream dictionaries
            
        Returns:
            True if successful
        """
        with self._streams_lock:
            success = self._save_json(self.streams_file, streams)
            if success:
                self._update_metadata('streams_last_updated')
            return success
    
    def get_stream_by_id(self, stream_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific stream by ID.
        
        Args:
            stream_id: The stream ID
            
        Returns:
            Stream dictionary or None if not found
        """
        streams = self.load_streams()
        for stream in streams:
            if stream.get('id') == stream_id:
                return stream
        return None
    
    def update_stream(self, stream_id: int, stream_data: Dict[str, Any]) -> bool:
        """Update a specific stream in storage.
        
        Args:
            stream_id: The stream ID
            stream_data: Updated stream data
            
        Returns:
            True if successful
        """
        with self._streams_lock:
            streams = self._load_json(self.streams_file) or []
            updated = False
            for i, stream in enumerate(streams):
                if stream.get('id') == stream_id:
                    streams[i] = stream_data
                    updated = True
                    break
            
            if not updated:
                streams.append(stream_data)
            
            return self._save_json(self.streams_file, streams)
    
    # Channel Groups
    def load_channel_groups(self) -> List[Dict[str, Any]]:
        """Load all channel groups from storage.
        
        Returns:
            List of channel group dictionaries
        """
        with self._channel_groups_lock:
            data = self._load_json(self.channel_groups_file)
            return data if isinstance(data, list) else []
    
    def save_channel_groups(self, groups: List[Dict[str, Any]]) -> bool:
        """Save channel groups to storage.
        
        Args:
            groups: List of channel group dictionaries
            
        Returns:
            True if successful
        """
        with self._channel_groups_lock:
            success = self._save_json(self.channel_groups_file, groups)
            if success:
                self._update_metadata('channel_groups_last_updated')
            return success
    
    # Logos
    def load_logos(self) -> List[Dict[str, Any]]:
        """Load all logos from storage.
        
        Returns:
            List of logo dictionaries
        """
        with self._logos_lock:
            data = self._load_json(self.logos_file)
            return data if isinstance(data, list) else []
    
    def save_logos(self, logos: List[Dict[str, Any]]) -> bool:
        """Save logos to storage.
        
        Args:
            logos: List of logo dictionaries
            
        Returns:
            True if successful
        """
        with self._logos_lock:
            success = self._save_json(self.logos_file, logos)
            if success:
                self._update_metadata('logos_last_updated')
            return success
    
    def get_logo_by_id(self, logo_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific logo by ID.
        
        Args:
            logo_id: The logo ID
            
        Returns:
            Logo dictionary or None if not found
        """
        logos = self.load_logos()
        for logo in logos:
            if logo.get('id') == logo_id:
                return logo
        return None
    
    # M3U Accounts
    def load_m3u_accounts(self) -> List[Dict[str, Any]]:
        """Load all M3U accounts from storage.
        
        Returns:
            List of M3U account dictionaries
        """
        with self._m3u_accounts_lock:
            data = self._load_json(self.m3u_accounts_file)
            return data if isinstance(data, list) else []
    
    def save_m3u_accounts(self, accounts: List[Dict[str, Any]]) -> bool:
        """Save M3U accounts to storage.
        
        Args:
            accounts: List of M3U account dictionaries
            
        Returns:
            True if successful
        """
        with self._m3u_accounts_lock:
            success = self._save_json(self.m3u_accounts_file, accounts)
            if success:
                self._update_metadata('m3u_accounts_last_updated')
            return success
            return success
    
    # Channel Profiles
    def load_channel_profiles(self) -> List[Dict[str, Any]]:
        """Load all channel profiles from storage.
        
        Returns:
            List of channel profile dictionaries
        """
        with self._channel_profiles_lock:
            data = self._load_json(self.channel_profiles_file)
            return data if isinstance(data, list) else []
    
    def save_channel_profiles(self, profiles: List[Dict[str, Any]]) -> bool:
        """Save channel profiles to storage.
        
        Args:
            profiles: List of channel profile dictionaries
            
        Returns:
            True if successful
        """
        with self._channel_profiles_lock:
            success = self._save_json(self.channel_profiles_file, profiles)
            if success:
                self._update_metadata('channel_profiles_last_updated')
            return success
    
    # Profile Channels (channel-profile associations)
    def load_profile_channels(self) -> Dict[int, Dict[str, Any]]:
        """Load profile channels data from storage.
        
        Returns:
            Dictionary mapping profile_id to profile channel data
        """
        with self._profile_channels_lock:
            data = self._load_json(self.profile_channels_file)
            # Convert string keys back to integers and validate values are dictionaries
            if isinstance(data, dict):
                result = {}
                for k, v in data.items():
                    try:
                        # Convert key to integer
                        key = int(k) if isinstance(k, str) else k
                        # Validate value is a dictionary, skip if not
                        if isinstance(v, dict):
                            result[key] = v
                        else:
                            logger.warning(f"Skipping invalid profile_channels data for profile {k}: value is {type(v).__name__}, not dict")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Skipping invalid profile_channels key {k}: {e}")
                return result
            return {}
    
    def save_profile_channels(self, profile_channels: Dict[int, Dict[str, Any]]) -> bool:
        """Save profile channels data to storage.
        
        Args:
            profile_channels: Dictionary mapping profile_id to profile channel data
            
        Returns:
            True if successful
        """
        with self._profile_channels_lock:
            success = self._save_json(self.profile_channels_file, profile_channels)
            if success:
                self._update_metadata('profile_channels_last_updated')
            return success
    
    def load_profile_channels_by_id(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Load channel data for a specific profile.
        
        Args:
            profile_id: The profile ID
            
        Returns:
            Profile channel data or None
        """
        all_profile_channels = self.load_profile_channels()
        return all_profile_channels.get(profile_id)
    
    def save_profile_channels_by_id(self, profile_id: int, channels_data: Dict[str, Any]) -> bool:
        """Save channel data for a specific profile.
        
        Args:
            profile_id: The profile ID
            channels_data: Channel data for the profile
            
        Returns:
            True if successful
        """
        with self._profile_channels_lock:
            all_profile_channels = self.load_profile_channels()
            all_profile_channels[profile_id] = channels_data
            return self.save_profile_channels(all_profile_channels)
    
    # Metadata
    def load_metadata(self) -> Dict[str, Any]:
        """Load UDI metadata.
        
        Returns:
            Metadata dictionary
        """
        with self._metadata_lock:
            data = self._load_json(self.metadata_file)
            return data if isinstance(data, dict) else {}
    
    def save_metadata(self, metadata: Dict[str, Any]) -> bool:
        """Save UDI metadata.
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            True if successful
        """
        with self._metadata_lock:
            return self._save_json(self.metadata_file, metadata)
    
    def _update_metadata(self, field: str) -> None:
        """Update a specific metadata field with current timestamp.
        
        Args:
            field: The metadata field to update
        """
        with self._metadata_lock:
            metadata = self._load_json(self.metadata_file) or {}
            metadata[field] = datetime.now().isoformat()
            self._save_json(self.metadata_file, metadata)
    
    def get_last_updated(self, entity_type: str) -> Optional[str]:
        """Get the last updated timestamp for an entity type.
        
        Args:
            entity_type: One of 'channels', 'streams', 'channel_groups', 'logos', 'm3u_accounts'
            
        Returns:
            ISO format timestamp string or None
        """
        metadata = self.load_metadata()
        return metadata.get(f'{entity_type}_last_updated')
    
    def clear_all(self) -> bool:
        """Clear all stored data.
        
        Returns:
            True if successful
        """
        try:
            for file_path in [
                self.channels_file,
                self.streams_file,
                self.channel_groups_file,
                self.logos_file,
                self.m3u_accounts_file,
                self.metadata_file
            ]:
                if file_path.exists():
                    file_path.unlink()
            logger.info("UDI storage cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear UDI storage: {e}")
            return False
    
    def is_initialized(self) -> bool:
        """Check if UDI storage has been initialized with data.
        
        Returns:
            True if at least one data file exists with content
        """
        return any([
            self.channels_file.exists(),
            self.streams_file.exists(),
            self.channel_groups_file.exists(),
            self.m3u_accounts_file.exists()
        ])
