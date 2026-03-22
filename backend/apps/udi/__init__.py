"""
Universal Data Index (UDI) - Single source of truth for all Dispatcharr data.

This package provides a centralized data management system that:
- Caches data from the Dispatcharr API
- Provides consistent access to channels, streams, groups, logos, and M3U accounts
- Implements background refresh with configurable intervals
- Reduces API calls by serving data from local cache

Usage:
    from apps.udi import get_udi_manager
    
    udi = get_udi_manager()
    channels = udi.get_channels()
    streams = udi.get_streams()
"""

from apps.udi.manager import UDIManager, get_udi_manager

__all__ = ['UDIManager', 'get_udi_manager']
