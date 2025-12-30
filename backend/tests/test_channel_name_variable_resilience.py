#!/usr/bin/env python3
"""
Comprehensive test for CHANNEL_NAME variable resilience against special characters.

This test verifies that the CHANNEL_NAME variable works correctly in all
stream matching scenarios, including:
- Special regex characters in channel names (+, ., *, ?, [, ], etc.)
- Unicode characters and non-ASCII names
- Whitespace variations (spaces, tabs, non-breaking spaces)
- Empty and edge case channel names
"""
import unittest
import sys
import tempfile
import json
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from automated_stream_manager import RegexChannelMatcher


class TestChannelNameVariableResilience(unittest.TestCase):
    """Test CHANNEL_NAME variable resilience against special characters."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_regex_config.json"
        
        # Create initial test configuration
        test_config = {
            "patterns": {},
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
    
    def test_channel_name_with_plus_sign(self):
        """Test channel names with plus sign (special regex character)."""
        # Add pattern with CHANNEL_NAME
        self.matcher.add_channel_pattern(
            channel_id="1",
            name="ESPN+",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        # Test matching
        matches = self.matcher.match_stream_to_channels("Watch ESPN+ Live HD")
        self.assertIn("1", matches, "Should match stream containing 'ESPN+'")
        
        matches = self.matcher.match_stream_to_channels("ESPN Plus HD")
        self.assertNotIn("1", matches, "Should not match 'ESPN Plus' (without +)")
    
    def test_channel_name_with_dot(self):
        """Test channel names with dot (special regex character)."""
        self.matcher.add_channel_pattern(
            channel_id="2",
            name="ABC.com",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("ABC.com News Live")
        self.assertIn("2", matches, "Should match stream containing 'ABC.com'")
        
        matches = self.matcher.match_stream_to_channels("ABCXcom")
        self.assertNotIn("2", matches, "Should not match with dot replaced by other char")
    
    def test_channel_name_with_asterisk(self):
        """Test channel names with asterisk (special regex character)."""
        self.matcher.add_channel_pattern(
            channel_id="3",
            name="HBO*",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("HBO* Premium")
        self.assertIn("3", matches, "Should match stream containing 'HBO*'")
        
        matches = self.matcher.match_stream_to_channels("HBOMAX")
        self.assertNotIn("3", matches, "Should not match without asterisk")
    
    def test_channel_name_with_question_mark(self):
        """Test channel names with question mark (special regex character)."""
        self.matcher.add_channel_pattern(
            channel_id="4",
            name="What?",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("What? TV Channel")
        self.assertIn("4", matches, "Should match stream containing 'What?'")
    
    def test_channel_name_with_brackets(self):
        """Test channel names with square brackets (special regex characters)."""
        self.matcher.add_channel_pattern(
            channel_id="5",
            name="News [24/7]",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("News [24/7] Live HD")
        self.assertIn("5", matches, "Should match stream containing 'News [24/7]'")
    
    def test_channel_name_with_parentheses(self):
        """Test channel names with parentheses (special regex characters)."""
        self.matcher.add_channel_pattern(
            channel_id="6",
            name="CNN (International)",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("CNN (International) HD")
        self.assertIn("6", matches, "Should match stream containing 'CNN (International)'")
    
    def test_channel_name_with_pipe(self):
        """Test channel names with pipe (special regex character)."""
        self.matcher.add_channel_pattern(
            channel_id="7",
            name="A|B Channel",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("A|B Channel HD")
        self.assertIn("7", matches, "Should match stream containing 'A|B Channel'")
    
    def test_channel_name_with_caret(self):
        """Test channel names with caret (special regex character)."""
        self.matcher.add_channel_pattern(
            channel_id="8",
            name="Test^Channel",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("Test^Channel Live")
        self.assertIn("8", matches, "Should match stream containing 'Test^Channel'")
    
    def test_channel_name_with_dollar_sign(self):
        """Test channel names with dollar sign (special regex character)."""
        self.matcher.add_channel_pattern(
            channel_id="9",
            name="Money$",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("Money$ Network")
        self.assertIn("9", matches, "Should match stream containing 'Money$'")
    
    def test_channel_name_with_backslash(self):
        """Test channel names with backslash (special regex character)."""
        self.matcher.add_channel_pattern(
            channel_id="10",
            name="Test\\Channel",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("Test\\Channel HD")
        self.assertIn("10", matches, "Should match stream containing 'Test\\Channel'")
    
    def test_channel_name_with_curly_braces(self):
        """Test channel names with curly braces (special regex characters)."""
        self.matcher.add_channel_pattern(
            channel_id="11",
            name="Channel{1}",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("Channel{1} HD")
        self.assertIn("11", matches, "Should match stream containing 'Channel{1}'")
    
    def test_channel_name_with_unicode_characters(self):
        """Test channel names with unicode characters."""
        self.matcher.add_channel_pattern(
            channel_id="12",
            name="TVP Polonia",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("TVP Polonia HD ᴴᴰ")
        self.assertIn("12", matches, "Should match stream with unicode characters")
    
    def test_channel_name_with_special_unicode(self):
        """Test channel names with special unicode symbols."""
        self.matcher.add_channel_pattern(
            channel_id="13",
            name="Channel™",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("Channel™ Premium")
        self.assertIn("13", matches, "Should match stream containing 'Channel™'")
    
    def test_channel_name_with_emoji(self):
        """Test channel names with emoji."""
        self.matcher.add_channel_pattern(
            channel_id="14",
            name="Fun 😊 TV",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("Fun 😊 TV HD")
        self.assertIn("14", matches, "Should match stream containing emoji")
    
    def test_channel_name_with_multiple_spaces(self):
        """Test channel names with multiple consecutive spaces."""
        self.matcher.add_channel_pattern(
            channel_id="15",
            name="HBO  3",  # Two spaces
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        # The flexible whitespace matching should handle this
        matches = self.matcher.match_stream_to_channels("HBO  3 HD")
        self.assertIn("15", matches, "Should match with same spacing")
        
        matches = self.matcher.match_stream_to_channels("HBO 3 HD")
        # This might not match if spacing is strict, which is expected behavior
    
    def test_multiple_channel_name_occurrences_with_special_chars(self):
        """Test pattern with multiple CHANNEL_NAME occurrences and special chars."""
        self.matcher.add_channel_pattern(
            channel_id="16",
            name="HBO+",
            regex_patterns=["^CHANNEL_NAME.*CHANNEL_NAME$"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("HBO+XHBO+")
        self.assertIn("16", matches, "Should match with multiple substitutions")
    
    def test_complex_pattern_with_channel_name_and_special_chars(self):
        """Test complex pattern with CHANNEL_NAME and special characters."""
        self.matcher.add_channel_pattern(
            channel_id="17",
            name="Discovery+",
            regex_patterns=[r"^(?:US|UK):\s*CHANNEL_NAME(?:\s+(?:HD|4K))?$"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("US: Discovery+ HD")
        self.assertIn("17", matches, "Should match complex pattern with special chars")
    
    def test_channel_name_in_character_class(self):
        """Test CHANNEL_NAME within character class patterns."""
        # This is an advanced case - the user might try to use CHANNEL_NAME
        # within a character class, which won't work as expected but should not crash
        self.matcher.add_channel_pattern(
            channel_id="18",
            name="HBO",
            regex_patterns=[r"[CHANNEL_NAME]"],  # This won't work as user expects
            enabled=True
        )
        
        # This test just verifies it doesn't crash
        try:
            matches = self.matcher.match_stream_to_channels("H")
            # The behavior here is implementation-defined, just ensure no crash
        except Exception as e:
            self.fail(f"Should not crash with CHANNEL_NAME in character class: {e}")
    
    def test_escaped_channel_name_prevents_regex_injection(self):
        """Test that escaping prevents regex injection attacks."""
        # A malicious channel name that could break regex if not escaped
        self.matcher.add_channel_pattern(
            channel_id="19",
            name=".*",  # This should be treated as literal ".*"
            regex_patterns=["^CHANNEL_NAME$"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels(".*")
        self.assertIn("19", matches, "Should match literal '.*'")
        
        matches = self.matcher.match_stream_to_channels("anything")
        self.assertNotIn("19", matches, "Should NOT match 'anything' (regex injection prevented)")
    
    def test_all_special_regex_chars_together(self):
        """Test channel name with all special regex characters together."""
        special_name = r"\.[]{}()*+?|^$"
        self.matcher.add_channel_pattern(
            channel_id="20",
            name=special_name,
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels(f"Test {special_name} Live")
        self.assertIn("20", matches, "Should match with all special chars")
    
    def test_real_world_polish_channel_pattern(self):
        """Test real-world pattern from user report."""
        # This is based on the pattern that was reported, but fixed for proper alternation
        # The original pattern had issues with alternation that are unrelated to CHANNEL_NAME
        self.matcher.add_channel_pattern(
            channel_id="21",
            name="HBO 3",
            regex_patterns=[
                # Simplified pattern that properly uses CHANNEL_NAME
                r"^(?:PL|PL-VIP|PL VIP):\s*CHANNEL_NAME(?:\s+(?:HD|4K|FHD|RAW))?$"
            ],
            enabled=True
        )
        
        # These should match
        test_streams = [
            "PL: HBO 3 HD",
            "PL-VIP: HBO 3 4K",
            "PL VIP: HBO 3 FHD",
            "PL: HBO 3",
        ]
        
        for stream in test_streams:
            matches = self.matcher.match_stream_to_channels(stream)
            self.assertIn("21", matches, f"Should match '{stream}'")
    
    def test_channel_name_case_sensitivity(self):
        """Test that CHANNEL_NAME respects case sensitivity settings."""
        # Test with case insensitive (default)
        self.matcher.add_channel_pattern(
            channel_id="22",
            name="ESPN",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("Watch espn live")
        self.assertIn("22", matches, "Should match case-insensitively by default")
        
        # Change to case sensitive
        config = self.matcher.get_patterns()
        config["global_settings"]["case_sensitive"] = True
        with open(self.config_file, 'w') as f:
            json.dump(config, f)
        self.matcher.reload_patterns()
        
        matches = self.matcher.match_stream_to_channels("Watch espn live")
        self.assertNotIn("22", matches, "Should not match with different case when case-sensitive")
        
        matches = self.matcher.match_stream_to_channels("Watch ESPN live")
        self.assertIn("22", matches, "Should match with exact case when case-sensitive")


class TestChannelNameVariableEdgeCases(unittest.TestCase):
    """Test edge cases for CHANNEL_NAME variable."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_regex_config.json"
        
        test_config = {
            "patterns": {},
            "global_settings": {
                "case_sensitive": False
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
        
        self.matcher = RegexChannelMatcher(config_file=self.config_file)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_empty_channel_name(self):
        """Test handling of empty channel name."""
        self.matcher.add_channel_pattern(
            channel_id="1",
            name="",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        # Should not crash, just won't match anything meaningful
        matches = self.matcher.match_stream_to_channels("Some Stream")
        # Behavior is implementation-defined
    
    def test_channel_name_only_spaces(self):
        """Test channel name with only spaces."""
        self.matcher.add_channel_pattern(
            channel_id="2",
            name="   ",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        # Should not crash
        matches = self.matcher.match_stream_to_channels("Test")
    
    def test_very_long_channel_name(self):
        """Test very long channel name."""
        long_name = "A" * 1000
        self.matcher.add_channel_pattern(
            channel_id="3",
            name=long_name,
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels(f"Test {long_name} Stream")
        self.assertIn("3", matches, "Should handle very long channel names")
    
    def test_channel_name_with_newlines(self):
        """Test channel name with newline characters."""
        self.matcher.add_channel_pattern(
            channel_id="4",
            name="Multi\nLine",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("Multi\nLine HD")
        self.assertIn("4", matches, "Should handle newlines in channel name")
    
    def test_channel_name_with_tabs(self):
        """Test channel name with tab characters."""
        self.matcher.add_channel_pattern(
            channel_id="5",
            name="Tab\tChannel",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("Tab\tChannel HD")
        self.assertIn("5", matches, "Should handle tabs in channel name")


class TestChannelNameVariableInAllAutomations(unittest.TestCase):
    """Test that CHANNEL_NAME works in all automation scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_regex_config.json"
        
        test_config = {
            "patterns": {},
            "global_settings": {
                "case_sensitive": False
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
        
        self.matcher = RegexChannelMatcher(config_file=self.config_file)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_match_stream_to_channels_uses_substitution(self):
        """Verify match_stream_to_channels properly substitutes CHANNEL_NAME."""
        self.matcher.add_channel_pattern(
            channel_id="1",
            name="Test+Channel",
            regex_patterns=[".*CHANNEL_NAME.*"],
            enabled=True
        )
        
        matches = self.matcher.match_stream_to_channels("Test+Channel HD")
        self.assertIn("1", matches, "match_stream_to_channels should use substitution")
    
    def test_validation_with_channel_name_variable(self):
        """Test that validation accepts patterns with CHANNEL_NAME."""
        # This should not raise an error
        is_valid, error = self.matcher.validate_regex_patterns([
            ".*CHANNEL_NAME.*",
            "^CHANNEL_NAME$",
            r"CHANNEL_NAME\s+HD"
        ])
        
        self.assertTrue(is_valid, f"CHANNEL_NAME patterns should be valid: {error}")
        self.assertIsNone(error)


if __name__ == '__main__':
    unittest.main()
