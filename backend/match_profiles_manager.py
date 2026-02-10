"""
Match Profiles Manager for StreamFlow.

This module manages match profiles that define how streams are matched to channels.
Supports:
- Three match types: Regex (stream name), TVG-ID (exact match), Regex (stream URL)
- Dynamic variables: {channel_name}, {channel_group}, {m3u_account_name}
- Profile application at channel or group level
- Visual pipeline/building blocks structure
"""

import re
import json
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from logging_config import setup_logging
from udi.storage import UDIStorage
from udi.models import MatchProfile, MatchProfileStep

logger = setup_logging(__name__)


class MatchProfilesManager:
    """Manager for match profiles that define stream-to-channel matching rules."""
    
    def __init__(self, storage: Optional[UDIStorage] = None):
        """
        Initialize the MatchProfilesManager.
        
        Args:
            storage: Optional UDIStorage instance. If None, creates a new instance.
        """
        self.storage = storage or UDIStorage()
        logger.info("MatchProfilesManager initialized")
    
    def list_profiles(self) -> List[MatchProfile]:
        """
        Get all match profiles.
        
        Returns:
            List of MatchProfile objects
        """
        profiles_data = self.storage.load_match_profiles()
        return [MatchProfile.from_dict(p) for p in profiles_data]
    
    def get_profile(self, profile_id: int) -> Optional[MatchProfile]:
        """
        Get a specific match profile by ID.
        
        Args:
            profile_id: The profile ID
            
        Returns:
            MatchProfile object or None if not found
        """
        profile_data = self.storage.get_match_profile(profile_id)
        if profile_data:
            return MatchProfile.from_dict(profile_data)
        return None
    
    def create_profile(self, name: str, description: Optional[str] = None,
                      steps: Optional[List[Dict[str, Any]]] = None) -> MatchProfile:
        """
        Create a new match profile.
        
        Args:
            name: Profile name
            description: Optional description
            steps: Optional list of step dictionaries
            
        Returns:
            The created MatchProfile
        """
        profiles = self.storage.load_match_profiles()
        
        # Generate new ID
        new_id = max([p.get('id', 0) for p in profiles], default=0) + 1
        
        # Create profile data
        now = datetime.now().isoformat()
        profile_data = {
            'id': new_id,
            'name': name,
            'description': description,
            'steps': steps or [],
            'enabled': True,
            'created_at': now,
            'updated_at': now
        }
        
        # Save to storage
        profiles.append(profile_data)
        self.storage.save_match_profiles(profiles)
        
        logger.info(f"Created match profile: {name} (ID: {new_id})")
        return MatchProfile.from_dict(profile_data)
    
    def update_profile(self, profile_id: int, name: Optional[str] = None,
                      description: Optional[str] = None, steps: Optional[List[Dict[str, Any]]] = None,
                      enabled: Optional[bool] = None) -> Optional[MatchProfile]:
        """
        Update an existing match profile.
        
        Args:
            profile_id: The profile ID
            name: Optional new name
            description: Optional new description
            steps: Optional new steps
            enabled: Optional enabled status
            
        Returns:
            Updated MatchProfile or None if not found
        """
        profile_data = self.storage.get_match_profile(profile_id)
        if not profile_data:
            logger.warning(f"Match profile {profile_id} not found")
            return None
        
        # Update fields
        if name is not None:
            profile_data['name'] = name
        if description is not None:
            profile_data['description'] = description
        if steps is not None:
            profile_data['steps'] = steps
        if enabled is not None:
            profile_data['enabled'] = enabled
        
        profile_data['updated_at'] = datetime.now().isoformat()
        
        # Save to storage
        self.storage.update_match_profile(profile_id, profile_data)
        
        logger.info(f"Updated match profile: {profile_id}")
        return MatchProfile.from_dict(profile_data)
    
    def delete_profile(self, profile_id: int) -> bool:
        """
        Delete a match profile.
        
        Args:
            profile_id: The profile ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        # Check if profile exists
        if not self.storage.get_match_profile(profile_id):
            logger.warning(f"Match profile {profile_id} not found")
            return False
        
        # Delete from storage
        result = self.storage.delete_match_profile(profile_id)
        
        if result:
            logger.info(f"Deleted match profile: {profile_id}")
        else:
            logger.error(f"Failed to delete match profile: {profile_id}")
        
        return result
    
    def apply_profile_to_variables(self, profile: MatchProfile, 
                                   channel_name: str = "",
                                   channel_group: str = "",
                                   m3u_account_name: str = "") -> MatchProfile:
        """
        Apply dynamic variables to a match profile.
        
        Args:
            profile: The match profile
            channel_name: Channel name variable value
            channel_group: Channel group variable value
            m3u_account_name: M3U account name variable value
            
        Returns:
            MatchProfile with variables replaced in patterns
        """
        variables = {
            '{channel_name}': channel_name,
            '{channel_group}': channel_group,
            '{m3u_account_name}': m3u_account_name
        }
        
        # Create a copy with resolved patterns
        resolved_steps = []
        for step in profile.steps:
            resolved_pattern = step.pattern
            for var, value in variables.items():
                resolved_pattern = resolved_pattern.replace(var, value)
            
            resolved_step = MatchProfileStep(
                id=step.id,
                type=step.type,
                pattern=resolved_pattern,
                variables=step.variables,
                enabled=step.enabled,
                order=step.order
            )
            resolved_steps.append(resolved_step)
        
        return MatchProfile(
            id=profile.id,
            name=profile.name,
            description=profile.description,
            steps=resolved_steps,
            enabled=profile.enabled,
            created_at=profile.created_at,
            updated_at=profile.updated_at
        )
    
    def test_profile_against_stream(self, profile: MatchProfile, 
                                    stream_name: str = "",
                                    stream_url: str = "",
                                    stream_tvg_id: str = "") -> Dict[str, Any]:
        """
        Test a match profile against a stream to see if it matches.
        
        Args:
            profile: The match profile to test
            stream_name: Stream name
            stream_url: Stream URL
            stream_tvg_id: Stream TVG-ID
            
        Returns:
            Dict with match result and details
        """
        if not profile.enabled:
            return {
                'matched': False,
                'reason': 'Profile is disabled',
                'steps_results': []
            }
        
        steps_results = []
        overall_match = False
        
        for step in sorted(profile.steps, key=lambda s: s.order):
            if not step.enabled:
                steps_results.append({
                    'step_id': step.id,
                    'type': step.type,
                    'pattern': step.pattern,
                    'matched': False,
                    'reason': 'Step is disabled'
                })
                continue
            
            matched = False
            reason = ""
            
            try:
                if step.type == 'regex_name':
                    # Regex match on stream name
                    if re.search(step.pattern, stream_name, re.IGNORECASE):
                        matched = True
                        reason = f"Stream name '{stream_name}' matches pattern '{step.pattern}'"
                    else:
                        reason = f"Stream name '{stream_name}' does not match pattern '{step.pattern}'"
                
                elif step.type == 'tvg_id':
                    # Exact match on TVG-ID
                    if step.pattern == stream_tvg_id:
                        matched = True
                        reason = f"TVG-ID '{stream_tvg_id}' matches '{step.pattern}'"
                    else:
                        reason = f"TVG-ID '{stream_tvg_id}' does not match '{step.pattern}'"
                
                elif step.type == 'regex_url':
                    # Regex match on stream URL
                    if re.search(step.pattern, stream_url, re.IGNORECASE):
                        matched = True
                        reason = f"Stream URL matches pattern '{step.pattern}'"
                    else:
                        reason = f"Stream URL does not match pattern '{step.pattern}'"
                
                else:
                    reason = f"Unknown step type: {step.type}"
            
            except re.error as e:
                matched = False
                reason = f"Invalid regex pattern: {e}"
            
            steps_results.append({
                'step_id': step.id,
                'type': step.type,
                'pattern': step.pattern,
                'matched': matched,
                'reason': reason
            })
            
            # If any step matches, overall match is true (OR logic)
            if matched:
                overall_match = True
        
        return {
            'matched': overall_match,
            'reason': 'At least one step matched' if overall_match else 'No steps matched',
            'steps_results': steps_results
        }


# Global instance and lock for thread-safe singleton
_match_profiles_manager = None
_manager_lock = threading.Lock()


def get_match_profiles_manager(storage: Optional[UDIStorage] = None) -> MatchProfilesManager:
    """
    Get the global MatchProfilesManager instance (thread-safe singleton).
    
    Args:
        storage: Optional UDIStorage instance
        
    Returns:
        MatchProfilesManager instance
    """
    global _match_profiles_manager
    if _match_profiles_manager is None:
        with _manager_lock:
            # Double-check locking pattern
            if _match_profiles_manager is None:
                _match_profiles_manager = MatchProfilesManager(storage)
    return _match_profiles_manager
