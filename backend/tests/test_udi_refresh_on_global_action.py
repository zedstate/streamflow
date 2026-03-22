#!/usr/bin/env python3
"""
Test that verifies UDI cache is refreshed before scheduled global action starts.

This test ensures that when a scheduled global action is triggered, the UDI cache
is refreshed first to ensure we have current data from Dispatcharr.
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


class TestUDIRefreshOnGlobalAction(unittest.TestCase):
    """Test that UDI cache is refreshed before scheduled global action."""
    
    @patch('udi.get_udi_manager')
    @patch('automated_stream_manager.AutomatedStreamManager')
    def test_udi_refresh_called_before_global_action(self, mock_asm_class, mock_get_udi):
        """Test that UDI refresh_all is called at the start of global action."""
        from apps.stream.stream_checker_service import StreamCheckerService
        
        # Setup mocks
        mock_udi = Mock()
        mock_udi.refresh_all.return_value = True
        mock_udi.get_channels.return_value = []
        mock_udi.get_streams.return_value = []
        mock_get_udi.return_value = mock_udi
        
        # Mock the automation manager
        mock_manager = Mock()
        mock_manager.refresh_playlists.return_value = True
        mock_manager.discover_and_assign_streams.return_value = {}
        mock_asm_class.return_value = mock_manager
        
        # Create service instance
        service = StreamCheckerService()
        
        # Mock the methods called during global action
        with patch.object(service, '_queue_all_channels') as mock_queue:
            # Call the global action
            service._perform_global_action()
        
        # Verify that UDI refresh_all was called
        mock_udi.refresh_all.assert_called_once()
        
        # Verify the global action flag was set and cleared
        self.assertFalse(service.global_action_in_progress,
                        "global_action_in_progress should be False after completion")
    
    @patch('udi.get_udi_manager')
    @patch('automated_stream_manager.AutomatedStreamManager')
    def test_udi_refresh_happens_before_playlist_update(self, mock_asm_class, mock_get_udi):
        """Test that UDI refresh happens before M3U playlist update."""
        from apps.stream.stream_checker_service import StreamCheckerService
        
        # Track call order
        call_order = []
        
        # Setup mocks
        mock_udi = Mock()
        
        def udi_refresh_side_effect():
            call_order.append('udi_refresh')
            return True
        
        mock_udi.refresh_all.side_effect = udi_refresh_side_effect
        mock_udi.get_channels.return_value = []
        mock_udi.get_streams.return_value = []
        mock_get_udi.return_value = mock_udi
        
        # Mock the automation manager
        mock_manager = Mock()
        
        def playlist_refresh_side_effect():
            call_order.append('playlist_refresh')
            return True
        
        mock_manager.refresh_playlists.side_effect = playlist_refresh_side_effect
        mock_manager.discover_and_assign_streams.return_value = {}
        mock_asm_class.return_value = mock_manager
        
        # Create service instance
        service = StreamCheckerService()
        
        # Mock the methods called during global action
        with patch.object(service, '_queue_all_channels'):
            # Call the global action
            service._perform_global_action()
        
        # Verify the order: UDI refresh should happen before playlist refresh
        self.assertEqual(call_order[:2], ['udi_refresh', 'playlist_refresh'],
                        "UDI refresh should happen before playlist refresh")
    
    @patch('udi.get_udi_manager')
    @patch('automated_stream_manager.AutomatedStreamManager')
    def test_global_action_continues_even_if_udi_refresh_fails(self, mock_asm_class, mock_get_udi):
        """Test that global action continues even if UDI refresh fails."""
        from apps.stream.stream_checker_service import StreamCheckerService
        
        # Setup mocks - UDI refresh will fail
        mock_udi = Mock()
        mock_udi.refresh_all.side_effect = Exception("UDI refresh failed")
        mock_udi.get_channels.return_value = []
        mock_udi.get_streams.return_value = []
        mock_get_udi.return_value = mock_udi
        
        # Mock the automation manager
        mock_manager = Mock()
        mock_manager.refresh_playlists.return_value = True
        mock_manager.discover_and_assign_streams.return_value = {}
        mock_asm_class.return_value = mock_manager
        
        # Create service instance
        service = StreamCheckerService()
        
        # Mock the methods called during global action
        with patch.object(service, '_queue_all_channels') as mock_queue:
            # Call the global action - should not raise exception
            service._perform_global_action()
        
        # Verify that despite UDI refresh failure, other steps continued
        mock_manager.refresh_playlists.assert_called_once()
        mock_manager.discover_and_assign_streams.assert_called_once()
        mock_queue.assert_called_once()
        
        # Verify the global action flag was cleared
        self.assertFalse(service.global_action_in_progress,
                        "global_action_in_progress should be False after completion")


if __name__ == '__main__':
    unittest.main()
