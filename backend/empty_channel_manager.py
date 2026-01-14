#!/usr/bin/env python3
"""
Empty Channel Manager

Provides functionality to disable channels with no working streams in Dispatcharr profiles.
This module can be reused across different parts of the application (manual operations,
automated checks, global actions, etc.)
"""

import requests
from typing import List, Tuple, Optional
from logging_config import setup_logging
from dead_streams_tracker import DeadStreamsTracker
from udi import get_udi_manager
from api_utils import _get_base_url

logger = setup_logging(__name__)


def disable_empty_channels_in_profile(profile_id: int, 
                                      check_enabled_only: bool = False,
                                      snapshot_channel_ids: Optional[List[int]] = None) -> Tuple[int, int]:
    """Disable channels with no working streams in a specific profile.
    
    This function identifies channels that have either:
    - No streams at all, or
    - All streams marked as dead in the dead streams tracker
    
    Then disables those channels in the specified Dispatcharr profile.
    
    Args:
        profile_id: Dispatcharr profile ID where channels should be disabled
        check_enabled_only: If True, only check channels that are currently enabled in the profile
        snapshot_channel_ids: If provided, only consider channels in this list (snapshot mode)
        
    Returns:
        Tuple of (disabled_count, total_checked) - number of channels disabled and total channels checked
        
    Raises:
        Exception: If Dispatcharr base URL is not configured or API calls fail
    """
    try:
        base_url = _get_base_url()
        if not base_url:
            raise Exception("Dispatcharr base URL not configured")
        
        # Get all channels from UDI
        udi = get_udi_manager()
        all_channels = udi.get_channels()
        
        if not all_channels:
            logger.warning("No channels found in UDI")
            return 0, 0
        
        # Initialize dead streams tracker
        tracker = DeadStreamsTracker()
        
        # If snapshot_channel_ids is provided, filter to only those channels
        if snapshot_channel_ids is not None:
            channels_to_check = [ch for ch in all_channels if ch.get('id') in snapshot_channel_ids]
            logger.info(f"Checking {len(channels_to_check)} channels from snapshot (out of {len(all_channels)} total)")
        else:
            channels_to_check = all_channels
        
        # If check_enabled_only is True, we need to fetch the profile and filter
        # This is used when snapshot mode is enabled to only check channels that are
        # currently enabled in the profile (the snapshot represents the desired state)
        if check_enabled_only:
            try:
                profile_channels = udi.get_profile_channels(profile_id)
                if profile_channels and isinstance(profile_channels, dict):
                    # Get list of enabled channel IDs in this profile
                    enabled_channel_ids = set()
                    for ch in profile_channels.get('channels', []):
                        if isinstance(ch, dict) and ch.get('enabled', False):
                            enabled_channel_ids.add(ch.get('channel_id'))
                    
                    # Filter to only enabled channels
                    channels_to_check = [ch for ch in channels_to_check if ch.get('id') in enabled_channel_ids]
                    logger.info(f"Checking {len(channels_to_check)} enabled channels in profile {profile_id}")
                else:
                    logger.warning(f"Could not fetch valid profile channels data for profile {profile_id}, checking all channels")
            except Exception as e:
                logger.warning(f"Could not fetch profile {profile_id} to filter enabled channels: {e}")
        
        # Find channels with all streams dead or no streams
        channels_to_disable = []
        
        for channel in channels_to_check:
            channel_id = channel.get('id')
            if not channel_id:
                continue
            
            # Get streams for this channel
            stream_ids = channel.get('streams', [])
            
            if not stream_ids:
                # Channel has no streams at all - consider it empty
                channels_to_disable.append(channel_id)
                logger.debug(f"Channel {channel_id} has no streams - marking for disabling")
                continue
            
            # Check if all streams are dead
            all_dead = True
            for stream_id in stream_ids:
                stream = udi.get_stream_by_id(stream_id)
                if stream and not tracker.is_dead(stream.get('url', '')):
                    all_dead = False
                    break
            
            if all_dead:
                channels_to_disable.append(channel_id)
                logger.debug(f"Channel {channel_id} has all dead streams - marking for disabling")
        
        # Disable channels in the profile via Dispatcharr API
        from udi.fetcher import _get_auth_headers
        
        disabled_count = 0
        for channel_id in channels_to_disable:
            try:
                # PATCH /api/channels/profiles/{profile_id}/channels/{channel_id}/
                url = f"{base_url}/api/channels/profiles/{profile_id}/channels/{channel_id}/"
                resp = requests.patch(
                    url,
                    headers=_get_auth_headers(),
                    json={'enabled': False},
                    timeout=30
                )
                
                if resp.status_code in [200, 204]:
                    disabled_count += 1
                    logger.debug(f"Disabled channel {channel_id} in profile {profile_id}")
                else:
                    logger.warning(f"Failed to disable channel {channel_id} in profile {profile_id}: {resp.status_code}")
                    
            except Exception as e:
                logger.error(f"Error disabling channel {channel_id}: {e}")
                continue
        
        if disabled_count > 0:
            logger.info(f"Disabled {disabled_count} empty channels in profile {profile_id} (checked {len(channels_to_check)} channels)")
        else:
            logger.info(f"No empty channels to disable in profile {profile_id} (checked {len(channels_to_check)} channels)")
        
        return disabled_count, len(channels_to_check)
        
    except Exception as e:
        logger.error(f"Error disabling empty channels in profile {profile_id}: {e}", exc_info=True)
        raise


def should_disable_empty_channels() -> Tuple[bool, Optional[int], Optional[List[int]]]:
    """Check if empty channel disabling is enabled and get the configuration.
    
    Returns:
        Tuple of (enabled, target_profile_id, snapshot_channel_ids)
        - enabled: True if empty channel management is enabled
        - target_profile_id: Profile ID where channels should be disabled, or None
        - snapshot_channel_ids: List of channel IDs from snapshot, or None if not using snapshot
    """
    try:
        from profile_config import get_profile_config
        
        profile_config = get_profile_config()
        dead_stream_config = profile_config.get_dead_stream_config()
        
        if not dead_stream_config.get('enabled', False):
            return False, None, None
        
        target_profile_id = dead_stream_config.get('target_profile_id')
        if not target_profile_id:
            logger.warning("Empty channel management is enabled but no target profile is configured")
            return False, None, None
        
        # Check if we should use snapshot
        use_snapshot = dead_stream_config.get('use_snapshot', False)
        snapshot_channel_ids = None
        
        if use_snapshot:
            snapshot = profile_config.get_snapshot(target_profile_id)
            if snapshot:
                snapshot_channel_ids = snapshot.get('channel_ids', [])
                logger.debug(f"Using snapshot with {len(snapshot_channel_ids)} channels for empty channel management")
            else:
                logger.warning(f"Snapshot is enabled but no snapshot found for profile {target_profile_id}")
        
        return True, target_profile_id, snapshot_channel_ids
        
    except Exception as e:
        logger.error(f"Error checking empty channel management configuration: {e}")
        return False, None, None


def re_enable_channels_with_working_streams(profile_id: int,
                                            snapshot_channel_ids: Optional[List[int]] = None) -> Tuple[int, int]:
    """Re-enable channels that now have working streams in a specific profile.
    
    This function identifies channels that are currently disabled but have at least
    one working (non-dead) stream, and re-enables them in the specified profile.
    
    This is the complementary operation to disable_empty_channels_in_profile,
    giving channels a second chance when their streams come back online.
    
    Args:
        profile_id: Dispatcharr profile ID where channels should be re-enabled
        snapshot_channel_ids: If provided, only consider channels in this list (snapshot mode)
        
    Returns:
        Tuple of (enabled_count, total_checked) - number of channels re-enabled and total channels checked
        
    Raises:
        Exception: If Dispatcharr base URL is not configured or API calls fail
    """
    try:
        base_url = _get_base_url()
        if not base_url:
            raise Exception("Dispatcharr base URL not configured")
        
        # Get all channels from UDI
        udi = get_udi_manager()
        all_channels = udi.get_channels()
        
        if not all_channels:
            logger.warning("No channels found in UDI")
            return 0, 0
        
        # Initialize dead streams tracker
        tracker = DeadStreamsTracker()
        
        # If snapshot_channel_ids is provided, filter to only those channels
        if snapshot_channel_ids is not None:
            channels_to_check = [ch for ch in all_channels if ch.get('id') in snapshot_channel_ids]
            logger.info(f"Checking {len(channels_to_check)} channels from snapshot for re-enabling")
        else:
            channels_to_check = all_channels
        
        # Get profile channels to find which are currently disabled
        try:
            profile_channels = udi.get_profile_channels(profile_id)
            if not profile_channels or not isinstance(profile_channels, dict):
                logger.warning(f"Could not fetch valid profile channels data for profile {profile_id}")
                return 0, 0
            
            # Get list of disabled channel IDs in this profile
            disabled_channel_ids = set()
            for ch in profile_channels.get('channels', []):
                if isinstance(ch, dict) and not ch.get('enabled', True):
                    disabled_channel_ids.add(ch.get('channel_id'))
            
            # Filter to only disabled channels
            channels_to_check = [ch for ch in channels_to_check if ch.get('id') in disabled_channel_ids]
            logger.info(f"Found {len(channels_to_check)} disabled channels to check in profile {profile_id}")
        except Exception as e:
            logger.warning(f"Could not fetch profile {profile_id} to filter disabled channels: {e}")
            return 0, 0
        
        # Find channels with at least one working stream
        channels_to_enable = []
        
        for channel in channels_to_check:
            channel_id = channel.get('id')
            if not channel_id:
                continue
            
            # Get streams for this channel
            stream_ids = channel.get('streams', [])
            
            if not stream_ids:
                # Channel has no streams - keep it disabled
                continue
            
            # Check if at least one stream is working (not dead)
            has_working_stream = False
            for stream_id in stream_ids:
                stream = udi.get_stream_by_id(stream_id)
                if stream and not tracker.is_dead(stream.get('url', '')):
                    has_working_stream = True
                    break
            
            if has_working_stream:
                channels_to_enable.append(channel_id)
                logger.debug(f"Channel {channel_id} has working streams - marking for re-enabling")
        
        # Re-enable channels in the profile via Dispatcharr API
        from udi.fetcher import _get_auth_headers
        
        enabled_count = 0
        for channel_id in channels_to_enable:
            try:
                # PATCH /api/channels/profiles/{profile_id}/channels/{channel_id}/
                url = f"{base_url}/api/channels/profiles/{profile_id}/channels/{channel_id}/"
                resp = requests.patch(
                    url,
                    headers=_get_auth_headers(),
                    json={'enabled': True},
                    timeout=30
                )
                
                if resp.status_code in [200, 204]:
                    enabled_count += 1
                    logger.debug(f"Re-enabled channel {channel_id} in profile {profile_id}")
                else:
                    logger.warning(f"Failed to re-enable channel {channel_id} in profile {profile_id}: {resp.status_code}")
                    
            except Exception as e:
                logger.error(f"Error re-enabling channel {channel_id}: {e}")
                continue
        
        if enabled_count > 0:
            logger.info(f"Re-enabled {enabled_count} channels with working streams in profile {profile_id} (checked {len(channels_to_check)} channels)")
        else:
            logger.debug(f"No disabled channels with working streams to re-enable in profile {profile_id} (checked {len(channels_to_check)} channels)")
        
        return enabled_count, len(channels_to_check)
        
    except Exception as e:
        logger.error(f"Error re-enabling channels in profile {profile_id}: {e}", exc_info=True)
        raise


def trigger_empty_channel_disabling() -> Optional[Tuple[int, int]]:
    """Trigger empty channel disabling if configured.
    
    This is a convenience function that checks if empty channel management is enabled
    and triggers the disabling operation if so.
    
    Returns:
        Tuple of (disabled_count, total_checked) if operation was performed, None otherwise
    """
    enabled, target_profile_id, snapshot_channel_ids = should_disable_empty_channels()
    
    if not enabled or not target_profile_id:
        return None
    
    try:
        return disable_empty_channels_in_profile(
            profile_id=target_profile_id,
            check_enabled_only=snapshot_channel_ids is not None,
            snapshot_channel_ids=snapshot_channel_ids
        )
    except Exception as e:
        logger.error(f"Failed to disable empty channels: {e}")
        return None


def trigger_channel_re_enabling() -> Optional[Tuple[int, int]]:
    """Trigger channel re-enabling if configured.
    
    This is a convenience function that checks if empty channel management and
    snapshot mode are enabled, and triggers the re-enabling operation if so.
    
    This gives previously disabled channels a second chance when their streams
    come back online.
    
    Returns:
        Tuple of (enabled_count, total_checked) if operation was performed, None otherwise
    """
    enabled, target_profile_id, snapshot_channel_ids = should_disable_empty_channels()
    
    # Only re-enable if snapshot mode is enabled (use_snapshot) and a snapshot exists
    # This ensures we're working with a known good channel list from the snapshot
    # Note: snapshot_channel_ids will be None if snapshot mode is disabled, or an empty/populated list if enabled
    if not enabled or not target_profile_id or snapshot_channel_ids is None:
        return None
    
    try:
        return re_enable_channels_with_working_streams(
            profile_id=target_profile_id,
            snapshot_channel_ids=snapshot_channel_ids
        )
    except Exception as e:
        logger.error(f"Failed to re-enable channels: {e}")
        return None
