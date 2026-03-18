"""
Test that manual Quick Actions bypass feature flags.

This ensures that users can manually trigger playlist refresh and stream discovery
from the UI Quick Actions, even when automated features are disabled in the configuration.
"""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from apps.automation.automated_stream_manager import AutomatedStreamManager


class TestManualQuickActions(unittest.TestCase):
    """Test manual Quick Actions bypass feature flag checks."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_refresh_playlists_respects_feature_flag_by_default(self):
        """Test that refresh_playlists respects auto_playlist_update flag when force=False."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            manager = AutomatedStreamManager()
            # Disable the feature
            manager.config['enabled_features']['auto_playlist_update'] = False
            
            # Test with force=False (should respect flag)
            result = manager.refresh_playlists(force=False)
            self.assertFalse(result, "refresh_playlists should return False when feature is disabled and force=False")
            
            # Test without force parameter (should default to force=False)
            result = manager.refresh_playlists()
            self.assertFalse(result, "refresh_playlists should respect feature flag when called without force parameter")
    
    def test_refresh_playlists_bypasses_flag_when_forced(self):
        """Test that refresh_playlists with force=True bypasses the early return check."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            manager = AutomatedStreamManager()
            # Disable the feature
            manager.config['enabled_features']['auto_playlist_update'] = False
            manager.config['enabled_features']['changelog_tracking'] = False  # Disable to simplify test
            
            # Mock the underlying API call to avoid network issues
            with patch('automated_stream_manager.get_m3u_accounts', return_value=[{'id': 1, 'name': 'Test', 'is_active': True}]):
                with patch('automated_stream_manager.refresh_m3u_playlists', return_value=True) as mock_refresh:
                    # Test with force=True (should bypass flag and attempt refresh)
                    result = manager.refresh_playlists(force=True)
                    # Verify it attempted to call the refresh function (bypassed the early return)
                    mock_refresh.assert_called()
                    self.assertTrue(result, "refresh_playlists should succeed when force=True even if feature is disabled")
    
    def test_discover_and_assign_respects_feature_flag_by_default(self):
        """Test that discover_and_assign_streams respects auto_stream_discovery flag when force=False."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            manager = AutomatedStreamManager()
            # Disable the feature
            manager.config['enabled_features']['auto_stream_discovery'] = False
            
            # Test with force=False (should respect flag)
            result = manager.discover_and_assign_streams(force=False)
            self.assertEqual(result, {}, "discover_and_assign_streams should return empty dict when feature is disabled and force=False")
            
            # Test without force parameter (should default to force=False)
            result = manager.discover_and_assign_streams()
            self.assertEqual(result, {}, "discover_and_assign_streams should respect feature flag when called without force parameter")
    
    @patch('automated_stream_manager.get_streams')
    def test_discover_and_assign_bypasses_flag_when_forced(self, mock_get_streams):
        """Test that discover_and_assign_streams with force=True bypasses auto_stream_discovery flag."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            manager = AutomatedStreamManager()
            # Disable the feature
            manager.config['enabled_features']['auto_stream_discovery'] = False
            
            # Mock API responses
            mock_get_streams.return_value = []
            
            # Mock the regex matcher
            manager.regex_matcher.reload_patterns = Mock()
            
            # Test with force=True (should bypass flag and attempt discovery)
            result = manager.discover_and_assign_streams(force=True)
            # Should attempt to reload patterns and process
            manager.regex_matcher.reload_patterns.assert_called_once()


if __name__ == '__main__':
    unittest.main()
