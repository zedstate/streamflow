"""Test wizard pattern loading to ensure empty entries are not displayed."""
import unittest
import json
from pathlib import Path
import tempfile
import sys

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from apps.automation.automated_stream_manager import RegexChannelMatcher


class TestWizardPatternLoading(unittest.TestCase):
    """Test that wizard correctly loads and displays patterns."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_regex_config.json"
        
        # Create test configuration with patterns
        test_config = {
            "patterns": {
                "1": {
                    "name": "CNN",
                    "regex": [".*CNN.*"],
                    "enabled": True
                },
                "2": {
                    "name": "ESPN", 
                    "regex": [".*ESPN.*"],
                    "enabled": True
                }
            },
            "global_settings": {
                "case_sensitive": False,
                "require_exact_match": False
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
        
        self.matcher = RegexChannelMatcher(config_file=self.config_file)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_patterns_returns_full_structure(self):
        """Test that get_patterns returns the full config structure."""
        patterns = self.matcher.get_patterns()
        
        # Should have both patterns and global_settings
        self.assertIn('patterns', patterns)
        self.assertIn('global_settings', patterns)
        
        # Patterns should be a dict
        self.assertIsInstance(patterns['patterns'], dict)
        self.assertEqual(len(patterns['patterns']), 2)
    
    def test_only_actual_patterns_have_required_fields(self):
        """Test that only actual pattern entries have name/regex/enabled fields."""
        patterns = self.matcher.get_patterns()
        
        # The top-level keys are NOT patterns
        self.assertNotIn('name', patterns)
        self.assertNotIn('regex', patterns)
        
        # global_settings is not a pattern
        global_settings = patterns.get('global_settings', {})
        self.assertNotIn('name', global_settings)
        self.assertNotIn('regex', global_settings)
        
        # Only the entries inside patterns['patterns'] are actual patterns
        actual_patterns = patterns.get('patterns', {})
        for channel_id, pattern in actual_patterns.items():
            self.assertIn('name', pattern)
            self.assertIn('regex', pattern)
            self.assertIn('enabled', pattern)
    
    def test_wizard_should_extract_patterns_subkey(self):
        """Test simulating how wizard should extract patterns from API response."""
        # Simulate API response
        api_response = self.matcher.get_patterns()
        
        # OLD WAY (BUGGY) - would iterate over all keys
        old_way_keys = list(api_response.keys())
        # This would include 'patterns' and 'global_settings' as if they were channel IDs
        self.assertIn('patterns', old_way_keys)
        self.assertIn('global_settings', old_way_keys)
        
        # NEW WAY (CORRECT) - extract only the patterns subkey
        patterns_only = api_response.get('patterns', {})
        correct_keys = list(patterns_only.keys())
        # This only includes actual channel IDs
        self.assertIn('1', correct_keys)
        self.assertIn('2', correct_keys)
        self.assertNotIn('patterns', correct_keys)
        self.assertNotIn('global_settings', correct_keys)
    
    def test_empty_patterns_not_included(self):
        """Test that patterns with empty regex arrays are not saved."""
        # Try to add a pattern with empty regex (should fail validation)
        with self.assertRaises(ValueError):
            self.matcher.add_channel_pattern(
                channel_id="3",
                name="Empty Pattern",
                regex_patterns=[],
                enabled=True
            )
        
        # Verify it wasn't saved
        patterns = self.matcher.get_patterns()
        self.assertNotIn('3', patterns.get('patterns', {}))
    
    def test_patterns_with_only_empty_strings_rejected(self):
        """Test that patterns with only empty strings are rejected."""
        with self.assertRaises(ValueError):
            self.matcher.add_channel_pattern(
                channel_id="4",
                name="Empty String Pattern",
                regex_patterns=["", "  "],
                enabled=True
            )
        
        # Verify it wasn't saved
        patterns = self.matcher.get_patterns()
        self.assertNotIn('4', patterns.get('patterns', {}))


if __name__ == '__main__':
    unittest.main()
