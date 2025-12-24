#!/usr/bin/env python3
"""
Integration test for priority-based stream ordering bug fix.

This test verifies that when global priority mode is set to "all_streams",
streams from higher priority playlists are correctly ordered ahead of
streams from lower priority playlists, regardless of quality.

Reproduces the user's bug report:
- p1 with priority 100
- p2 with priority 0  
- Global priority mode set to "all_streams"
- Expected: p1's streams should rank higher than p2's streams
"""

import unittest
import os
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPriorityStreamOrdering(unittest.TestCase):
    """Integration test for priority-based stream ordering."""
    
    def setUp(self):
        """Set up test with a temporary config directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.old_config_dir = os.environ.get('CONFIG_DIR')
        os.environ['CONFIG_DIR'] = self.temp_dir
    
    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        
        # Restore original CONFIG_DIR
        if self.old_config_dir:
            os.environ['CONFIG_DIR'] = self.old_config_dir
        elif 'CONFIG_DIR' in os.environ:
            del os.environ['CONFIG_DIR']
    
    @patch('stream_checker_service.get_udi_manager')
    def test_all_streams_mode_respects_priority(self, mock_get_udi):
        """Test that all_streams mode properly prioritizes higher priority playlists."""
        from m3u_priority_config import M3UPriorityConfig
        from stream_checker_service import StreamCheckerService
        
        # Set up priority config with global mode "all_streams"
        priority_config = M3UPriorityConfig()
        priority_config.set_global_priority_mode('all_streams')
        
        # Set up mock UDI manager
        mock_udi = MagicMock()
        mock_get_udi.return_value = mock_udi
        
        # Create mock M3U accounts
        # p1 with priority 100 (high priority)
        # p2 with priority 0 (low priority)
        # Note: priority_mode is NOT set here - should fall back to global setting
        mock_m3u_account_p1 = {
            'id': 1,
            'name': 'p1',
            'priority': 100
        }
        
        mock_m3u_account_p2 = {
            'id': 2,
            'name': 'p2',
            'priority': 0
        }
        
        # Create mock streams
        # Stream from p1 with lower quality
        stream_p1 = {
            'id': 101,
            'm3u_account': 1,
            'url': 'http://p1.example.com/stream'
        }
        
        # Stream from p2 with higher quality
        stream_p2 = {
            'id': 201,
            'm3u_account': 2,
            'url': 'http://p2.example.com/stream'
        }
        
        # Set up UDI manager to return appropriate data
        def get_stream_by_id(stream_id):
            if stream_id == 101:
                return stream_p1
            elif stream_id == 201:
                return stream_p2
            return None
        
        def get_m3u_account_by_id(account_id):
            if account_id == 1:
                # Use global priority mode
                account = mock_m3u_account_p1.copy()
                account['priority_mode'] = priority_config.get_priority_mode(1)
                return account
            elif account_id == 2:
                # Use global priority mode
                account = mock_m3u_account_p2.copy()
                account['priority_mode'] = priority_config.get_priority_mode(2)
                return account
            return None
        
        mock_udi.get_stream_by_id.side_effect = get_stream_by_id
        mock_udi.get_m3u_account_by_id.side_effect = get_m3u_account_by_id
        
        # Create stream checker service
        service = StreamCheckerService()
        
        # Create mock stream data
        # p2's stream has better quality (higher bitrate, resolution, fps)
        stream_data_p2 = {
            'stream_id': 201,
            'bitrate_kbps': 5000,
            'resolution': '1920x1080',
            'fps': 60,
            'video_codec': 'h264'
        }
        
        # p1's stream has lower quality
        stream_data_p1 = {
            'stream_id': 101,
            'bitrate_kbps': 2000,
            'resolution': '1280x720',
            'fps': 30,
            'video_codec': 'h264'
        }
        
        # Calculate scores
        score_p1 = service._calculate_stream_score(stream_data_p1)
        score_p2 = service._calculate_stream_score(stream_data_p2)
        
        # With "all_streams" mode and priority 100 vs 0:
        # p1 should get a boost of 100 * 0.5 = 50 points
        # p2 should get 0 boost (priority 0)
        # Even though p2 has better quality, p1 should score higher due to priority
        
        self.assertGreater(score_p1, score_p2,
                          f"Stream from p1 (priority 100) should score higher than p2 (priority 0). "
                          f"p1 score: {score_p1}, p2 score: {score_p2}")
        
        # Verify that p1 got a significant boost
        self.assertGreater(score_p1, 40,
                          f"p1 should get significant priority boost. Score: {score_p1}")
    
    @patch('stream_checker_service.get_udi_manager')
    def test_disabled_mode_ignores_priority(self, mock_get_udi):
        """Test that disabled mode ignores priority and uses quality only."""
        from m3u_priority_config import M3UPriorityConfig
        from stream_checker_service import StreamCheckerService
        
        # Set up priority config with global mode "disabled"
        priority_config = M3UPriorityConfig()
        priority_config.set_global_priority_mode('disabled')
        
        # Set up mock UDI manager
        mock_udi = MagicMock()
        mock_get_udi.return_value = mock_udi
        
        # Create mock M3U accounts
        # Note: priority_mode is NOT set here - should fall back to global setting
        mock_m3u_account_p1 = {
            'id': 1,
            'name': 'p1',
            'priority': 100
        }
        
        mock_m3u_account_p2 = {
            'id': 2,
            'name': 'p2',
            'priority': 0
        }
        
        # Create mock streams
        stream_p1 = {
            'id': 101,
            'm3u_account': 1,
            'url': 'http://p1.example.com/stream'
        }
        
        stream_p2 = {
            'id': 201,
            'm3u_account': 2,
            'url': 'http://p2.example.com/stream'
        }
        
        # Set up UDI manager
        def get_stream_by_id(stream_id):
            if stream_id == 101:
                return stream_p1
            elif stream_id == 201:
                return stream_p2
            return None
        
        def get_m3u_account_by_id(account_id):
            if account_id == 1:
                account = mock_m3u_account_p1.copy()
                account['priority_mode'] = priority_config.get_priority_mode(1)
                return account
            elif account_id == 2:
                account = mock_m3u_account_p2.copy()
                account['priority_mode'] = priority_config.get_priority_mode(2)
                return account
            return None
        
        mock_udi.get_stream_by_id.side_effect = get_stream_by_id
        mock_udi.get_m3u_account_by_id.side_effect = get_m3u_account_by_id
        
        # Create stream checker service
        service = StreamCheckerService()
        
        # Create mock stream data
        # p2's stream has better quality
        stream_data_p2 = {
            'stream_id': 201,
            'bitrate_kbps': 5000,
            'resolution': '1920x1080',
            'fps': 60,
            'video_codec': 'h264'
        }
        
        # p1's stream has lower quality
        stream_data_p1 = {
            'stream_id': 101,
            'bitrate_kbps': 2000,
            'resolution': '1280x720',
            'fps': 30,
            'video_codec': 'h264'
        }
        
        # Calculate scores
        score_p1 = service._calculate_stream_score(stream_data_p1)
        score_p2 = service._calculate_stream_score(stream_data_p2)
        
        # With "disabled" mode, priority should be ignored
        # p2 should score higher due to better quality
        self.assertGreater(score_p2, score_p1,
                          f"With disabled mode, higher quality stream should win. "
                          f"p1 score: {score_p1}, p2 score: {score_p2}")
        
        # Verify neither got a priority boost
        self.assertLess(score_p1, 2.0,
                       f"p1 should not get priority boost in disabled mode. Score: {score_p1}")
        self.assertLess(score_p2, 2.0,
                       f"p2 should not get priority boost in disabled mode. Score: {score_p2}")


if __name__ == '__main__':
    unittest.main()
