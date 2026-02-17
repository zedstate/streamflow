#!/usr/bin/env python3
"""
Automated Stream Manager for Dispatcharr

This module handles the automated process of:
1. Updating M3U playlists
2. Discovering new streams and assigning them to channels via regex
3. Maintaining changelog of updates

Uses the Universal Data Index (UDI) as the single source of truth for data access.
"""

import json
import logging
import os
import re
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
import concurrent.futures
from collections import defaultdict

# Pre-compiled regex pattern for whitespace conversion (performance optimization)
# This pattern matches one or more spaces that are NOT preceded by a backslash
# Used to convert literal spaces to flexible whitespace while preserving escaped spaces
_WHITESPACE_PATTERN = re.compile(r'(?<!\\) +')

# Placeholder for CHANNEL_NAME variable during regex validation
# Used to substitute CHANNEL_NAME in patterns before compiling for validation
_CHANNEL_NAME_PLACEHOLDER = 'PLACEHOLDER'

# Import croniter for cron expression support
try:
    from croniter import croniter
    CRONITER_AVAILABLE = True
except ImportError:
    CRONITER_AVAILABLE = False

from api_utils import (
    refresh_m3u_playlists,
    get_m3u_accounts,
    get_streams,
    add_streams_to_channel,
    _get_base_url
)

# Import UDI for direct data access
from udi import get_udi_manager
from automation_config_manager import get_automation_config_manager

# Import channel settings manager
# Import channel settings manager - DEPRECATED/REMOVED
# from channel_settings_manager import get_channel_settings_manager

# Import profile config
# Import profile config - DEPRECATED/REMOVED
# from profile_config import get_profile_config

# Setup centralized logging
from logging_config import setup_logging, log_function_call, log_function_return, log_exception, log_state_change

logger = setup_logging(__name__)

# Import DeadStreamsTracker
try:
    from dead_streams_tracker import DeadStreamsTracker
    DEAD_STREAMS_TRACKER_AVAILABLE = True
except ImportError:
    DEAD_STREAMS_TRACKER_AVAILABLE = False
    logger.warning("DeadStreamsTracker not available. Dead stream filtering will be disabled.")

# Configuration directory - persisted via Docker volume
CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', '/app/data'))

class ChangelogManager:
    """Manages changelog entries for stream updates."""
    
    def __init__(self, changelog_file=None):
        if changelog_file is None:
            changelog_file = CONFIG_DIR / "changelog.json"
        self.changelog_file = Path(changelog_file)
        self.changelog = self._load_changelog()
    
    def _load_changelog(self) -> List[Dict]:
        """Load existing changelog or create empty one."""
        if self.changelog_file.exists():
            try:
                with open(self.changelog_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                logger.warning(f"Could not load {self.changelog_file}, creating new changelog")
        return []
    
    def add_entry(self, action: str, details: Dict, timestamp: Optional[str] = None, subentries: Optional[List[Dict[str, Any]]] = None):
        """Add a new changelog entry.
        
        Args:
            action: Type of action (e.g., 'playlist_update_match', 'global_check', 'single_channel_check')
            details: Main details of the action including global stats
            timestamp: Optional timestamp (defaults to now)
            subentries: Optional list of subentry groups (e.g., updates, checks)
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        entry = {
            "timestamp": timestamp,
            "action": action,
            "details": details
        }
        
        # Add subentries if provided
        if subentries:
            entry["subentries"] = subentries
        
        self.changelog.append(entry)
        self._save_changelog()
        logger.info(f"Changelog entry added: {action}")
    
    def _save_changelog(self):
        """Save changelog to file."""
        # Ensure parent directory exists
        self.changelog_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.changelog_file, 'w') as f:
            json.dump(self.changelog, f, indent=2)
    
    def get_recent_entries(self, days: int = 7) -> List[Dict]:
        """Get changelog entries from the last N days, filtered and sorted."""
        cutoff = datetime.now() - timedelta(days=days)
        recent = []
        
        for entry in self.changelog:
            try:
                entry_time = datetime.fromisoformat(entry['timestamp'])
                if entry_time >= cutoff:
                    # Filter out entries without meaningful channel updates
                    if self._has_channel_updates(entry):
                        recent.append(entry)
            except (ValueError, KeyError):
                continue
        
        # Sort by timestamp in reverse chronological order (newest first)
        recent.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return recent
    
    def add_playlist_update_entry(self, channels_updated: Dict[int, Dict], global_stats: Dict):
        """Add a playlist update & match entry with subentries.
        
        Args:
            channels_updated: Dict mapping channel_id to update info (streams added, stats, logo_url)
            global_stats: Global statistics (total streams added, dead streams, avg resolution, avg bitrate)
        """
        # Create subentries for streams matched per channel
        update_subentries = []
        for channel_id, info in channels_updated.items():
            if info.get('streams_added'):
                update_subentries.append({
                    'type': 'update_match',
                    'channel_id': channel_id,
                    'channel_name': info.get('channel_name', f'Channel {channel_id}'),
                    'logo_url': info.get('logo_url'),
                    'streams': info.get('streams_added', [])
                })
        
        # Create subentries for channel checks
        check_subentries = []
        for channel_id, info in channels_updated.items():
            if info.get('check_stats'):
                check_subentries.append({
                    'type': 'check',
                    'channel_id': channel_id,
                    'channel_name': info.get('channel_name', f'Channel {channel_id}'),
                    'logo_url': info.get('logo_url'),
                    'stats': info.get('check_stats', {})
                })
        
        subentries = []
        if update_subentries:
            subentries.append({'group': 'update_match', 'items': update_subentries})
        if check_subentries:
            subentries.append({'group': 'check', 'items': check_subentries})
        
        self.add_entry(
            action='playlist_update_match',
            details=global_stats,
            subentries=subentries
        )
    
    def add_global_check_entry(self, channels_checked: Dict[int, Dict], global_stats: Dict):
        """Add a global check entry with subentries.
        
        Args:
            channels_checked: Dict mapping channel_id to check stats (including logo_url)
            global_stats: Global statistics across all channels
        """
        check_subentries = []
        for channel_id, stats in channels_checked.items():
            check_subentries.append({
                'type': 'check',
                'channel_id': channel_id,
                'channel_name': stats.get('channel_name', f'Channel {channel_id}'),
                'logo_url': stats.get('logo_url'),
                'stats': stats
            })
        
        subentries = [{'group': 'check', 'items': check_subentries}] if check_subentries else []
        
        self.add_entry(
            action='global_check',
            details=global_stats,
            subentries=subentries
        )
    
    def add_single_channel_check_entry(self, channel_id: int, channel_name: str, check_stats: Dict, logo_url: Optional[str] = None, program_name: Optional[str] = None):
        """Add a single channel check entry.
        
        Args:
            channel_id: ID of the channel checked
            channel_name: Name of the channel
            check_stats: Statistics from the channel check
            logo_url: Optional URL for the channel logo
            program_name: Optional program name if this was a scheduled EPG check
        """
        check_subentries = [{
            'type': 'check',
            'channel_id': channel_id,
            'channel_name': channel_name,
            'logo_url': logo_url,
            'stats': check_stats
        }]
        
        subentries = [{'group': 'check', 'items': check_subentries}]
        
        # Build details dict
        details = {
            'channel_id': channel_id,
            'channel_name': channel_name,
            'total_streams': check_stats.get('total_streams', 0),
            'dead_streams': check_stats.get('dead_streams', 0),
            'avg_resolution': check_stats.get('avg_resolution', 'N/A'),
            'avg_bitrate': check_stats.get('avg_bitrate', 'N/A')
        }
        
        # Add program name if provided (for scheduled EPG checks)
        if program_name:
            details['program_name'] = program_name
        
        self.add_entry(
            action='single_channel_check',
            details=details,
            subentries=subentries
        )
    
    def _has_channel_updates(self, entry: Dict) -> bool:
        """Check if a changelog entry contains meaningful channel/stream updates."""
        details = entry.get('details', {})
        action = entry.get('action', '')
        
        # For new action types, check if they have subentries
        if action in ['playlist_update_match', 'global_check', 'single_channel_check']:
            subentries = entry.get('subentries', [])
            # Include if there are subentries with items
            return any(group.get('items') for group in subentries)
        
        # For playlist_refresh, only include if there were actual changes
        if action == 'playlist_refresh':
            added = details.get('added_streams', [])
            removed = details.get('removed_streams', [])
            return len(added) > 0 or len(removed) > 0
        
        # For streams_assigned, only include if streams were actually assigned
        if action == 'streams_assigned':
            total_assigned = details.get('total_assigned', 0)
            return total_assigned > 0
        
        # For other actions, include if success is True or not specified
        # (exclude failed operations without updates)
        if 'success' in details:
            return details['success'] is True
        
        return True  # Include entries without explicit success flag


class RegexChannelMatcher:
    """Handles regex-based channel matching for stream assignment."""
    
    def __init__(self, config_file=None):
        if config_file is None:
            config_file = CONFIG_DIR / "channel_regex_config.json"
        self.config_file = Path(config_file)
        self.lock = threading.RLock()
        self.channel_patterns = self._load_patterns()
    
    def _load_patterns(self) -> Dict:
        """Load regex patterns for channel matching.
        
        Handles corrupted JSON and invalid regex patterns gracefully by:
        - Creating default config if JSON is invalid
        - Removing patterns with invalid regex on load to prevent persistent errors
        - Migrating old format (regex array) to new format (regex_patterns array of objects)
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                
                # Validate and sanitize patterns - remove any with invalid regex
                # Also migrate old format to new format
                if 'patterns' in loaded_config and isinstance(loaded_config['patterns'], dict):
                    patterns_to_remove = []
                    needs_migration = False
                    
                    for channel_id, pattern_data in loaded_config['patterns'].items():
                        if not isinstance(pattern_data, dict):
                            patterns_to_remove.append(channel_id)
                            continue
                        
                        # Check if migration needed (old format uses 'regex', new uses 'regex_patterns')
                        if 'regex' in pattern_data and 'regex_patterns' not in pattern_data:
                            needs_migration = True
                            # Migrate from old format to new format
                            regex_list = pattern_data.get('regex', [])
                            channel_m3u_accounts = pattern_data.get('m3u_accounts')  # Channel-level m3u_accounts
                            
                            if not isinstance(regex_list, list):
                                patterns_to_remove.append(channel_id)
                                continue
                            
                            # Convert to new format
                            regex_patterns = []
                            for pattern_str in regex_list:
                                if not pattern_str or not isinstance(pattern_str, str):
                                    continue
                                regex_patterns.append({
                                    "pattern": pattern_str,
                                    "m3u_accounts": channel_m3u_accounts,  # Apply channel-level to all patterns
                                    "priority": 0  # Default priority for migrated patterns
                                })
                            
                            if regex_patterns:
                                pattern_data['regex_patterns'] = regex_patterns
                                # Keep old 'regex' field for backward compatibility temporarily
                                # Remove old m3u_accounts field as it's now per-pattern
                                if 'm3u_accounts' in pattern_data:
                                    del pattern_data['m3u_accounts']
                        
                        # Validate patterns (support both old and new format)
                        regex_patterns = pattern_data.get('regex_patterns', [])
                        if not regex_patterns:
                            # Fallback to old format
                            regex_patterns = [{"pattern": p, "priority": 0} for p in pattern_data.get('regex', [])]
                        
                        # Check if any regex patterns are invalid
                        has_invalid = False
                        for pattern_obj in regex_patterns:
                            if isinstance(pattern_obj, dict):
                                pattern = pattern_obj.get('pattern', '')
                            else:
                                # Legacy format within regex_patterns
                                pattern = pattern_obj
                            
                            if not pattern or not isinstance(pattern, str):
                                has_invalid = True
                                break
                            try:
                                # Temporarily substitute CHANNEL_NAME for validation
                                validation_pattern = pattern.replace('CHANNEL_NAME', _CHANNEL_NAME_PLACEHOLDER)
                                re.compile(validation_pattern)
                            except re.error as e:
                                logger.warning(
                                    f"Removing channel {channel_id} with invalid regex pattern '{pattern}': {e}. "
                                    f"Please reconfigure this channel with valid patterns."
                                )
                                has_invalid = True
                                break
                        
                        if has_invalid:
                            patterns_to_remove.append(channel_id)
                    
                    # Remove invalid patterns
                    if patterns_to_remove:
                        for channel_id in patterns_to_remove:
                            del loaded_config['patterns'][channel_id]
                        
                        logger.info(f"Removed {len(patterns_to_remove)} pattern(s) with invalid regex")
                    
                    # Save if we made changes (migration or cleanup)
                    if patterns_to_remove or needs_migration:
                        if needs_migration:
                            logger.info("Migrated regex patterns from old format to new format with per-pattern M3U accounts")
                        self._save_patterns(loaded_config)
                
                return loaded_config
                
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.warning(f"Could not load {self.config_file}: {e}. Creating default config")
        
        # Create default configuration
        default_config = {
            "patterns": {
                # Example patterns - these should be configured by the user
                # "1": {"name": "CNN", "regex_patterns": [{"pattern": ".*CNN.*", "m3u_accounts": null}], "enabled": True}
            },
            "global_settings": {
                "case_sensitive": True,
                "require_exact_match": False
            }
        }
        
        self._save_patterns(default_config)
        return default_config
    
    def _save_patterns(self, patterns: Dict):
        """Save patterns to file."""
        # Ensure parent directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(patterns, f, indent=2)
    
    def validate_regex_patterns(self, patterns: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate a list of regex patterns.
        
        Args:
            patterns: List of regex pattern strings to validate
            
        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        if not patterns:
            return False, "At least one regex pattern is required"
        
        for pattern in patterns:
            if not pattern or not isinstance(pattern, str):
                return False, f"Pattern must be a non-empty string"
            
            try:
                # Temporarily substitute CHANNEL_NAME with a placeholder for validation
                # Use a simple placeholder that won't interfere with regex syntax
                validation_pattern = pattern.replace('CHANNEL_NAME', _CHANNEL_NAME_PLACEHOLDER)
                re.compile(validation_pattern)
            except re.error as e:
                return False, f"Invalid regex pattern '{pattern}': {str(e)}"
        
        return True, None
    
    def add_channel_pattern(self, channel_id: str, name: str, regex_patterns: 'Union[List[str], List[Dict]]', enabled: bool = True, m3u_accounts: Optional[List[int]] = None, silent: bool = False):
        """Add or update a channel pattern.
        
        Args:
            channel_id: Channel ID
            name: Channel name
            regex_patterns: Can be either:
                          - List[str]: Legacy format, list of regex pattern strings
                          - List[Dict]: New format with per-pattern m3u_accounts
                              [{"pattern": str, "m3u_accounts": List[int] | None}, ...]
            enabled: Whether the pattern is enabled
            m3u_accounts: Optional list of M3U account IDs (legacy, channel-level).
                         Only used when regex_patterns is List[str].
                         Examples:
                         - None: Field not stored, applies to all M3U accounts (backward compatible)
                         - []: Empty list stored, explicitly means "all M3U accounts"
                         - [1, 2, 3]: Only match streams from M3U accounts with these IDs
            silent: If True, log at DEBUG level instead of INFO (useful for batch operations)
            
        Raises:
            ValueError: If any regex pattern is invalid
        """
        # Normalize regex_patterns to new format
        normalized_patterns = []
        
        if isinstance(regex_patterns, list) and len(regex_patterns) > 0:
            if isinstance(regex_patterns[0], dict):
                # New format: List[Dict]
                for item in regex_patterns:
                    if not isinstance(item, dict) or "pattern" not in item:
                        raise ValueError("Each pattern object must have a 'pattern' field")
                    normalized_patterns.append({
                        "pattern": item["pattern"],
                        "m3u_accounts": item.get("m3u_accounts"),
                        "priority": item.get("priority", 0)  # Default priority is 0
                    })
            else:
                # Legacy format: List[str] - convert to new format
                for pattern in regex_patterns:
                    normalized_patterns.append({
                        "pattern": pattern,
                        "m3u_accounts": m3u_accounts,  # Use channel-level m3u_accounts for all patterns
                        "priority": 0  # Default priority for legacy patterns
                    })
        else:
            raise ValueError("At least one regex pattern is required")
        
        # Validate patterns
        pattern_strings = [p["pattern"] for p in normalized_patterns]
        is_valid, error_msg = self.validate_regex_patterns(pattern_strings)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Store in new format
        pattern_data = {
            "name": name,
            "regex_patterns": normalized_patterns,  # New field name
            "enabled": enabled
        }
        
        self.channel_patterns["patterns"][str(channel_id)] = pattern_data
        self._save_patterns(self.channel_patterns)
        
        # Log at appropriate level based on silent flag
        if silent:
            logger.debug(f"Added/updated {len(normalized_patterns)} pattern(s) for channel {channel_id}: {name}")
        else:
            logger.info(f"Added/updated {len(normalized_patterns)} pattern(s) for channel {channel_id}: {name}")
    
    def delete_channel_pattern(self, channel_id: str):
        """Delete all regex patterns for a channel.
        
        Args:
            channel_id: Channel ID
        """
        channel_id = str(channel_id)
        if channel_id in self.channel_patterns.get("patterns", {}):
            del self.channel_patterns["patterns"][channel_id]
            self._save_patterns(self.channel_patterns)
            logger.info(f"Deleted all patterns for channel {channel_id}")
        else:
            logger.warning(f"No patterns found for channel {channel_id}")
    
    
    def reload_patterns(self):
        """Reload patterns from the config file.
        
        This is useful when patterns have been updated by another process
        and we need to ensure we're using the latest patterns.
        """
        self.channel_patterns = self._load_patterns()
        logger.debug("Reloaded regex patterns from config file")
    
    def _substitute_channel_variables(self, pattern: str, channel_name: str) -> str:
        """Substitute channel name variables in a regex pattern.
        
        Args:
            pattern: Regex pattern that may contain CHANNEL_NAME
            channel_name: Name of the channel to substitute
            
        Returns:
            Pattern with variables substituted
        """
        # Replace CHANNEL_NAME with the actual channel name
        # Escape special regex characters in channel name to avoid issues
        escaped_channel_name = re.escape(channel_name)
        return pattern.replace('CHANNEL_NAME', escaped_channel_name)
    
    def match_stream_to_channels(self, stream_name: str, stream_m3u_account: Optional[int] = None, 
                               stream_tvg_id: Optional[str] = None, channel_tvg_ids: Optional[Dict[str, str]] = None,
                               channel_match_priorities: Optional[Dict[str, List[str]]] = None) -> List[str]:
        """
        Match a stream name and optionally TVG-ID to channels using regex patterns and TVG-ID matching.
        
        Args:
            stream_name: The name of the stream to match
            stream_m3u_account: The ID of the M3U account the stream belongs to (optional)
            stream_tvg_id: The TVG-ID of the stream (optional)
            channel_tvg_ids: Dictionary mapping channel_id -> tvg_id (optional, for optimization)
            channel_match_priorities: Dictionary mapping channel_id -> ['tvg', 'regex'] or ['regex', 'tvg'] (optional)
            
        Returns:
            List of channel IDs that match the stream
        """
        matches = []
        case_sensitive = self.channel_patterns.get("global_settings", {}).get("case_sensitive", True)
        
        search_name = stream_name if case_sensitive else stream_name.lower()
        
        with self.lock:
            for channel_id, config in self.channel_patterns.get("patterns", {}).items():
                if not isinstance(config, dict):
                    continue
                
                # Determine priority order
                # Default: TVG first (if enabled)
                priority_order = ['tvg', 'regex']
                if channel_match_priorities:
                    # Look up by string ID since config keys are stringified
                    mapped_order = channel_match_priorities.get(str(channel_id))
                    if mapped_order:
                        priority_order = mapped_order
                
                matched_channel = False
                
                # Check based on priority order
                # We stop checking a channel if one method matches (optimization and precedence)
                for match_type in priority_order:
                    if match_type == 'tvg':
                        # Check for TVG-ID match if enabled and not already matched
                        if not matched_channel and stream_tvg_id and channel_tvg_ids and config.get("match_by_tvg_id", False):
                            channel_tvg_id = channel_tvg_ids.get(str(channel_id))
                            if channel_tvg_id and stream_tvg_id == channel_tvg_id:
                                matches.append(channel_id)
                                matched_channel = True
                                break # Skip other match types for this channel
                                
                    elif match_type == 'regex':
                        if matched_channel: 
                            continue
                            
                        if not config.get("enabled", True):
                            continue
                        
                        channel_name = config.get("name", "")
                        
                        # Support both new format (regex_patterns) and old format (regex) for backward compatibility
                        regex_patterns = config.get("regex_patterns")
                        if regex_patterns is None:
                            # Fallback to old format
                            old_regex = config.get("regex", [])
                            old_m3u_accounts = config.get("m3u_accounts")
                            regex_patterns = [{"pattern": p, "m3u_accounts": old_m3u_accounts} for p in old_regex]
                        
                        regex_matched = False
                        for pattern_obj in regex_patterns:
                            # Handle both dict and string patterns for flexibility
                            if isinstance(pattern_obj, dict):
                                pattern = pattern_obj.get("pattern", "")
                                pattern_m3u_accounts = pattern_obj.get("m3u_accounts")
                            else:
                                # Legacy string format
                                pattern = pattern_obj
                                pattern_m3u_accounts = None
                            
                            if not pattern:
                                continue
                            
                            # Check if this regex pattern applies to the stream's M3U account
                            if pattern_m3u_accounts is not None and len(pattern_m3u_accounts) > 0:
                                # Pattern is limited to specific M3U accounts
                                if stream_m3u_account is None or stream_m3u_account not in pattern_m3u_accounts:
                                    # Stream's M3U account is not in the allowed list, skip this pattern
                                    continue
                            
                            # SAFETY CHECK: If match_by_tvg_id is enabled, IGNORE catch-all regexes
                            # This prevents the issue where a lingering ".*" causes unwanted matches
                            # despite the user enabling TVG matching.
                            if config.get("match_by_tvg_id", False):
                                is_catch_all = pattern == ".*" or pattern == "^.*$" or pattern == ".+" or pattern == "^.+$"
                                if is_catch_all:
                                    # logger.debug(f"Ignoring catch-all regex '{pattern}' for channel {channel_id} because match_by_tvg_id is enabled")
                                    continue

                            # Substitute channel name variable if present
                            substituted_pattern = self._substitute_channel_variables(pattern, channel_name)
                            
                            search_pattern = substituted_pattern if case_sensitive else substituted_pattern.lower()
                            
                            # Convert literal spaces in pattern to flexible whitespace regex
                            search_pattern = _WHITESPACE_PATTERN.sub(r'\\s+', search_pattern)
                            
                            try:
                                if re.search(search_pattern, search_name):
                                    matches.append(channel_id)
                                    matched_channel = True
                                    regex_matched = True
                                    # logger.debug(f"Stream '{stream_name}' matched channel {channel_id} with pattern '{pattern}'")
                                    break  # Only match once per channel
                            except re.error as e:
                                logger.error(f"Invalid regex pattern '{pattern}' for channel {channel_id}: {e}")
                        
                        if regex_matched:
                            break # Skip other match types for this channel
        
        return matches
    
    def match_stream_to_channels_with_priority(self, stream_name: str, stream_m3u_account: Optional[int] = None,
                                             stream_tvg_id: Optional[str] = None, channel_tvg_ids: Optional[Dict[str, str]] = None,
                                             channel_match_priorities: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, Any]]:
        """Match a stream name and optionally TVG-ID to channels using regex patterns with priority.
        
        Args:
            stream_name: The name of the stream to match
            stream_m3u_account: The ID of the M3U account the stream belongs to (optional)
            stream_tvg_id: The TVG-ID of the stream (optional)
            channel_tvg_ids: Dictionary mapping channel_id -> tvg_id (optional)
            channel_match_priorities: Dictionary mapping channel_id -> priority order list (optional)
            
        Returns:
            List of dictionaries containing channel_id and priority
        """
        matches = []
        case_sensitive = self.channel_patterns.get("global_settings", {}).get("case_sensitive", True)
        
        search_name = stream_name if case_sensitive else stream_name.lower()
        
        with self.lock:
            for channel_id, config in self.channel_patterns.get("patterns", {}).items():
                if not isinstance(config, dict):
                    continue
                
                matched = False
                priority = 0
                match_source = "regex"
                
                # Determine priority order
                priority_order = ['tvg', 'regex']
                if channel_match_priorities:
                    mapped_order = channel_match_priorities.get(str(channel_id))
                    if mapped_order:
                        priority_order = mapped_order
                        
                for match_type in priority_order:
                    if match_type == 'tvg':
                        # Check for TVG-ID match if enabled and not already matched
                        if not matched and stream_tvg_id and channel_tvg_ids and config.get("match_by_tvg_id", False):
                            channel_tvg_id = channel_tvg_ids.get(str(channel_id))
                            if channel_tvg_id and stream_tvg_id == channel_tvg_id:
                                matched = True
                                match_source = "tvg_id"
                                # Assign priority based on order preference
                                # TVG-ID matches get a very high internal priority (1000)
                                # This is normalized in stream_checker_service's scoring logic
                                if priority_order[0] == 'tvg':
                                    priority = 1000
                                else:
                                    priority = 0
                                break
                                
                    elif match_type == 'regex':
                        if matched:
                            continue
                            
                        if not config.get("enabled", True):
                            continue
                        
                        channel_name = config.get("name", "")
                        
                        # Support both new format (regex_patterns) and old format (regex) for backward compatibility
                        regex_patterns = config.get("regex_patterns")
                        if regex_patterns is None:
                            # Fallback to old format
                            old_regex = config.get("regex", [])
                            old_m3u_accounts = config.get("m3u_accounts")
                            regex_patterns = [{"pattern": p, "m3u_accounts": old_m3u_accounts, "priority": 0} for p in old_regex]
                        
                        regex_matched = False
                        best_regex_priority = 0
                        
                        for pattern_obj in regex_patterns:
                            # Handle both dict and string patterns for flexibility
                            if isinstance(pattern_obj, dict):
                                pattern = pattern_obj.get("pattern", "")
                                pattern_m3u_accounts = pattern_obj.get("m3u_accounts")
                                pattern_priority = pattern_obj.get("priority", 0)
                            else:
                                # Legacy string format
                                pattern = pattern_obj
                                pattern_m3u_accounts = None
                                pattern_priority = 0
                            
                            if not pattern:
                                continue
                            
                            # Check if this regex pattern applies to the stream's M3U account
                            if pattern_m3u_accounts is not None and len(pattern_m3u_accounts) > 0:
                                # Pattern is limited to specific M3U accounts
                                if stream_m3u_account is None or stream_m3u_account not in pattern_m3u_accounts:
                                    # Stream's M3U account is not in the allowed list, skip this pattern
                                    continue
                            
                            # SAFETY CHECK: If match_by_tvg_id is enabled, IGNORE catch-all regexes
                            if config.get("match_by_tvg_id", False):
                                is_catch_all = pattern == ".*" or pattern == "^.*$" or pattern == ".+" or pattern == "^.+$"
                                if is_catch_all:
                                    continue

                            # Substitute channel name variable if present
                            substituted_pattern = self._substitute_channel_variables(pattern, channel_name)
                            
                            search_pattern = substituted_pattern if case_sensitive else substituted_pattern.lower()
                            
                            # Convert literal spaces in pattern to flexible whitespace regex
                            search_pattern = _WHITESPACE_PATTERN.sub(r'\\s+', search_pattern)
                            
                            try:
                                if re.search(search_pattern, search_name):
                                    regex_matched = True
                                    best_regex_priority = max(best_regex_priority, pattern_priority)
                                    # We don't break here because we want to find the HIGHEST priority regex match
                                    # But previous logic did break. Let's stick to "highest priority regex wins" assumption for 'with_priority'
                            except re.error as e:
                                logger.error(f"Invalid regex pattern '{pattern}' for channel {channel_id}: {e}")
                                
                        if regex_matched:
                            matched = True
                            match_source = "regex"
                            # Regex priorities are typically 0-50 and scale separately from TVG matches
                            priority = best_regex_priority
                            break

            
                if matched:
                    matches.append({
                        "channel_id": channel_id,
                        "priority": priority,
                        "source": match_source
                    })
    
        return matches

    def set_match_by_tvg_id(self, channel_id: Union[str, int], enabled: bool) -> bool:
        """Enable or disable matching by TVG-ID for a channel."""
        with self.lock:
            channel_id = str(channel_id)
            if "patterns" not in self.channel_patterns:
                self.channel_patterns["patterns"] = {}
                
            if channel_id not in self.channel_patterns["patterns"]:
                self.channel_patterns["patterns"][channel_id] = {
                    "regex_patterns": [],
                    "match_by_tvg_id": enabled
                }
            else:
                self.channel_patterns["patterns"][channel_id]["match_by_tvg_id"] = enabled
                
            self._save_patterns(self.channel_patterns)
            return True

    def get_match_by_tvg_id(self, channel_id: Union[str, int]) -> bool:
        """Check if matching by TVG-ID is enabled for a channel."""
        with self.lock:
            patterns = self.channel_patterns.get("patterns", {})
            channel_config = patterns.get(str(channel_id), {})
            if isinstance(channel_config, dict):
                return channel_config.get("match_by_tvg_id", False)
            return False
    
    def get_patterns(self) -> Dict:
        """Get current patterns configuration."""
        return self.channel_patterns
    
    def has_regex_patterns(self, channel_id: str) -> bool:
        """Check if a channel has regex patterns configured and enabled.
        
        A channel is considered to have regex patterns if:
        1. The channel exists in the patterns configuration
        2. The pattern configuration is enabled (enabled=True)
        3. The regex list is non-empty
        
        Args:
            channel_id: Channel ID to check
            
        Returns:
            True if the channel has at least one enabled regex pattern, False otherwise
        """
        channel_config = self.channel_patterns.get("patterns", {}).get(str(channel_id))
        if not channel_config:
            return False
        
        # Check if the pattern is enabled
        if not channel_config.get("enabled", True):
            return False
        
        # Check if there are any regex patterns (support both old and new format)
        regex_patterns = channel_config.get("regex_patterns")
        if regex_patterns is None:
            # Fallback to old format
            regex_patterns = channel_config.get("regex", [])
        
        return isinstance(regex_patterns, list) and len(regex_patterns) > 0
    
    def get_channel_regex_filter(self, channel_id: str, default: str = ".*") -> Optional[str]:
        """Get the combined regex filter for a channel for stream name matching.
        
        Combines all enabled regex patterns for the channel into a single OR pattern.
        Returns `default` (standard ".*") if no patterns are configured or channel is disabled.
        
        Args:
            channel_id: Channel ID to get regex filter for
            default: Default value to return if no patterns found (default: ".*")
            
        Returns:
            Combined regex pattern string (e.g., '(pattern1|pattern2|pattern3)')
        """
        channel_config = self.channel_patterns.get("patterns", {}).get(str(channel_id))
        if not channel_config:
            return default
        
        # Check if the pattern is enabled
        if not channel_config.get("enabled", True):
            return default
        
        # Get regex patterns (support both old and new format)
        regex_patterns = channel_config.get("regex_patterns")
        if regex_patterns is None:
            # Fallback to old format
            regex_patterns = channel_config.get("regex", [])
        
        if not isinstance(regex_patterns, list) or len(regex_patterns) == 0:
            return default
        
        # Extract pattern strings from objects (new format) or use directly (old format)
        pattern_strings = []
        for pattern_obj in regex_patterns:
            if isinstance(pattern_obj, dict):
                pattern = pattern_obj.get('pattern', '')
            else:
                # Legacy format
                pattern = pattern_obj
            
            if pattern and isinstance(pattern, str):
                pattern_strings.append(pattern)
        
        if not pattern_strings:
            return default
        
        # If only one pattern, return it directly
        if len(pattern_strings) == 1:
            return pattern_strings[0]
        
        # Combine multiple patterns with OR
        # Each pattern is wrapped in a non-capturing group for safety
        combined = '|'.join(f'(?:{p})' for p in pattern_strings)
        return f'({combined})'

    def get_channel_match_config(self, channel_id: str) -> Dict[str, Any]:
        """Get the matching configuration for a channel.
        
        Args:
            channel_id: Channel ID
            
        Returns:
            Dictionary with matching configuration (match_by_tvg_id, enabled, etc.)
        """
        channel_config = self.channel_patterns.get("patterns", {}).get(str(channel_id), {})
        return {
            "match_by_tvg_id": channel_config.get("match_by_tvg_id", False),
            "enabled": channel_config.get("enabled", True),
            "name": channel_config.get("name", "")
        }


class AutomatedStreamManager:
    """Main automated stream management system."""
    
    def __init__(self, config_file=None):
        if config_file is None:
            config_file = CONFIG_DIR / "automation_config.json"
        self.config_file = Path(config_file)
        self.config = self._load_config()
        self.changelog = ChangelogManager()
        self.regex_matcher = RegexChannelMatcher()
        
        # Initialize dead streams tracker
        self.dead_streams_tracker = None
        if DEAD_STREAMS_TRACKER_AVAILABLE:
            try:
                self.dead_streams_tracker = DeadStreamsTracker()
                logger.info("Dead streams tracker initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize dead streams tracker: {e}")
        
        self.running = False
        self.last_playlist_update = None
        self.automation_start_time = None
        
        # Cache for M3U accounts to avoid redundant API calls within a single automation cycle
        # This is cleared after each cycle completes
        self._m3u_accounts_cache = None
        
        # Cache for dead stream removal setting to avoid repeated file I/O
        self._dead_stream_removal_enabled_cache = None
        
        # Background thread management
        self.automation_thread = None
        self.automation_running = False
        self.automation_wake_event = threading.Event()
        self.force_next_run = False
        self._dead_stream_removal_cache_time = None
        
        # Lock to prevent concurrent execution of heavy batch processes
        self._lock = threading.Lock()
    
    def _load_config(self) -> Dict:
        """Load automation configuration."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                logger.warning(f"Could not load {self.config_file}, creating default config")
        
        # Default configuration
        default_config = {
            "playlist_update_interval_minutes": 5,
            "playlist_update_cron": "",  # Empty means use interval. When both are set, cron takes precedence.
            "enabled_m3u_accounts": [],  # Empty list means all accounts enabled
            "autostart_automation": False,  # Don't auto-start by default
            "enabled_features": {
                "auto_playlist_update": True,
                "auto_stream_discovery": True,
                "changelog_tracking": True
            },
            "validate_existing_streams": False,  # Validate existing streams in channels against regex patterns
            "verify_stream_assignments": False  # Verify stream assignments by refreshing UDI (adds API overhead)
        }
        
        self._save_config(default_config)
        return default_config
    
    def _save_config(self, config: Dict):
        """Save configuration to file."""
        # Ensure parent directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def update_config(self, updates: Dict):
        """Update configuration with new values and apply immediately."""
        # Log what's being updated
        config_changes = []
        
        if 'playlist_update_interval_minutes' in updates:
            old_interval = self.config.get('playlist_update_interval_minutes', 5)
            new_interval = updates['playlist_update_interval_minutes']
            if old_interval != new_interval:
                config_changes.append(f"Playlist update interval: {old_interval} → {new_interval} minutes")
        
        if 'enabled_features' in updates:
            old_features = self.config.get('enabled_features', {})
            new_features = updates['enabled_features']
            for feature, enabled in new_features.items():
                old_value = old_features.get(feature, True)
                if old_value != enabled:
                    status = "enabled" if enabled else "disabled"
                    config_changes.append(f"{feature}: {status}")
        
        if 'enabled_m3u_accounts' in updates:
            old_accounts = self.config.get('enabled_m3u_accounts', [])
            new_accounts = updates['enabled_m3u_accounts']
            if old_accounts != new_accounts:
                if not new_accounts:
                    config_changes.append("M3U accounts: all enabled")
                else:
                    config_changes.append(f"M3U accounts: {len(new_accounts)} selected")
        
        # Apply the configuration update
        self.config.update(updates)
        self._save_config(self.config)
        
        # Log the changes
        if config_changes:
            logger.info(f"Automation configuration updated: {'; '.join(config_changes)}")
            logger.info("Changes will take effect on next scheduled operation")
        else:
            logger.info("Automation configuration updated")
    
    def _is_dead_stream_removal_enabled(self) -> bool:
        """Check if dead stream removal is enabled in stream checker config.
        
        Uses a 60-second cache to avoid repeated file I/O operations.
        
        Returns:
            True if dead stream removal is enabled, False otherwise
        """
        import time
        current_time = time.time()
        
        # Check if cache is still valid (60 seconds)
        if (self._dead_stream_removal_cache_time is not None and 
            current_time - self._dead_stream_removal_cache_time < 60 and
            self._dead_stream_removal_enabled_cache is not None):
            return self._dead_stream_removal_enabled_cache
        
        # Cache expired or not set, read from file
        try:
            stream_checker_config_file = CONFIG_DIR / 'stream_checker_config.json'
            if stream_checker_config_file.exists():
                with open(stream_checker_config_file, 'r') as f:
                    config = json.load(f)
                    enabled = config.get('dead_stream_handling', {}).get('enabled', True)
            else:
                # Default to True if config doesn't exist
                enabled = True
            
            # Update cache
            self._dead_stream_removal_enabled_cache = enabled
            self._dead_stream_removal_cache_time = current_time
            return enabled
        except Exception as e:
            logger.error(f"Error reading stream checker config: {e}")
            # Default to True on error (conservative approach)
            # Don't cache errors, try again next time
            return True
    
    def _filter_channels_by_profile(self, all_channels: List[Dict], action_description: str) -> List[Dict]:
        """Filter channels by selected profile if one is configured.
        
        Args:
            all_channels: List of all channels from UDI
            action_description: Description of the action (e.g., "stream assignment", "stream validation")
                               Used in log messages to provide context
        
        Returns:
            Filtered list of channels. If no profile is selected or an error occurs,
            returns the original list.
        """
        # Legacy profile filtering is deprecated in favor of granular per-channel automation profiles.
        # This method is kept for backward compatibility but now returns all channels,
        # letting the specific logic (assignment/validation) handle per-channel profiles.
        return all_channels
    
    def refresh_playlists(self, force: bool = False, account_id: Optional[int] = None) -> bool:
        """Refresh M3U playlists and track changes.
        
        Args:
            force: If True, bypass the auto_playlist_update feature flag check.
                   Used for manual/quick action triggers from the UI.
            account_id: Optional ID of specific account to refresh. If None, refreshes all enabled accounts.
        """
        try:
            if not force and not self.config.get("enabled_features", {}).get("auto_playlist_update", True):
                if not force:  # Allow force to override feature flag
                    logger.info("Playlist update is disabled in configuration")
                    return False
            
            logger.info("Starting M3U playlist refresh...")
            
            # Get streams before refresh
            from api_utils import get_streams
            streams_before = get_streams(log_result=False) if self.config.get("enabled_features", {}).get("changelog_tracking", True) else []
            before_stream_ids = {s.get('id'): s.get('name', '') for s in streams_before if isinstance(s, dict) and s.get('id')}
            
            # Get all M3U accounts
            all_accounts = get_m3u_accounts()
            self._m3u_accounts_cache = all_accounts
            logger.debug(f"M3U accounts fetched from UDI cache: {len(all_accounts) if all_accounts else 0} accounts")
            
            if all_accounts:
                # Filter out "custom" account and non-active accounts
                non_custom_accounts = [
                    acc for acc in all_accounts
                    if acc.get('name', '').lower() != 'custom' and acc.get('is_active', True)
                ]
                
                # Determine which accounts to refresh
                accounts_to_process = []
                
                if account_id is not None:
                    # Refresh specific account
                    target_account = next((a for a in non_custom_accounts if a.get('id') == account_id), None)
                    if target_account:
                        accounts_to_process = [target_account]
                    else:
                        logger.warning(f"Requested refresh for account {account_id}, but it was not found or is inactive/custom.")
                else:
                    # Refresh all (or filtered by enabled_m3u_accounts config)
                    enabled_accounts = self.config.get("enabled_m3u_accounts", [])
                    if enabled_accounts:
                         # Filter to only enabled accounts
                         accounts_to_process = [a for a in non_custom_accounts if a.get('id') in enabled_accounts]
                    else:
                         # All non-custom active accounts
                         accounts_to_process = non_custom_accounts

                # Execute refresh
                for account in accounts_to_process:
                    acc_id = account.get('id')
                    if acc_id is not None:
                        logger.info(f"Refreshing M3U account {acc_id}: {account.get('name')}")
                        refresh_m3u_playlists(account_id=acc_id)
                
                if not accounts_to_process:
                    logger.info("No accounts matched criteria for refresh.")
            else:
                # Fallback: if we can't get accounts, refresh all (legacy behavior)
                logger.warning("Could not fetch M3U accounts, refreshing all as fallback")
                refresh_m3u_playlists()
            
            # Refresh UDI cache to get updated streams and channels after playlist update
            # This ensures deleted/added streams are reflected in the cache
            # Also refresh M3U accounts to detect any new accounts added in Dispatcharr
            # And refresh channel groups to detect any group changes (splits, merges, etc.)
            # Profile refresh is critical: ensures channel profiles stay synced with Dispatcharr
            # (deletions, modifications, new profiles) to prevent orphaned profile references
            logger.info("Refreshing UDI cache after playlist update...")
            udi = get_udi_manager()
            udi.refresh_m3u_accounts()  # Check for new M3U accounts
            udi.refresh_streams()
            udi.refresh_channels()
            udi.refresh_channel_groups()  # Check for new/updated channel groups
            udi.refresh_channel_profiles()  # Sync profiles with Dispatcharr to prevent orphaned references
            logger.info("UDI cache refreshed successfully")
            
            # Trigger EPG refresh to pick up any EPG/tvg-id changes made in Dispatcharr
            # This ensures that if a channel's EPG assignment was changed in Dispatcharr,
            # the new program data will be available in StreamFlow
            try:
                logger.info("Triggering EPG refresh after playlist update...")
                from scheduling_service import get_scheduling_service
                scheduling_service = get_scheduling_service()
                # Force refresh to bypass cache and get fresh EPG data
                scheduling_service.fetch_epg_grid(force_refresh=True)
                logger.info("EPG refresh completed successfully")
            except Exception as e:
                logger.error(f"Error triggering EPG refresh after playlist update: {e}")
                # Continue even if EPG refresh fails
            
            # Get streams after refresh - log this one since it shows the final result
            streams_after = get_streams(log_result=True) if self.config.get("enabled_features", {}).get("changelog_tracking", True) else []
            after_stream_ids = {s.get('id'): s.get('name', '') for s in streams_after if isinstance(s, dict) and s.get('id')}
            
            self.last_playlist_update = datetime.now()
            
            # Calculate differences
            added_stream_ids = set(after_stream_ids.keys()) - set(before_stream_ids.keys())
            removed_stream_ids = set(before_stream_ids.keys()) - set(after_stream_ids.keys())
            
            added_streams = [{"id": sid, "name": after_stream_ids[sid]} for sid in added_stream_ids]
            removed_streams = [{"id": sid, "name": before_stream_ids[sid]} for sid in removed_stream_ids]
            
            
            if self.config.get("enabled_features", {}).get("changelog_tracking", True):
                self.changelog.add_entry("playlist_refresh", {
                    "success": True,
                    "timestamp": self.last_playlist_update.isoformat(),
                    "total_streams": len(after_stream_ids),
                    "added_streams": added_streams[:50],  # Limit to first 50 for changelog size
                    "removed_streams": removed_streams[:50],  # Limit to first 50 for changelog size
                    "added_count": len(added_streams),
                    "removed_count": len(removed_streams)
                })
            
            logger.info(f"M3U playlist refresh completed successfully. Added: {len(added_streams)}, Removed: {len(removed_streams)}")
            
            # Clean up dead streams that are no longer in the playlist
            if self.dead_streams_tracker:
                try:
                    current_stream_urls = {s.get('url', '') for s in streams_after if isinstance(s, dict) and s.get('url')}
                    # Remove empty URLs from the set
                    current_stream_urls.discard('')
                    cleaned_count = self.dead_streams_tracker.cleanup_removed_streams(current_stream_urls)
                    if cleaned_count > 0:
                        logger.info(f"Dead streams cleanup: removed {cleaned_count} stream(s) no longer in playlist")
                except Exception as cleanup_error:
                    logger.error(f"Error during dead streams cleanup: {cleanup_error}")
            
            # Note: Channel marking for stream quality checking is handled in discover_and_assign_streams()
            # after streams are actually assigned to specific channels. This prevents marking all channels
            # when we only know that *some* streams changed in the playlist, not which channels are affected.
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh M3U playlists: {e}")
            
            
            if self.config.get("enabled_features", {}).get("changelog_tracking", True):
                self.changelog.add_entry("playlist_refresh", {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
    def _match_streams_batch(self, streams: List[Dict], channel_streams: Dict[str, set], 
                             dead_stream_removal_enabled: bool,
                             channel_to_allowed_playlists: Dict[str, List[int]],
                             channel_to_revive_enabled: Dict[str, bool] = None,
                             channel_tvg_map: Dict[str, str] = None,
                             channel_to_match_priorities: Dict[str, List[str]] = None) -> Tuple[Dict[str, List[str]], Dict[str, List[Dict]]]:
        """
        Process a batch of streams for regex matching.
        This method is designed to be run in a separate thread.
        
        Args:
            streams: List of stream dictionaries to process
            channel_streams: Dict of existing channel streams {channel_id: {stream_ids}}
            dead_stream_removal_enabled: Whether to skip dead streams
            channel_to_allowed_playlists: Mapping of channel IDs to their allowed playlist names
            channel_to_revive_enabled: Mapping of channel IDs to their Stream Revival setting
            channel_tvg_map: Mapping of channel IDs to their TVG-ID (optional)
            channel_to_match_priorities: Mapping of channel IDs to priority order (optional)
            
        Returns:
            Tuple of (assignments, assignment_details)
        """
        assignments = defaultdict(list)
        assignment_details = defaultdict(list)
        channel_to_revive_enabled = channel_to_revive_enabled or {}
        channel_tvg_map = channel_tvg_map or {}
        channel_to_match_priorities = channel_to_match_priorities or {}
        
        for stream in streams:
            # Validate that stream is a dictionary before accessing attributes
            if not isinstance(stream, dict):
                continue
                
            stream_name = stream.get('name', '')
            stream_id = stream.get('id')
            
            if not stream_name or not stream_id:
                continue
            
            # Get stream's url and m3u_account
            stream_url = stream.get('url', '')
            stream_m3u_account = stream.get('m3u_account')
            
            # Find matching channels (with M3U account filtering if applicable)
            # Pass TVG-ID data for matching
            stream_tvg_id = stream.get('tvg_id')
            matching_channels = self.regex_matcher.match_stream_to_channels(
                stream_name, stream_m3u_account, stream_tvg_id, channel_tvg_map, channel_to_match_priorities
            )
            if not matching_channels:
                continue

            # Check if any matching channel allows reviving dead streams
            any_revive_enabled = False
            for ch_id in matching_channels:
                if channel_to_revive_enabled.get(str(ch_id), False):
                    any_revive_enabled = True
                    break

            # Skip dead streams if removal is enabled globally
            if self.dead_streams_tracker and self.dead_streams_tracker.is_dead(stream_url):
                if dead_stream_removal_enabled:
                    # If any matched channel has Stream Revival enabled, we DON'T skip it, 
                    # even if it's offline. We want it added so the checker can re-evaluate it.
                    if any_revive_enabled:
                        # logger.debug(f"Allowing dead stream {stream_id} for potential revival")
                        pass
                    else:
                        # Revival is disabled for all matching channels - skip ALL dead streams
                        # This prevents the continuous re-addition loop for low quality/failed streams
                        # logger.debug(f"Skipping dead stream {stream_id} (revival disabled)")
                        continue
            
            # Get stream's m3u_account for M3U account filtering
            stream_m3u_account = stream.get('m3u_account')
            
            # Find matching channels (with M3U account filtering if applicable)
            # RegexChannelMatcher is thread-safe for reading patterns
            # Pass TVG-ID data for matching
            stream_tvg_id = stream.get('tvg_id')
            matching_channels = self.regex_matcher.match_stream_to_channels(
                stream_name, stream_m3u_account, stream_tvg_id, channel_tvg_map, channel_to_match_priorities
            )
            
            for channel_id in matching_channels:
                # Profile-level playlist filter for stream matching
                allowed_playlists = channel_to_allowed_playlists.get(channel_id)
                if allowed_playlists is not None and len(allowed_playlists) > 0:
                    if stream_m3u_account is None or stream_m3u_account not in allowed_playlists:
                        # Stream's M3U account not allowed for matching in this channel's profile
                        continue
                # Check if stream is already in this channel
                if channel_id in channel_streams and stream_id not in channel_streams[channel_id]:
                    assignments[channel_id].append(stream_id)
                    assignment_details[channel_id].append({
                        "stream_id": stream_id,
                        "stream_name": stream_name
                    })
                    
        return assignments, assignment_details

    def _validate_channels_batch(self, channels: List[Dict], stream_lookup: Dict[int, Dict], 
                               matching_enabled_channel_ids: List[str],
                               channel_validation_settings: Dict[str, Dict] = None) -> Dict[str, Any]:
        """
        Process a batch of channels for stream validation.
        This method is designed to be run in a separate thread.
        
        Args:
            channels: List of channel dictionaries to process
            stream_lookup: Dict of all streams {stream_id: stream_data}
            matching_enabled_channel_ids: List of channel IDs where matching is enabled
            channel_validation_settings: Dict of channel ID -> validation settings
            
        Returns:
            Dict containing partial validation results
        """
        results = {
            "channels_checked": 0,
            "streams_removed": 0,
            "channels_modified": 0,
            "details": []
        }
        
        udi = get_udi_manager() # Singleton, thread-safe access
        
        if channel_validation_settings is None:
            channel_validation_settings = {}
        
        
        # Build TVG-ID map for validation
        channel_tvg_map = {}
        for ch in channels:
            if isinstance(ch, dict) and ch.get('tvg_id'):
                channel_tvg_map[str(ch.get('id'))] = ch.get('tvg_id')
                
        for channel in channels:
            channel_id = channel.get('id')
            channel_name = channel.get('name', f'Channel {channel_id}')
            
            # Skip channels with matching disabled
            if channel_id not in matching_enabled_channel_ids:
                continue
            
            # Skip channels without matching criteria (no regex AND no TVG-ID matching)
            if not self.regex_matcher.has_regex_patterns(str(channel_id)) and not self.regex_matcher.get_match_by_tvg_id(str(channel_id)):
                continue
            
            results["channels_checked"] += 1
            
            # Get settings for this channel
            settings = channel_validation_settings.get(channel_id, {})
            validate_enabled = settings.get("validate_enabled", False)
            allowed_playlists = settings.get("allowed_playlists", [])
            
            # If validation is disabled for this channel, we skip checking streams
            # UNLESS the caller forced it (which is handled outside this function by checking force flag)
            # But wait, this function returns candidates for removal.
            # If we return candidate removals, the caller decides whether to apply them.
            # So we should probably perform the check regardless? 
            # OR we optimize by skipping if we know we won't apply it.
            # The caller passes `channel_validation_settings`. If the caller invoked this with `force=True`, 
            # they might override the enablement check. 
            # Let's assume this function blindly finds non-matching streams, 
            # BUT we need to respect the playlist filter logic here.
            
            # Optimization: If the caller isn't going to use the result (validation disabled and not forced),
            # we shouldn't waste time. But the caller (impl method) iterates results and checks flags there.
            # To be safe and keep logic simple, we check everything unless explicitly told not to?
            # Actually, `validate_existing_streams` is now per profile. 
            # Unlike global setting (which was forceable), here we have fine-grained control.
            
            # Get streams for this channel
            channel_streams = udi.get_channel_streams(channel_id)
            if not channel_streams:
                continue
            
            streams_to_keep = []
            streams_to_remove = []
            
            for stream in channel_streams:
                if not isinstance(stream, dict) or 'id' not in stream:
                    continue
                
                stream_id = stream['id']
                stream_name_in_channel = stream.get('name', '')
                
                # Look up full stream data to get m3u_account and up-to-date name
                full_stream = stream_lookup.get(stream_id)
                if not full_stream:
                    # Stream not found in UDI, keep it safe
                    streams_to_keep.append(stream_id)
                    continue
                
                stream_name = full_stream.get('name', stream_name_in_channel)
                stream_m3u_account = full_stream.get('m3u_account')
                
                # 1. Check Playlist Validity (if configured)
                # If profile has specific playlists, stream MUST be from one of them
                # This is part of the new "Validate Existing Streams" requirement
                if allowed_playlists and stream_m3u_account not in allowed_playlists:
                    # Stream is from a playlist not in the allowed list for this profile
                    streams_to_remove.append({
                        "id": stream_id,
                        "name": stream_name,
                        "reason": "playlist_mismatch"
                    })
                    continue

                # 2. Check Regex/TVG-ID Validity
                # Check if stream still matches this channel
                stream_tvg_id = full_stream.get('tvg_id')
                matching_channels = self.regex_matcher.match_stream_to_channels(
                    stream_name, stream_m3u_account, stream_tvg_id, channel_tvg_map
                )
                
                if str(channel_id) in matching_channels:
                    streams_to_keep.append(stream_id)
                else:
                    streams_to_remove.append({
                        "id": stream_id, 
                        "name": stream_name,
                        "reason": "regex_mismatch"
                    })
            
            if streams_to_remove:
                results["streams_removed"] += len(streams_to_remove)
                results["channels_modified"] += 1
                results["details"].append({
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "removed_count": len(streams_to_remove),
                    "removed_streams": streams_to_remove,
                    "kept_ids": streams_to_keep
                })
                
        return results

    def discover_and_assign_streams(self, force: bool = False, skip_check_trigger: bool = False) -> Dict[str, int]:
        """Wrapper for stream discovery to ensure single execution."""
        if not self._lock.acquire(blocking=False):
            logger.warning("Stream discovery already active - skipping concurrent request")
            return {}
        
        try:
            return self._discover_and_assign_streams_impl(force, skip_check_trigger)
        finally:
            self._lock.release()

    def _discover_and_assign_streams_impl(self, force: bool = False, skip_check_trigger: bool = False) -> Dict[str, int]:
        """Discover new streams and assign them to channels based on regex patterns.
        
        Args:
            force: If True, bypass the auto_stream_discovery feature flag check.
                   Used for manual/quick action triggers from the UI.
            skip_check_trigger: If True, don't trigger immediate stream quality check.
                   Used when the caller will handle the check itself (e.g., check_single_channel).
        """
        if not force and not self.config.get("enabled_features", {}).get("auto_stream_discovery", True):
            logger.info("Stream discovery is disabled in configuration")
            return {}
        
        try:
            # Reload patterns to ensure we have the latest changes
            self.regex_matcher.reload_patterns()
            
            logger.info("Starting stream discovery and assignment...")
            
            # Get all available streams (don't log, we already logged during refresh)
            from api_utils import get_streams
            all_streams = get_streams(log_result=False)
            if not all_streams:
                logger.warning("No streams found")
                return {}
            
            # Validate that all_streams is a list
            if not isinstance(all_streams, list):
                logger.error(f"Invalid streams response format: expected list, got {type(all_streams).__name__}")
                return {}
            
            # Filter streams by enabled M3U accounts
            # Use cached M3U accounts if available (from refresh_playlists), otherwise fetch
            # This optimization ensures M3U accounts are only queried once per playlist refresh cycle
            if self._m3u_accounts_cache is not None:
                all_accounts = self._m3u_accounts_cache
                logger.debug(f"Using cached M3U accounts from playlist refresh (no UDI/API call - {len(all_accounts) if all_accounts else 0} accounts)")
            else:
                all_accounts = get_m3u_accounts()
                logger.debug(f"Fetched M3U accounts from UDI cache (cache was empty - {len(all_accounts) if all_accounts else 0} accounts)")
            enabled_account_ids = set()
            
            if all_accounts:
                # Filter specific accounts
                non_custom_accounts = [
                    acc for acc in all_accounts
                    if acc.get('is_active', True)
                ]
                
                # Get enabled accounts from config
                enabled_accounts_config = self.config.get("enabled_m3u_accounts", [])
                
                if enabled_accounts_config:
                    # Only include accounts that are in the enabled list
                    enabled_account_ids = set(
                        acc.get('id') for acc in non_custom_accounts 
                        if acc.get('id') in enabled_accounts_config and acc.get('id') is not None
                    )
                else:
                    # If no specific accounts are enabled in config, use all non-custom active accounts
                    enabled_account_ids = set(
                        acc.get('id') for acc in non_custom_accounts 
                        if acc.get('id') is not None
                    )
                
                # Filter streams to only include those from enabled accounts
                # Also include custom streams (is_custom=True) as they don't belong to an M3U account
                filtered_streams = [
                    stream for stream in all_streams
                    if stream.get('is_custom', False) or stream.get('m3u_account') in enabled_account_ids
                ]
                
                streams_filtered_count = len(all_streams) - len(filtered_streams)
                if streams_filtered_count > 0:
                    logger.info(f"Filtered out {streams_filtered_count} streams from disabled/inactive M3U accounts")
                
                all_streams = filtered_streams
                
                if not all_streams:
                    logger.info("No streams found after filtering by enabled M3U accounts")
                    return {}
            else:
                logger.warning("Could not fetch M3U accounts, using all streams")
            
            # Get all channels from UDI
            udi = get_udi_manager()
            all_channels = udi.get_channels()
            if not all_channels:
                logger.warning("No channels found")
                return {}
            
            # Filter by profile if one is selected
            all_channels = self._filter_channels_by_profile(all_channels, "stream assignment")
            
            # Filter channels by automation profile settings
            from automation_config_manager import get_automation_config_manager
            automation_config = get_automation_config_manager()
            matching_enabled_channel_ids = []
            channel_to_allowed_playlists = {}
            channel_to_revive_enabled = {}
            channel_tvg_map = {}
            channel_to_match_priorities = {}
            
            for channel in all_channels:
                if not isinstance(channel, dict) or 'id' not in channel:
                    continue
                channel_id = channel['id']
                channel_tvg_id = channel.get('tvg_id')
                if channel_tvg_id:
                    channel_tvg_map[str(channel_id)] = channel_tvg_id
                
                # Get effective profile
                profile = automation_config.get_effective_profile(channel_id, channel.get('group_id'))
                
                # Check if stream matching is enabled
                matching_enabled = profile and profile.get('stream_matching', {}).get('enabled', False)
                
                # Global Action Override: Include if global action affected is True and force is True
                if force and profile and profile.get('global_action', {}).get('affected', False):
                    matching_enabled = True
                
                if matching_enabled:
                    matching_enabled_channel_ids.append(channel_id)
                    # Store playlist filter for this channel
                    channel_to_allowed_playlists[str(channel_id)] = profile.get('stream_matching', {}).get('playlists', [])
                    # Store match priority order
                    channel_to_match_priorities[str(channel_id)] = profile.get('stream_matching', {}).get('match_priority_order', ['tvg', 'regex'])
                    
                # Check if revive is enabled (needs to be checked even if matching is disabled?)
                # Usually revive only makes sense if we are managing streams for the channel
                if profile and profile.get('stream_checking', {}).get('allow_revive', False):
                    channel_to_revive_enabled[str(channel_id)] = True
            
            # Filter channels to only those with matching enabled
            filtered_channels = [ch for ch in all_channels if ch.get('id') in matching_enabled_channel_ids]
            
            excluded_count = len(all_channels) - len(filtered_channels)
            if excluded_count > 0:
                logger.info(f"Excluding {excluded_count} channel(s) with matching disabled (channel or group level) from stream assignment")
            
            # Use filtered channels for the rest of the logic
            all_channels = filtered_channels
            
            # Exclude channels in active monitoring sessions (coordination with monitoring system)
            from stream_session_manager import get_session_manager
            session_manager = get_session_manager()
            channels_in_monitoring = session_manager.get_channels_in_active_sessions()
            
            if channels_in_monitoring:
                pre_filter_count = len(all_channels)
                all_channels = [ch for ch in all_channels if ch.get('id') not in channels_in_monitoring]
                monitoring_excluded = pre_filter_count - len(all_channels)
                if monitoring_excluded > 0:
                    logger.info(f"⏸ Excluding {monitoring_excluded} channel(s) in active monitoring sessions from stream discovery/assignment")
            
            if not all_channels:
                logger.info("No channels available for stream assignment (all filtered or in monitoring)")
                return {}
            
            # Removed redundant loop that was re-building maps (channel_to_allowed_playlists etc)
            # These maps are already built in the initial channel loop above

            
            # Create a map of existing channel streams
            channel_streams = {}
            channel_names = {}  # Store channel names for changelog
            channel_logo_urls = {}  # Store channel logo URLs for changelog
            for channel in all_channels:
                # Validate that channel is a dictionary
                if not isinstance(channel, dict) or 'id' not in channel:
                    logger.warning(f"Invalid channel format encountered: {type(channel).__name__} - {channel}")
                    continue
                    
                channel_id = str(channel['id'])
                channel_names[channel_id] = channel.get('name', f'Channel {channel_id}')
                
                # Get logo URL for this channel
                logo_id = channel.get('logo_id')
                if logo_id:
                    try:
                        logo = udi.get_logo_by_id(logo_id)
                        if logo and logo.get('cache_url'):
                            channel_logo_urls[channel_id] = logo.get('cache_url')
                    except Exception as e:
                        logger.debug(f"Could not fetch logo for channel {channel_id}: {e}")
                
                # Get streams for this channel from UDI
                streams = udi.get_channel_streams(int(channel_id))
                if streams:
                    valid_stream_ids = set()
                    for s in streams:
                        if isinstance(s, dict) and 'id' in s:
                            valid_stream_ids.add(s['id'])
                        else:
                            logger.warning(f"Invalid stream format in channel {channel_id}: {type(s).__name__} - {s}")
                    channel_streams[channel_id] = valid_stream_ids
                else:
                    channel_streams[channel_id] = set()
            
            assignments = defaultdict(list)
            assignment_details = defaultdict(list)  # Track stream details for changelog
            assignment_count = {}
            
            # Log progress info
            total_streams = len(all_streams)
            # Use parallel processing for faster matching
            # Limit workers to avoid system thrashing and log spam. 
            # 8 workers is a sweet spot for regex CPU bound work on typical systems without causing GIL thrashing.
            max_workers = min(8, os.cpu_count() or 4)
            # Batch size for streams
            batch_size = max(100, total_streams // max_workers)
            
            logger.info(f"Processing {total_streams} streams for pattern matching (Parallel, {max_workers} workers)...")
            
            # Get dead stream removal config once
            dead_stream_removal_enabled = self._is_dead_stream_removal_enabled()
            
            # Create batches
            batches = [all_streams[i:i + batch_size] for i in range(0, total_streams, batch_size)]
            
            completed_count = 0
            last_log_pct = 0
            
            # Process batches in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_batch = {
                    executor.submit(self._match_streams_batch, batch, channel_streams, 
                                   dead_stream_removal_enabled, channel_to_allowed_playlists,
                                   channel_to_revive_enabled, channel_tvg_map, channel_to_match_priorities): batch 
                    for batch in batches
                }
                
                for future in concurrent.futures.as_completed(future_to_batch):
                    try:
                        batch_assignments, batch_details = future.result()
                        
                        # Merge results
                        for channel_id, stream_ids in batch_assignments.items():
                            assignments[channel_id].extend(stream_ids)
                            
                        for channel_id, details in batch_details.items():
                            assignment_details[channel_id].extend(details)
                            
                        completed_count += len(future_to_batch[future])
                        
                        # Log progress monotonically
                        current_pct = int((completed_count / total_streams) * 100)
                        if current_pct >= last_log_pct + 10 or completed_count == total_streams:
                             logger.info(f"  Progress: {completed_count}/{total_streams} streams processed ({current_pct}%)")
                             last_log_pct = current_pct
                             
                    except Exception as e:
                        logger.error(f"Error in stream matching batch: {e}")
            
            logger.info(f"✓ Completed processing {total_streams} streams. Found {sum(len(s) for s in assignments.values())} new stream assignments across {len(assignments)} channels")
            
            # Get channels in active monitoring sessions to handle them separately
            from stream_session_manager import get_session_manager
            session_manager = get_session_manager()
            channels_in_sessions = session_manager.get_channels_in_active_sessions()
            
            if channels_in_sessions:
                logger.info(f"Found {len(channels_in_sessions)} channel(s) in active monitoring sessions - will add streams to sessions instead of direct assignment")
            
            # Prepare detailed changelog data
            detailed_assignments = []
            
            # Get dead stream removal config once for this discovery run
            dead_stream_removal_enabled = self._is_dead_stream_removal_enabled()
            
            # Assign streams to channels
            for channel_id, stream_ids in assignments.items():
                if stream_ids:
                    try:
                        channel_id_int = int(channel_id)
                        
                        # Check if channel is in an active monitoring session
                        if channel_id_int in channels_in_sessions:
                            # Add streams to the active session(s) instead of direct channel assignment
                            logger.info(f"Channel {channel_id} is in an active monitoring session - adding {len(stream_ids)} streams to session(s)")
                            added_to_session = 0
                            
                            # Find all active sessions for this channel
                            active_sessions = [s for s in session_manager.get_active_sessions() if s.channel_id == channel_id_int]
                            
                            for session in active_sessions:
                                for stream_id in stream_ids:
                                    if session_manager.add_stream_to_session(session.session_id, stream_id):
                                        added_to_session += 1
                            
                            if added_to_session > 0:
                                logger.info(f"Added {added_to_session} new streams to monitoring session(s) for channel {channel_id}")
                                assignment_count[channel_id] = added_to_session
                                
                                # Prepare detailed assignment info
                                channel_assignment = {
                                    "channel_id": channel_id,
                                    "channel_name": channel_names.get(channel_id, f'Channel {channel_id}'),
                                    "logo_url": channel_logo_urls.get(channel_id),
                                    "stream_count": added_to_session,
                                    "streams": assignment_details[channel_id][:20],  # Limit to first 20 for changelog
                                    "added_to_session": True
                                }
                                detailed_assignments.append(channel_assignment)
                            continue
                        
                        # Normal channel assignment (not in session)
                        added_count = add_streams_to_channel(channel_id_int, stream_ids, allow_dead_streams=(not dead_stream_removal_enabled))
                        assignment_count[channel_id] = added_count
                        
                        # Verify streams were added correctly (if enabled in config)
                        verify_enabled = self.config.get('verify_stream_assignments', False)
                        if added_count > 0 and verify_enabled:
                            try:
                                time.sleep(0.5)  # Brief delay for API processing
                                # Refresh this specific channel in UDI to get updated data after write
                                udi.refresh_channel_by_id(int(channel_id))
                                updated_channel = udi.get_channel_by_id(int(channel_id))
                                
                                if updated_channel:
                                    updated_stream_ids = set(updated_channel.get('streams', []))
                                    expected_stream_ids = set(stream_ids)
                                    added_stream_ids = expected_stream_ids & updated_stream_ids
                                    
                                    if len(added_stream_ids) == added_count:
                                        logger.info(f"✓ Verified: {added_count} streams successfully added to channel {channel_id} ({channel_names.get(channel_id, f'Channel {channel_id}')})")
                                    else:
                                        logger.warning(f"⚠ Verification mismatch for channel {channel_id}: expected {added_count} streams, found {len(added_stream_ids)} in channel")
                                else:
                                    logger.warning(f"⚠ Could not verify stream addition for channel {channel_id}: channel not found")
                            except Exception as verify_error:
                                logger.warning(f"⚠ Could not verify stream addition for channel {channel_id}: {verify_error}")
                        elif added_count > 0:
                            logger.debug(f"Skipped verification for channel {channel_id} (disabled in config)")
                        
                        # Prepare detailed assignment info
                        channel_assignment = {
                            "channel_id": channel_id,
                            "channel_name": channel_names.get(channel_id, f'Channel {channel_id}'),
                            "logo_url": channel_logo_urls.get(channel_id),
                            "stream_count": added_count,
                            "streams": assignment_details[channel_id][:20],  # Limit to first 20 for changelog
                            "added_to_session": False
                        }
                        detailed_assignments.append(channel_assignment)
                        
                        
                    except Exception as e:
                        logger.error(f"Failed to assign streams to channel {channel_id}: {e}")
            
            # Add comprehensive changelog entry
            total_assigned = sum(assignment_count.values())
            if self.config.get("enabled_features", {}).get("changelog_tracking", True):
                # Limit detailed assignments to prevent oversized changelog entries
                # Sort by stream count (descending) to show the most significant updates
                sorted_assignments = sorted(detailed_assignments, key=lambda x: x['stream_count'], reverse=True)
                max_channels_in_changelog = 50  # Limit to 50 channels to prevent performance issues
                
                self.changelog.add_entry("streams_assigned", {
                    "total_assigned": total_assigned,
                    "channel_count": len(assignment_count),
                    "assignments": sorted_assignments[:max_channels_in_changelog],
                    "has_more_channels": len(sorted_assignments) > max_channels_in_changelog,
                    "timestamp": datetime.now().isoformat()
                })
            
            logger.info(f"Stream discovery completed. Assigned {total_assigned} new streams across {len(assignment_count)} channels")
            
            # Mark channels that received new streams for stream quality checking
            if total_assigned > 0 and assignment_count:
                try:
                    # Get updated stream counts for channels that received new streams
                    channel_ids_to_mark = []
                    stream_counts = {}
                    
                    for channel_id in assignment_count.keys():
                        if assignment_count[channel_id] > 0:
                            channel_ids_to_mark.append(int(channel_id))
                            # Get current stream count from UDI
                            try:
                                channel = udi.get_channel_by_id(int(channel_id))
                                if channel:
                                    streams_list = channel.get('streams', [])
                                    stream_counts[int(channel_id)] = len(streams_list) if isinstance(streams_list, list) else 0
                            except Exception:
                                pass  # If we can't get count, marking will still work
                    
                    # Try to get stream checker service and mark channels
                    if channel_ids_to_mark:
                        try:
                            from stream_checker_service import get_stream_checker_service
                            stream_checker = get_stream_checker_service()
                            stream_checker.update_tracker.mark_channels_updated(channel_ids_to_mark, stream_counts=stream_counts)
                            logger.info(f"Marked {len(channel_ids_to_mark)} channels with new streams for stream quality checking")
                            # Trigger immediate check instead of waiting for scheduled interval
                            # Skip if caller will handle the check (e.g., check_single_channel)
                            if not skip_check_trigger:
                                stream_checker.trigger_check_updated_channels()
                            else:
                                logger.debug("Skipping automatic check trigger (will be handled by caller)")
                        except Exception as sc_error:
                            logger.debug(f"Stream checker not available or error marking channels: {sc_error}")
                except Exception as mark_error:
                    logger.debug(f"Could not mark channels for stream checking after discovery: {mark_error}")
            
            return assignment_count
            
        except Exception as e:
            logger.error(f"Stream discovery failed: {e}")
            if self.config.get("enabled_features", {}).get("changelog_tracking", True):
                self.changelog.add_entry("stream_discovery", {
                    "success": False,
                    "error": str(e)
                })
            return {}
    
    def validate_and_remove_non_matching_streams(self, force: bool = False) -> Dict[str, Any]:
        """
        Validate existing streams in channels against regex patterns.
        Remove streams that no longer match their channel's patterns.
        
        This function respects the automation_controls.remove_non_matching_streams setting
        unless force=True is passed. This ensures consistent behavior across:
        - Automation cycles (step 1.5 in the pipeline)
        - Single channel checks
        - Global actions
        
        Args:
            force: If True, bypass the automation_controls config check.
                   Reserved for future use or special cases where removal must happen
                   regardless of user settings. Default is False to respect user config.
        
        Returns:
            Dict containing validation statistics:
            - channels_checked: Number of channels checked
            - streams_removed: Total streams removed
            - channels_modified: Number of channels that had streams removed
            - details: List of channel details with removed streams
        """
        log_function_call(logger, "validate_and_remove_non_matching_streams")
        
        # Check if removal is enabled in stream checker config (unless forced)
        if not force:
            try:
                from stream_checker_service import get_stream_checker_service
                stream_checker = get_stream_checker_service()
                removal_enabled = stream_checker.config.get('automation_controls', {}).get('remove_non_matching_streams', False)
                
                if not removal_enabled:
                    logger.debug("Stream removal is disabled in automation_controls")
                    return {
                        "channels_checked": 0,
                        "streams_removed": 0,
                        "channels_modified": 0,
                        "details": []
                    }
            except Exception as e:
                logger.warning(f"Could not check stream checker config: {e}, skipping validation")
                return {
                    "channels_checked": 0,
                    "streams_removed": 0,
                    "channels_modified": 0,
                    "details": []
                }
        
        # Lock to prevent concurrent execution
        if not self._lock.acquire(blocking=False):
            logger.warning("Stream validation already active - skipping concurrent request")
            return {
                "channels_checked": 0,
                "streams_removed": 0,
                "channels_modified": 0,
                "details": []
            }
            
        try:
            return self._validate_and_remove_non_matching_streams_impl(force)
        finally:
            self._lock.release()

    def _validate_and_remove_non_matching_streams_impl(self, force: bool = False) -> Dict[str, Any]:
        """Core implementation of stream validation."""
        log_function_call(logger, "validate_and_remove_non_matching_streams")
        try:
            logger.info("=" * 80)
            
            udi = get_udi_manager()
            all_channels = udi.get_channels()
            
            if not all_channels:
                logger.info("No channels found")
                return {
                    "channels_checked": 0,
                    "streams_removed": 0,
                    "channels_modified": 0,
                    "details": []
                }
            
            # Filter by profile if one is selected
            all_channels = self._filter_channels_by_profile(all_channels, "stream validation")
            
            # Filter channels with matching enabled using Automation Profiles
            from automation_config_manager import get_automation_config_manager
            automation_config = get_automation_config_manager()
            
            matching_enabled_channel_ids = []
            for channel in all_channels:
                channel_id = channel.get('id')
                channel_group_id = channel.get('channel_group_id') # Ensure we use correct key for group ID from UDI
                
                # Get effective profile
                profile = automation_config.get_effective_profile(channel_id, channel_group_id)
                
                # Check if stream matching is enabled in the profile
                matching_enabled = profile and profile.get('stream_matching', {}).get('enabled', False)
                
                # Global Action Override: Include if global action affected is True and force is True
                if force and profile and profile.get('global_action', {}).get('affected', False):
                    matching_enabled = True
                    
                if matching_enabled:
                    matching_enabled_channel_ids.append(channel_id)
            
            # Exclude channels in active monitoring sessions (coordination with monitoring system)
            from stream_session_manager import get_session_manager
            session_manager = get_session_manager()
            channels_in_monitoring = session_manager.get_channels_in_active_sessions()
            
            if channels_in_monitoring:
                # Filter out channels in monitoring from matching_enabled list
                pre_filter_count = len(matching_enabled_channel_ids)
                matching_enabled_channel_ids = [ch_id for ch_id in matching_enabled_channel_ids if ch_id not in channels_in_monitoring]
                monitoring_excluded = pre_filter_count - len(matching_enabled_channel_ids)
                if monitoring_excluded > 0:
                    logger.info(f"⏸ Excluding {monitoring_excluded} channel(s) in active monitoring sessions from stream validation")
            
            validation_results = {
                "channels_checked": 0,
                "streams_removed": 0,
                "channels_modified": 0,
                "details": []
            }
            
            # Get dead stream removal setting to pass to update_channel_streams
            # This ensures the setting is respected when validating streams
            dead_stream_removal_enabled = self._is_dead_stream_removal_enabled()
            
            # Get all streams from UDI for lookup
            all_streams = udi.get_streams(log_result=False)
            stream_lookup = {s['id']: s for s in all_streams if isinstance(s, dict) and 'id' in s}
            
            # Parallel validation for faster processing
            # Limit workers to avoid system thrashing.
            max_workers = min(8, os.cpu_count() or 4)
            # Batch size for channels - smaller than streams since per-channel work is heavier
            batch_size = max(20, len(all_channels) // (max_workers * 2))
            
            logger.info(f"Validating {len(all_channels)} channels (Parallel, {max_workers} workers)...")
            
            # Create batches
            batches = [all_channels[i:i + batch_size] for i in range(0, len(all_channels), batch_size)]
            
            completed_count = 0
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_batch = {
                    executor.submit(self._validate_channels_batch, batch, stream_lookup, matching_enabled_channel_ids): batch 
                    for batch in batches
                }
                
                for future in concurrent.futures.as_completed(future_to_batch):
                    try:
                        batch_results = future.result()
                        
                        validation_results["channels_checked"] += batch_results["channels_checked"]
                        
                        # Process results and update UDI if needed
                        for detail in batch_results.get("details", []):
                            channel_id = detail["channel_id"]
                            channel_name = detail["channel_name"]
                            kept_ids = detail["kept_ids"]
                            removed_streams = detail["removed_streams"]
                            
                            # Only apply updates if enabled
                            if dead_stream_removal_enabled or force:
                                try:
                                    from api_utils import update_channel_streams
                                    # Update channel with kept streams
                                    success = update_channel_streams(channel_id, kept_ids, allow_dead_streams=(not dead_stream_removal_enabled))
                                    
                                    if success:
                                        validation_results["streams_removed"] += len(removed_streams)
                                        validation_results["channels_modified"] += 1
                                        validation_results["details"].append(detail)
                                        
                                        logger.info(f"✓ Removed {len(removed_streams)} non-matching stream(s) from {channel_name}")
                                    else:
                                        logger.error(f"Failed to update channel {channel_name} after validation")
                                        
                                except Exception as update_err:
                                    logger.error(f"Failed to update channel {channel_id}: {update_err}")
                            else:
                                if len(removed_streams) > 0:
                                    # Log but don't count as removed since we didn't update
                                    logger.debug(f"Found {len(removed_streams)} non-matching streams in channel {channel_id}, but removal is disabled")
                        
                        completed_count += len(future_to_batch[future])
                        # Log less frequently
                        if completed_count == len(all_channels):
                             logger.info(f"  Validation progress: 100%")
                        elif completed_count % 100 == 0:
                             logger.info(f"  Validation progress: {int(completed_count/len(all_channels)*100)}%")

                    except Exception as e:
                        logger.error(f"Error in channel validation batch: {e}")
            
            logger.info(f"Stream validation completed: Checked {validation_results['channels_checked']} channels, " +
                       f"removed {validation_results['streams_removed']} streams from {validation_results['channels_modified']} channels")
            
            # Add changelog entry if there were changes
            if validation_results['streams_removed'] > 0 and self.config.get("enabled_features", {}).get("changelog_tracking", True):
                self.changelog.add_entry("stream_validation", {
                    "channels_checked": validation_results['channels_checked'],
                    "streams_removed": validation_results['streams_removed'],
                    "channels_modified": validation_results['channels_modified'],
                    "timestamp": datetime.now().isoformat()
                })
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Stream validation failed: {e}", exc_info=True)
            return {
                "channels_checked": 0,
                "streams_removed": 0,
                "channels_modified": 0,
                "details": [],
                "error": str(e)
            }
    
    def should_run_playlist_update(self) -> bool:
        """Check if it's time to run playlist update."""
        if not self.last_playlist_update:
            return True
            
        from automation_config_manager import get_automation_config_manager
        automation_config = get_automation_config_manager()
        settings = automation_config.get_global_settings()
        
        # If automation is globally disabled, we shouldn't run unless manually triggered
        # But this check is usually done in run_automation_cycle.
        
        # We can implement schedule logic here from automation_config if we moved it there.
        # For now, let's keep the legacy cron/interval config from `self.config` which comes from dispatcharr_config/channel_settings?
        # Actually `self.config` seems to be loaded from somewhere else.
        # Let's assume scheduling is still in the main config for now, as we didn't move scheduling to profiles yet.
        
        # Check if cron expression is configured
        cron_expr = self.config.get("playlist_update_cron", "")
        if cron_expr and CRONITER_AVAILABLE:
            try:
                # Use croniter to check if it's time to run
                cron = croniter(cron_expr, self.last_playlist_update)
                next_run = cron.get_next(datetime)
                return datetime.now() >= next_run
            except Exception as e:
                logger.warning(f"Invalid cron expression '{cron_expr}', falling back to interval: {e}")
        
        # Fall back to interval-based scheduling
        schedule = settings.get("playlist_update_interval_minutes", {"type": "interval", "value": 5})
        
        # Handle legacy integer format (defensive)
        if isinstance(schedule, int):
            schedule = {"type": "interval", "value": schedule}
            
        if schedule.get("type") == "cron" and CRONITER_AVAILABLE:
            try:
                cron_expr = schedule.get("value")
                cron = croniter(cron_expr, self.last_playlist_update)
                next_run = cron.get_next(datetime)
                return datetime.now() >= next_run
            except Exception as e:
                logger.warning(f"Invalid cron expression '{schedule.get('value')}', falling back to default interval: {e}")
                interval = timedelta(minutes=5)
        else:
            interval_mins = schedule.get("value", 5)
            interval = timedelta(minutes=interval_mins)
            
        return datetime.now() - self.last_playlist_update >= interval
    
    def run_automation_cycle(self):
        """Run one complete automation cycle with profile support."""
        # Check if forced run
        forced = self.force_next_run
        if forced:
            logger.info("Forcing automation cycle (manual trigger)")
            self.force_next_run = False
            
        # 1. Check Global Automation Switch
        from automation_config_manager import get_automation_config_manager
        automation_config = get_automation_config_manager()
        global_settings = automation_config.get_global_settings()
        
        if not forced and not global_settings.get('regular_automation_enabled', False):
            logger.debug("Regular automation is disabled globally. Skipping cycle.")
            return

        # Check if stream checking mode is active - if so, skip this cycle
        try:
            from stream_checker_service import get_stream_checker_service
            stream_checker = get_stream_checker_service()
            status = stream_checker.get_status()
            if status.get('stream_checking_mode', False) and not forced:
                logger.debug("Stream checking is active. Skipping automation cycle.")
                return
        except Exception as e:
            logger.debug(f"Could not check stream checking mode status: {e}")
        
        # Only log and run if it's actually time to update OR if forced
        if not forced and not self.should_run_playlist_update():
            return
        
        logger.info("Starting automation cycle...")
        
        try:
            # 2. Determine which playlists to update based on ACTIVE profiles
            # Iterate through all channels to find active profiles
            udi = get_udi_manager()
            channels = udi.get_channels()
            active_profile_ids = set()
            
            for channel in channels:
                p_id = automation_config.get_effective_profile_id(channel.get('id'), channel.get('group_id'))
                if p_id:
                    active_profile_ids.add(p_id)
            
            if not active_profile_ids:
                logger.info("No active automation profiles found among channels. Skipping cycle.")
                self.last_playlist_update = datetime.now()
                return
            
            # Determine playlists to update
            playlists_to_update = set()
            update_all_playlists = False
            
            for p_id in active_profile_ids:
                profile = automation_config.get_profile(p_id)
                if not profile: continue
                
                m3u_config = profile.get('m3u_update', {})
                if m3u_config.get('enabled', False):
                    pf_playlists = m3u_config.get('playlists', [])
                    if not pf_playlists:
                        # Empty list usually implies ALL playlists in this context?
                        # Or if we want to be strict: empty means none.
                        # Given the requirement "Elegir qué playlists", empty likely means "All" or "Default behavior".
                        # Let's assume empty list = ALL for safety to match legacy behavior where we updated everything.
                        update_all_playlists = True
                    else:
                        playlists_to_update.update(pf_playlists)
            
            # 3. Update Playlists
            success = False
            if update_all_playlists:
                logger.info("Updating ALL playlists (requested by one or more profiles)")
                success = self.refresh_playlists(account_id=None)
            elif playlists_to_update:
                logger.info(f"Updating {len(playlists_to_update)} specific playlists: {playlists_to_update}")
                # We need to map playlist names/IDs. The profile likely stores IDs.
                # refresh_playlists takes account_id.
                success = True
                for acc_id in playlists_to_update:
                    if not self.refresh_playlists(account_id=int(acc_id)):
                        success = False
            else:
                logger.info("No playlists to update based on active profile settings.")
                # Update timestamp to prevent immediate re-execution in the next loop
                self.last_playlist_update = datetime.now()
                success = True # Treat as success so we continue to matching (maybe local matching?)
            
            if success:
                # Small delay to allow playlist processing
                time.sleep(10)
                
                # 4. Stream Matching (Validation & Assignment)
                # We pass the automation_config to these methods or they fetch it internally.
                # But they iterate channels anyway, so they can check per-channel profile.
                
                # Validate existing streams
                try:
                    validation_results = self.validate_and_remove_non_matching_streams()
                    if validation_results.get("streams_removed", 0) > 0:
                        logger.info(f"✓ Removed {validation_results['streams_removed']} non-matching streams")
                except Exception as e:
                    logger.error(f"✗ Failed to validate streams: {e}")
                
                # Discover and assign new streams
                assignments = self.discover_and_assign_streams()
            
            logger.info("Automation cycle completed")
            
        finally:
            self._m3u_accounts_cache = None

    def _filter_channels_by_profile(self, channels: List[Dict], operation: str = "") -> List[Dict]:
        """
        Filter channels based on their effective profile settings.
        Deprecated: Logic moved into specific methods (validation/assignment) to handle per-channel profiles.
        This helper returns all channels to avoid breaking legacy callers if any.
        """
        return channels
        
    def trigger_automation(self):
        """Manually trigger an automation cycle."""
        logger.info("Triggering manual automation cycle")
        self.force_next_run = True
        if self.automation_thread and self.automation_thread.is_alive():
            self.automation_wake_event.set()
        else:
            # If not running, we could potentially run it synchronously or just log warning.
            # But the requirement is likely to trigger the *service*.
            logger.warning("Automation service not running, manual trigger queueing for next run or ignored")
            
    def start_automation(self):
        """Start the automation background thread."""
        if self.automation_thread and self.automation_thread.is_alive():
            logger.info("Automation service already running")
            return
            
        logger.info("Starting automation service...")
        self.automation_running = True
        self.automation_wake_event.clear()
        self.automation_thread = threading.Thread(target=self._automation_loop, daemon=True)
        self.automation_thread.start()
        logger.info("Automation service started")
        
    def stop_automation(self):
        """Stop the automation background thread."""
        logger.info("Stopping automation service...")
        self.automation_running = False
        self.automation_wake_event.set()  # Wake up thread to exit
        
        if self.automation_thread:
            self.automation_thread.join(timeout=5)
            logger.info("Automation service stopped")
            
    def _automation_loop(self):
        """Main loop for automation service."""
        logger.info("Automation background loop started")
        while self.automation_running:
            try:
                # Run automation cycle
                self.run_automation_cycle()
                
            except Exception as e:
                logger.error(f"Error in automation loop: {e}", exc_info=True)
            
            # Sleep interval (e.g. 60 seconds)
            # We use wait() on the event to allow early wake-up/exit
            if self.automation_running:
                # Loop interval can be configured, default to 60s for responsiveness to schedule changes
                self.automation_wake_event.wait(timeout=60)
                if self.automation_wake_event.is_set() and not self.automation_running:
                    break
                self.automation_wake_event.clear()
        
        logger.info("Automation background loop stopped")