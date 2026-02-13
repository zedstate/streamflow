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
            "global_action_enabled": False,
            "playlist_update_interval_minutes": {"type": "interval", "value": 5},
            "global_schedule": {"type": "interval", "value": 60},
            "profiles": {},  # ID -> Profile Dict
            "channel_assignments": {},  # Channel ID -> Profile ID
            "group_assignments": {}     # Group ID -> Profile ID
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
                            
                        logger.info(f"Loaded {len(self._config.get('profiles', {}))} automation profiles")
                        self._sync_global_action_state(save=False)
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
                    "playlists": []  # Empty means all? Or specific? Requirement says "Elegir qué playlists"
                },
                "stream_matching": {
                    "enabled": True,
                    "validate_existing_streams": False,
                    "playlists": [], # Empty means all
                    "match_priority_order": ["tvg", "regex"]
                },
                "stream_checking": {
                    "enabled": True,
                    "allow_revive": False,
                    "check_all_streams": False,  # Check all streams in channel vs only matched ones
                    "stream_limit": 0,  # 0 = unlimited
                    "min_resolution": None,
                    "min_fps": 0,
                    "min_bitrate": 0,
                    "require_hdr": "any",  # any, hdr10, or hdr10+ (hdr10 also accepts hdr10+)
                    "m3u_priority": [],
                    "m3u_priority_mode": "absolute",  # absolute or same_resolution
                    "grace_period": False
                },
                "scoring_weights": {
                    "bitrate": 0.35,
                    "resolution": 0.30,
                    "fps": 0.15,
                    "codec": 0.10,
                    "hdr": 0.10,
                    "prefer_h265": True
                },
                "global_action": {
                    "affected": True
                }
            }
            logger.info("Created default automation profile")

    # --- Global Settings ---

    def get_global_settings(self) -> Dict[str, bool]:
        with self._lock:
            return {
                "regular_automation_enabled": self._config.get("regular_automation_enabled", False),
                "global_action_enabled": self._config.get("global_action_enabled", False),
                "playlist_update_interval_minutes": self._config.get("playlist_update_interval_minutes", {"type": "interval", "value": 5}),
                "validate_existing_streams": self._config.get("validate_existing_streams", False),
                "global_schedule": self._config.get("global_schedule", {"type": "interval", "value": 60}) # Default 60 minutes
            }

    def update_global_settings(self, regular_automation_enabled: Optional[bool] = None, global_action_enabled: Optional[bool] = None, settings: Dict[str, Any] = None) -> bool:
        """Update global automation settings.
        
        Args:
            regular_automation_enabled: (Optional) Legacy arg
            global_action_enabled: (Optional) Legacy arg
            settings: Dictionary of settings to update (preferred)
        """
        with self._lock:
            changed = False
            
            # Helper to update from dict or args
            # Robustness check: if regular_automation_enabled is a dict, it was likely passed 
            # as a positional argument from web_api.py (common bug pattern)
            updates = settings or {}
            if isinstance(regular_automation_enabled, dict):
                updates.update(regular_automation_enabled)
                regular_automation_enabled = None
            
            
            # Map legacy args to updates dict if provided
            if regular_automation_enabled is not None:
                updates["regular_automation_enabled"] = regular_automation_enabled
            if global_action_enabled is not None:
                updates["global_action_enabled"] = global_action_enabled
                
            # Process updates
            if "regular_automation_enabled" in updates:
                self._config["regular_automation_enabled"] = bool(updates["regular_automation_enabled"])
                changed = True
            
            if "global_action_enabled" in updates:
                self._config["global_action_enabled"] = bool(updates["global_action_enabled"])
                changed = True
                
            if "validate_existing_streams" in updates:
                self._config["validate_existing_streams"] = bool(updates["validate_existing_streams"])
                changed = True

            if "playlist_update_interval_minutes" in updates:
                new_val = updates["playlist_update_interval_minutes"]
                # Handle legacy integer format
                if isinstance(new_val, int):
                    self._config["playlist_update_interval_minutes"] = {"type": "interval", "value": new_val}
                else:
                    self._config["playlist_update_interval_minutes"] = new_val
                changed = True

            if "global_schedule" in updates:
                self._config["global_schedule"] = updates["global_schedule"]
                changed = True
            
            if changed:
                return self._save_config()
            return True

    def _sync_global_action_state(self, save: bool = True) -> bool:
        """
        Synchronize the global_action_enabled master switch based on profiles.
        If any profile has global_action.affected == True, enable the master switch.
        """
        with self._lock:
            any_affected = False
            for profile in self._config["profiles"].values():
                if profile.get("global_action", {}).get("affected", False):
                    any_affected = True
                    break
            
            old_state = self._config.get("global_action_enabled", False)
            self._config["global_action_enabled"] = any_affected
            
            if old_state != any_affected:
                logger.info(f"Global action master switch automatically turned {'ON' if any_affected else 'OFF'}")
                if save:
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
        """
        Create a new profile.
        profile_data should contain name, description, and settings.
        ID is auto-generated.
        """
        with self._lock:
            profile_id = str(uuid.uuid4())
            new_profile = {
                "id": profile_id,
                "name": profile_data.get("name", "New Profile"),
                "description": profile_data.get("description", ""),
                "m3u_update": profile_data.get("m3u_update", {"enabled": False, "playlists": []}),
                "stream_matching": profile_data.get("stream_matching", {
                    "enabled": False, 
                    "playlists": [], 
                    "validate_existing_streams": False,
                    "match_priority_order": ["tvg", "regex"]
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
                }),
                "global_action": profile_data.get("global_action", {"affected": True})
            }
            self._config["profiles"][profile_id] = new_profile
            self._sync_global_action_state(save=False)
            if self._save_config():
                return profile_id
            return None

    def update_profile(self, profile_id: str, profile_data: Dict) -> bool:
        with self._lock:
            pid = str(profile_id)
            if pid not in self._config["profiles"]:
                return False
            
            # Update fields deeply if needed, or just replace sections
            # specific merge logic to ensure we don't wipe existing keys if partial data sent
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
            if "global_action" in profile_data:
                current["global_action"] = profile_data["global_action"]
            
            self._sync_global_action_state(save=False)
            return self._save_config()

    def delete_profile(self, profile_id: str) -> bool:
        with self._lock:
            pid = str(profile_id)
            if pid not in self._config["profiles"]:
                return False
            
            # Remove assignments
            # List channels assigned to this profile
            channels_to_update = [c for c, p in self._config["channel_assignments"].items() if p == pid]
            for c in channels_to_update:
                del self._config["channel_assignments"][c]
                
            groups_to_update = [g for g, p in self._config["group_assignments"].items() if p == pid]
            for g in groups_to_update:
                del self._config["group_assignments"][g]
            
            del self._config["profiles"][pid]
            self._sync_global_action_state(save=False)
            return self._save_config()

    # --- Assignments ---

    def assign_profile_to_channel(self, channel_id: int, profile_id: Optional[str]) -> bool:
        """Assign a profile to a channel. Pass None to unassign (use group/default)."""
        with self._lock:
            cid = int(channel_id)
            if profile_id is None:
                if cid in self._config["channel_assignments"]:
                    del self._config["channel_assignments"][cid]
                else:
                    return True # No change
            else:
                if profile_id not in self._config["profiles"]:
                    return False
                self._config["channel_assignments"][cid] = profile_id
            
            return self._save_config()

    def assign_profile_to_channels(self, channel_ids: List[int], profile_id: Optional[str]) -> bool:
        """Assigns a profile to multiple channels."""
        with self._lock:
            if profile_id and profile_id not in self._config["profiles"]:
                # If trying to assign a non-existent profile, return False immediately
                return False
            
            changes_made = False
            for cid_raw in channel_ids:
                cid = int(cid_raw)
                if profile_id is None:
                    # Unassign
                    if cid in self._config["channel_assignments"]:
                        del self._config["channel_assignments"][cid]
                        changes_made = True
                else:
                    # Assign (or overwrite)
                    if self._config["channel_assignments"].get(cid) != profile_id:
                        self._config["channel_assignments"][cid] = profile_id
                        changes_made = True
            
            if changes_made:
                return self._save_config()
            return True

    def assign_profile_to_group(self, group_id: int, profile_id: Optional[str]) -> bool:
        """Assign a profile to a group."""
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

    def get_effective_profile_id(self, channel_id: int, group_id: Optional[int] = None) -> str:
        """
        Determine the effective profile ID for a channel.
        Precedence: Channel Assignment > Group Assignment > Default
        """
        with self._lock:
            # 1. Channel Assignment
            if int(channel_id) in self._config["channel_assignments"]:
                return self._config["channel_assignments"][int(channel_id)]
            
            # 2. Group Assignment
            if group_id is not None and int(group_id) in self._config["group_assignments"]:
                return self._config["group_assignments"][int(group_id)]
            
            # 3. Default
            # We assume there's always a default profile (created in __init__)
            # If for some reason default is deleted, we might return None or a fallback
            if "default" in self._config["profiles"]:
                return "default"
            
            # Fallback if even default is gone (shouldn't happen)
            if self._config["profiles"]:
                return list(self._config["profiles"].keys())[0]
            
            return None

    def get_effective_profile(self, channel_id: int, group_id: Optional[int] = None) -> Optional[Dict]:
        """
        Get the full profile object effective for a channel.
        """
        pid = self.get_effective_profile_id(channel_id, group_id)
        if pid:
            return self.get_profile(pid)
        return None


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
