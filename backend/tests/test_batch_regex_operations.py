"""
Test for batch regex pattern operations (delete, edit, common patterns).

This test validates that:
1. bulk_delete_regex_patterns correctly deletes patterns from channels
2. bulk_edit_regex_pattern correctly updates patterns across channels
3. get_common_regex_patterns returns common patterns across channels
"""
import unittest
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


class TestBatchRegexOperations(unittest.TestCase):
    """Test batch regex pattern operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "channel_regex_config.json"
        
        # Initial configuration with patterns in new format
        self.initial_config = {
            "patterns": {
                "1": {
                    "name": "Channel 1",
                    "regex_patterns": [
                        {"pattern": ".*test.*", "m3u_accounts": None},
                        {"pattern": ".*common.*", "m3u_accounts": None}
                    ],
                    "enabled": True
                },
                "2": {
                    "name": "Channel 2",
                    "regex_patterns": [
                        {"pattern": ".*common.*", "m3u_accounts": None},
                        {"pattern": ".*channel2.*", "m3u_accounts": None}
                    ],
                    "enabled": True
                },
                "3": {
                    "name": "Channel 3",
                    "regex_patterns": [
                        {"pattern": ".*common.*", "m3u_accounts": None},
                        {"pattern": ".*unique.*", "m3u_accounts": None}
                    ],
                    "enabled": True
                }
            },
            "global_settings": {
                "case_sensitive": True,
                "require_exact_match": False
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(self.initial_config, f)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_delete_channel_pattern(self):
        """Test that delete_channel_pattern removes all patterns for a channel."""
        from automated_stream_manager import RegexChannelMatcher
        
        matcher = RegexChannelMatcher(self.config_file)
        
        # Verify channel 1 has patterns
        self.assertTrue(matcher.has_regex_patterns("1"))
        
        # Delete patterns for channel 1
        matcher.delete_channel_pattern("1")
        
        # Verify channel 1 no longer has patterns
        self.assertFalse(matcher.has_regex_patterns("1"))
        
        # Verify other channels still have patterns
        self.assertTrue(matcher.has_regex_patterns("2"))
        self.assertTrue(matcher.has_regex_patterns("3"))
        
        # Verify patterns were saved
        with open(self.config_file, 'r') as f:
            saved_config = json.load(f)
        
        self.assertNotIn("1", saved_config["patterns"])
        self.assertIn("2", saved_config["patterns"])
        self.assertIn("3", saved_config["patterns"])
    
    def test_delete_nonexistent_channel_pattern(self):
        """Test that deleting patterns for a non-existent channel doesn't raise an error."""
        from automated_stream_manager import RegexChannelMatcher
        
        matcher = RegexChannelMatcher(self.config_file)
        
        # Should not raise an error
        matcher.delete_channel_pattern("999")
    
    @patch('web_api.get_udi_manager')
    @patch('web_api.get_regex_matcher')
    def test_bulk_delete_regex_patterns(self, mock_matcher_func, mock_udi_manager):
        """Test bulk delete regex patterns endpoint."""
        from web_api import bulk_delete_regex_patterns
        from flask import Flask
        import json
        
        app = Flask(__name__)
        
        # Create actual matcher with temp config
        from automated_stream_manager import RegexChannelMatcher
        matcher = RegexChannelMatcher(self.config_file)
        mock_matcher_func.return_value = matcher
        
        # Test data - delete patterns from channels 1 and 2
        test_data = {
            'channel_ids': [1, 2]
        }
        
        with app.test_request_context(
            '/api/regex-patterns/bulk-delete',
            method='DELETE',
            data=json.dumps(test_data),
            content_type='application/json'
        ):
            response = bulk_delete_regex_patterns()
            response_data = json.loads(response.data)
            
            # Verify success
            self.assertEqual(response_data['success_count'], 2)
            self.assertEqual(response_data['total_channels'], 2)
            
            # Verify patterns were deleted
            self.assertFalse(matcher.has_regex_patterns("1"))
            self.assertFalse(matcher.has_regex_patterns("2"))
            
            # Verify channel 3 still has patterns
            self.assertTrue(matcher.has_regex_patterns("3"))
    
    @patch('web_api.get_udi_manager')
    @patch('web_api.get_regex_matcher')
    def test_bulk_edit_regex_pattern_new_format(self, mock_matcher_func, mock_udi_manager):
        """Test bulk edit regex pattern endpoint with new format."""
        from web_api import bulk_edit_regex_pattern
        from flask import Flask
        import json
        
        app = Flask(__name__)
        
        # Create actual matcher with temp config
        from automated_stream_manager import RegexChannelMatcher
        matcher = RegexChannelMatcher(self.config_file)
        mock_matcher_func.return_value = matcher
        
        # Mock UDI manager
        mock_udi = MagicMock()
        mock_udi.get_channel_by_id.side_effect = lambda cid: {
            'id': cid,
            'name': f'Channel {cid}'
        }
        mock_udi_manager.return_value = mock_udi
        
        # Test data - edit common pattern
        test_data = {
            'channel_ids': [1, 2, 3],
            'old_pattern': '.*common.*',
            'new_pattern': '.*updated.*'
        }
        
        with app.test_request_context(
            '/api/regex-patterns/bulk-edit',
            method='POST',
            data=json.dumps(test_data),
            content_type='application/json'
        ):
            response = bulk_edit_regex_pattern()
            response_data = json.loads(response.data)
            
            # Verify success
            self.assertEqual(response_data['success_count'], 3)
            self.assertEqual(response_data['total_channels'], 3)
            
            # Verify patterns were updated
            patterns = matcher.get_patterns()
            for channel_id in ['1', '2', '3']:
                channel_patterns = patterns['patterns'][channel_id]['regex_patterns']
                pattern_strings = [p['pattern'] for p in channel_patterns]
                
                # Old pattern should not exist
                self.assertNotIn('.*common.*', pattern_strings)
                
                # New pattern should exist
                self.assertIn('.*updated.*', pattern_strings)
    
    @patch('web_api.get_udi_manager')
    @patch('web_api.get_regex_matcher')
    def test_bulk_edit_regex_pattern_old_format(self, mock_matcher_func, mock_udi_manager):
        """Test bulk edit regex pattern endpoint with old format (backward compatibility)."""
        from web_api import bulk_edit_regex_pattern
        from flask import Flask
        import json
        from automated_stream_manager import RegexChannelMatcher
        
        app = Flask(__name__)
        
        # Create config with old format
        old_format_config = {
            "patterns": {
                "1": {
                    "name": "Channel 1",
                    "regex": [".*test.*", ".*common.*"],
                    "enabled": True,
                    "m3u_accounts": None
                },
                "2": {
                    "name": "Channel 2",
                    "regex": [".*common.*", ".*channel2.*"],
                    "enabled": True,
                    "m3u_accounts": None
                }
            },
            "global_settings": {
                "case_sensitive": True,
                "require_exact_match": False
            }
        }
        
        old_format_file = Path(self.temp_dir) / "old_format_config.json"
        with open(old_format_file, 'w') as f:
            json.dump(old_format_config, f)
        
        matcher = RegexChannelMatcher(old_format_file)
        mock_matcher_func.return_value = matcher
        
        # Mock UDI manager
        mock_udi = MagicMock()
        mock_udi.get_channel_by_id.side_effect = lambda cid: {
            'id': cid,
            'name': f'Channel {cid}'
        }
        mock_udi_manager.return_value = mock_udi
        
        # Test data - edit common pattern
        test_data = {
            'channel_ids': [1, 2],
            'old_pattern': '.*common.*',
            'new_pattern': '.*updated.*'
        }
        
        with app.test_request_context(
            '/api/regex-patterns/bulk-edit',
            method='POST',
            data=json.dumps(test_data),
            content_type='application/json'
        ):
            response = bulk_edit_regex_pattern()
            response_data = json.loads(response.data)
            
            # Verify success
            self.assertEqual(response_data['success_count'], 2)
            
            # Verify patterns were updated (should be migrated to new format)
            patterns = matcher.get_patterns()
            for channel_id in ['1', '2']:
                channel_patterns = patterns['patterns'][channel_id]['regex_patterns']
                pattern_strings = [p['pattern'] for p in channel_patterns]
                
                # Old pattern should not exist
                self.assertNotIn('.*common.*', pattern_strings)
                
                # New pattern should exist
                self.assertIn('.*updated.*', pattern_strings)
    
    @patch('web_api.get_regex_matcher')
    def test_get_common_regex_patterns_new_format(self, mock_matcher_func):
        """Test get common regex patterns endpoint with new format."""
        from web_api import get_common_regex_patterns
        from flask import Flask
        import json
        from automated_stream_manager import RegexChannelMatcher
        
        app = Flask(__name__)
        
        matcher = RegexChannelMatcher(self.config_file)
        mock_matcher_func.return_value = matcher
        
        # Test data - get common patterns across all channels
        test_data = {
            'channel_ids': [1, 2, 3]
        }
        
        with app.test_request_context(
            '/api/regex-patterns/common',
            method='POST',
            data=json.dumps(test_data),
            content_type='application/json'
        ):
            response = get_common_regex_patterns()
            response_data = json.loads(response.data)
            
            # Verify response structure
            self.assertIn('patterns', response_data)
            self.assertEqual(response_data['total_channels'], 3)
            
            # Find the common pattern
            common_pattern = None
            for pattern in response_data['patterns']:
                if pattern['pattern'] == '.*common.*':
                    common_pattern = pattern
                    break
            
            # Verify common pattern exists and appears in all 3 channels
            self.assertIsNotNone(common_pattern)
            self.assertEqual(common_pattern['count'], 3)
            self.assertEqual(common_pattern['percentage'], 100.0)
            self.assertEqual(set(common_pattern['channel_ids']), {'1', '2', '3'})
            
            # Verify unique patterns have lower counts
            for pattern in response_data['patterns']:
                if pattern['pattern'] in ['.*test.*', '.*channel2.*', '.*unique.*']:
                    self.assertEqual(pattern['count'], 1)
                    self.assertEqual(pattern['percentage'], 33.3)
    
    @patch('web_api.get_regex_matcher')
    def test_get_common_regex_patterns_old_format(self, mock_matcher_func):
        """Test get common regex patterns endpoint with old format (backward compatibility)."""
        from web_api import get_common_regex_patterns
        from flask import Flask
        import json
        from automated_stream_manager import RegexChannelMatcher
        
        app = Flask(__name__)
        
        # Create config with old format
        old_format_config = {
            "patterns": {
                "1": {
                    "name": "Channel 1",
                    "regex": [".*test.*", ".*common.*"],
                    "enabled": True
                },
                "2": {
                    "name": "Channel 2",
                    "regex": [".*common.*"],
                    "enabled": True
                }
            },
            "global_settings": {
                "case_sensitive": True,
                "require_exact_match": False
            }
        }
        
        old_format_file = Path(self.temp_dir) / "old_format_common.json"
        with open(old_format_file, 'w') as f:
            json.dump(old_format_config, f)
        
        matcher = RegexChannelMatcher(old_format_file)
        mock_matcher_func.return_value = matcher
        
        # Test data
        test_data = {
            'channel_ids': [1, 2]
        }
        
        with app.test_request_context(
            '/api/regex-patterns/common',
            method='POST',
            data=json.dumps(test_data),
            content_type='application/json'
        ):
            response = get_common_regex_patterns()
            response_data = json.loads(response.data)
            
            # Verify common pattern appears in both channels
            common_pattern = None
            for pattern in response_data['patterns']:
                if pattern['pattern'] == '.*common.*':
                    common_pattern = pattern
                    break
            
            self.assertIsNotNone(common_pattern)
            self.assertEqual(common_pattern['count'], 2)
            self.assertEqual(common_pattern['percentage'], 100.0)


if __name__ == '__main__':
    unittest.main()
