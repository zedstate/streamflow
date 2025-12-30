"""
Cache management for the Universal Data Index (UDI) system.

Handles cache invalidation logic and determines when data needs to be refreshed.
"""

from datetime import datetime, timedelta
from typing import Optional

from logging_config import setup_logging

logger = setup_logging(__name__)


# Valid entity types for caching
VALID_ENTITY_TYPES = ['channels', 'streams', 'channel_groups', 'logos', 'm3u_accounts', 'channel_profiles', 'profile_channels']


# Default TTL values in seconds
DEFAULT_CHANNELS_TTL = 300  # 5 minutes
DEFAULT_STREAMS_TTL = 300  # 5 minutes
DEFAULT_CHANNEL_GROUPS_TTL = 3600  # 1 hour
DEFAULT_LOGOS_TTL = 3600  # 1 hour
DEFAULT_M3U_ACCOUNTS_TTL = 3600  # 1 hour
DEFAULT_CHANNEL_PROFILES_TTL = 3600  # 1 hour
DEFAULT_PROFILE_CHANNELS_TTL = 3600  # 1 hour


class UDICache:
    """Cache invalidation logic for UDI data."""
    
    def __init__(
        self,
        channels_ttl: int = DEFAULT_CHANNELS_TTL,
        streams_ttl: int = DEFAULT_STREAMS_TTL,
        channel_groups_ttl: int = DEFAULT_CHANNEL_GROUPS_TTL,
        logos_ttl: int = DEFAULT_LOGOS_TTL,
        m3u_accounts_ttl: int = DEFAULT_M3U_ACCOUNTS_TTL,
        channel_profiles_ttl: int = DEFAULT_CHANNEL_PROFILES_TTL,
        profile_channels_ttl: int = DEFAULT_PROFILE_CHANNELS_TTL
    ):
        """Initialize cache settings.
        
        Args:
            channels_ttl: TTL in seconds for channels cache
            streams_ttl: TTL in seconds for streams cache
            channel_groups_ttl: TTL in seconds for channel groups cache
            logos_ttl: TTL in seconds for logos cache
            m3u_accounts_ttl: TTL in seconds for M3U accounts cache
            channel_profiles_ttl: TTL in seconds for channel profiles cache
            profile_channels_ttl: TTL in seconds for profile channels cache
        """
        self.ttl = {
            'channels': channels_ttl,
            'streams': streams_ttl,
            'channel_groups': channel_groups_ttl,
            'logos': logos_ttl,
            'm3u_accounts': m3u_accounts_ttl,
            'channel_profiles': channel_profiles_ttl,
            'profile_channels': profile_channels_ttl
        }
        
        # Track when each entity type was last refreshed
        self._last_refresh = {
            'channels': None,
            'streams': None,
            'channel_groups': None,
            'logos': None,
            'm3u_accounts': None,
            'channel_profiles': None,
            'profile_channels': None
        }
        
        # Track when cache was manually invalidated
        self._invalidated = {
            'channels': False,
            'streams': False,
            'channel_groups': False,
            'logos': False,
            'm3u_accounts': False,
            'channel_profiles': False,
            'profile_channels': False
        }
    
    def mark_refreshed(self, entity_type: str, timestamp: Optional[datetime] = None) -> None:
        """Mark an entity type as having been refreshed.
        
        Args:
            entity_type: One of the valid entity types (see VALID_ENTITY_TYPES constant)
            timestamp: When the refresh occurred (defaults to now)
        """
        if entity_type not in self.ttl:
            logger.warning(f"Unknown entity type: {entity_type}")
            return
        
        if timestamp is None:
            timestamp = datetime.now()
        
        self._last_refresh[entity_type] = timestamp
        self._invalidated[entity_type] = False
        logger.debug(f"Marked {entity_type} as refreshed at {timestamp.isoformat()}")
    
    def invalidate(self, entity_type: str) -> None:
        """Invalidate cache for a specific entity type.
        
        Args:
            entity_type: One of the valid entity types (see VALID_ENTITY_TYPES constant)
        """
        if entity_type not in self.ttl:
            logger.warning(f"Unknown entity type: {entity_type}")
            return
        
        self._invalidated[entity_type] = True
        logger.info(f"Invalidated cache for {entity_type}")
    
    def invalidate_all(self) -> None:
        """Invalidate cache for all entity types."""
        for entity_type in self.ttl:
            self._invalidated[entity_type] = True
        logger.info("Invalidated all caches")
    
    def is_valid(self, entity_type: str) -> bool:
        """Check if cache is valid for an entity type.
        
        Args:
            entity_type: One of the valid entity types (see VALID_ENTITY_TYPES constant)
            
        Returns:
            True if cache is valid, False if expired or invalidated
        """
        if entity_type not in self.ttl:
            logger.warning(f"Unknown entity type: {entity_type}")
            return False
        
        # Check if manually invalidated
        if self._invalidated.get(entity_type, False):
            return False
        
        # Check if never refreshed
        last_refresh = self._last_refresh.get(entity_type)
        if last_refresh is None:
            return False
        
        # Check if TTL has expired
        ttl_seconds = self.ttl.get(entity_type, 300)
        expiry_time = last_refresh + timedelta(seconds=ttl_seconds)
        
        return datetime.now() < expiry_time
    
    def needs_refresh(self, entity_type: str) -> bool:
        """Check if an entity type needs to be refreshed.
        
        Args:
            entity_type: One of the valid entity types (see VALID_ENTITY_TYPES constant)
            
        Returns:
            True if refresh is needed
        """
        return not self.is_valid(entity_type)
    
    def get_last_refresh(self, entity_type: str) -> Optional[datetime]:
        """Get the last refresh time for an entity type.
        
        Args:
            entity_type: One of the valid entity types (see VALID_ENTITY_TYPES constant)
            
        Returns:
            Datetime of last refresh or None
        """
        return self._last_refresh.get(entity_type)
    
    def get_time_until_expiry(self, entity_type: str) -> Optional[int]:
        """Get seconds until cache expires for an entity type.
        
        Args:
            entity_type: One of the valid entity types (see VALID_ENTITY_TYPES constant)
            
        Returns:
            Seconds until expiry, 0 if already expired, None if never refreshed
        """
        last_refresh = self._last_refresh.get(entity_type)
        if last_refresh is None:
            return None
        
        if self._invalidated.get(entity_type, False):
            return 0
        
        ttl_seconds = self.ttl.get(entity_type, 300)
        expiry_time = last_refresh + timedelta(seconds=ttl_seconds)
        remaining = (expiry_time - datetime.now()).total_seconds()
        
        return max(0, int(remaining))
    
    def set_ttl(self, entity_type: str, ttl_seconds: int) -> None:
        """Update the TTL for an entity type.
        
        Args:
            entity_type: One of the valid entity types (see VALID_ENTITY_TYPES constant)
            ttl_seconds: New TTL in seconds
        """
        if entity_type not in self.ttl:
            logger.warning(f"Unknown entity type: {entity_type}")
            return
        
        self.ttl[entity_type] = ttl_seconds
        logger.info(f"Updated TTL for {entity_type} to {ttl_seconds} seconds")
    
    def get_status(self) -> dict:
        """Get the current cache status for all entity types.
        
        Returns:
            Dictionary with cache status for each entity type
        """
        status = {}
        for entity_type in self.ttl:
            last_refresh = self._last_refresh.get(entity_type)
            status[entity_type] = {
                'is_valid': self.is_valid(entity_type),
                'invalidated': self._invalidated.get(entity_type, False),
                'last_refresh': last_refresh.isoformat() if last_refresh else None,
                'ttl_seconds': self.ttl.get(entity_type),
                'time_until_expiry': self.get_time_until_expiry(entity_type)
            }
        return status
