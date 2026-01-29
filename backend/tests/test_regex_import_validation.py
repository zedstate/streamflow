#!/usr/bin/env python3
"""
Unit tests for regex pattern import validation (both old and new formats).

This module tests the validation logic in the import endpoint to ensure it correctly
handles both the old format (regex field) and new format (regex_patterns field).
"""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automated_stream_manager import RegexChannelMatcher


class TestRegexImportValidation(unittest.TestCase):
    """Test regex pattern import validation for both old and new formats."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_validate_old_format_with_regex_field(self):
        """Test validation of old format with 'regex' field."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            matcher = RegexChannelMatcher()
            
            # Old format with 'regex' field
            old_format_data = {
                "patterns": {
                    "1": {
                        "name": "CNN",
                        "regex": [".*CNN.*", ".*News.*"],
                        "enabled": True
                    }
                },
                "global_settings": {
                    "case_sensitive": False
                }
            }
            
            # Validate that regex patterns can be extracted
            channel_data = old_format_data['patterns']['1']
            self.assertIn('regex', channel_data)
            self.assertIsInstance(channel_data['regex'], list)
            
            # Validate the patterns
            is_valid, error_msg = matcher.validate_regex_patterns(channel_data['regex'])
            self.assertTrue(is_valid, f"Validation failed: {error_msg}")
            self.assertIsNone(error_msg)
    
    def test_validate_new_format_with_regex_patterns_field(self):
        """Test validation of new format with 'regex_patterns' field."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            matcher = RegexChannelMatcher()
            
            # New format with 'regex_patterns' field (from problem statement)
            new_format_data = {
                "patterns": {
                    "1": {
                        "enabled": True,
                        "name": "M+ LaLiga",
                        "regex_patterns": [
                            {
                                "m3u_accounts": [13],
                                "pattern": "^M\\+ LALIGA(?: (?:4K|FHD|HD|SD))?(?: [a-zA-Z0-9]+)?\\s+-->\\s+(.+)$",
                                "priority": 0
                            },
                            {
                                "m3u_accounts": [11],
                                "pattern": "^CHANNEL_NAME(?: (?:1080|720)p)?$",
                                "priority": 0
                            }
                        ]
                    },
                    "2": {
                        "enabled": True,
                        "name": "M+ LaLiga 2",
                        "regex_patterns": [
                            {
                                "m3u_accounts": [13],
                                "pattern": "^M\\+ LALIGA 2(?: (?:4K|FHD|HD|SD))?(?: [a-zA-Z0-9]+)?\\s+-->\\s+(.+)$",
                                "priority": 0
                            },
                            {
                                "m3u_accounts": [11],
                                "pattern": "^CHANNEL_NAME(?: (?:1080|720)p)?$",
                                "priority": 0
                            }
                        ]
                    }
                }
            }
            
            # Validate that regex patterns can be extracted from new format
            for channel_id, channel_data in new_format_data['patterns'].items():
                self.assertIn('regex_patterns', channel_data)
                self.assertIsInstance(channel_data['regex_patterns'], list)
                
                # Extract pattern strings for validation
                pattern_strings = []
                for pattern_obj in channel_data['regex_patterns']:
                    self.assertIsInstance(pattern_obj, dict)
                    self.assertIn('pattern', pattern_obj)
                    pattern_strings.append(pattern_obj['pattern'])
                
                # Validate the patterns
                is_valid, error_msg = matcher.validate_regex_patterns(pattern_strings)
                self.assertTrue(is_valid, f"Validation failed for channel {channel_id}: {error_msg}")
                self.assertIsNone(error_msg)
    
    def test_validate_mixed_formats_in_same_file(self):
        """Test that a file can contain both old and new format patterns."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            matcher = RegexChannelMatcher()
            
            # Mixed format - some channels with old format, some with new
            mixed_format_data = {
                "patterns": {
                    "1": {
                        "name": "Old Format Channel",
                        "regex": [".*CNN.*"],
                        "enabled": True
                    },
                    "2": {
                        "name": "New Format Channel",
                        "regex_patterns": [
                            {
                                "pattern": ".*ESPN.*",
                                "m3u_accounts": [11, 13],
                                "priority": 0
                            }
                        ],
                        "enabled": True
                    }
                }
            }
            
            # Validate each channel
            for channel_id, channel_data in mixed_format_data['patterns'].items():
                pattern_strings = []
                
                if 'regex_patterns' in channel_data:
                    # New format
                    for pattern_obj in channel_data['regex_patterns']:
                        pattern_strings.append(pattern_obj['pattern'])
                elif 'regex' in channel_data:
                    # Old format
                    pattern_strings = channel_data['regex']
                else:
                    self.fail(f"Channel {channel_id} missing both 'regex' and 'regex_patterns'")
                
                # Validate patterns
                is_valid, error_msg = matcher.validate_regex_patterns(pattern_strings)
                self.assertTrue(is_valid, f"Validation failed for channel {channel_id}: {error_msg}")
    
    def test_reject_channel_with_neither_format(self):
        """Test that channels with neither 'regex' nor 'regex_patterns' are rejected."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            # Channel missing both fields
            invalid_data = {
                "patterns": {
                    "1": {
                        "name": "Invalid Channel",
                        "enabled": True
                        # Missing both 'regex' and 'regex_patterns'
                    }
                }
            }
            
            channel_data = invalid_data['patterns']['1']
            self.assertNotIn('regex', channel_data)
            self.assertNotIn('regex_patterns', channel_data)
    
    def test_new_format_with_empty_pattern_field(self):
        """Test that patterns with empty 'pattern' field are caught."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            matcher = RegexChannelMatcher()
            
            # New format with empty pattern
            invalid_data = {
                "patterns": {
                    "1": {
                        "name": "Channel with Empty Pattern",
                        "regex_patterns": [
                            {
                                "pattern": "",  # Empty pattern
                                "m3u_accounts": [11],
                                "priority": 0
                            }
                        ],
                        "enabled": True
                    }
                }
            }
            
            channel_data = invalid_data['patterns']['1']
            pattern_strings = [p['pattern'] for p in channel_data['regex_patterns']]
            
            # Empty patterns should fail validation
            is_valid, error_msg = matcher.validate_regex_patterns(pattern_strings)
            self.assertFalse(is_valid)
            self.assertIsNotNone(error_msg)
    
    def test_save_and_reload_new_format(self):
        """Test that new format patterns can be saved and reloaded."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            matcher = RegexChannelMatcher()
            
            # New format data
            new_format_data = {
                "patterns": {
                    "1": {
                        "name": "Test Channel",
                        "regex_patterns": [
                            {
                                "pattern": ".*Test.*",
                                "m3u_accounts": [11, 13],
                                "priority": 5
                            }
                        ],
                        "enabled": True
                    }
                },
                "global_settings": {
                    "case_sensitive": False
                }
            }
            
            # Save patterns
            matcher._save_patterns(new_format_data)
            
            # Reload and verify
            matcher.reload_patterns()
            loaded_patterns = matcher.get_patterns()
            
            self.assertIn("patterns", loaded_patterns)
            self.assertIn("1", loaded_patterns["patterns"])
            
            # Verify the pattern structure is preserved
            channel_data = loaded_patterns["patterns"]["1"]
            self.assertEqual(channel_data["name"], "Test Channel")
            self.assertIn("regex_patterns", channel_data)
            self.assertEqual(len(channel_data["regex_patterns"]), 1)
            
            # Verify pattern details
            pattern_obj = channel_data["regex_patterns"][0]
            self.assertEqual(pattern_obj["pattern"], ".*Test.*")
            self.assertEqual(pattern_obj["m3u_accounts"], [11, 13])
            self.assertEqual(pattern_obj["priority"], 5)
    
    def test_old_format_without_m3u_accounts_and_priority(self):
        """Test backward compatibility with old format (no m3u_accounts/priority)."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            matcher = RegexChannelMatcher()
            
            # Old format from new requirement - just name, regex, and enabled
            old_format_data = {
                "patterns": {
                    "27": {
                        "name": "M+ Liga De Campeones 4",
                        "regex": [
                            "^LIGA DE CAMPEONES 4(?: (?:4K|FHD|HD|SD))\\s+-->\\s+(.+)$"
                        ],
                        "enabled": True
                    }
                },
                "global_settings": {
                    "case_sensitive": False
                }
            }
            
            # Validate that this old format can be processed
            channel_data = old_format_data['patterns']['27']
            self.assertIn('regex', channel_data)
            self.assertNotIn('regex_patterns', channel_data)
            self.assertNotIn('m3u_accounts', channel_data)
            
            # Validate the patterns
            is_valid, error_msg = matcher.validate_regex_patterns(channel_data['regex'])
            self.assertTrue(is_valid, f"Validation failed: {error_msg}")
            
            # Save and reload to verify migration
            matcher._save_patterns(old_format_data)
            matcher.reload_patterns()
            loaded_patterns = matcher.get_patterns()
            
            # After reload, old format should be migrated to new format
            channel_data = loaded_patterns["patterns"]["27"]
            self.assertEqual(channel_data["name"], "M+ Liga De Campeones 4")
            self.assertTrue(channel_data["enabled"])
            
            # Check if migrated to new format
            self.assertIn("regex_patterns", channel_data)
            self.assertEqual(len(channel_data["regex_patterns"]), 1)
            
            # Verify migrated pattern
            pattern_obj = channel_data["regex_patterns"][0]
            self.assertEqual(pattern_obj["pattern"], "^LIGA DE CAMPEONES 4(?: (?:4K|FHD|HD|SD))\\s+-->\\s+(.+)$")
            # Old format had no m3u_accounts, so it should be None or null
            self.assertIn("m3u_accounts", pattern_obj)
            # Default priority for migrated patterns
            self.assertEqual(pattern_obj["priority"], 0)
    
    def test_multiple_old_format_channels(self):
        """Test multiple channels in old format without m3u_accounts/priority."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            matcher = RegexChannelMatcher()
            
            # Multiple channels in old format
            old_format_data = {
                "patterns": {
                    "1": {
                        "name": "CNN",
                        "regex": [".*CNN.*", ".*News Network.*"],
                        "enabled": True
                    },
                    "2": {
                        "name": "ESPN",
                        "regex": [".*ESPN.*"],
                        "enabled": False
                    },
                    "27": {
                        "name": "M+ Liga De Campeones 4",
                        "regex": [
                            "^LIGA DE CAMPEONES 4(?: (?:4K|FHD|HD|SD))\\s+-->\\s+(.+)$"
                        ],
                        "enabled": True
                    }
                },
                "global_settings": {
                    "case_sensitive": False
                }
            }
            
            # Validate all channels
            for channel_id, channel_data in old_format_data['patterns'].items():
                self.assertIn('regex', channel_data)
                self.assertIsInstance(channel_data['regex'], list)
                
                # Validate patterns
                is_valid, error_msg = matcher.validate_regex_patterns(channel_data['regex'])
                self.assertTrue(is_valid, f"Validation failed for channel {channel_id}: {error_msg}")
            
            # Save and reload
            matcher._save_patterns(old_format_data)
            matcher.reload_patterns()
            loaded_patterns = matcher.get_patterns()
            
            # Verify all channels were loaded and migrated
            self.assertEqual(len(loaded_patterns["patterns"]), 3)
            for channel_id in ["1", "2", "27"]:
                self.assertIn(channel_id, loaded_patterns["patterns"])
                channel_data = loaded_patterns["patterns"][channel_id]
                self.assertIn("regex_patterns", channel_data)


if __name__ == '__main__':
    unittest.main()
