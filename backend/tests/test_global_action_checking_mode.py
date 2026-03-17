#!/usr/bin/env python3
"""
Unit test to verify that channel checking_mode setting is respected during global action.

This test verifies that when a global action is triggered:
1. Only channels with checking_mode='enabled' are queued
2. Channels with checking_mode='disabled' are excluded from the queue
"""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os
import queue

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stream_checker_service import StreamCheckerService
from channel_settings_manager import ChannelSettingsManager


class TestGlobalActionCheckingMode(unittest.TestCase):
    """Test that global action respects channel checking_mode settings."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_queue_all_channels_filters_by_checking_mode(self):
        """Test that _queue_all_channels only queues channels with checking enabled."""
        with patch('stream_checker_service.CONFIG_DIR', Path(self.temp_dir)):
            with patch('channel_settings_manager.CONFIG_DIR', Path(self.temp_dir)):
                # Reset singleton to ensure fresh instance
                import channel_settings_manager
                channel_settings_manager._channel_settings_manager = None
                
                service = StreamCheckerService()
                
                # Get the singleton instance and configure it
                from channel_settings_manager import get_channel_settings_manager
                channel_settings = get_channel_settings_manager()
                
                # Set up mock channels
                mock_channels = [
                    {'id': 1, 'name': 'Channel 1'},
                    {'id': 2, 'name': 'Channel 2'},
                    {'id': 3, 'name': 'Channel 3'},
                ]
                
                # Configure channels: 1 enabled (default), 2 disabled, 3 enabled
                channel_settings.set_channel_settings(2, checking_mode='disabled')
                
                # Mock UDI to return our test channels
                with patch('stream_checker_service.get_udi_manager') as mock_udi:
                    mock_udi_instance = Mock()
                    mock_udi_instance.get_channels.return_value = mock_channels
                    mock_udi.return_value = mock_udi_instance
                    
                    # Call _queue_all_channels
                    service._queue_all_channels(force_check=True)
                    
                    # Verify that only channels with checking enabled were queued
                    queued_channels = []
                    while not service.check_queue.queue.empty():
                        try:
                            _, channel_id = service.check_queue.queue.get_nowait()
                            queued_channels.append(channel_id)
                        except queue.Empty:
                            break
                    
                    # Should have 2 channels (1 and 3), not 2
                    self.assertIn(1, queued_channels, "Channel 1 (enabled) should be queued")
                    self.assertNotIn(2, queued_channels, "Channel 2 (disabled) should NOT be queued")
                    self.assertIn(3, queued_channels, "Channel 3 (enabled) should be queued")
    
    def test_queue_all_channels_with_all_disabled(self):
        """Test that _queue_all_channels handles case where all channels are disabled."""
        with patch('stream_checker_service.CONFIG_DIR', Path(self.temp_dir)):
            with patch('channel_settings_manager.CONFIG_DIR', Path(self.temp_dir)):
                # Reset singleton to ensure fresh instance
                import channel_settings_manager
                channel_settings_manager._channel_settings_manager = None
                
                service = StreamCheckerService()
                
                # Get the singleton instance and configure it
                from channel_settings_manager import get_channel_settings_manager
                channel_settings = get_channel_settings_manager()
                
                # Set up mock channels
                mock_channels = [
                    {'id': 1, 'name': 'Channel 1'},
                    {'id': 2, 'name': 'Channel 2'},
                ]
                
                # Disable all channels
                channel_settings.set_channel_settings(1, checking_mode='disabled')
                channel_settings.set_channel_settings(2, checking_mode='disabled')
                
                # Mock UDI to return our test channels
                with patch('stream_checker_service.get_udi_manager') as mock_udi:
                    mock_udi_instance = Mock()
                    mock_udi_instance.get_channels.return_value = mock_channels
                    mock_udi.return_value = mock_udi_instance
                    
                    # Call _queue_all_channels
                    service._queue_all_channels(force_check=True)
                    
                    # Check that no channels were queued
                    self.assertTrue(service.check_queue.queue.empty(), 
                                  "Queue should be empty when all channels are disabled")
    
    def test_global_action_respects_checking_mode(self):
        """Test that full global action respects checking_mode settings."""
        with patch('stream_checker_service.CONFIG_DIR', Path(self.temp_dir)):
            with patch('channel_settings_manager.CONFIG_DIR', Path(self.temp_dir)):
                # Reset singleton to ensure fresh instance
                import channel_settings_manager
                channel_settings_manager._channel_settings_manager = None
                
                service = StreamCheckerService()
                
                # Get the singleton instance and configure it
                from channel_settings_manager import get_channel_settings_manager
                channel_settings = get_channel_settings_manager()
                
                # Set up mock channels
                mock_channels = [
                    {'id': 1, 'name': 'Channel 1'},
                    {'id': 2, 'name': 'Channel 2'},
                ]
                
                # Disable channel 2
                channel_settings.set_channel_settings(2, checking_mode='disabled')
                
                # Mock UDI and automation manager
                with patch('stream_checker_service.get_udi_manager') as mock_udi:
                    with patch('automated_stream_manager.AutomatedStreamManager'):
                        mock_udi_instance = Mock()
                        mock_udi_instance.get_channels.return_value = mock_channels
                        mock_udi_instance.refresh_all.return_value = True
                        mock_udi.return_value = mock_udi_instance
                        
                        # Call global action
                        service._perform_global_action()
                        
                        # Check that only channel 1 was queued
                        queued_channels = []
                        while not service.check_queue.queue.empty():
                            try:
                                _, channel_id = service.check_queue.queue.get_nowait()
                                queued_channels.append(channel_id)
                            except queue.Empty:
                                break
                        
                        self.assertIn(1, queued_channels, "Channel 1 (enabled) should be queued")
                        self.assertNotIn(2, queued_channels, "Channel 2 (disabled) should NOT be queued")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
