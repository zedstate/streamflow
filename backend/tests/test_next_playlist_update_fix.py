#!/usr/bin/env python3
"""
Unit tests for next_playlist_update fix.

This module tests:
- next_playlist_update shows a proper future time (not current time)
- automation_start_time is tracked correctly
- get_status() returns correct next_playlist_update in all states
"""

import unittest
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.automation.automated_stream_manager import AutomatedStreamManager


class TestNextPlaylistUpdateFix(unittest.TestCase):
    """Test next_playlist_update calculation fix."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_next_update_is_not_current_time(self):
        """Test that next_playlist_update is not the current time when automation just started."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            manager = AutomatedStreamManager()
            
            # Mock the refresh_playlists to not actually run
            with patch.object(manager, 'refresh_playlists', return_value=False):
                # Start automation
                manager.start_automation()
                
                # Give it a moment to start
                time.sleep(0.1)
                
                # Get status immediately
                status = manager.get_status()
                
                # Verify automation is running
                self.assertTrue(status['running'])
                
                # Verify next_playlist_update is NOT None
                self.assertIsNotNone(status['next_playlist_update'])
                
                # Parse the next update time
                next_update = datetime.fromisoformat(status['next_playlist_update'])
                current_time = datetime.now()
                
                # The next update should be in the future (at least 1 second from now)
                # but not more than the configured interval + 1 minute for safety
                interval_minutes = manager.config.get("playlist_update_interval_minutes", 5)
                time_diff = (next_update - current_time).total_seconds()
                
                self.assertGreater(
                    time_diff, 
                    1,  # At least 1 second in the future
                    f"next_playlist_update should be in the future, but was only {time_diff} seconds away"
                )
                
                self.assertLess(
                    time_diff,
                    (interval_minutes + 1) * 60,  # Not more than interval + 1 minute
                    f"next_playlist_update should be within interval, but was {time_diff/60} minutes away"
                )
                
                # Stop automation
                manager.stop_automation()
    
    def test_next_update_remains_stable_across_multiple_calls(self):
        """Test that next_playlist_update doesn't change on every status call."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            manager = AutomatedStreamManager()
            
            # Mock the refresh_playlists to not actually run
            with patch.object(manager, 'refresh_playlists', return_value=False):
                # Start automation
                manager.start_automation()
                
                # Give it a moment to start
                time.sleep(0.1)
                
                # Get status multiple times
                status1 = manager.get_status()
                time.sleep(0.5)  # Wait half a second
                status2 = manager.get_status()
                time.sleep(0.5)  # Wait another half second
                status3 = manager.get_status()
                
                # Parse times
                next_update1 = datetime.fromisoformat(status1['next_playlist_update'])
                next_update2 = datetime.fromisoformat(status2['next_playlist_update'])
                next_update3 = datetime.fromisoformat(status3['next_playlist_update'])
                
                # All three should be the same (or within 1 second due to timing)
                diff_1_2 = abs((next_update2 - next_update1).total_seconds())
                diff_2_3 = abs((next_update3 - next_update2).total_seconds())
                
                self.assertLess(
                    diff_1_2,
                    1.0,
                    "next_playlist_update should remain stable between status calls"
                )
                
                self.assertLess(
                    diff_2_3,
                    1.0,
                    "next_playlist_update should remain stable between status calls"
                )
                
                # Stop automation
                manager.stop_automation()
    
    def test_automation_start_time_is_tracked(self):
        """Test that automation_start_time is set when automation starts."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            manager = AutomatedStreamManager()
            
            # Initially should be None
            self.assertIsNone(manager.automation_start_time)
            
            # Mock the refresh_playlists to not actually run
            with patch.object(manager, 'refresh_playlists', return_value=False):
                # Start automation
                before_start = datetime.now()
                manager.start_automation()
                after_start = datetime.now()
                
                # Give it a moment to start
                time.sleep(0.1)
                
                # Should now have a start time
                self.assertIsNotNone(manager.automation_start_time)
                
                # Start time should be between before and after
                self.assertGreaterEqual(manager.automation_start_time, before_start)
                self.assertLessEqual(manager.automation_start_time, after_start)
                
                # Stop automation
                manager.stop_automation()
                
                # Start time should be cleared
                self.assertIsNone(manager.automation_start_time)
    
    def test_next_update_after_successful_playlist_update(self):
        """Test that next_playlist_update is calculated correctly after a successful update."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            manager = AutomatedStreamManager()
            manager.config['playlist_update_interval_minutes'] = 5
            
            # Start automation
            manager.start_automation()
            
            # Simulate a successful playlist update
            update_time = datetime.now()
            manager.last_playlist_update = update_time
            
            # Get status
            status = manager.get_status()
            
            # Parse next update time
            next_update = datetime.fromisoformat(status['next_playlist_update'])
            
            # Should be update_time + 5 minutes
            expected_next = update_time + timedelta(minutes=5)
            diff = abs((next_update - expected_next).total_seconds())
            
            self.assertLess(
                diff,
                1.0,
                f"next_playlist_update should be 5 minutes after last update, but was {diff} seconds off"
            )
            
            # Stop automation
            manager.stop_automation()
    
    def test_next_update_is_none_when_automation_stopped(self):
        """Test that next_playlist_update is None when automation is not running."""
        with patch('automated_stream_manager.CONFIG_DIR', Path(self.temp_dir)):
            manager = AutomatedStreamManager()
            
            # Get status when not running
            status = manager.get_status()
            
            # Should be None
            self.assertFalse(status['running'])
            self.assertIsNone(status['next_playlist_update'])


if __name__ == '__main__':
    unittest.main()
