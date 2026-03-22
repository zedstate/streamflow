#!/usr/bin/env python3
"""
Test that global action respects profile filtering.

When a profile is selected, global action should only queue channels
that are in that profile, not all channels.
"""

import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Set up environment before importing modules
os.environ['CONFIG_DIR'] = tempfile.mkdtemp()
os.environ['DISPATCHARR_URL'] = 'http://test'
os.environ['DISPATCHARR_API_KEY'] = 'test_key'

from apps.stream.stream_checker_service import StreamCheckerService
from profile_config import ProfileConfig


class TestGlobalActionProfileFiltering(unittest.TestCase):
    """Test global action profile filtering functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        os.environ['CONFIG_DIR'] = self.test_dir
        
        # Create a fresh service instance
        self.service = StreamCheckerService()
        self.service.running = True
        
        # Mock UDI to return test channels
        self.mock_udi = MagicMock()
        self.all_channels = [
            {'id': 1, 'name': 'Channel 1', 'channel_group_id': 1},
            {'id': 2, 'name': 'Channel 2', 'channel_group_id': 1},
            {'id': 3, 'name': 'Channel 3', 'channel_group_id': 2},
            {'id': 4, 'name': 'Channel 4', 'channel_group_id': 2},
            {'id': 5, 'name': 'Channel 5', 'channel_group_id': 3},
        ]
        self.mock_udi.get_channels.return_value = self.all_channels
        
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def _extract_queued_channels(self, mock_add):
        """Helper method to extract channel IDs from mock add_channels calls."""
        all_queued = []
        for call_args in mock_add.call_args_list:
            args, kwargs = call_args
            all_queued.extend(args[0])
        return all_queued

    @patch('stream_checker_service.get_udi_manager')
    @patch('stream_checker_service.get_channel_settings_manager')
    @patch('stream_checker_service.get_profile_config')
    def test_queue_all_channels_with_profile_filter(self, mock_get_profile_config, mock_get_settings, mock_get_udi):
        """Test that _queue_all_channels respects profile filtering."""
        # Setup mocks
        mock_get_udi.return_value = self.mock_udi
        
        # Mock channel settings to enable all channels
        mock_settings = MagicMock()
        mock_settings._settings = {}
        mock_settings.is_checking_enabled.return_value = True
        mock_settings.is_channel_enabled_by_group.return_value = True
        mock_get_settings.return_value = mock_settings
        
        # Mock profile config to use a specific profile
        mock_profile = MagicMock()
        mock_profile.is_using_profile.return_value = True
        mock_profile.get_selected_profile.return_value = 42
        mock_profile.get_config.return_value = {'selected_profile_name': 'Test Profile'}
        mock_get_profile_config.return_value = mock_profile
        
        # Mock UDI to return only channels 1, 2, and 5 in the profile
        profile_channels = [1, 2, 5]  # Only these channels are in the profile
        self.mock_udi.get_profile_channels.return_value = {
            'channels': profile_channels
        }
        
        # Mock the check queue to track what's added
        with patch.object(self.service.check_queue, 'add_channels', return_value=3) as mock_add:
            with patch.object(self.service.check_queue, 'remove_from_completed'):
                # Call _queue_all_channels
                self.service._queue_all_channels(force_check=False)
                
                # Verify that get_profile_channels was called
                self.mock_udi.get_profile_channels.assert_called_once_with(42)
                
                # Verify that add_channels was called with channels from the profile
                all_queued = self._extract_queued_channels(mock_add)
                
                # Should have queued only channels 1, 2, and 5
                self.assertEqual(set(all_queued), {1, 2, 5})
        
    @patch('stream_checker_service.get_udi_manager')
    @patch('stream_checker_service.get_channel_settings_manager')
    @patch('stream_checker_service.get_profile_config')
    def test_queue_all_channels_without_profile_filter(self, mock_get_profile_config, mock_get_settings, mock_get_udi):
        """Test that _queue_all_channels queues all channels when no profile is selected."""
        # Setup mocks
        mock_get_udi.return_value = self.mock_udi
        
        # Mock channel settings to enable all channels
        mock_settings = MagicMock()
        mock_settings._settings = {}
        mock_settings.is_checking_enabled.return_value = True
        mock_settings.is_channel_enabled_by_group.return_value = True
        mock_get_settings.return_value = mock_settings
        
        # Mock profile config to NOT use a specific profile
        mock_profile = MagicMock()
        mock_profile.is_using_profile.return_value = False  # No profile selected
        mock_get_profile_config.return_value = mock_profile
        
        # Mock the check queue to track what's added
        with patch.object(self.service.check_queue, 'add_channels', return_value=5) as mock_add:
            with patch.object(self.service.check_queue, 'remove_from_completed'):
                # Call _queue_all_channels
                self.service._queue_all_channels(force_check=False)
                
                # Verify that all channels were queued
                all_queued = self._extract_queued_channels(mock_add)
                
                # Should have queued all 5 channels
                self.assertEqual(set(all_queued), {1, 2, 3, 4, 5})


if __name__ == '__main__':
    unittest.main()
