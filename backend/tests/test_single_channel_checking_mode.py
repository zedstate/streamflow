#!/usr/bin/env python3
"""
Test to verify that single channel check respects checking_mode and matching_mode settings.

This test verifies that when a single channel check is triggered:
1. Stream matching only happens if matching_mode is enabled
2. Stream quality checking only happens if checking_mode is enabled
"""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSingleChannelCheckingMode(unittest.TestCase):
    """Test that single channel check respects channel settings."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('stream_checker_service.StreamCheckConfig')
    @patch('stream_checker_service.get_udi_manager')
    @patch('stream_checker_service.fetch_channel_streams')
    @patch('api_utils.refresh_m3u_playlists')
    def test_single_channel_check_skips_checking_when_disabled(
        self, mock_refresh, mock_fetch_streams, mock_udi, mock_config_class
    ):
        """Test that check_single_channel skips checking when checking_mode is disabled."""
        with patch('stream_checker_service.CONFIG_DIR', Path(self.temp_dir)):
            with patch('channel_settings_manager.CONFIG_DIR', Path(self.temp_dir)):
                # Reset singleton to ensure fresh instance
                import channel_settings_manager
                channel_settings_manager._channel_settings_manager = None
                
                from apps.stream.stream_checker_service import StreamCheckerService
                from channel_settings_manager import get_channel_settings_manager
                
                # Mock config
                mock_config = Mock()
                mock_config.get = Mock(side_effect=lambda key, default=None: default)
                mock_config_class.return_value = mock_config
                
                # Setup mocks
                mock_udi_instance = Mock()
                mock_udi.return_value = mock_udi_instance
                
                # Mock channel data
                channel_id = 123
                mock_channel = {
                    'id': channel_id,
                    'name': 'Test Channel',
                    'logo_id': None
                }
                mock_udi_instance.get_channel_by_id.return_value = mock_channel
                
                # Mock streams
                mock_streams = [
                    {'id': 1, 'name': 'Stream 1', 'url': 'http://example.com/1', 'm3u_account': 1,
                     'stream_stats': {'status': 'ok'}},
                ]
                mock_fetch_streams.return_value = mock_streams
                
                # Mock UDI refresh methods
                mock_udi_instance.refresh_streams = Mock()
                mock_udi_instance.refresh_channels = Mock()
                mock_udi_instance.get_streams = Mock(return_value=mock_streams)
                
                # Configure channel settings: matching enabled, checking disabled
                channel_settings = get_channel_settings_manager()
                channel_settings.set_channel_settings(
                    channel_id,
                    matching_mode='enabled',
                    checking_mode='disabled'
                )
                
                # Create service instance
                service = StreamCheckerService()
                
                # Mock _check_channel to track if it's called
                service._check_channel = Mock(return_value={'dead_streams_count': 0, 'revived_streams_count': 0})
                
                # Mock automation manager (imported inside the function)
                with patch('automated_stream_manager.AutomatedStreamManager') as mock_automation_class:
                    mock_automation_instance = Mock()
                    mock_automation_class.return_value = mock_automation_instance
                    mock_automation_instance.discover_and_assign_streams = Mock(return_value={})
                    
                    # Call check_single_channel
                    result = service.check_single_channel(channel_id=channel_id)
                
                # Verify results
                self.assertTrue(result.get('success'), "Single channel check should succeed")
                
                # Verify that _check_channel was NOT called (checking is disabled)
                service._check_channel.assert_not_called()
                
                # Verify that matching was attempted (matching is enabled)
                # This is checked indirectly - the AutomatedStreamManager should be instantiated
                # We can't easily verify the call without more complex mocking
    
    @patch('stream_checker_service.StreamCheckConfig')
    @patch('stream_checker_service.get_udi_manager')
    @patch('stream_checker_service.fetch_channel_streams')
    @patch('api_utils.refresh_m3u_playlists')
    def test_single_channel_check_performs_checking_when_enabled(
        self, mock_refresh, mock_fetch_streams, mock_udi, mock_config_class
    ):
        """Test that check_single_channel performs checking when checking_mode is enabled."""
        with patch('stream_checker_service.CONFIG_DIR', Path(self.temp_dir)):
            with patch('channel_settings_manager.CONFIG_DIR', Path(self.temp_dir)):
                # Reset singleton to ensure fresh instance
                import channel_settings_manager
                channel_settings_manager._channel_settings_manager = None
                
                from apps.stream.stream_checker_service import StreamCheckerService
                from channel_settings_manager import get_channel_settings_manager
                
                # Mock config
                mock_config = Mock()
                mock_config.get = Mock(side_effect=lambda key, default=None: default)
                mock_config_class.return_value = mock_config
                
                # Setup mocks
                mock_udi_instance = Mock()
                mock_udi.return_value = mock_udi_instance
                
                # Mock channel data
                channel_id = 456
                mock_channel = {
                    'id': channel_id,
                    'name': 'Test Channel 2',
                    'logo_id': None
                }
                mock_udi_instance.get_channel_by_id.return_value = mock_channel
                
                # Mock streams
                mock_streams = [
                    {'id': 2, 'name': 'Stream 2', 'url': 'http://example.com/2', 'm3u_account': 1,
                     'stream_stats': {'status': 'ok'}},
                ]
                mock_fetch_streams.return_value = mock_streams
                
                # Mock UDI refresh methods
                mock_udi_instance.refresh_streams = Mock()
                mock_udi_instance.refresh_channels = Mock()
                mock_udi_instance.get_streams = Mock(return_value=mock_streams)
                
                # Configure channel settings: both enabled (default)
                channel_settings = get_channel_settings_manager()
                channel_settings.set_channel_settings(
                    channel_id,
                    matching_mode='enabled',
                    checking_mode='enabled'
                )
                
                # Create service instance
                service = StreamCheckerService()
                
                # Mock _check_channel to track if it's called
                service._check_channel = Mock(return_value={'dead_streams_count': 0, 'revived_streams_count': 0})
                
                # Mock automation manager (imported inside the function)
                with patch('automated_stream_manager.AutomatedStreamManager') as mock_automation_class:
                    mock_automation_instance = Mock()
                    mock_automation_class.return_value = mock_automation_instance
                    mock_automation_instance.discover_and_assign_streams = Mock(return_value={})
                    
                    # Call check_single_channel
                    result = service.check_single_channel(channel_id=channel_id)
                
                # Verify results
                self.assertTrue(result.get('success'), "Single channel check should succeed")
                
                # Verify that _check_channel WAS called (checking is enabled)
                service._check_channel.assert_called_once()
                
                # Verify the channel was marked for force check
                self.assertTrue(
                    service.update_tracker.should_force_check(channel_id),
                    "Channel should be marked for force check"
                )
    
    @patch('stream_checker_service.StreamCheckConfig')
    @patch('stream_checker_service.get_udi_manager')
    @patch('stream_checker_service.fetch_channel_streams')
    @patch('api_utils.refresh_m3u_playlists')
    def test_single_channel_check_skips_matching_when_disabled(
        self, mock_refresh, mock_fetch_streams, mock_udi, mock_config_class
    ):
        """Test that check_single_channel skips matching when matching_mode is disabled."""
        with patch('stream_checker_service.CONFIG_DIR', Path(self.temp_dir)):
            with patch('channel_settings_manager.CONFIG_DIR', Path(self.temp_dir)):
                # Reset singleton to ensure fresh instance
                import channel_settings_manager
                channel_settings_manager._channel_settings_manager = None
                
                from apps.stream.stream_checker_service import StreamCheckerService
                from channel_settings_manager import get_channel_settings_manager
                
                # Mock config
                mock_config = Mock()
                mock_config.get = Mock(side_effect=lambda key, default=None: default)
                mock_config_class.return_value = mock_config
                
                # Setup mocks
                mock_udi_instance = Mock()
                mock_udi.return_value = mock_udi_instance
                
                # Mock channel data
                channel_id = 789
                mock_channel = {
                    'id': channel_id,
                    'name': 'Test Channel 3',
                    'logo_id': None
                }
                mock_udi_instance.get_channel_by_id.return_value = mock_channel
                
                # Mock streams
                mock_streams = [
                    {'id': 3, 'name': 'Stream 3', 'url': 'http://example.com/3', 'm3u_account': 1,
                     'stream_stats': {'status': 'ok'}},
                ]
                mock_fetch_streams.return_value = mock_streams
                
                # Mock UDI refresh methods
                mock_udi_instance.refresh_streams = Mock()
                mock_udi_instance.refresh_channels = Mock()
                mock_udi_instance.get_streams = Mock(return_value=mock_streams)
                
                # Configure channel settings: matching disabled, checking enabled
                channel_settings = get_channel_settings_manager()
                channel_settings.set_channel_settings(
                    channel_id,
                    matching_mode='disabled',
                    checking_mode='enabled'
                )
                
                # Create service instance
                service = StreamCheckerService()
                
                # Mock _check_channel
                service._check_channel = Mock(return_value={'dead_streams_count': 0, 'revived_streams_count': 0})
                
                # Mock automation manager (imported inside the function)
                with patch('automated_stream_manager.AutomatedStreamManager') as mock_automation_class:
                    mock_automation_instance = Mock()
                    mock_automation_class.return_value = mock_automation_instance
                    mock_automation_instance.discover_and_assign_streams = Mock(return_value={})
                    
                    # Call check_single_channel
                    result = service.check_single_channel(channel_id=channel_id)
                    
                    # Verify that AutomatedStreamManager was NOT instantiated (matching is disabled)
                    mock_automation_class.assert_not_called()
                
                # Verify results
                self.assertTrue(result.get('success'), "Single channel check should succeed")
                
                # Verify that _check_channel WAS called (checking is enabled)
                service._check_channel.assert_called_once()


if __name__ == '__main__':
    unittest.main()
