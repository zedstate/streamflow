"""
Unit tests for Match Profiles functionality.

Tests the match profiles manager, data models, and storage layer.
"""

import unittest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from udi.models import MatchProfile, MatchProfileStep
from udi.storage import UDIStorage
from match_profiles_manager import MatchProfilesManager


class TestMatchProfileModels(unittest.TestCase):
    """Test MatchProfile and MatchProfileStep data models."""
    
    def test_match_profile_step_creation(self):
        """Test creating a MatchProfileStep."""
        step = MatchProfileStep(
            id="step1",
            type="regex_name",
            pattern=".*ESPN.*",
            variables={},
            enabled=True,
            order=0
        )
        
        self.assertEqual(step.id, "step1")
        self.assertEqual(step.type, "regex_name")
        self.assertEqual(step.pattern, ".*ESPN.*")
        self.assertTrue(step.enabled)
    
    def test_match_profile_step_to_dict(self):
        """Test converting MatchProfileStep to dictionary."""
        step = MatchProfileStep(
            id="step1",
            type="tvg_id",
            pattern="ESPN.us",
            variables={"test": "value"},
            enabled=False,
            order=1
        )
        
        step_dict = step.to_dict()
        self.assertEqual(step_dict["id"], "step1")
        self.assertEqual(step_dict["type"], "tvg_id")
        self.assertEqual(step_dict["pattern"], "ESPN.us")
        self.assertEqual(step_dict["variables"], {"test": "value"})
        self.assertFalse(step_dict["enabled"])
        self.assertEqual(step_dict["order"], 1)
    
    def test_match_profile_step_from_dict(self):
        """Test creating MatchProfileStep from dictionary."""
        step_dict = {
            "id": "step2",
            "type": "regex_url",
            "pattern": ".*provider1.*",
            "variables": {},
            "enabled": True,
            "order": 2
        }
        
        step = MatchProfileStep.from_dict(step_dict)
        self.assertEqual(step.id, "step2")
        self.assertEqual(step.type, "regex_url")
        self.assertEqual(step.pattern, ".*provider1.*")
    
    def test_match_profile_creation(self):
        """Test creating a MatchProfile."""
        steps = [
            MatchProfileStep(
                id="step1",
                type="regex_name",
                pattern=".*ESPN.*",
                enabled=True,
                order=0
            )
        ]
        
        profile = MatchProfile(
            id=1,
            name="Sports Profile",
            description="Match sports channels",
            steps=steps,
            enabled=True
        )
        
        self.assertEqual(profile.id, 1)
        self.assertEqual(profile.name, "Sports Profile")
        self.assertEqual(len(profile.steps), 1)
        self.assertTrue(profile.enabled)
    
    def test_match_profile_to_dict(self):
        """Test converting MatchProfile to dictionary."""
        steps = [
            MatchProfileStep(
                id="step1",
                type="regex_name",
                pattern=".*ESPN.*",
                enabled=True,
                order=0
            )
        ]
        
        profile = MatchProfile(
            id=1,
            name="Test Profile",
            description="Test description",
            steps=steps,
            enabled=True,
            created_at="2025-01-01T00:00:00",
            updated_at="2025-01-01T00:00:00"
        )
        
        profile_dict = profile.to_dict()
        self.assertEqual(profile_dict["id"], 1)
        self.assertEqual(profile_dict["name"], "Test Profile")
        self.assertEqual(profile_dict["description"], "Test description")
        self.assertEqual(len(profile_dict["steps"]), 1)
        self.assertTrue(profile_dict["enabled"])
    
    def test_match_profile_from_dict(self):
        """Test creating MatchProfile from dictionary."""
        profile_dict = {
            "id": 2,
            "name": "News Profile",
            "description": "News channels",
            "steps": [
                {
                    "id": "step1",
                    "type": "regex_name",
                    "pattern": ".*News.*",
                    "variables": {},
                    "enabled": True,
                    "order": 0
                }
            ],
            "enabled": True,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00"
        }
        
        profile = MatchProfile.from_dict(profile_dict)
        self.assertEqual(profile.id, 2)
        self.assertEqual(profile.name, "News Profile")
        self.assertEqual(len(profile.steps), 1)
        self.assertEqual(profile.steps[0].pattern, ".*News.*")


class TestMatchProfilesStorage(unittest.TestCase):
    """Test match profiles storage layer."""
    
    def setUp(self):
        """Set up test storage directory."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.storage = UDIStorage(storage_dir=self.test_dir)
    
    def tearDown(self):
        """Clean up test storage directory."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_save_and_load_match_profiles(self):
        """Test saving and loading match profiles."""
        profiles = [
            {
                "id": 1,
                "name": "Profile 1",
                "description": "Test profile",
                "steps": [],
                "enabled": True,
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00"
            }
        ]
        
        # Save profiles
        result = self.storage.save_match_profiles(profiles)
        self.assertTrue(result)
        
        # Load profiles
        loaded_profiles = self.storage.load_match_profiles()
        self.assertEqual(len(loaded_profiles), 1)
        self.assertEqual(loaded_profiles[0]["name"], "Profile 1")
    
    def test_get_match_profile(self):
        """Test getting a specific match profile."""
        profiles = [
            {
                "id": 1,
                "name": "Profile 1",
                "steps": [],
                "enabled": True
            },
            {
                "id": 2,
                "name": "Profile 2",
                "steps": [],
                "enabled": True
            }
        ]
        
        self.storage.save_match_profiles(profiles)
        
        # Get profile by ID
        profile = self.storage.get_match_profile(2)
        self.assertIsNotNone(profile)
        self.assertEqual(profile["name"], "Profile 2")
        
        # Non-existent profile
        profile = self.storage.get_match_profile(999)
        self.assertIsNone(profile)
    
    def test_update_match_profile(self):
        """Test updating a match profile."""
        profiles = [
            {
                "id": 1,
                "name": "Original Name",
                "steps": [],
                "enabled": True
            }
        ]
        
        self.storage.save_match_profiles(profiles)
        
        # Update profile
        updated_profile = {
            "id": 1,
            "name": "Updated Name",
            "steps": [],
            "enabled": False
        }
        
        result = self.storage.update_match_profile(1, updated_profile)
        self.assertTrue(result)
        
        # Verify update
        loaded_profile = self.storage.get_match_profile(1)
        self.assertEqual(loaded_profile["name"], "Updated Name")
        self.assertFalse(loaded_profile["enabled"])
    
    def test_delete_match_profile(self):
        """Test deleting a match profile."""
        profiles = [
            {"id": 1, "name": "Profile 1", "steps": [], "enabled": True},
            {"id": 2, "name": "Profile 2", "steps": [], "enabled": True}
        ]
        
        self.storage.save_match_profiles(profiles)
        
        # Delete profile
        result = self.storage.delete_match_profile(1)
        self.assertTrue(result)
        
        # Verify deletion
        loaded_profiles = self.storage.load_match_profiles()
        self.assertEqual(len(loaded_profiles), 1)
        self.assertEqual(loaded_profiles[0]["id"], 2)


class TestMatchProfilesManager(unittest.TestCase):
    """Test match profiles manager."""
    
    def setUp(self):
        """Set up test storage and manager."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.storage = UDIStorage(storage_dir=self.test_dir)
        self.manager = MatchProfilesManager(storage=self.storage)
    
    def tearDown(self):
        """Clean up test storage directory."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_create_profile(self):
        """Test creating a match profile."""
        profile = self.manager.create_profile(
            name="Test Profile",
            description="Test description",
            steps=[
                {
                    "id": "step1",
                    "type": "regex_name",
                    "pattern": ".*ESPN.*",
                    "variables": {},
                    "enabled": True,
                    "order": 0
                }
            ]
        )
        
        self.assertEqual(profile.id, 1)
        self.assertEqual(profile.name, "Test Profile")
        self.assertEqual(len(profile.steps), 1)
    
    def test_list_profiles(self):
        """Test listing all profiles."""
        # Create multiple profiles
        self.manager.create_profile(name="Profile 1")
        self.manager.create_profile(name="Profile 2")
        self.manager.create_profile(name="Profile 3")
        
        profiles = self.manager.list_profiles()
        self.assertEqual(len(profiles), 3)
    
    def test_get_profile(self):
        """Test getting a specific profile."""
        created = self.manager.create_profile(name="Test Profile")
        
        retrieved = self.manager.get_profile(created.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "Test Profile")
    
    def test_update_profile(self):
        """Test updating a profile."""
        profile = self.manager.create_profile(name="Original Name")
        
        updated = self.manager.update_profile(
            profile_id=profile.id,
            name="Updated Name",
            enabled=False
        )
        
        self.assertIsNotNone(updated)
        self.assertEqual(updated.name, "Updated Name")
        self.assertFalse(updated.enabled)
    
    def test_delete_profile(self):
        """Test deleting a profile."""
        profile = self.manager.create_profile(name="To Delete")
        
        result = self.manager.delete_profile(profile.id)
        self.assertTrue(result)
        
        # Verify deletion
        profiles = self.manager.list_profiles()
        self.assertEqual(len(profiles), 0)
    
    def test_apply_variables(self):
        """Test applying variables to a profile."""
        steps = [
            MatchProfileStep(
                id="step1",
                type="regex_name",
                pattern=".*{channel_name}.*",
                enabled=True,
                order=0
            )
        ]
        
        profile = MatchProfile(
            id=1,
            name="Test Profile",
            steps=steps,
            enabled=True
        )
        
        resolved = self.manager.apply_profile_to_variables(
            profile,
            channel_name="ESPN",
            channel_group="Sports",
            m3u_account_name="Provider1"
        )
        
        self.assertEqual(resolved.steps[0].pattern, ".*ESPN.*")
    
    def test_test_profile_regex_name_match(self):
        """Test profile matching with regex_name step."""
        steps = [
            MatchProfileStep(
                id="step1",
                type="regex_name",
                pattern=".*ESPN.*",
                enabled=True,
                order=0
            )
        ]
        
        profile = MatchProfile(
            id=1,
            name="Test Profile",
            steps=steps,
            enabled=True
        )
        
        # Test matching stream
        result = self.manager.test_profile_against_stream(
            profile,
            stream_name="ESPN Sports HD",
            stream_url="",
            stream_tvg_id=""
        )
        
        self.assertTrue(result["matched"])
        self.assertTrue(result["steps_results"][0]["matched"])
    
    def test_test_profile_tvg_id_match(self):
        """Test profile matching with tvg_id step."""
        steps = [
            MatchProfileStep(
                id="step1",
                type="tvg_id",
                pattern="ESPN.us",
                enabled=True,
                order=0
            )
        ]
        
        profile = MatchProfile(
            id=1,
            name="Test Profile",
            steps=steps,
            enabled=True
        )
        
        # Test matching stream
        result = self.manager.test_profile_against_stream(
            profile,
            stream_name="",
            stream_url="",
            stream_tvg_id="ESPN.us"
        )
        
        self.assertTrue(result["matched"])
    
    def test_test_profile_regex_url_match(self):
        """Test profile matching with regex_url step."""
        steps = [
            MatchProfileStep(
                id="step1",
                type="regex_url",
                pattern=".*provider1.*",
                enabled=True,
                order=0
            )
        ]
        
        profile = MatchProfile(
            id=1,
            name="Test Profile",
            steps=steps,
            enabled=True
        )
        
        # Test matching stream
        result = self.manager.test_profile_against_stream(
            profile,
            stream_name="",
            stream_url="http://provider1.com/stream",
            stream_tvg_id=""
        )
        
        self.assertTrue(result["matched"])
    
    def test_test_profile_no_match(self):
        """Test profile with no matching steps."""
        steps = [
            MatchProfileStep(
                id="step1",
                type="regex_name",
                pattern=".*ESPN.*",
                enabled=True,
                order=0
            )
        ]
        
        profile = MatchProfile(
            id=1,
            name="Test Profile",
            steps=steps,
            enabled=True
        )
        
        # Test non-matching stream
        result = self.manager.test_profile_against_stream(
            profile,
            stream_name="CNN News",
            stream_url="",
            stream_tvg_id=""
        )
        
        self.assertFalse(result["matched"])
    
    def test_test_profile_disabled(self):
        """Test profile matching with disabled profile."""
        steps = [
            MatchProfileStep(
                id="step1",
                type="regex_name",
                pattern=".*ESPN.*",
                enabled=True,
                order=0
            )
        ]
        
        profile = MatchProfile(
            id=1,
            name="Test Profile",
            steps=steps,
            enabled=False  # Profile disabled
        )
        
        result = self.manager.test_profile_against_stream(
            profile,
            stream_name="ESPN Sports HD",
            stream_url="",
            stream_tvg_id=""
        )
        
        self.assertFalse(result["matched"])
        self.assertEqual(result["reason"], "Profile is disabled")


if __name__ == '__main__':
    unittest.main()
