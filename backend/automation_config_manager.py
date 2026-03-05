#!/usr/bin/env python3
"""
Automation Configuration Manager

Manages Automation Profiles and Global Automation Settings.
Stores configuration in automation_config.json.
"""

import json
import os
import threading
import uuid
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from threading import RLock

from logging_config import setup_logging

logger = setup_logging(__name__)

# Configuration directory
CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', '/app/data'))
AUTOMATION_CONFIG_FILE = CONFIG_DIR / 'automation_config.json'

class AutomationConfigManager:
    """
    Manages Automation Profiles and Settings.
    """
    
    def __init__(self):
        # Check and migrate legacy configuration before initializing
        try:
            from config_migrator import check_and_migrate_legacy_config
            if check_and_migrate_legacy_config():
                logger.info("Legacy configuration migrated to new profile-based system")
        except ImportError:
            logger.warning("config_migrator not available - skipping migration check")
        except Exception as e:
            logger.error(f"Error during migration check: {e}", exc_info=True)
        
        self._lock = RLock()
        self._config = {
            "regular_automation_enabled": False,
            "playlist_update_interval_minutes": {"type": "interval", "value": 5},
            "profiles": {},  # ID -> Profile Dict
            "channel_assignments": {},  # Channel ID -> Profile ID (legacy, kept for backward compatibility)
            "group_assignments": {},     # Group ID -> Profile ID (legacy, kept for backward compatibility)
            "automation_periods": {},    # Period ID -> Period Dict (name, schedule) - NO profile_id
            "channel_period_assignments": {}  # Channel ID -> Dict of {Period ID: Profile ID}
        }
        self._load_config()
        
    def _load_config(self):
        """Load configuration from file."""
        with self._lock:
            try:
                if AUTOMATION_CONFIG_FILE.exists():
                    with open(AUTOMATION_CONFIG_FILE, 'r') as f:
                        data = json.load(f)
                        # Ensure structure
                        self._config.update(data)
                        
                        # Convert integer keys in assignments back to integers if JSON stringified them
                        if "channel_assignments" in self._config:
                            self._config["channel_assignments"] = {int(k): v for k, v in self._config["channel_assignments"].items()}
                        if "group_assignments" in self._config:
                            self._config["group_assignments"] = {int(k): v for k, v in self._config["group_assignments"].items()}
                        if "channel_period_assignments" in self._config:
                            self._config["channel_period_assignments"] = {int(k): v for k, v in self._config["channel_period_assignments"].items()}
                        
                        # Ensure new fields exist
                        if "automation_periods" not in self._config:
                            self._config["automation_periods"] = {}
                        if "channel_period_assignments" not in self._config:
                            self._config["channel_period_assignments"] = {}
                        
                        logger.info(
                            f"Loaded {len(self._config.get('profiles', {}))} automation profiles "
                            f"and {len(self._config.get('automation_periods', {}))} automation periods"
                        )
                else:
                    logger.info("No automation config found, initializing defaults")
                    self._create_default_profile()
                    self._save_config()
            except Exception as e:
                logger.error(f"Error loading automation config: {e}", exc_info=True)
                # Fallback to defaults if load fails
                self._create_default_profile()

    def _save_config(self) -> bool:
        """Save configuration to file."""
        with self._lock:
            try:
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                # Convert integer keys to strings for JSON
                data_to_save = self._config.copy()
                data_to_save["channel_assignments"] = {str(k): v for k, v in self._config["channel_assignments"].items()}
                data_to_save["group_assignments"] = {str(k): v for k, v in self._config["group_assignments"].items()}
                data_to_save["channel_period_assignments"] = {str(k): v for k, v in self._config["channel_period_assignments"].items()}
                
                with open(AUTOMATION_CONFIG_FILE, 'w') as f:
                    json.dump(data_to_save, f, indent=2)
                return True
            except Exception as e:
                logger.error(f"Error saving automation config: {e}", exc_info=True)
                return False

    def _create_default_profile(self):
        """Creates a default profile if none exists."""
        default_id = "default"
        if default_id not in self._config["profiles"]:
            self._config["profiles"][default_id] = {
                "id": default_id,
                "name": "Default Profile",
                "description": "Default automation settings",
                "m3u_update": {
                    "enabled": True,
                    "playlists": []
                },
                "stream_matching": {
                    "enabled": True,
                    "validate_existing_streams": False
                },
                "stream_checking": {
                    "enabled": True,
                    "allow_revive": False,
                    "check_all_streams": False,
                    "stream_limit": 0,
                    "min_resolution": None,
                    "min_fps": 0,
                    "min_bitrate": 0,
                    "require_hdr": "any",
                    "m3u_priority": [],
                    "m3u_priority_mode": "absolute",
                    "grace_period": False
                },
                "scoring_weights": {
                    "bitrate": 0.35,
                    "resolution": 0.30,
                    "fps": 0.15,
                    "codec": 0.10,
                    "hdr": 0.10,
                    "prefer_h265": True
                }
            }
            logger.info("Created default automation profile")

    # --- Global Settings ---

    def get_global_settings(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "regular_automation_enabled": self._config.get("regular_automation_enabled", False),
                "playlist_update_interval_minutes": self._config.get("playlist_update_interval_minutes", {"type": "interval", "value": 5}),
                "validate_existing_streams": self._config.get("validate_existing_streams", False)
            }

    def update_global_settings(self, regular_automation_enabled: Optional[bool] = None, settings: Dict[str, Any] = None) -> bool:
        """Update global automation settings."""
        with self._lock:
            changed = False
            updates = settings or {}
            if isinstance(regular_automation_enabled, dict):
                updates.update(regular_automation_enabled)
                regular_automation_enabled = None
            
            if regular_automation_enabled is not None:
                updates["regular_automation_enabled"] = regular_automation_enabled
                
            if "regular_automation_enabled" in updates:
                self._config["regular_automation_enabled"] = bool(updates["regular_automation_enabled"])
                changed = True
            
            if "validate_existing_streams" in updates:
                self._config["validate_existing_streams"] = bool(updates["validate_existing_streams"])
                changed = True

            if "playlist_update_interval_minutes" in updates:
                new_val = updates["playlist_update_interval_minutes"]
                if isinstance(new_val, int):
                    self._config["playlist_update_interval_minutes"] = {"type": "interval", "value": new_val}
                else:
                    self._config["playlist_update_interval_minutes"] = new_val
                changed = True

            if changed:
                return self._save_config()
            return True

    # --- Profile Management ---

    def get_all_profiles(self) -> List[Dict]:
        with self._lock:
            return list(self._config["profiles"].values())

    def get_profile(self, profile_id: str) -> Optional[Dict]:
        with self._lock:
            return self._config["profiles"].get(str(profile_id))

    def create_profile(self, profile_data: Dict) -> Optional[str]:
        """Create a new profile."""
        with self._lock:
            profile_id = str(uuid.uuid4())
            new_profile = {
                "id": profile_id,
                "name": profile_data.get("name", "New Profile"),
                "description": profile_data.get("description", ""),
                "m3u_update": profile_data.get("m3u_update", {"enabled": False, "playlists": []}),
                "stream_matching": profile_data.get("stream_matching", {
                    "enabled": False, 
                    "validate_existing_streams": False
                }),
                "stream_checking": profile_data.get("stream_checking", {
                    "enabled": False, 
                    "allow_revive": False,
                    "check_all_streams": False,
                    "stream_limit": 0,
                    "min_resolution": None,
                    "min_fps": 0,
                    "min_bitrate": 0,
                    "m3u_priority": [],
                    "grace_period": False
                }),
                "scoring_weights": profile_data.get("scoring_weights", {
                    "bitrate": 0.40,
                    "resolution": 0.35,
                    "fps": 0.15,
                    "codec": 0.10,
                    "prefer_h265": True
                })
            }
            self._config["profiles"][profile_id] = new_profile
            if self._save_config():
                return profile_id
            return None

    def update_profile(self, profile_id: str, profile_data: Dict) -> bool:
        with self._lock:
            pid = str(profile_id)
            if pid not in self._config["profiles"]:
                return False
            
            current = self._config["profiles"][pid]
            
            if "name" in profile_data:
                current["name"] = profile_data["name"]
            if "description" in profile_data:
                current["description"] = profile_data["description"]
                
            if "m3u_update" in profile_data:
                current["m3u_update"] = profile_data["m3u_update"]
            if "stream_matching" in profile_data:
                current["stream_matching"] = profile_data["stream_matching"]
            if "stream_checking" in profile_data:
                current["stream_checking"] = profile_data["stream_checking"]
            if "scoring_weights" in profile_data:
                current["scoring_weights"] = profile_data["scoring_weights"]
            
            return self._save_config()

    def delete_profile(self, profile_id: str) -> bool:
        with self._lock:
            pid = str(profile_id)
            if pid not in self._config["profiles"]:
                return False
            
            channels_to_update = [c for c, p in self._config["channel_assignments"].items() if p == pid]
            for c in channels_to_update:
                del self._config["channel_assignments"][c]
                
            groups_to_update = [g for g, p in self._config["group_assignments"].items() if p == pid]
            for g in groups_to_update:
                del self._config["group_assignments"][g]
            
            # Also clean up channel_period_assignments - remove references to the deleted profile
            for channel_id in list(self._config["channel_period_assignments"].keys()):
                period_assignments = self._config["channel_period_assignments"][channel_id]
                if isinstance(period_assignments, dict):
                    # Remove any period entries that point to the deleted profile
                    periods_to_remove = [period_id for period_id, prof_id in period_assignments.items() if prof_id == pid]
                    for period_id in periods_to_remove:
                        del period_assignments[period_id]
                    # Remove the channel entry entirely if no periods left
                    if not period_assignments:
                        del self._config["channel_period_assignments"][channel_id]
            
            del self._config["profiles"][pid]
            logger.info(f"Deleted profile {pid} and cleaned up all assignments")
            return self._save_config()

    # --- Assignments ---

    def assign_profile_to_channel(self, channel_id: int, profile_id: Optional[str]) -> bool:
        with self._lock:
            cid = int(channel_id)
            if profile_id is None:
                if cid in self._config["channel_assignments"]:
                    del self._config["channel_assignments"][cid]
                else:
                    return True
            else:
                if profile_id not in self._config["profiles"]:
                    return False
                self._config["channel_assignments"][cid] = profile_id
            return self._save_config()

    def assign_profile_to_channels(self, channel_ids: List[int], profile_id: Optional[str]) -> bool:
        with self._lock:
            if profile_id and profile_id not in self._config["profiles"]:
                return False
            
            changes_made = False
            for cid_raw in channel_ids:
                cid = int(cid_raw)
                if profile_id is None:
                    if cid in self._config["channel_assignments"]:
                        del self._config["channel_assignments"][cid]
                        changes_made = True
                else:
                    if self._config["channel_assignments"].get(cid) != profile_id:
                        self._config["channel_assignments"][cid] = profile_id
                        changes_made = True
            
            if changes_made:
                return self._save_config()
            return True

    def assign_profile_to_group(self, group_id: int, profile_id: Optional[str]) -> bool:
        with self._lock:
            gid = int(group_id)
            if profile_id is None:
                if gid in self._config["group_assignments"]:
                    del self._config["group_assignments"][gid]
            else:
                if profile_id not in self._config["profiles"]:
                    return False
                self._config["group_assignments"][gid] = profile_id
            return self._save_config()
            
    def get_channel_assignment(self, channel_id: int) -> Optional[str]:
        return self._config["channel_assignments"].get(int(channel_id))

    def get_group_assignment(self, group_id: int) -> Optional[str]:
        return self._config["group_assignments"].get(int(group_id))

    def get_effective_profile_id(self, channel_id: int, group_id: Optional[int] = None) -> Optional[str]:
        with self._lock:
            if int(channel_id) in self._config["channel_assignments"]:
                return self._config["channel_assignments"][int(channel_id)]
            if group_id is not None and int(group_id) in self._config["group_assignments"]:
                return self._config["group_assignments"][int(group_id)]
            return None

    def get_effective_profile(self, channel_id: int, group_id: Optional[int] = None) -> Optional[Dict]:
        pid = self.get_effective_profile_id(channel_id, group_id)
        if pid:
            return self.get_profile(pid)
        return None

    # --- Automation Periods Management ---

    def get_all_periods(self) -> List[Dict]:
        """Get all automation periods."""
        with self._lock:
            return list(self._config["automation_periods"].values())

    def get_period(self, period_id: str) -> Optional[Dict]:
        """Get a specific automation period by ID."""
        with self._lock:
            return self._config["automation_periods"].get(str(period_id))

    def create_period(self, period_data: Dict) -> Optional[str]:
        """Create a new automation period.
        
        Args:
            period_data: Dict with keys: name, schedule
                schedule format: {"type": "interval"/"cron", "value": int/"cron_expr"}
                Note: profile_id is NOT stored in the period, it's per-channel
        
        Returns:
            Period ID if successful, None otherwise
        """
        with self._lock:
            period_id = str(uuid.uuid4())
            new_period = {
                "id": period_id,
                "name": period_data.get("name", "New Period"),
                "schedule": period_data.get("schedule", {"type": "interval", "value": 60}),
                "priority": int(period_data.get("priority", 0))
            }
            self._config["automation_periods"][period_id] = new_period
            if self._save_config():
                logger.info(f"Created automation period: {period_id} - {new_period['name']}")
                self._invalidate_events_cache()
                return period_id
            return None

    def update_period(self, period_id: str, period_data: Dict) -> bool:
        """Update an existing automation period."""
        with self._lock:
            pid = str(period_id)
            if pid not in self._config["automation_periods"]:
                logger.error(f"Period {pid} not found")
                return False
            
            current = self._config["automation_periods"][pid]
            
            if "name" in period_data:
                current["name"] = period_data["name"]
            if "schedule" in period_data:
                current["schedule"] = period_data["schedule"]
            if "priority" in period_data:
                current["priority"] = int(period_data["priority"])
            # Note: profile_id is no longer stored in periods, it's per-channel
            
            logger.info(f"Updated automation period: {pid}")
            result = self._save_config()
            if result:
                self._invalidate_events_cache()
            return result

    def delete_period(self, period_id: str) -> bool:
        """Delete an automation period and remove all channel assignments."""
        with self._lock:
            pid = str(period_id)
            if pid not in self._config["automation_periods"]:
                logger.error(f"Period {pid} not found")
                return False
            
            # Remove from all channel assignments
            for channel_id in list(self._config["channel_period_assignments"].keys()):
                period_assignments = self._config["channel_period_assignments"][channel_id]
                if isinstance(period_assignments, dict) and pid in period_assignments:
                    del period_assignments[pid]
                    if not period_assignments:  # Remove channel entry if no periods left
                        del self._config["channel_period_assignments"][channel_id]
                elif isinstance(period_assignments, list) and pid in period_assignments:
                    # Handle old format for backwards compatibility
                    period_assignments.remove(pid)
                    if not period_assignments:
                        del self._config["channel_period_assignments"][channel_id]
            
            del self._config["automation_periods"][pid]
            logger.info(f"Deleted automation period: {pid}")
            result = self._save_config()
            if result:
                self._invalidate_events_cache()
            return result

    # --- Period-Channel Assignments ---

    def assign_period_to_channels(self, period_id: str, channel_ids: List[int], profile_id: str, replace: bool = False) -> bool:
        """Assign an automation period to multiple channels with a specific profile.
        
        Args:
            period_id: ID of the period to assign
            channel_ids: List of channel IDs
            profile_id: ID of the profile to use for this period on these channels
            replace: If True, replace all existing periods for these channels. If False, add to existing.
        
        Returns:
            True if successful
        """
        with self._lock:
            pid = str(period_id)
            if pid not in self._config["automation_periods"]:
                logger.error(f"Period {pid} not found")
                return False
            
            # Validate profile exists
            if profile_id not in self._config["profiles"]:
                logger.error(f"Profile {profile_id} not found")
                return False
            
            changes_made = False
            for cid_raw in channel_ids:
                cid = int(cid_raw)
                
                if replace:
                    # Replace all periods for this channel
                    self._config["channel_period_assignments"][cid] = {pid: profile_id}
                    changes_made = True
                else:
                    # Add to existing periods (or create new dict)
                    if cid not in self._config["channel_period_assignments"]:
                        self._config["channel_period_assignments"][cid] = {}
                    elif isinstance(self._config["channel_period_assignments"][cid], list):
                        # Migrate old list format to new dict format
                        self._config["channel_period_assignments"][cid] = {}
                    
                    # Add/update the period-profile mapping
                    self._config["channel_period_assignments"][cid][pid] = profile_id
                    changes_made = True
            
            if changes_made:
                logger.info(f"Assigned period {pid} with profile {profile_id} to {len(channel_ids)} channels")
                result = self._save_config()
                if result:
                    self._invalidate_events_cache()
                return result
            return True

    def remove_period_from_channels(self, period_id: str, channel_ids: List[int]) -> bool:
        """Remove a period assignment from specific channels."""
        with self._lock:
            pid = str(period_id)
            changes_made = False
            
            for cid_raw in channel_ids:
                cid = int(cid_raw)
                if cid in self._config["channel_period_assignments"]:
                    period_assignments = self._config["channel_period_assignments"][cid]
                    if isinstance(period_assignments, dict) and pid in period_assignments:
                        del period_assignments[pid]
                        changes_made = True
                        if not period_assignments:  # Remove channel entry if no periods left
                            del self._config["channel_period_assignments"][cid]
                    elif isinstance(period_assignments, list) and pid in period_assignments:
                        # Handle old format
                        period_assignments.remove(pid)
                        changes_made = True
                        if not period_assignments:
                            del self._config["channel_period_assignments"][cid]
            
            if changes_made:
                logger.info(f"Removed period {pid} from {len(channel_ids)} channels")
                result = self._save_config()
                if result:
                    self._invalidate_events_cache()
                return result
            return True

    def get_channel_periods(self, channel_id: int) -> Dict[str, str]:
        """Get dict of period IDs to profile IDs assigned to a channel.
        
        Returns:
            Dict mapping period_id -> profile_id
        """
        with self._lock:
            assignments = self._config["channel_period_assignments"].get(int(channel_id), {})
            if isinstance(assignments, dict):
                return assignments.copy()
            elif isinstance(assignments, list):
                # Old format - log warning and return empty dict (requires manual reassignment)
                logger.warning(f"Channel {channel_id} has old-format period assignments - manual reassignment required")
                return {}
            return {}

    def get_period_channels(self, period_id: str) -> List[int]:
        """Get list of channel IDs assigned to a period."""
        with self._lock:
            pid = str(period_id)
            channels = []
            for channel_id, period_assignments in self._config["channel_period_assignments"].items():
                if isinstance(period_assignments, dict) and pid in period_assignments:
                    channels.append(channel_id)
                elif isinstance(period_assignments, list) and pid in period_assignments:
                    # Handle old format
                    channels.append(channel_id)
            return channels

    def is_period_active_now(self, period_id: str) -> bool:
        """Check if a period's schedule is currently active.
        
        Args:
            period_id: The period ID to check
            
        Returns:
            True if the period should be running right now based on its schedule
        """
        period = self.get_period(period_id)
        if not period:
            return False
        
        schedule = period.get("schedule", {})
        schedule_type = schedule.get("type", "interval")
        
        if schedule_type == "cron":
            # For cron schedules, we consider them "always active" - the cron determines WHEN to run
            # The actual checking of "should we run now" is done by the scheduler
            return True
        elif schedule_type == "interval":
            # For interval schedules, they're also always active
            # The interval just determines how often to run
            return True
        
        return False

    def get_active_periods_for_channel(self, channel_id: int) -> List[Dict]:
        """Get all active automation periods for a channel.
        
        Returns list of period dicts with full details including the profile for that channel.
        """
        with self._lock:
            period_to_profile = self.get_channel_periods(channel_id)  # Now returns dict
            active_periods = []
            
            for pid, profile_id in period_to_profile.items():
                period = self.get_period(pid)
                if period and self.is_period_active_now(pid):
                    # Add the full profile data to the period (channel-specific profile)
                    period_with_profile = period.copy()
                    if profile_id:
                        period_with_profile["profile"] = self.get_profile(profile_id)
                        period_with_profile["profile_id"] = profile_id
                    else:
                        period_with_profile["profile"] = None
                        period_with_profile["profile_id"] = None
                    active_periods.append(period_with_profile)
            
            return active_periods

    def get_effective_configuration(self, channel_id: int, group_id: Optional[int] = None) -> Optional[Dict]:
        """Get the effective automation configuration for a channel.
        
        Only channels with automation periods assigned will participate in automation.
        Legacy profile assignments are ignored.
        
        Returns:
            Dict with 'source' ('period'), 'periods' (list of periods), 'period_id', 'period_name', and 'profile' (the profile dict), or None
        """
        with self._lock:
            # Only use automation periods - legacy profile assignments are ignored
            active_periods = self.get_active_periods_for_channel(channel_id)
            if active_periods:
                # If there are multiple active periods, sort them by priority (descending) 
                # then by ID (ascending) to guarantee deterministic resolution
                if len(active_periods) > 1:
                    active_periods.sort(key=lambda p: (-int(p.get('priority', 0)), p.get('id', '')))
                    logger.warning(
                        f"Channel {channel_id} triggered by {len(active_periods)} overlapping periods. "
                        f"Defaulting to highest priority period: {active_periods[0].get('name')} (Priority: {active_periods[0].get('priority', 0)})"
                    )

                # Use the highest priority active period's profile
                period = active_periods[0]
                profile = period.get('profile')
                if profile:
                    return {
                        'source': 'period',
                        'periods': active_periods,
                        'period_id': period.get('id'),
                        'period_name': period.get('name'),
                        'profile': profile
                    }
            
            # No automation periods assigned - channel does not participate in automation
            return None
    
    def _invalidate_events_cache(self):
        """Invalidate the automation events cache when periods are modified."""
        try:
            from automation_events_scheduler import get_events_scheduler
            scheduler = get_events_scheduler()
            scheduler.invalidate_cache()
            logger.debug("Invalidated automation events cache")
        except Exception as e:
            logger.warning(f"Failed to invalidate events cache: {e}")

# Singleton instance
_automation_config_manager = None
_manager_lock = threading.Lock()

def get_automation_config_manager() -> AutomationConfigManager:
    global _automation_config_manager
    if _automation_config_manager is None:
        with _manager_lock:
            if _automation_config_manager is None:
                _automation_config_manager = AutomationConfigManager()
    return _automation_config_manager
