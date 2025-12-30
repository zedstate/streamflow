"""Test regex pattern reload functionality to ensure cached patterns are refreshed."""
import unittest
import sys
from pathlib import Path
import tempfile
import json
import shutil

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from automated_stream_manager import RegexChannelMatcher


class TestRegexPatternReload(unittest.TestCase):
    """Test that regex patterns are properly reloaded from disk."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_regex_config.json"
        
        # Create initial test configuration
        initial_config = {
            "patterns": {
                "1": {
                    "name": "Test Channel",
                    "regex": [".*TEST.*"],
                    "enabled": True
                }
            },
            "global_settings": {
                "case_sensitive": False,
                "require_exact_match": False
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(initial_config, f)
        
        self.matcher = RegexChannelMatcher(config_file=self.config_file)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_reload_picks_up_manual_changes(self):
        """Test that reload_patterns() picks up manual file edits."""
        # Initial state - should have one pattern
        patterns = self.matcher.get_patterns()
        self.assertIn('1', patterns['patterns'])
        self.assertEqual(patterns['patterns']['1']['name'], 'Test Channel')
        
        # Manually edit the config file (simulating user editing it)
        updated_config = {
            "patterns": {
                "1": {
                    "name": "Updated Channel",
                    "regex": [".*UPDATED.*"],
                    "enabled": True
                },
                "2": {
                    "name": "New Channel",
                    "regex": [".*NEW.*"],
                    "enabled": True
                }
            },
            "global_settings": {
                "case_sensitive": False,
                "require_exact_match": False
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(updated_config, f)
        
        # Before reload - should still have old data
        patterns = self.matcher.get_patterns()
        self.assertEqual(patterns['patterns']['1']['name'], 'Test Channel')
        self.assertNotIn('2', patterns['patterns'])
        
        # After reload - should have new data
        self.matcher.reload_patterns()
        patterns = self.matcher.get_patterns()
        self.assertEqual(patterns['patterns']['1']['name'], 'Updated Channel')
        self.assertIn('2', patterns['patterns'])
        self.assertEqual(patterns['patterns']['2']['name'], 'New Channel')
    
    def test_reload_removes_invalid_regex(self):
        """Test that reload automatically removes patterns with invalid regex."""
        # Create config with invalid regex pattern
        invalid_config = {
            "patterns": {
                "1": {
                    "name": "Valid Channel",
                    "regex": [".*VALID.*"],
                    "enabled": True
                },
                "2": {
                    "name": "Invalid Channel",
                    "regex": [".*CBS.*WWAY(?!-"],  # Invalid - missing closing paren
                    "enabled": True
                }
            },
            "global_settings": {
                "case_sensitive": False,
                "require_exact_match": False
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(invalid_config, f)
        
        # Reload should remove the invalid pattern
        self.matcher.reload_patterns()
        patterns = self.matcher.get_patterns()
        
        # Valid pattern should remain
        self.assertIn('1', patterns['patterns'])
        self.assertEqual(patterns['patterns']['1']['name'], 'Valid Channel')
        
        # Invalid pattern should be removed
        self.assertNotIn('2', patterns['patterns'])
    
    def test_reload_handles_corrupted_json(self):
        """Test that reload handles corrupted JSON gracefully."""
        # Write corrupted JSON to file
        with open(self.config_file, 'w') as f:
            f.write('{ "patterns": { "1": { "name": ')  # Incomplete JSON
        
        # Reload should create default config
        self.matcher.reload_patterns()
        patterns = self.matcher.get_patterns()
        
        # Should have valid structure with empty patterns
        self.assertIn('patterns', patterns)
        self.assertIn('global_settings', patterns)
        self.assertEqual(patterns['patterns'], {})
    
    def test_multiple_reloads(self):
        """Test that multiple reloads work correctly."""
        # First reload
        config_v1 = {
            "patterns": {
                "1": {"name": "Version 1", "regex": [".*V1.*"], "enabled": True}
            },
            "global_settings": {"case_sensitive": False, "require_exact_match": False}
        }
        with open(self.config_file, 'w') as f:
            json.dump(config_v1, f)
        
        self.matcher.reload_patterns()
        patterns = self.matcher.get_patterns()
        self.assertEqual(patterns['patterns']['1']['name'], 'Version 1')
        
        # Second reload
        config_v2 = {
            "patterns": {
                "1": {"name": "Version 2", "regex": [".*V2.*"], "enabled": True}
            },
            "global_settings": {"case_sensitive": False, "require_exact_match": False}
        }
        with open(self.config_file, 'w') as f:
            json.dump(config_v2, f)
        
        self.matcher.reload_patterns()
        patterns = self.matcher.get_patterns()
        self.assertEqual(patterns['patterns']['1']['name'], 'Version 2')
        
        # Third reload
        config_v3 = {
            "patterns": {
                "1": {"name": "Version 3", "regex": [".*V3.*"], "enabled": True}
            },
            "global_settings": {"case_sensitive": False, "require_exact_match": False}
        }
        with open(self.config_file, 'w') as f:
            json.dump(config_v3, f)
        
        self.matcher.reload_patterns()
        patterns = self.matcher.get_patterns()
        self.assertEqual(patterns['patterns']['1']['name'], 'Version 3')


if __name__ == '__main__':
    unittest.main()
