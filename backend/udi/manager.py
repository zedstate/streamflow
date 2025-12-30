"""
Universal Data Index (UDI) Manager - Single source of truth for all Dispatcharr data.

The UDIManager is a singleton class that:
- Manages all data access for channels, streams, groups, logos, and M3U accounts
- Provides cached data with configurable TTL
- Supports background refresh
- Handles data persistence via JSON storage

Usage:
    from udi import get_udi_manager
    
    udi = get_udi_manager()
    
    # Initialize on startup (fetches all data)
    udi.initialize()
    
    # Get data (from cache)
    channels = udi.get_channels()
    streams = udi.get_streams()
    
    # Force refresh
    udi.refresh_all()
"""

import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Set

from udi.storage import UDIStorage
from udi.fetcher import UDIFetcher
from udi.cache import UDICache

from logging_config import setup_logging

# Import at module level for better performance
from dispatcharr_config import get_dispatcharr_config

# Import M3U priority config for merging priority_mode
from m3u_priority_config import get_m3u_priority_config

logger = setup_logging(__name__)


class UDIManager:
    """
    Universal Data Index Manager - Singleton class for all Dispatcharr data access.
    
    This class provides:
    - Centralized data access for all Dispatcharr entities
    - Automatic cache management with configurable TTL
    - Background refresh capability
    - Thread-safe operations
    """
    
    def __init__(self):
        """Initialize the UDI Manager with file-based storage."""
        # Use file-based storage only
        from udi.storage import UDIStorage
        self.storage = UDIStorage()
        logger.info("Using file storage for UDI")
        
        self.fetcher = UDIFetcher()
        self.cache = UDICache()
        
        self._initialized = False
        self._lock = threading.Lock()
        self._refresh_thread = None
        self._refresh_running = False
        
        # In-memory caches for faster access
        self._channels_cache: List[Dict[str, Any]] = []
        self._streams_cache: List[Dict[str, Any]] = []
        self._channel_groups_cache: List[Dict[str, Any]] = []
        self._logos_cache: List[Dict[str, Any]] = []
        self._m3u_accounts_cache: List[Dict[str, Any]] = []
        self._channel_profiles_cache: List[Dict[str, Any]] = []
        self._profile_channels_cache: Dict[int, Dict[str, Any]] = {}
        
        # Index caches for fast lookups
        self._channels_by_id: Dict[int, Dict[str, Any]] = {}
        self._streams_by_id: Dict[int, Dict[str, Any]] = {}
        self._streams_by_url: Dict[str, Dict[str, Any]] = {}
        self._valid_stream_ids: Set[int] = set()
        self._profiles_by_id: Dict[int, Dict[str, Any]] = {}
        
        # Proxy status cache for real-time stream viewer information
        self._proxy_status_cache: Dict[str, Any] = {}
        self._proxy_status_last_fetch: float = 0
        self._proxy_status_ttl: float = 5.0  # Cache proxy status for 5 seconds
        
        logger.info("UDI Manager created")
    
    def initialize(self, force_refresh: bool = False) -> bool:
        """
        Initialize the UDI Manager by loading or fetching all data.
        
        This should be called on application startup. It will:
        1. Load existing data from storage if available
        2. Fetch fresh data from the API if storage is empty or force_refresh is True
        
        Args:
            force_refresh: If True, always fetch fresh data from API
            
        Returns:
            True if initialization successful
        """
        with self._lock:
            if self._initialized and not force_refresh:
                logger.debug("UDI Manager already initialized")
                return True
            
            logger.info("Initializing UDI Manager...")
            
            # Check if we have existing data
            if not force_refresh and self.storage.is_initialized():
                logger.info("Loading existing data from storage...")
                self._load_from_storage()
                self._initialized = True
                logger.info("UDI Manager initialized from storage")
                return True
            
            # Check if Dispatcharr is configured before fetching from API
            config = get_dispatcharr_config()
            if not config.is_configured():
                logger.warning("Cannot fetch data from API: Dispatcharr credentials not configured")
                # Mark as initialized with empty data to prevent repeated attempts
                self._initialized = True
                return False
            
            # Fetch fresh data from API
            logger.info("Fetching fresh data from API...")
            try:
                success = self.refresh_all()
                if success:
                    self._initialized = True
                    logger.info("UDI Manager initialized with fresh data")
                    return True
                else:
                    logger.error("Failed to initialize UDI Manager")
                    return False
            except Exception as e:
                logger.error(f"Error initializing UDI Manager: {e}")
                return False
    
    def _load_from_storage(self) -> None:
        """Load all data from storage into memory caches."""
        self._channels_cache = self.storage.load_channels()
        self._streams_cache = self.storage.load_streams()
        self._channel_groups_cache = self.storage.load_channel_groups()
        self._logos_cache = self.storage.load_logos()
        self._m3u_accounts_cache = self.storage.load_m3u_accounts()
        self._channel_profiles_cache = self.storage.load_channel_profiles()
        self._profile_channels_cache = self.storage.load_profile_channels()
        
        # Build index caches
        self._build_indexes()
        
        # Mark caches as refreshed based on storage metadata
        metadata = self.storage.load_metadata()
        for entity_type in ['channels', 'streams', 'channel_groups', 'logos', 'm3u_accounts', 'channel_profiles']:
            timestamp_str = metadata.get(f'{entity_type}_last_updated')
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    self.cache.mark_refreshed(entity_type, timestamp)
                except ValueError:
                    pass
        
        # Also mark profile_channels if present
        profile_channels_timestamp = metadata.get('profile_channels_last_updated')
        if profile_channels_timestamp:
            try:
                timestamp = datetime.fromisoformat(profile_channels_timestamp)
                self.cache.mark_refreshed('profile_channels', timestamp)
            except ValueError:
                pass
        
        logger.info(
            f"Loaded from storage: {len(self._channels_cache)} channels, "
            f"{len(self._streams_cache)} streams, {len(self._channel_groups_cache)} groups, "
            f"{len(self._logos_cache)} logos, {len(self._m3u_accounts_cache)} M3U accounts, "
            f"{len(self._channel_profiles_cache)} profiles, "
            f"{len(self._profile_channels_cache)} profile channels"
        )
    
    def _build_indexes(self) -> None:
        """Build index caches for fast lookups."""
        self._channels_by_id = {ch.get('id'): ch for ch in self._channels_cache if ch.get('id') is not None}
        self._streams_by_id = {st.get('id'): st for st in self._streams_cache if st.get('id') is not None}
        self._streams_by_url = {st.get('url'): st for st in self._streams_cache if st.get('url')}
        self._valid_stream_ids = set(self._streams_by_id.keys())
        self._profiles_by_id = {p.get('id'): p for p in self._channel_profiles_cache if p.get('id') is not None}
    
    # === Data Access Methods ===
    
    def is_initialized(self) -> bool:
        """Check if the UDI Manager has been initialized.
        
        Returns:
            True if initialized, False otherwise
        """
        return self._initialized
    
    def get_channels(self) -> List[Dict[str, Any]]:
        """Get all channels.
        
        Returns:
            List of channel dictionaries
        """
        self._ensure_initialized()
        return self._channels_cache.copy()
    
    def get_channel_by_id(self, channel_id: int, fetch_if_missing: bool = True) -> Optional[Dict[str, Any]]:
        """Get a specific channel by ID.
        
        If the channel is not in the cache and fetch_if_missing is True,
        attempts to fetch it from the API and add it to the cache.
        
        Args:
            channel_id: The channel ID
            fetch_if_missing: If True, fetch from API when not in cache (default: True)
            
        Returns:
            Channel dictionary or None if not found
        """
        self._ensure_initialized()
        channel = self._channels_by_id.get(channel_id)
        
        if channel is None and fetch_if_missing:
            # Channel not in cache, try fetching from API
            logger.debug(f"Channel {channel_id} not in cache, fetching from API")
            try:
                # Fetch channel from Dispatcharr API (returns channel dict or None)
                channel = self.fetcher.fetch_channel_by_id(channel_id)
                if channel:
                    # Add to caches under lock to ensure thread safety
                    with self._lock:
                        # Only add if still not in cache (could have been added by another thread)
                        if channel_id not in self._channels_by_id:
                            self._channels_by_id[channel_id] = channel
                            self._channels_cache.append(channel)
                        else:
                            # Already in cache, use the cached version
                            channel = self._channels_by_id[channel_id]
                    logger.info(f"Fetched and cached channel {channel_id}")
            except Exception as e:
                logger.warning(f"Failed to fetch channel {channel_id} from API: {e}")
                channel = None
        
        return channel
    
    def get_channel_streams(self, channel_id: int) -> List[Dict[str, Any]]:
        """Get streams for a specific channel.
        
        Args:
            channel_id: The channel ID
            
        Returns:
            List of stream dictionaries for the channel
        """
        self._ensure_initialized()
        channel = self._channels_by_id.get(channel_id)
        if not channel:
            return []
        
        stream_ids = channel.get('streams', [])
        return [self._streams_by_id.get(sid) for sid in stream_ids if sid in self._streams_by_id]
    
    def get_streams(self, log_result: bool = True) -> List[Dict[str, Any]]:
        """Get all streams.
        
        Args:
            log_result: Whether to log the number of streams returned
            
        Returns:
            List of stream dictionaries
        """
        self._ensure_initialized()
        if log_result:
            logger.info(f"Returning {len(self._streams_cache)} streams from UDI")
        return self._streams_cache.copy()
    
    def get_stream_by_id(self, stream_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific stream by ID.
        
        Args:
            stream_id: The stream ID
            
        Returns:
            Stream dictionary or None if not found
        """
        self._ensure_initialized()
        return self._streams_by_id.get(stream_id)
    
    def get_stream_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get a specific stream by URL.
        
        Args:
            url: The stream URL
            
        Returns:
            Stream dictionary or None if not found
        """
        self._ensure_initialized()
        return self._streams_by_url.get(url)
    
    def get_valid_stream_ids(self) -> Set[int]:
        """Get a set of all valid stream IDs.
        
        Returns:
            Set of valid stream IDs
        """
        self._ensure_initialized()
        return self._valid_stream_ids.copy()
    
    def get_channel_groups(self) -> List[Dict[str, Any]]:
        """Get all channel groups that have associated channels.
        
        Only returns groups where channel_count > 0 to avoid cluttering
        the Group Management UI.
        
        Returns:
            List of channel group dictionaries with channels
        """
        self._ensure_initialized()
        # Filter out groups with no channels
        return [
            group for group in self._channel_groups_cache 
            if group.get('channel_count', 0) > 0
        ]
    
    def get_channel_group_by_id(self, group_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific channel group by ID.
        
        Args:
            group_id: The channel group ID
            
        Returns:
            Channel group dictionary or None if not found
        """
        self._ensure_initialized()
        for group in self._channel_groups_cache:
            if group.get('id') == group_id:
                return group
        return None
    
    def get_channels_by_group(self, group_id: int) -> Optional[List[Dict[str, Any]]]:
        """Get all channels that belong to a specific channel group.
        
        Args:
            group_id: The channel group ID
            
        Returns:
            List of channel dictionaries or None if group not found
        """
        self._ensure_initialized()
        
        # Verify group exists
        group = self.get_channel_group_by_id(group_id)
        if not group:
            return None
        
        # Filter channels by group
        channels = [
            channel for channel in self._channels_cache
            if channel.get('channel_group_id') == group_id
        ]
        return channels
    
    def get_logos(self) -> List[Dict[str, Any]]:
        """Get all logos.
        
        Returns:
            List of logo dictionaries
        """
        self._ensure_initialized()
        return self._logos_cache.copy()
    
    def get_logo_by_id(self, logo_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific logo by ID.
        
        Args:
            logo_id: The logo ID
            
        Returns:
            Logo dictionary or None if not found
        """
        self._ensure_initialized()
        for logo in self._logos_cache:
            if logo.get('id') == logo_id:
                return logo
        return None
    
    def get_m3u_accounts(self) -> List[Dict[str, Any]]:
        """Get all M3U accounts with priority_mode merged from local config.
        
        Returns:
            List of M3U account dictionaries with priority_mode included
        """
        self._ensure_initialized()
        logger.debug(f"Returning {len(self._m3u_accounts_cache)} M3U accounts from UDI cache")
        accounts = self._m3u_accounts_cache.copy()
        
        # Merge priority_mode from local configuration
        try:
            priority_config = get_m3u_priority_config()
            for account in accounts:
                account_id = account.get('id')
                if account_id:
                    account['priority_mode'] = priority_config.get_priority_mode(account_id)
        except Exception as e:
            logger.error(f"Error merging priority_mode: {e}")
        
        return accounts
    
    def get_m3u_account_by_id(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific M3U account by ID with priority_mode merged.
        
        Args:
            account_id: M3U account ID
            
        Returns:
            M3U account dictionary or None if not found
        """
        self._ensure_initialized()
        
        # Try fast lookup from storage if using Redis
        if hasattr(self.storage, 'get_m3u_account_by_id'):
            account = self.storage.get_m3u_account_by_id(account_id)
            if account:
                # Merge priority_mode from local configuration
                try:
                    priority_config = get_m3u_priority_config()
                    account['priority_mode'] = priority_config.get_priority_mode(account_id)
                except Exception as e:
                    logger.error(f"Error merging priority_mode: {e}")
                return account
        
        # Fallback to in-memory cache
        for account in self._m3u_accounts_cache:
            if account.get('id') == account_id:
                result = account.copy()
                # Merge priority_mode from local configuration
                try:
                    priority_config = get_m3u_priority_config()
                    result['priority_mode'] = priority_config.get_priority_mode(account_id)
                except Exception as e:
                    logger.error(f"Error merging priority_mode: {e}")
                return result
        
        logger.debug(f"M3U account {account_id} not found in UDI")
        return None
    
    def get_channel_profiles(self) -> List[Dict[str, Any]]:
        """Get all channel profiles.
        
        Returns:
            List of channel profile dictionaries
        """
        self._ensure_initialized()
        return self._channel_profiles_cache.copy()
    
    def get_channel_profile_by_id(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific channel profile by ID.
        
        Args:
            profile_id: The profile ID
            
        Returns:
            Profile dictionary or None if not found
        """
        self._ensure_initialized()
        return self._profiles_by_id.get(profile_id)
    
    def get_profile_channels(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get channel associations for a specific profile.
        
        Args:
            profile_id: The profile ID
            
        Returns:
            Profile channel data or None if not cached
        """
        self._ensure_initialized()
        return self._profile_channels_cache.get(profile_id)
    
    def has_custom_streams(self) -> bool:
        """Check if any custom streams exist.
        
        Returns:
            True if at least one custom stream exists
        """
        self._ensure_initialized()
        return any(st.get('is_custom', False) for st in self._streams_cache)
    
    # === Refresh Methods ===
    
    def refresh_all(self) -> bool:
        """Refresh all data from the API.
        
        Returns:
            True if refresh successful
        """
        logger.info("Refreshing all UDI data...")
        
        # Check if Dispatcharr is configured before attempting API calls
        config = get_dispatcharr_config()
        if not config.is_configured():
            logger.warning("Cannot refresh data: Dispatcharr credentials not configured")
            return False
        
        try:
            data = self.fetcher.refresh_all()
            
            # Update in-memory caches
            self._channels_cache = data.get('channels', [])
            self._streams_cache = data.get('streams', [])
            self._channel_groups_cache = data.get('channel_groups', [])
            self._logos_cache = data.get('logos', [])
            self._m3u_accounts_cache = data.get('m3u_accounts', [])
            self._channel_profiles_cache = data.get('channel_profiles', [])
            
            # Fetch profile channels data for all profiles
            profile_ids = [p.get('id') for p in self._channel_profiles_cache if p.get('id')]
            if profile_ids:
                logger.info(f"Fetching channel data for {len(profile_ids)} profiles...")
                self._profile_channels_cache = self.fetcher.fetch_profile_channels(profile_ids)
            else:
                self._profile_channels_cache = {}
            
            # Build index caches
            self._build_indexes()
            
            # Save to storage
            self.storage.save_channels(self._channels_cache)
            self.storage.save_streams(self._streams_cache)
            self.storage.save_channel_groups(self._channel_groups_cache)
            self.storage.save_logos(self._logos_cache)
            self.storage.save_m3u_accounts(self._m3u_accounts_cache)
            self.storage.save_channel_profiles(self._channel_profiles_cache)
            self.storage.save_profile_channels(self._profile_channels_cache)
            
            # Update metadata
            now = datetime.now()
            metadata = {
                'last_full_refresh': now.isoformat(),
                'channels_last_updated': now.isoformat(),
                'streams_last_updated': now.isoformat(),
                'channel_groups_last_updated': now.isoformat(),
                'logos_last_updated': now.isoformat(),
                'm3u_accounts_last_updated': now.isoformat(),
                'channel_profiles_last_updated': now.isoformat(),
                'profile_channels_last_updated': now.isoformat(),
                'version': '1.0.0'
            }
            self.storage.save_metadata(metadata)
            
            # Mark all caches as refreshed
            for entity_type in ['channels', 'streams', 'channel_groups', 'logos', 'm3u_accounts', 'channel_profiles', 'profile_channels']:
                self.cache.mark_refreshed(entity_type, now)
            
            logger.info("UDI data refresh complete")
            return True
            
        except Exception as e:
            logger.error(f"Error refreshing UDI data: {e}")
            return False
    
    def refresh_channels(self) -> bool:
        """Refresh only channels data.
        
        Returns:
            True if refresh successful
        """
        # Check if Dispatcharr is configured
        config = get_dispatcharr_config()
        if not config.is_configured():
            logger.warning("Cannot refresh channels: Dispatcharr credentials not configured")
            return False
        
        logger.info("Refreshing channels...")
        try:
            channels = self.fetcher.fetch_channels()
            self._channels_cache = channels
            self._channels_by_id = {ch.get('id'): ch for ch in channels if ch.get('id') is not None}
            self.storage.save_channels(channels)
            self.cache.mark_refreshed('channels')
            return True
        except Exception as e:
            logger.error(f"Error refreshing channels: {e}")
            return False
    
    def refresh_channel_by_id(self, channel_id: int) -> bool:
        """Refresh a single channel by ID from the API.
        
        This is more efficient than refreshing all channels when only one channel
        needs to be updated (e.g., after modifying its stream list).
        
        Args:
            channel_id: The channel ID to refresh
            
        Returns:
            True if refresh successful
        """
        logger.info(f"Refreshing channel {channel_id}...")
        try:
            channel = self.fetcher.fetch_channel_by_id(channel_id)
            if channel:
                # Update in-memory caches
                with self._lock:
                    self._channels_by_id[channel_id] = channel
                    
                    # Update list cache
                    found = False
                    for i, ch in enumerate(self._channels_cache):
                        if ch.get('id') == channel_id:
                            self._channels_cache[i] = channel
                            found = True
                            break
                    
                    if not found:
                        self._channels_cache.append(channel)
                    
                    # Update storage
                    self.storage.update_channel(channel_id, channel)
                
                logger.info(f"Channel {channel_id} refreshed successfully")
                return True
            else:
                logger.warning(f"Failed to refresh channel {channel_id}: channel not found")
                return False
        except Exception as e:
            logger.error(f"Error refreshing channel {channel_id}: {e}")
            return False
    
    def refresh_streams(self) -> bool:
        """Refresh only streams data.
        
        Returns:
            True if refresh successful
        """
        logger.info("Refreshing streams...")
        try:
            streams = self.fetcher.fetch_streams()
            self._streams_cache = streams
            self._streams_by_id = {st.get('id'): st for st in streams if st.get('id') is not None}
            self._streams_by_url = {st.get('url'): st for st in streams if st.get('url')}
            self._valid_stream_ids = set(self._streams_by_id.keys())
            self.storage.save_streams(streams)
            self.cache.mark_refreshed('streams')
            return True
        except Exception as e:
            logger.error(f"Error refreshing streams: {e}")
            return False
    
    def refresh_channel_groups(self) -> bool:
        """Refresh only channel groups data.
        
        Returns:
            True if refresh successful
        """
        logger.info("Refreshing channel groups...")
        try:
            groups = self.fetcher.fetch_channel_groups()
            self._channel_groups_cache = groups
            self.storage.save_channel_groups(groups)
            self.cache.mark_refreshed('channel_groups')
            return True
        except Exception as e:
            logger.error(f"Error refreshing channel groups: {e}")
            return False
    
    def refresh_m3u_accounts(self) -> bool:
        """Refresh only M3U accounts data.
        
        Returns:
            True if refresh successful
        """
        logger.info("Refreshing M3U accounts...")
        try:
            accounts = self.fetcher.fetch_m3u_accounts()
            self._m3u_accounts_cache = accounts
            self.storage.save_m3u_accounts(accounts)
            self.cache.mark_refreshed('m3u_accounts')
            return True
        except Exception as e:
            logger.error(f"Error refreshing M3U accounts: {e}")
            return False
    
    def refresh_channel_profiles(self) -> bool:
        """Refresh only channel profiles data and their channel associations.
        
        Returns:
            True if refresh successful
        """
        logger.info("Refreshing channel profiles...")
        try:
            profiles = self.fetcher.fetch_channel_profiles()
            self._channel_profiles_cache = profiles
            self._profiles_by_id = {p.get('id'): p for p in profiles if p.get('id') is not None}
            if hasattr(self.storage, 'save_channel_profiles'):
                self.storage.save_channel_profiles(profiles)
            self.cache.mark_refreshed('channel_profiles')
            
            # Also refresh profile channel associations
            profile_ids = [p.get('id') for p in profiles if p.get('id')]
            if profile_ids:
                logger.info(f"Fetching channel data for {len(profile_ids)} profiles...")
                self._profile_channels_cache = self.fetcher.fetch_profile_channels(profile_ids)
                if hasattr(self.storage, 'save_profile_channels'):
                    self.storage.save_profile_channels(self._profile_channels_cache)
                self.cache.mark_refreshed('profile_channels')
            
            return True
        except Exception as e:
            logger.error(f"Error refreshing channel profiles: {e}")
            return False
    
    def invalidate_cache(self, entity_type: Optional[str] = None) -> None:
        """Invalidate cache for entity type(s).
        
        Args:
            entity_type: Specific type to invalidate, or None for all
        """
        if entity_type:
            self.cache.invalidate(entity_type)
        else:
            self.cache.invalidate_all()
    
    # === Background Refresh ===
    
    def start_background_refresh(self, interval_seconds: int = 300) -> None:
        """Start background refresh thread.
        
        Args:
            interval_seconds: Seconds between refresh cycles
        """
        if self._refresh_running:
            logger.warning("Background refresh already running")
            return
        
        self._refresh_running = True
        
        def refresh_loop():
            logger.info(f"Starting background refresh (interval: {interval_seconds}s)")
            while self._refresh_running:
                time.sleep(interval_seconds)
                if self._refresh_running:
                    try:
                        # Refresh data that needs updating based on TTL
                        for entity_type in ['channels', 'streams', 'channel_groups', 'logos', 'm3u_accounts', 'channel_profiles']:
                            if self.cache.needs_refresh(entity_type):
                                getattr(self, f'refresh_{entity_type}')()
                    except Exception as e:
                        logger.error(f"Error in background refresh: {e}")
            logger.info("Background refresh stopped")
        
        self._refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
        self._refresh_thread.start()
        logger.info("Background refresh thread started")
    
    def stop_background_refresh(self) -> None:
        """Stop background refresh thread."""
        if self._refresh_running:
            self._refresh_running = False
            if self._refresh_thread:
                self._refresh_thread.join(timeout=5)
            logger.info("Background refresh stopped")
    
    # === Update Methods (for write-through) ===
    
    def update_channel(self, channel_id: int, channel_data: Dict[str, Any]) -> bool:
        """Update a channel in the cache.
        
        This is called after a successful API update to keep the cache in sync.
        
        Args:
            channel_id: The channel ID
            channel_data: The updated channel data
            
        Returns:
            True if successful
        """
        with self._lock:
            # Update in-memory cache
            self._channels_by_id[channel_id] = channel_data
            
            # Update list cache
            for i, ch in enumerate(self._channels_cache):
                if ch.get('id') == channel_id:
                    self._channels_cache[i] = channel_data
                    break
            else:
                self._channels_cache.append(channel_data)
            
            # Save to storage
            return self.storage.update_channel(channel_id, channel_data)
    
    def update_stream(self, stream_id: int, stream_data: Dict[str, Any]) -> bool:
        """Update a stream in the cache.
        
        This is called after a successful API update to keep the cache in sync.
        
        Args:
            stream_id: The stream ID
            stream_data: The updated stream data
            
        Returns:
            True if successful
        """
        with self._lock:
            # Update in-memory caches
            self._streams_by_id[stream_id] = stream_data
            if stream_data.get('url'):
                self._streams_by_url[stream_data['url']] = stream_data
            
            # Update list cache
            for i, st in enumerate(self._streams_cache):
                if st.get('id') == stream_id:
                    self._streams_cache[i] = stream_data
                    break
            else:
                self._streams_cache.append(stream_data)
                self._valid_stream_ids.add(stream_id)
            
            # Save to storage
            return self.storage.update_stream(stream_id, stream_data)
    
    def update_profile_channels(self, profile_id: int, profile_channels_data: Dict[str, Any]) -> bool:
        """Update profile channels data in the cache.
        
        This is called after fetching profile channels to keep the cache in sync.
        
        Args:
            profile_id: The profile ID
            profile_channels_data: The profile channels data (dict with 'profile' and 'channels' keys)
            
        Returns:
            True if successful
        """
        with self._lock:
            # Update in-memory cache
            self._profile_channels_cache[profile_id] = profile_channels_data
            
            # Save to storage
            if hasattr(self.storage, 'save_profile_channels_by_id'):
                try:
                    return self.storage.save_profile_channels_by_id(profile_id, profile_channels_data)
                except Exception as e:
                    logger.error(f"Error saving profile channels to storage: {e}")
                    return False
            return True
    
    # === Status Methods ===
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current UDI Manager status.
        
        Returns:
            Dictionary with status information
        """
        return {
            'initialized': self._initialized,
            'background_refresh_running': self._refresh_running,
            'data_counts': {
                'channels': len(self._channels_cache),
                'streams': len(self._streams_cache),
                'channel_groups': len(self._channel_groups_cache),
                'logos': len(self._logos_cache),
                'm3u_accounts': len(self._m3u_accounts_cache),
                'channel_profiles': len(self._channel_profiles_cache)
            },
            'cache_status': self.cache.get_status(),
            'storage_path': str(self.storage.storage_dir)
        }
    
    def get_cache_last_refresh(self, entity_type: str) -> Optional[Any]:
        """Get the last refresh time for a specific entity type from cache.
        
        Args:
            entity_type: The entity type to query (e.g., 'channel_profiles')
            
        Returns:
            The last refresh datetime or None if never refreshed
        """
        return self.cache.get_last_refresh(entity_type)
    
    def get_storage_count(self, entity_type: str) -> int:
        """Get the count of entities in storage for a specific type.
        
        Args:
            entity_type: The entity type to query (e.g., 'channel_profiles')
            
        Returns:
            Count of entities in storage, or 0 on error
        """
        # Mapping of entity types to storage loader methods
        entity_loaders = {
            'channels': self.storage.load_channels,
            'streams': self.storage.load_streams,
            'channel_groups': self.storage.load_channel_groups,
            'logos': self.storage.load_logos,
            'm3u_accounts': self.storage.load_m3u_accounts,
            'channel_profiles': self.storage.load_channel_profiles
        }
        
        loader = entity_loaders.get(entity_type)
        if not loader:
            logger.warning(f"Unknown entity type: {entity_type}")
            return 0
        
        try:
            data = loader()
            return len(data) if data else 0
        except Exception as e:
            logger.error(f"Error getting storage count for {entity_type}: {e}")
            return 0
    
    def is_initialized(self) -> bool:
        """Check if UDI Manager is initialized.
        
        Returns:
            True if initialized
        """
        return self._initialized
    
    def _find_account_for_profile(self, profile_id: int) -> Optional[int]:
        """Find the M3U account ID that contains a specific profile.
        
        Args:
            profile_id: M3U account profile ID
            
        Returns:
            M3U account ID or None if profile not found
        """
        accounts = self.get_m3u_accounts()
        
        for account in accounts:
            profiles = account.get('profiles', [])
            if isinstance(profiles, list):
                for profile in profiles:
                    if profile.get('id') == profile_id:
                        return account.get('id')
        
        return None
    
    def _is_channel_status_active(self, status: Dict[str, Any]) -> bool:
        """Check if a channel status indicates it's active.
        
        Args:
            status: Channel status dictionary from proxy
            
        Returns:
            True if channel is active, False otherwise
        """
        if not isinstance(status, dict):
            return False
            
        # Check various indicators of activity
        if status.get('current_stream'):
            return True
        if status.get('active'):
            return True
            
        # Check if there are active clients
        clients = status.get('clients')
        if clients and len(clients) > 0:
            return True
            
        return False
    
    def _get_proxy_status(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get cached proxy status or fetch fresh if needed.
        
        Args:
            force_refresh: If True, always fetch fresh data
            
        Returns:
            Dictionary with proxy status information
        """
        current_time = time.time()
        
        # Check if cache is valid
        if not force_refresh and self._proxy_status_cache:
            age = current_time - self._proxy_status_last_fetch
            if age < self._proxy_status_ttl:
                logger.debug(f"Using cached proxy status (age: {age:.1f}s)")
                return self._proxy_status_cache
        
        # Fetch fresh data
        try:
            logger.debug("Fetching fresh proxy status")
            proxy_status = self.fetcher.fetch_proxy_status()
            self._proxy_status_cache = proxy_status
            self._proxy_status_last_fetch = current_time
            return proxy_status
        except Exception as e:
            logger.warning(f"Failed to fetch proxy status: {e}")
            # Return cached data even if expired, or empty dict
            return self._proxy_status_cache if self._proxy_status_cache else {}
    
    def _count_active_streams(self, account_id: int) -> int:
        """Count streams with active viewers for an account.
        
        This method now uses real-time proxy status to determine which streams
        are actually running, rather than relying on the potentially stale
        current_viewers field in the database.
        
        Args:
            account_id: M3U account ID
            
        Returns:
            Number of active streams
        """
        # Get real-time proxy status
        proxy_status = self._get_proxy_status()
        
        # Build a map of active channel IDs from proxy status
        active_channels = {}
        for channel_id_str, status in proxy_status.items():
            if self._is_channel_status_active(status):
                try:
                    channel_id = int(channel_id_str)
                    active_channels[channel_id] = status
                except (ValueError, TypeError):
                    pass
        
        # Now count how many streams from this account are in active channels
        active_count = 0
        
        for channel_id, status in active_channels.items():
            # Find the channel
            channel = self._channels_by_id.get(channel_id)
            if not channel:
                continue
                
            # Get the streams for this channel
            stream_ids = channel.get('streams', [])
            if not stream_ids:
                continue
                
            # Check if any stream belongs to this account
            for stream_id in stream_ids:
                stream = self._streams_by_id.get(stream_id)
                if stream and stream.get('m3u_account') == account_id:
                    active_count += 1
                    # Only count once per channel - a channel can have multiple streams
                    # from the same account, but we only count it as one active stream
                    # for the account limit purposes
                    break
        
        logger.debug(f"Account {account_id} has {active_count} active streams (from proxy status)")
        return active_count
    
    def _sum_total_viewers(self, account_id: int) -> int:
        """Sum all current_viewers for an account.
        
        Args:
            account_id: M3U account ID
            
        Returns:
            Total number of viewers
        """
        total_viewers = 0
        for stream in self._streams_cache:
            if stream.get('m3u_account') == account_id:
                current_viewers = stream.get('current_viewers', 0)
                total_viewers += current_viewers
        return total_viewers
    
    def get_active_streams_for_profile(self, profile_id: int) -> int:
        """Calculate the number of active streams for a specific M3U account profile.
        
        This counts all streams that have current_viewers > 0 for the given profile.
        
        Args:
            profile_id: M3U account profile ID
            
        Returns:
            Number of active streams (current_viewers > 0)
        """
        self._ensure_initialized()
        
        # Find the account that contains this profile
        account_id = self._find_account_for_profile(profile_id)
        
        if not account_id:
            logger.warning(f"Profile {profile_id} not found in any M3U account")
            return 0
        
        # Count active streams for this account
        active_count = self._count_active_streams(account_id)
        logger.debug(f"Profile {profile_id} has {active_count} active streams")
        return active_count
    
    def get_active_streams_for_account(self, account_id: int) -> int:
        """Calculate the number of active streams for an M3U account.
        
        This counts all streams that have current_viewers > 0 for the given account.
        
        Args:
            account_id: M3U account ID
            
        Returns:
            Number of active streams (current_viewers > 0)
        """
        self._ensure_initialized()
        
        # Count active streams for this account
        active_count = self._count_active_streams(account_id)
        logger.debug(f"Account {account_id} has {active_count} active streams")
        return active_count
    
    def is_channel_active(self, channel_id: int) -> bool:
        """Check if a channel currently has active viewers.
        
        Uses real-time proxy status to determine if the channel is currently streaming.
        
        Args:
            channel_id: Channel ID to check
            
        Returns:
            True if channel has active viewers, False otherwise
        """
        self._ensure_initialized()
        
        # Get real-time proxy status
        proxy_status = self._get_proxy_status()
        
        # Check if this channel is in the proxy status
        channel_id_str = str(channel_id)
        if channel_id_str in proxy_status:
            status = proxy_status[channel_id_str]
            is_active = self._is_channel_status_active(status)
            logger.debug(f"Channel {channel_id} is {'active' if is_active else 'inactive'} (from proxy status)")
            return is_active
        
        logger.debug(f"Channel {channel_id} is not in proxy status, assuming inactive")
        return False
    
    def get_total_viewers_for_profile(self, profile_id: int) -> int:
        """Calculate the total number of viewers for a specific M3U account profile.
        
        This sums all current_viewers across all streams for the given profile.
        
        Args:
            profile_id: M3U account profile ID
            
        Returns:
            Total number of current viewers
        """
        self._ensure_initialized()
        
        # Find the account that contains this profile
        account_id = self._find_account_for_profile(profile_id)
        
        if not account_id:
            logger.warning(f"Profile {profile_id} not found in any M3U account")
            return 0
        
        # Sum viewers for this account
        total_viewers = self._sum_total_viewers(account_id)
        logger.debug(f"Profile {profile_id} has {total_viewers} total viewers")
        return total_viewers
    
    def get_total_viewers_for_account(self, account_id: int) -> int:
        """Calculate the total number of viewers for an M3U account.
        
        This sums all current_viewers across all streams for the given account.
        
        Args:
            account_id: M3U account ID
            
        Returns:
            Total number of current viewers
        """
        self._ensure_initialized()
        
        # Sum viewers for this account
        total_viewers = self._sum_total_viewers(account_id)
        logger.debug(f"Account {account_id} has {total_viewers} total viewers")
        return total_viewers
    
    def _ensure_initialized(self) -> None:
        """Ensure UDI Manager is initialized before data access.
        
        This will auto-initialize if not already done, but only if
        Dispatcharr credentials are configured.
        """
        if not self._initialized:
            # Check if Dispatcharr is configured before auto-initializing
            config = get_dispatcharr_config()
            
            if not config.is_configured():
                logger.warning("UDI Manager not initialized and Dispatcharr credentials not configured. Skipping auto-initialization.")
                return
            
            logger.info("UDI Manager not initialized, auto-initializing...")
            self.initialize()


# Global singleton instance
_udi_manager: Optional[UDIManager] = None
_udi_lock = threading.Lock()


def get_udi_manager() -> UDIManager:
    """Get the global UDI Manager singleton instance.
    
    Returns:
        The UDI Manager instance
    """
    global _udi_manager
    with _udi_lock:
        if _udi_manager is None:
            _udi_manager = UDIManager()
        return _udi_manager
