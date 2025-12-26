"""
Scheduling Service for EPG-based channel checks.

This service manages scheduled channel checks based on EPG program data.
It fetches EPG data from Dispatcharr, caches it, and manages scheduled events.
"""

import json
import os
import re
import uuid
import requests
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from logging_config import setup_logging
from udi import get_udi_manager
from dispatcharr_config import get_dispatcharr_config

logger = setup_logging(__name__)

# Configuration
CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', '/app/data'))
SCHEDULING_CONFIG_FILE = CONFIG_DIR / 'scheduling_config.json'
SCHEDULED_EVENTS_FILE = CONFIG_DIR / 'scheduled_events.json'
AUTO_CREATE_RULES_FILE = CONFIG_DIR / 'auto_create_rules.json'
EXECUTED_EVENTS_FILE = CONFIG_DIR / 'executed_events.json'

# Constants
DUPLICATE_DETECTION_WINDOW_SECONDS = 300  # 5 minutes window for detecting duplicate events
EXECUTED_EVENTS_RETENTION_DAYS = 7  # Keep executed events history for 7 days


class SchedulingService:
    """
    Service for managing EPG-based scheduled channel checks.
    """
    
    def __init__(self):
        """Initialize the scheduling service."""
        self._lock = threading.Lock()
        self._epg_cache: List[Dict[str, Any]] = []
        self._epg_cache_time: Optional[datetime] = None
        self._config = self._load_config()
        self._scheduled_events = self._load_scheduled_events()
        self._auto_create_rules = self._load_auto_create_rules()
        self._executed_events = self._load_executed_events()
        logger.info("Scheduling service initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load scheduling configuration from file.
        
        Returns:
            Configuration dictionary
        """
        default_config = {
            'epg_refresh_interval_minutes': 60,  # Default 1 hour
            'enabled': True
        }
        
        try:
            if SCHEDULING_CONFIG_FILE.exists():
                with open(SCHEDULING_CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    logger.info(f"Loaded scheduling config: {config}")
                    return config
        except Exception as e:
            logger.error(f"Error loading scheduling config: {e}")
        
        return default_config
    
    def _save_config(self) -> bool:
        """Save scheduling configuration to file.
        
        Returns:
            True if successful
        """
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(SCHEDULING_CONFIG_FILE, 'w') as f:
                json.dump(self._config, f, indent=2)
            logger.info("Saved scheduling config")
            return True
        except Exception as e:
            logger.error(f"Error saving scheduling config: {e}")
            return False
    
    def _load_scheduled_events(self) -> List[Dict[str, Any]]:
        """Load scheduled events from file.
        
        Returns:
            List of scheduled event dictionaries
        """
        try:
            if SCHEDULED_EVENTS_FILE.exists():
                with open(SCHEDULED_EVENTS_FILE, 'r') as f:
                    events = json.load(f)
                    logger.info(f"Loaded {len(events)} scheduled events")
                    return events
        except Exception as e:
            logger.error(f"Error loading scheduled events: {e}")
        
        return []
    
    def _save_scheduled_events(self) -> bool:
        """Save scheduled events to file.
        
        Returns:
            True if successful
        """
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(SCHEDULED_EVENTS_FILE, 'w') as f:
                json.dump(self._scheduled_events, f, indent=2)
            logger.info(f"Saved {len(self._scheduled_events)} scheduled events")
            return True
        except Exception as e:
            logger.error(f"Error saving scheduled events: {e}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """Get scheduling configuration.
        
        Returns:
            Configuration dictionary
        """
        return self._config.copy()
    
    def update_config(self, config: Dict[str, Any]) -> bool:
        """Update scheduling configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            True if successful
        """
        with self._lock:
            self._config.update(config)
            return self._save_config()
    
    def _get_base_url(self) -> Optional[str]:
        """Get Dispatcharr base URL from configuration.
        
        Priority: Environment variable > Config file
        
        Returns:
            Base URL or None
        """
        config = get_dispatcharr_config()
        return config.get_base_url()
    
    def _get_auth_token(self) -> Optional[str]:
        """Get authentication token from environment.
        
        Returns:
            Auth token or None
        """
        return os.getenv("DISPATCHARR_TOKEN")
    
    def fetch_epg_grid(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetch EPG grid data from Dispatcharr API with caching.
        
        Args:
            force_refresh: If True, bypass cache and fetch fresh data
            
        Returns:
            List of program dictionaries
        """
        programs_copy = []  # Initialize to ensure it's always defined
        
        with self._lock:
            # Check cache
            if not force_refresh and self._epg_cache and self._epg_cache_time:
                cache_age = datetime.now() - self._epg_cache_time
                refresh_interval = timedelta(minutes=self._config.get('epg_refresh_interval_minutes', 60))
                
                if cache_age < refresh_interval:
                    logger.debug(f"Returning cached EPG data (age: {cache_age})")
                    return self._epg_cache.copy()
            
            # Fetch fresh data
            base_url = self._get_base_url()
            token = self._get_auth_token()
            
            if not base_url or not token:
                logger.error("Missing Dispatcharr configuration")
                return []
            
            try:
                url = f"{base_url}/api/epg/grid/"
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json"
                }
                
                logger.info(f"Fetching EPG grid data from {url}")
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                # Handle different response formats from Dispatcharr API
                # According to swagger, it should be an array, but handle edge cases
                if isinstance(data, list):
                    programs = data
                elif isinstance(data, dict):
                    # If wrapped in an object, try to extract the array
                    # Common keys: results, data, programs
                    programs = data.get('results', data.get('data', data.get('programs', [])))
                    if not isinstance(programs, list):
                        logger.error(f"Unexpected EPG grid response format: {type(data)}, keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
                        programs = []
                else:
                    logger.error(f"Unexpected EPG grid response type: {type(data)}")
                    programs = []
                
                # Validate that programs is a list of dictionaries
                if programs:
                    # Filter out any non-dict items
                    valid_programs = [p for p in programs if isinstance(p, dict)]
                    if len(valid_programs) != len(programs):
                        logger.warning(f"Filtered out {len(programs) - len(valid_programs)} invalid program entries")
                    programs = valid_programs
                
                logger.info(f"Fetched {len(programs)} programs from EPG grid")
                
                # Update cache
                self._epg_cache = programs
                self._epg_cache_time = datetime.now()
                
                # Copy programs before releasing lock
                programs_copy = programs.copy()
                
            except Exception as e:
                logger.error(f"Error fetching EPG grid: {e}")
                # Return cached data if available, even if stale
                if self._epg_cache:
                    logger.warning("Returning stale cached EPG data due to fetch error")
                    programs_copy = self._epg_cache.copy()
                # programs_copy is already initialized to [] at the start
        
        # Match outside the lock to avoid deadlock
        try:
            self.match_programs_to_rules()
        except Exception as e:
            logger.error(f"Error matching programs to rules: {e}", exc_info=True)
        
        return programs_copy
    
    def get_programs_by_channel(self, channel_id: int, tvg_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get programs for a specific channel from cached EPG data.
        
        Args:
            channel_id: Channel ID
            tvg_id: Optional TVG ID for filtering
            
        Returns:
            List of program dictionaries
        """
        # Get EPG data (from cache or fetch if needed)
        programs = self.fetch_epg_grid()
        
        if not programs:
            return []
        
        # Get channel from UDI to get its tvg_id if not provided
        if not tvg_id:
            udi = get_udi_manager()
            channel = udi.get_channel_by_id(channel_id)
            if channel:
                tvg_id = channel.get('tvg_id')
        
        if not tvg_id:
            logger.warning(f"No TVG ID found for channel {channel_id}")
            return []
        
        # Filter programs by tvg_id - ensure we only process dictionaries
        channel_programs = [p for p in programs if isinstance(p, dict) and p.get('tvg_id') == tvg_id]
        
        # Sort by start time
        channel_programs.sort(key=lambda p: p.get('start_time', ''))
        
        logger.debug(f"Found {len(channel_programs)} programs for channel {channel_id} (tvg_id: {tvg_id})")
        return channel_programs
    
    def get_scheduled_events(self) -> List[Dict[str, Any]]:
        """Get all scheduled events sorted by check_time.
        
        Returns:
            List of scheduled event dictionaries ordered by check_time (earliest first)
        """
        events = self._scheduled_events.copy()
        
        # Sort by check_time
        def get_check_time(event):
            check_time = event.get('check_time', '')
            try:
                # Parse ISO format datetime
                return datetime.fromisoformat(check_time.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                # If parsing fails, return a very far future date to push invalid entries to end
                return datetime.max.replace(tzinfo=timezone.utc)
        
        events.sort(key=get_check_time)
        return events
    
    def create_scheduled_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new scheduled event.
        
        Args:
            event_data: Event data dictionary containing:
                - channel_id: Channel ID
                - program_start_time: Program start time (ISO format)
                - program_end_time: Program end time (ISO format)
                - program_title: Program title
                - minutes_before: Minutes before program start to check
                
        Returns:
            Created event dictionary
        """
        with self._lock:
            # Generate unique ID
            event_id = str(uuid.uuid4())
            
            # Get channel info
            udi = get_udi_manager()
            channel = udi.get_channel_by_id(event_data['channel_id'])
            if not channel:
                raise ValueError(f"Channel {event_data['channel_id']} not found")
            
            # Calculate check time
            program_start = datetime.fromisoformat(event_data['program_start_time'].replace('Z', '+00:00'))
            minutes_before = event_data.get('minutes_before', 0)
            check_time = program_start - timedelta(minutes=minutes_before)
            
            # Defensive: Ensure check_time is timezone-aware for proper comparison
            # program_start should already be timezone-aware after parsing, so this
            # should only trigger if the input data was malformed
            if check_time.tzinfo is None:
                logger.warning(f"check_time is missing timezone info, assuming UTC: {check_time}")
                check_time = check_time.replace(tzinfo=timezone.utc)
            
            # Get channel logo info
            logo_id = channel.get('logo_id')
            logo_url = None
            if logo_id:
                logo = udi.get_logo_by_id(logo_id)
                if logo:
                    logo_url = logo.get('cache_url') or logo.get('url')
            
            # Create event
            event = {
                'id': event_id,
                'channel_id': event_data['channel_id'],
                'channel_name': channel.get('name', ''),
                'channel_logo_url': logo_url,
                'program_title': event_data['program_title'],
                'program_start_time': event_data['program_start_time'],
                'program_end_time': event_data['program_end_time'],
                'minutes_before': minutes_before,
                'check_time': check_time.isoformat(),
                'tvg_id': channel.get('tvg_id'),
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            self._scheduled_events.append(event)
            self._save_scheduled_events()
            
            logger.info(f"Created scheduled event {event_id} for channel {channel.get('name')} at {check_time}")
            return event
    
    def delete_scheduled_event(self, event_id: str) -> bool:
        """Delete a scheduled event.
        
        Args:
            event_id: Event ID
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            initial_count = len(self._scheduled_events)
            self._scheduled_events = [e for e in self._scheduled_events if e.get('id') != event_id]
            
            if len(self._scheduled_events) < initial_count:
                self._save_scheduled_events()
                logger.info(f"Deleted scheduled event {event_id}")
                return True
            
            logger.warning(f"Scheduled event {event_id} not found")
            return False
    
    def get_due_events(self) -> List[Dict[str, Any]]:
        """Get all events that are due for execution.
        
        Returns:
            List of events where check_time is in the past or now
        """
        now = datetime.now(timezone.utc)
        due_events = []
        
        for event in self._scheduled_events:
            try:
                check_time = datetime.fromisoformat(event['check_time'].replace('Z', '+00:00'))
                # Ensure check_time is timezone-aware
                if check_time.tzinfo is None:
                    check_time = check_time.replace(tzinfo=timezone.utc)
                if check_time <= now:
                    due_events.append(event)
            except (ValueError, KeyError) as e:
                logger.warning(f"Invalid check_time for event {event.get('id')}: {e}")
        
        return due_events
    
    def execute_scheduled_check(self, event_id: str, stream_checker_service) -> bool:
        """Execute a scheduled channel check and remove the event.
        
        Args:
            event_id: Event ID to execute
            stream_checker_service: Stream checker service instance
            
        Returns:
            True if executed successfully, False otherwise
        """
        # First, find and extract event data while holding the lock
        with self._lock:
            event = None
            for e in self._scheduled_events:
                if e.get('id') == event_id:
                    event = e
                    break
            
            if not event:
                logger.warning(f"Scheduled event {event_id} not found for execution")
                return False
            
            # Extract event data
            channel_id = event.get('channel_id')
            program_title = event.get('program_title', 'Unknown Program')
            program_start_time = event.get('program_start_time')
            
            # Validate required fields
            if not channel_id or not program_start_time:
                logger.error(f"Scheduled event {event_id} missing required fields (channel_id or program_start_time)")
                return False
        
        # Release lock before executing the long-running channel check
        logger.info(f"Executing scheduled check for channel {channel_id} (program: {program_title})")
        
        try:
            # Execute the check with program context (without holding the lock)
            result = stream_checker_service.check_single_channel(
                channel_id, 
                program_name=program_title
            )
            
            if result.get('success'):
                # Re-acquire lock only to delete the event and record execution
                with self._lock:
                    # Remove the event and check if it was actually present
                    initial_count = len(self._scheduled_events)
                    self._scheduled_events = [e for e in self._scheduled_events if e.get('id') != event_id]
                    
                    if len(self._scheduled_events) < initial_count:
                        self._save_scheduled_events()
                        logger.info(f"Scheduled event {event_id} executed and removed successfully")
                    else:
                        logger.warning(f"Scheduled event {event_id} was already removed by another thread")
                    
                    # Record the executed event to prevent re-creation
                    if program_start_time:
                        self._record_executed_event(channel_id, program_start_time)
                
                return True
            else:
                logger.error(f"Scheduled check for event {event_id} failed: {result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing scheduled event {event_id}: {e}", exc_info=True)
            return False
    
    def _load_auto_create_rules(self) -> List[Dict[str, Any]]:
        """Load auto-create rules from file.
        
        Returns:
            List of auto-create rule dictionaries
        """
        try:
            if AUTO_CREATE_RULES_FILE.exists():
                with open(AUTO_CREATE_RULES_FILE, 'r') as f:
                    rules = json.load(f)
                    logger.info(f"Loaded {len(rules)} auto-create rules")
                    return rules
        except Exception as e:
            logger.error(f"Error loading auto-create rules: {e}")
        
        return []
    
    def _save_auto_create_rules(self) -> bool:
        """Save auto-create rules to file.
        
        Returns:
            True if successful
        """
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(AUTO_CREATE_RULES_FILE, 'w') as f:
                json.dump(self._auto_create_rules, f, indent=2)
            logger.info(f"Saved {len(self._auto_create_rules)} auto-create rules")
            return True
        except Exception as e:
            logger.error(f"Error saving auto-create rules: {e}")
            return False
    
    def _load_executed_events(self) -> List[Dict[str, Any]]:
        """Load executed events history from file and clean up old entries.
        
        Returns:
            List of executed event dictionaries (cleaned of old entries)
        """
        try:
            if EXECUTED_EVENTS_FILE.exists():
                with open(EXECUTED_EVENTS_FILE, 'r') as f:
                    executed_events = json.load(f)
                    
                    # Clean up old executed events (older than retention period)
                    cutoff_time = datetime.now(timezone.utc) - timedelta(days=EXECUTED_EVENTS_RETENTION_DAYS)
                    cleaned_events = []
                    
                    for event in executed_events:
                        try:
                            executed_at = datetime.fromisoformat(event.get('executed_at', '').replace('Z', '+00:00'))
                            if executed_at.tzinfo is None:
                                executed_at = executed_at.replace(tzinfo=timezone.utc)
                            
                            if executed_at >= cutoff_time:
                                cleaned_events.append(event)
                        except (ValueError, AttributeError):
                            # Skip events with invalid timestamps
                            continue
                    
                    if len(cleaned_events) < len(executed_events):
                        logger.info(f"Cleaned up {len(executed_events) - len(cleaned_events)} old executed events")
                    
                    logger.info(f"Loaded {len(cleaned_events)} executed events")
                    return cleaned_events
        except Exception as e:
            logger.error(f"Error loading executed events: {e}")
        
        return []
    
    def _save_executed_events(self) -> bool:
        """Save executed events history to file.
        
        Returns:
            True if successful
        """
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(EXECUTED_EVENTS_FILE, 'w') as f:
                json.dump(self._executed_events, f, indent=2)
            logger.debug(f"Saved {len(self._executed_events)} executed events")
            return True
        except Exception as e:
            logger.error(f"Error saving executed events: {e}")
            return False
    
    def _record_executed_event(self, channel_id: int, program_start_time: str) -> None:
        """Record an event as executed to prevent re-creation.
        
        Args:
            channel_id: Channel ID
            program_start_time: Program start time (ISO format)
        """
        executed_event = {
            'channel_id': channel_id,
            'program_start_time': program_start_time,
            'executed_at': datetime.now(timezone.utc).isoformat()
        }
        
        self._executed_events.append(executed_event)
        self._save_executed_events()
        logger.debug(f"Recorded executed event for channel {channel_id} at {program_start_time}")
    
    def _is_event_executed(self, channel_id: int, program_start_time: str) -> bool:
        """Check if an event has already been executed.
        
        Args:
            channel_id: Channel ID
            program_start_time: Program start time (ISO format)
            
        Returns:
            True if the event has been executed within the detection window
        """
        try:
            start_dt = datetime.fromisoformat(program_start_time.replace('Z', '+00:00'))
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            return False
        
        for executed in self._executed_events:
            if executed.get('channel_id') != channel_id:
                continue
            
            try:
                executed_start = datetime.fromisoformat(executed.get('program_start_time', '').replace('Z', '+00:00'))
                if executed_start.tzinfo is None:
                    executed_start = executed_start.replace(tzinfo=timezone.utc)
                
                # Check if within duplicate detection window
                time_diff = abs((executed_start - start_dt).total_seconds())
                if time_diff < DUPLICATE_DETECTION_WINDOW_SECONDS:
                    return True
            except (ValueError, AttributeError):
                continue
        
        return False
    
    def get_auto_create_rules(self) -> List[Dict[str, Any]]:
        """Get all auto-create rules.
        
        Returns:
            List of auto-create rule dictionaries
        """
        return self._auto_create_rules.copy()
    
    def create_auto_create_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new auto-create rule.
        
        Args:
            rule_data: Rule data dictionary containing:
                - name: Rule name
                - channel_ids: List of Channel IDs to match (optional)
                - channel_group_ids: List of Channel Group IDs to match (optional)
                - channel_id: Single channel ID for backward compatibility (optional)
                - regex_pattern: Regex pattern to match program names
                - minutes_before: Minutes before program start to check
                
        Returns:
            Created rule dictionary
        """
        with self._lock:
            # Generate unique ID
            rule_id = str(uuid.uuid4())
            
            # Get channel info - support both channel_id (single) and channel_ids (multiple)
            udi = get_udi_manager()
            
            # Collect channel IDs from multiple sources
            channel_ids = []
            channel_group_ids = []
            
            # Handle backward compatibility: convert channel_id to channel_ids
            if 'channel_id' in rule_data and 'channel_ids' not in rule_data and 'channel_group_ids' not in rule_data:
                channel_ids = [rule_data['channel_id']]
            else:
                # Get individual channel IDs
                if 'channel_ids' in rule_data:
                    channel_ids = list(rule_data['channel_ids'])
                
                # Get channel group IDs
                if 'channel_group_ids' in rule_data:
                    channel_group_ids = list(rule_data['channel_group_ids'])
            
            # Validate that at least one channel or channel group is provided
            if not channel_ids and not channel_group_ids:
                raise ValueError("At least one channel_id, channel_ids, or channel_group_ids must be provided")
            
            # Expand channel groups to individual channels for processing
            all_channel_ids = set(channel_ids)
            
            # Validate and expand channel groups
            channel_groups_info = []
            if channel_group_ids:
                for group_id in channel_group_ids:
                    # Get all channels in this group
                    group_channels = udi.get_channels_by_group(group_id)
                    if group_channels is None:
                        raise ValueError(f"Channel group {group_id} not found")
                    
                    # Get group info for display
                    group = udi.get_channel_group_by_id(group_id)
                    if group:
                        channel_groups_info.append({
                            'id': group_id,
                            'name': group.get('name', ''),
                            'channel_count': len(group_channels)
                        })
                    
                    # Add all channel IDs from this group
                    for channel in group_channels:
                        all_channel_ids.add(channel['id'])
            
            # Convert back to list
            all_channel_ids = list(all_channel_ids)
            
            # Validate all channels exist and collect their info
            channels_info = []
            for channel_id in all_channel_ids:
                channel = udi.get_channel_by_id(channel_id)
                if not channel:
                    logger.warning(f"Channel {channel_id} not found, skipping")
                    continue
                
                # Get channel logo info
                logo_id = channel.get('logo_id')
                logo_url = None
                if logo_id:
                    logo = udi.get_logo_by_id(logo_id)
                    if logo:
                        logo_url = logo.get('cache_url') or logo.get('url')
                
                channels_info.append({
                    'id': channel_id,
                    'name': channel.get('name', ''),
                    'logo_url': logo_url,
                    'tvg_id': channel.get('tvg_id')
                })
            
            if not channels_info:
                raise ValueError("No valid channels found for this rule")
            
            # Validate regex pattern
            # Temporarily substitute CHANNEL_NAME with a placeholder for validation
            try:
                validation_pattern = rule_data['regex_pattern'].replace('CHANNEL_NAME', 'PLACEHOLDER')
                re.compile(validation_pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
            
            # Create rule
            rule = {
                'id': rule_id,
                'name': rule_data['name'],
                'channel_ids': channel_ids,  # Store originally selected individual channels
                'channel_group_ids': channel_group_ids,  # Store originally selected channel groups
                'channel_groups_info': channel_groups_info,  # Store group metadata for display
                'channels_info': channels_info,  # Store full channel info for display (expanded)
                'regex_pattern': rule_data['regex_pattern'],
                'minutes_before': rule_data.get('minutes_before', 5),
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            self._auto_create_rules.append(rule)
            self._save_auto_create_rules()
            
            # Log rule creation
            desc_parts = []
            if channel_ids:
                desc_parts.append(f"{len(channel_ids)} individual channel(s)")
            if channel_group_ids:
                desc_parts.append(f"{len(channel_group_ids)} channel group(s)")
            logger.info(f"Created auto-create rule {rule_id} '{rule_data['name']}' for {', '.join(desc_parts)} (total {len(channels_info)} channels)")
            
            # Schedule matching in background thread to avoid blocking
            def match_in_background():
                try:
                    # Ensure EPG data is fetched before matching
                    self.fetch_epg_grid()
                    # Note: fetch_epg_grid already calls match_programs_to_rules at the end
                except Exception as e:
                    logger.error(f"Error matching programs to rules in background: {e}", exc_info=True)
            
            match_thread = threading.Thread(target=match_in_background, daemon=True)
            match_thread.start()
            
            return rule
    
    def delete_auto_create_rule(self, rule_id: str) -> bool:
        """Delete an auto-create rule and all events created by it.
        
        Args:
            rule_id: Rule ID
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            initial_count = len(self._auto_create_rules)
            self._auto_create_rules = [r for r in self._auto_create_rules if r.get('id') != rule_id]
            
            if len(self._auto_create_rules) < initial_count:
                self._save_auto_create_rules()
                
                # Delete all events that were auto-created by this rule
                initial_events_count = len(self._scheduled_events)
                self._scheduled_events = [
                    e for e in self._scheduled_events 
                    if e.get('auto_create_rule_id') != rule_id
                ]
                deleted_events_count = initial_events_count - len(self._scheduled_events)
                
                if deleted_events_count > 0:
                    self._save_scheduled_events()
                    logger.info(f"Deleted auto-create rule {rule_id} and {deleted_events_count} associated event(s)")
                else:
                    logger.info(f"Deleted auto-create rule {rule_id} (no associated events)")
                
                return True
            
            logger.warning(f"Auto-create rule {rule_id} not found")
            return False
    
    def update_auto_create_rule(self, rule_id: str, rule_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing auto-create rule.
        
        Args:
            rule_id: Rule ID to update
            rule_data: Updated rule data (only provided fields will be updated)
            
        Returns:
            Updated rule dictionary or None if not found
        """
        with self._lock:
            # Find the rule
            rule = None
            rule_index = None
            for i, r in enumerate(self._auto_create_rules):
                if r.get('id') == rule_id:
                    rule = r
                    rule_index = i
                    break
            
            if not rule:
                logger.warning(f"Auto-create rule {rule_id} not found for update")
                return None
            
            # Validate and update fields
            udi = get_udi_manager()
            
            # Update channels and/or channel groups if provided
            if 'channel_id' in rule_data or 'channel_ids' in rule_data or 'channel_group_ids' in rule_data:
                # Collect channel IDs from multiple sources
                channel_ids = []
                channel_group_ids = []
                
                # Convert channel_id to channel_ids for backward compatibility
                if 'channel_id' in rule_data and 'channel_ids' not in rule_data and 'channel_group_ids' not in rule_data:
                    channel_ids = [rule_data['channel_id']]
                else:
                    # Get individual channel IDs
                    if 'channel_ids' in rule_data:
                        channel_ids = list(rule_data['channel_ids'])
                    
                    # Get channel group IDs
                    if 'channel_group_ids' in rule_data:
                        channel_group_ids = list(rule_data['channel_group_ids'])
                
                # Expand channel groups to individual channels for processing
                all_channel_ids = set(channel_ids)
                
                # Validate and expand channel groups
                channel_groups_info = []
                if channel_group_ids:
                    for group_id in channel_group_ids:
                        # Get all channels in this group
                        group_channels = udi.get_channels_by_group(group_id)
                        if group_channels is None:
                            raise ValueError(f"Channel group {group_id} not found")
                        
                        # Get group info for display
                        group = udi.get_channel_group_by_id(group_id)
                        if group:
                            channel_groups_info.append({
                                'id': group_id,
                                'name': group.get('name', ''),
                                'channel_count': len(group_channels)
                            })
                        
                        # Add all channel IDs from this group
                        for channel in group_channels:
                            all_channel_ids.add(channel['id'])
                
                # Convert back to list
                all_channel_ids = list(all_channel_ids)
                
                # Validate all channels exist and collect their info
                channels_info = []
                for channel_id in all_channel_ids:
                    channel = udi.get_channel_by_id(channel_id)
                    if not channel:
                        logger.warning(f"Channel {channel_id} not found, skipping")
                        continue
                    
                    # Get channel logo info
                    logo_id = channel.get('logo_id')
                    logo_url = None
                    if logo_id:
                        logo = udi.get_logo_by_id(logo_id)
                        if logo:
                            logo_url = logo.get('cache_url') or logo.get('url')
                    
                    channels_info.append({
                        'id': channel_id,
                        'name': channel.get('name', ''),
                        'logo_url': logo_url,
                        'tvg_id': channel.get('tvg_id')
                    })
                
                if not channels_info:
                    raise ValueError("No valid channels found for this rule")
                
                # Update channel-related fields
                rule['channel_ids'] = channel_ids
                rule['channel_group_ids'] = channel_group_ids
                rule['channel_groups_info'] = channel_groups_info
                rule['channels_info'] = channels_info
                
                # Keep old fields for backward compatibility but mark as deprecated
                # Store first channel's info in old format for compatibility
                if channel_ids:
                    first_channel_info = channels_info[0] if channels_info else None
                    if first_channel_info:
                        rule['channel_id'] = first_channel_info['id']  # For backward compatibility
                        rule['channel_name'] = first_channel_info['name']
                        rule['channel_logo_url'] = first_channel_info.get('logo_url')
                        rule['tvg_id'] = first_channel_info.get('tvg_id')
            
            # Update regex pattern if provided
            if 'regex_pattern' in rule_data:
                try:
                    # Temporarily substitute CHANNEL_NAME with a placeholder for validation
                    validation_pattern = rule_data['regex_pattern'].replace('CHANNEL_NAME', 'PLACEHOLDER')
                    re.compile(validation_pattern)
                    rule['regex_pattern'] = rule_data['regex_pattern']
                except re.error as e:
                    raise ValueError(f"Invalid regex pattern: {e}")
            
            # Update other fields
            if 'name' in rule_data:
                rule['name'] = rule_data['name']
            if 'minutes_before' in rule_data:
                rule['minutes_before'] = rule_data['minutes_before']
            
            # Save changes
            self._auto_create_rules[rule_index] = rule
            self._save_auto_create_rules()
            
            logger.info(f"Updated auto-create rule {rule_id}")
            
            # Delete old events created by this rule and rematch
            initial_events_count = len(self._scheduled_events)
            self._scheduled_events = [
                e for e in self._scheduled_events 
                if e.get('auto_create_rule_id') != rule_id
            ]
            deleted_events_count = initial_events_count - len(self._scheduled_events)
            
            if deleted_events_count > 0:
                self._save_scheduled_events()
                logger.info(f"Deleted {deleted_events_count} old event(s) from updated rule {rule_id}")
            
            # Schedule matching in background thread
            def match_in_background():
                try:
                    self.fetch_epg_grid()
                except Exception as e:
                    logger.error(f"Error matching programs to updated rule: {e}", exc_info=True)
            
            match_thread = threading.Thread(target=match_in_background, daemon=True)
            match_thread.start()
            
            return rule
    
    def test_regex_against_epg(self, channel_id: int, regex_pattern: str) -> List[Dict[str, Any]]:
        """Test a regex pattern against EPG programs for a channel.
        
        Args:
            channel_id: Channel ID
            regex_pattern: Regex pattern to test
            
        Returns:
            List of matching programs
        """
        # Validate regex pattern
        # Temporarily substitute CHANNEL_NAME with a placeholder for validation
        try:
            validation_pattern = regex_pattern.replace('CHANNEL_NAME', 'PLACEHOLDER')
            re.compile(validation_pattern, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
        
        # Compile the actual pattern for matching
        # Note: CHANNEL_NAME is not substituted here as this is for EPG program matching
        pattern = re.compile(regex_pattern, re.IGNORECASE)
        
        # Get programs for channel
        programs = self.get_programs_by_channel(channel_id)
        
        # Filter matching programs
        matching_programs = []
        for program in programs:
            title = program.get('title', '')
            if pattern.search(title):
                matching_programs.append(program)
        
        logger.debug(f"Regex '{regex_pattern}' matched {len(matching_programs)} programs for channel {channel_id}")
        return matching_programs
    
    def match_programs_to_rules(self) -> Dict[str, Any]:
        """Match EPG programs to auto-create rules and create/update scheduled events.
        
        This method:
        1. Scans all programs in EPG cache
        2. For each rule, finds matching programs
        3. Creates new events for programs not yet scheduled
        4. Updates existing events if program name or time changed
        
        Returns:
            Dictionary with statistics about created/updated events
        """
        # First, get a snapshot of the data we need without holding the lock for long
        with self._lock:
            if not self._auto_create_rules:
                logger.debug("No auto-create rules to process")
                return {'created': 0, 'updated': 0, 'skipped': 0}
            
            # Make copies of the data we need to avoid holding lock during processing
            rules_snapshot = self._auto_create_rules.copy()
            epg_cache_snapshot = self._epg_cache.copy()
        
        # Now process outside the lock
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        udi = get_udi_manager()
        events_to_add = []
        events_to_update = []
        
        # Pre-group programs by tvg_id for efficient lookup (performance optimization)
        programs_by_tvg_id = defaultdict(list)
        for program in epg_cache_snapshot:
            if isinstance(program, dict):
                tvg_id = program.get('tvg_id')
                if tvg_id:
                    programs_by_tvg_id[tvg_id].append(program)
        
        # Sort programs by start time for each channel
        for tvg_id in programs_by_tvg_id:
            programs_by_tvg_id[tvg_id].sort(key=lambda p: p.get('start_time', ''))
        
        for rule in rules_snapshot:
            # Support both old format (channel_id) and new format (channel_ids + channel_group_ids)
            channel_ids = rule.get('channel_ids') or ([rule.get('channel_id')] if rule.get('channel_id') else [])
            channel_group_ids = rule.get('channel_group_ids', [])
            regex_pattern = rule.get('regex_pattern')
            minutes_before = rule.get('minutes_before', 5)
            
            # Dynamically expand channel groups to get current list of channels
            all_channel_ids = set(channel_ids)
            
            # Expand channel groups in real-time to include newly added channels
            if channel_group_ids:
                for group_id in channel_group_ids:
                    group_channels = udi.get_channels_by_group(group_id)
                    if group_channels:
                        for channel in group_channels:
                            all_channel_ids.add(channel['id'])
            
            # Convert to list
            all_channel_ids = list(all_channel_ids)
            
            if not all_channel_ids:
                logger.warning(f"Rule {rule.get('id')} has no channels, skipping")
                continue
            
            # Build channels_info from expanded channel list
            channels_info = []
            for channel_id in all_channel_ids:
                channel = udi.get_channel_by_id(channel_id)
                if channel:
                    channels_info.append({
                        'id': channel_id,
                        'tvg_id': channel.get('tvg_id')
                    })
            
            try:
                # Temporarily substitute CHANNEL_NAME with a placeholder for validation
                validation_pattern = regex_pattern.replace('CHANNEL_NAME', 'PLACEHOLDER')
                re.compile(validation_pattern, re.IGNORECASE)
            except re.error as e:
                logger.error(f"Invalid regex pattern in rule {rule.get('id')}: {e}")
                continue
            
            # Compile the actual pattern for matching
            # Note: CHANNEL_NAME is not substituted here as this is for EPG program matching
            pattern = re.compile(regex_pattern, re.IGNORECASE)
            
            # Process each channel in the rule
            for channel_info in channels_info:
                channel_id = channel_info.get('id')
                tvg_id = channel_info.get('tvg_id')
                
                if not tvg_id:
                    logger.warning(f"Rule {rule.get('id')} channel {channel_id} has no TVG ID, skipping")
                    continue
                
                # Get programs for this channel from the pre-grouped dictionary
                programs = programs_by_tvg_id.get(tvg_id, [])
                
                for program in programs:
                    title = program.get('title', '')
                    if not pattern.search(title):
                        continue
                    
                    # Program matches! Check if we already have an event for it
                    program_start = program.get('start_time')
                    program_end = program.get('end_time')
                    
                    if not program_start or not program_end:
                        logger.warning(f"Program missing start/end time: {title}")
                        continue
                    
                    # Parse times
                    try:
                        start_dt = datetime.fromisoformat(program_start.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(program_end.replace('Z', '+00:00'))
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"Invalid program times for {title}: {e}")
                        continue
                    
                    # Ensure timezone aware
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                    if end_dt.tzinfo is None:
                        end_dt = end_dt.replace(tzinfo=timezone.utc)
                    
                    # Skip programs that have already started or are in the past
                    now = datetime.now(timezone.utc)
                    if start_dt <= now:
                        logger.debug(f"Skipping past/started program '{title}' (start: {start_dt}, now: {now})")
                        continue
                    
                    # Skip if this event has already been executed
                    if self._is_event_executed(channel_id, program_start):
                        logger.debug(f"Skipping already-executed program '{title}' on channel {channel_id}")
                        continue
                    
                    # Get the date of the program (for duplicate detection)
                    program_date = start_dt.date().isoformat()
                    
                    # Create new event data
                    check_time = start_dt - timedelta(minutes=minutes_before)
                    
                    # Get channel info for logo
                    channel = udi.get_channel_by_id(channel_id)
                    logo_id = channel.get('logo_id') if channel else None
                    logo_url = None
                    if logo_id:
                        logo = udi.get_logo_by_id(logo_id)
                        if logo:
                            logo_url = logo.get('cache_url') or logo.get('url')
                    
                    event_data = {
                        'id': str(uuid.uuid4()),
                        'channel_id': channel_id,
                        'channel_name': channel.get('name', '') if channel else '',
                        'channel_logo_url': logo_url,
                        'program_title': title,
                        'program_start_time': program_start,
                        'program_end_time': program_end,
                        'minutes_before': minutes_before,
                        'check_time': check_time.isoformat(),
                        'tvg_id': tvg_id,
                        'created_at': datetime.now(timezone.utc).isoformat(),
                        'auto_created': True,
                        'auto_create_rule_id': rule.get('id'),
                        'program_date': program_date  # For duplicate detection
                    }
                    
                    events_to_add.append(event_data)
        
        # Now acquire the lock briefly to update the scheduled events
        with self._lock:
            for event_data in events_to_add:
                # Look for existing event with same channel, program date within detection window
                program_date = event_data.pop('program_date')
                channel_id = event_data['channel_id']
                title = event_data['program_title']
                program_start = event_data['program_start_time']
                
                try:
                    start_dt = datetime.fromisoformat(program_start.replace('Z', '+00:00'))
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                except (ValueError, AttributeError):
                    continue
                
                existing_event = None
                for event in self._scheduled_events:
                    if event.get('channel_id') != channel_id:
                        continue
                    
                    event_start = event.get('program_start_time', '')
                    try:
                        event_start_dt = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                        if event_start_dt.tzinfo is None:
                            event_start_dt = event_start_dt.replace(tzinfo=timezone.utc)
                        event_date = event_start_dt.date().isoformat()
                    except (ValueError, AttributeError):
                        continue
                    
                    # Check if same date and within duplicate detection window
                    if event_date == program_date:
                        time_diff = abs((event_start_dt - start_dt).total_seconds())
                        if time_diff < DUPLICATE_DETECTION_WINDOW_SECONDS:
                            existing_event = event
                            break
                
                if existing_event:
                    # Check if we need to update the event
                    needs_update = False
                    if existing_event.get('program_title') != title:
                        logger.info(f"Updating event title: '{existing_event.get('program_title')}' -> '{title}'")
                        existing_event['program_title'] = title
                        needs_update = True
                    
                    if existing_event.get('program_start_time') != program_start:
                        logger.info(f"Updating event time: {existing_event.get('program_start_time')} -> {program_start}")
                        existing_event['program_start_time'] = event_data['program_start_time']
                        existing_event['program_end_time'] = event_data['program_end_time']
                        existing_event['check_time'] = event_data['check_time']
                        needs_update = True
                    
                    if needs_update:
                        updated_count += 1
                    else:
                        skipped_count += 1
                else:
                    # Add new event
                    self._scheduled_events.append(event_data)
                    created_count += 1
                    channel_name = event_data.get('channel_name', channel_id)
                    logger.info(f"Auto-created event for '{title}' on channel {channel_name}")
            
            # Save if we made changes
            if created_count > 0 or updated_count > 0:
                self._save_scheduled_events()
        
        # Return result outside the lock
        result = {
            'created': created_count,
            'updated': updated_count,
            'skipped': skipped_count
        }
        
        if created_count > 0 or updated_count > 0:
            logger.info(f"Auto-create matching complete: {result}")
        
        return result
    
    def export_auto_create_rules(self) -> List[Dict[str, Any]]:
        """Export auto-create rules for backup/transfer.
        
        Returns:
            List of rules with only essential fields for import.
            
        Note:
            For backward compatibility with single-channel rules, both 'channel_id' 
            (single) and 'channel_ids' (array) are included when there's only one channel.
            Channel groups are exported as 'channel_group_ids'.
        """
        exported_rules = []
        for rule in self._auto_create_rules:
            # Export only the essential fields needed for import
            exported_rule = {
                'name': rule.get('name'),
                'channel_ids': rule.get('channel_ids', []),
                'channel_group_ids': rule.get('channel_group_ids', []),
                'regex_pattern': rule.get('regex_pattern'),
                'minutes_before': rule.get('minutes_before', 5)
            }
            # For backward compatibility, also include channel_id if there's only one channel and no groups
            if len(exported_rule['channel_ids']) == 1 and not exported_rule['channel_group_ids']:
                exported_rule['channel_id'] = exported_rule['channel_ids'][0]
            
            exported_rules.append(exported_rule)
        
        logger.info(f"Exported {len(exported_rules)} auto-create rules")
        return exported_rules
    
    def import_auto_create_rules(self, rules_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Import auto-create rules from JSON data.
        
        Deduplication logic:
        - If exact same regex, channels, and groups exist, replace with imported rule
        - If same regex but different channels/groups exist, merge into existing rule
        
        Args:
            rules_data: List of rule dictionaries to import
            
        Returns:
            Dictionary with import results
        """
        if not isinstance(rules_data, list):
            raise ValueError("Rules data must be a list")
        
        imported_count = 0
        merged_count = 0
        replaced_count = 0
        failed_count = 0
        errors = []
        
        for idx, rule_data in enumerate(rules_data):
            try:
                # Validate required fields
                required_fields = ['name', 'regex_pattern']
                for field in required_fields:
                    if field not in rule_data:
                        raise ValueError(f"Missing required field: {field}")
                
                # Check that either channel_id, channel_ids, or channel_group_ids is provided
                if 'channel_id' not in rule_data and 'channel_ids' not in rule_data and 'channel_group_ids' not in rule_data:
                    raise ValueError("Missing required field: channel_id, channel_ids, or channel_group_ids")
                
                # Normalize to lists
                if 'channel_ids' in rule_data:
                    import_channel_ids = list(rule_data['channel_ids'])
                elif 'channel_id' in rule_data:
                    import_channel_ids = [rule_data['channel_id']]
                else:
                    import_channel_ids = []
                
                import_channel_group_ids = list(rule_data.get('channel_group_ids', []))
                import_regex = rule_data['regex_pattern']
                import_name = rule_data['name']
                
                # Check for existing rules with same regex
                with self._lock:
                    matching_rule = None
                    for existing_rule in self._auto_create_rules:
                        if existing_rule['regex_pattern'] == import_regex:
                            matching_rule = existing_rule
                            break
                    
                    if matching_rule:
                        existing_channel_ids = set(matching_rule.get('channel_ids', []))
                        existing_channel_group_ids = set(matching_rule.get('channel_group_ids', []))
                        import_channel_ids_set = set(import_channel_ids)
                        import_channel_group_ids_set = set(import_channel_group_ids)
                        
                        # Check if it's an exact match (same regex, channels, and groups)
                        if (existing_channel_ids == import_channel_ids_set and 
                            existing_channel_group_ids == import_channel_group_ids_set):
                            # Replace: Update the name and other properties from imported rule
                            matching_rule['name'] = import_name
                            matching_rule['minutes_before'] = rule_data.get('minutes_before', 5)
                            
                            # Refresh channel and group info
                            udi = get_udi_manager()
                            
                            # Update channel groups info
                            channel_groups_info = []
                            for group_id in import_channel_group_ids:
                                group = udi.get_channel_group_by_id(group_id)
                                if group:
                                    group_channels = udi.get_channels_by_group(group_id)
                                    channel_groups_info.append({
                                        'id': group_id,
                                        'name': group.get('name', ''),
                                        'channel_count': len(group_channels) if group_channels else 0
                                    })
                            
                            matching_rule['channel_groups_info'] = channel_groups_info
                            
                            # Expand all channels (individual + from groups)
                            all_channel_ids = set(import_channel_ids)
                            for group_id in import_channel_group_ids:
                                group_channels = udi.get_channels_by_group(group_id)
                                if group_channels:
                                    for ch in group_channels:
                                        all_channel_ids.add(ch['id'])
                            
                            # Update channels info
                            channels_info = []
                            for channel_id in all_channel_ids:
                                channel = udi.get_channel_by_id(channel_id)
                                if channel:
                                    logo_id = channel.get('logo_id')
                                    logo_url = None
                                    if logo_id:
                                        logo = udi.get_logo_by_id(logo_id)
                                        if logo:
                                            logo_url = logo.get('cache_url') or logo.get('url')
                                    
                                    channels_info.append({
                                        'id': channel_id,
                                        'name': channel.get('name', ''),
                                        'logo_url': logo_url,
                                        'tvg_id': channel.get('tvg_id')
                                    })
                            
                            matching_rule['channels_info'] = channels_info
                            self._save_auto_create_rules()
                            
                            replaced_count += 1
                            logger.info(f"Replaced existing rule '{matching_rule['name']}' with imported rule '{import_name}'")
                        else:
                            # Merge: Combine channel lists, use imported rule's name
                            merged_channel_ids = list(existing_channel_ids.union(import_channel_ids_set))
                            matching_rule['channel_ids'] = merged_channel_ids
                            matching_rule['name'] = import_name  # Use imported name
                            matching_rule['minutes_before'] = rule_data.get('minutes_before', matching_rule.get('minutes_before', 5))
                            
                            # Update channel info for all channels
                            udi = get_udi_manager()
                            channels_info = []
                            for channel_id in merged_channel_ids:
                                channel = udi.get_channel_by_id(channel_id)
                                if channel:
                                    logo_id = channel.get('logo_id')
                                    logo_url = None
                                    if logo_id:
                                        logo = udi.get_logo_by_id(logo_id)
                                        if logo:
                                            logo_url = logo.get('cache_url') or logo.get('url')
                                    
                                    channels_info.append({
                                        'id': channel_id,
                                        'name': channel.get('name', ''),
                                        'logo_url': logo_url,
                                        'tvg_id': channel.get('tvg_id')
                                    })
                            
                            matching_rule['channels_info'] = channels_info
                            self._save_auto_create_rules()
                            
                            merged_count += 1
                            channel_names = ', '.join([ch['name'] for ch in channels_info])
                            logger.info(f"Merged channels into existing rule (now '{import_name}'): {channel_names}")
                    else:
                        # No existing rule with same regex, create new one
                        self.create_auto_create_rule(rule_data)
                        imported_count += 1
                
            except Exception as e:
                failed_count += 1
                error_msg = f"Rule {idx + 1} ('{rule_data.get('name', 'unknown')}'): {str(e)}"
                errors.append(error_msg)
                logger.warning(f"Failed to import rule: {error_msg}")
        
        result = {
            'imported': imported_count,
            'merged': merged_count,
            'replaced': replaced_count,
            'failed': failed_count,
            'total': len(rules_data),
            'errors': errors
        }
        
        logger.info(f"Import complete: {imported_count} new, {merged_count} merged, {replaced_count} replaced, {failed_count} failed out of {len(rules_data)} rules")
        return result


# Global singleton instance
_scheduling_service: Optional[SchedulingService] = None
_scheduling_lock = threading.Lock()


def get_scheduling_service() -> SchedulingService:
    """Get the global scheduling service singleton instance.
    
    Returns:
        The scheduling service instance
    """
    global _scheduling_service
    with _scheduling_lock:
        if _scheduling_service is None:
            _scheduling_service = SchedulingService()
        return _scheduling_service
