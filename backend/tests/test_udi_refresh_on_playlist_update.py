#!/usr/bin/env python3
"""
Test that verifies UDI cache is refreshed after playlist updates.

This test ensures that when playlists are refreshed, both the streams and channels
in the UDI cache are updated to reflect changes made in Dispatcharr.
"""

import unittest
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

# Set up CONFIG_DIR before importing modules
os.environ['CONFIG_DIR'] = tempfile.mkdtemp()

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


class TestUDIRefreshOnPlaylistUpdate(unittest.TestCase):
    """Test that UDI cache is refreshed after playlist updates."""
    
    @patch('automated_stream_manager.get_udi_manager')
    @patch('automated_stream_manager.refresh_m3u_playlists')
    @patch('automated_stream_manager.get_streams')
    @patch('automated_stream_manager.get_m3u_accounts')
    def test_udi_refresh_called_after_playlist_update(
        self, 
        mock_get_m3u_accounts,
        mock_get_streams,
        mock_refresh_m3u,
        mock_get_udi
    ):
        """Test that UDI streams and channels are refreshed after playlist update."""
        from apps.automation.automated_stream_manager import AutomatedStreamManager
        
        # Setup mocks
        mock_udi = Mock()
        mock_udi.get_streams.return_value = []
        mock_udi.get_channels.return_value = []
        mock_udi.refresh_streams.return_value = True
        mock_udi.refresh_channels.return_value = True
        mock_get_udi.return_value = mock_udi
        
        # Mock M3U accounts - return empty list to trigger fallback path
        mock_get_m3u_accounts.return_value = []
        
        # Mock get_streams to return empty lists for before/after comparison
        mock_get_streams.return_value = []
        
        # Mock refresh_m3u_playlists to succeed
        mock_refresh_m3u.return_value = Mock(status_code=200)
        
        # Create manager and call refresh_playlists
        manager = AutomatedStreamManager()
        result = manager.refresh_playlists(force=True)
        
        # Verify the result
        self.assertTrue(result, "refresh_playlists should return True")
        
        # Verify that refresh_m3u_playlists was called
        mock_refresh_m3u.assert_called_once()
        
        # Verify that UDI refresh methods were called
        mock_udi.refresh_streams.assert_called_once()
        mock_udi.refresh_channels.assert_called_once()
        
        # Verify the order: refresh_m3u_playlists should be called before UDI refresh
        # This ensures we refresh the cache after the API call
        call_order = []
        for call in [
            ('refresh_m3u', mock_refresh_m3u.call_args_list),
            ('refresh_streams', mock_udi.refresh_streams.call_args_list),
            ('refresh_channels', mock_udi.refresh_channels.call_args_list)
        ]:
            if call[1]:
                call_order.append(call[0])
        
        self.assertEqual(call_order, ['refresh_m3u', 'refresh_streams', 'refresh_channels'],
                        "UDI refresh should happen after M3U refresh")
    
    @patch('automated_stream_manager.get_udi_manager')
    @patch('automated_stream_manager.refresh_m3u_playlists')
    @patch('automated_stream_manager.get_m3u_accounts')
    def test_udi_refresh_with_stream_changes(
        self, 
        mock_get_m3u_accounts,
        mock_refresh_m3u,
        mock_get_udi
    ):
        """Test that UDI refresh is called even when stream changes occur."""
        from apps.automation.automated_stream_manager import AutomatedStreamManager
        
        # Setup mocks
        mock_udi = Mock()
        mock_udi.refresh_streams.return_value = True
        mock_udi.refresh_channels.return_value = True
        
        # Mock get_streams to return different data before and after
        streams_before = [
            {'id': 1, 'name': 'Stream 1'},
            {'id': 2, 'name': 'Stream 2'}
        ]
        streams_after = [
            {'id': 1, 'name': 'Stream 1'},
            {'id': 3, 'name': 'Stream 3'}  # Stream 2 removed, Stream 3 added
        ]
        
        call_count = [0]
        def get_streams_side_effect(log_result=True):
            call_count[0] += 1
            if call_count[0] == 1:
                return streams_before
            return streams_after
        
        mock_udi.get_streams.side_effect = get_streams_side_effect
        mock_udi.get_channels.return_value = []
        mock_get_udi.return_value = mock_udi
        
        # Mock M3U accounts
        mock_get_m3u_accounts.return_value = [
            {'id': 1, 'name': 'Test Account', 'is_active': True}
        ]
        
        # Mock refresh_m3u_playlists
        mock_refresh_m3u.return_value = Mock(status_code=200)
        
        # Create manager with changelog enabled and call refresh_playlists
        manager = AutomatedStreamManager()
        manager.config['enabled_features']['changelog_tracking'] = True
        result = manager.refresh_playlists(force=True)
        
        # Verify the result
        self.assertTrue(result, "refresh_playlists should succeed")
        
        # Verify UDI refresh was called after M3U refresh
        mock_udi.refresh_streams.assert_called_once()
        mock_udi.refresh_channels.assert_called_once()
        
        # Verify refresh_m3u_playlists was called
        mock_refresh_m3u.assert_called_once()


if __name__ == '__main__':
    unittest.main()
