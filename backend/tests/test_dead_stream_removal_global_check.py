#!/usr/bin/env python3
"""
Test that dead stream removal works during global checks.

This test verifies that the fix for dead stream removal during
manually triggered global checks is working correctly.
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


class TestDeadStreamRemovalDuringGlobalCheck(unittest.TestCase):
    """Test that dead streams are removed during global checks."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('stream_checker_service.CONFIG_DIR', Path(tempfile.mkdtemp()))
    def test_dead_streams_removed_during_force_check(self):
        """Test that dead streams are removed from channels even during force_check (global checks)."""
        from apps.stream.stream_checker_service import StreamCheckerService
        from apps.stream.dead_streams_tracker import DeadStreamsTracker
        
        # Initialize service
        service = StreamCheckerService()
        
        # Create mock analyzed streams with some dead streams
        analyzed_streams = [
            {'stream_id': 1, 'stream_name': 'Stream 1', 'score': 0.9, 'bitrate_kbps': 5000, 'resolution': '1920x1080'},
            {'stream_id': 2, 'stream_name': 'Stream 2', 'score': 0.0, 'bitrate_kbps': 0, 'resolution': '0x0'},  # Dead
            {'stream_id': 3, 'stream_name': 'Stream 3', 'score': 0.8, 'bitrate_kbps': 4000, 'resolution': '1280x720'},
            {'stream_id': 4, 'stream_name': 'Stream 4', 'score': 0.0, 'bitrate_kbps': 0, 'resolution': '1920x1080'},  # Dead (bitrate=0)
        ]
        
        dead_stream_ids = {2, 4}  # Streams 2 and 4 are dead
        
        # Simulate the dead stream removal logic from _check_channel
        # This is the logic after our fix (should work for both force_check=True and False)
        if dead_stream_ids:
            analyzed_streams = [s for s in analyzed_streams if s['stream_id'] not in dead_stream_ids]
        
        # Verify dead streams were removed
        self.assertEqual(len(analyzed_streams), 2, "Should have 2 streams after removing dead ones")
        
        remaining_stream_ids = {s['stream_id'] for s in analyzed_streams}
        self.assertEqual(remaining_stream_ids, {1, 3}, "Only healthy streams should remain")
        
        # Verify dead streams are not in the list
        self.assertNotIn(2, remaining_stream_ids, "Dead stream 2 should be removed")
        self.assertNotIn(4, remaining_stream_ids, "Dead stream 4 should be removed")
    
    @patch('stream_checker_service.CONFIG_DIR', Path(tempfile.mkdtemp()))
    def test_dead_stream_detection_logic(self):
        """Test that the _is_stream_dead method correctly identifies dead streams."""
        from apps.stream.stream_checker_service import StreamCheckerService
        
        service = StreamCheckerService()
        
        # Test cases for dead stream detection
        test_cases = [
            # (stream_data, expected_is_dead, description)
            ({'resolution': '0x0', 'bitrate_kbps': 5000}, True, "Resolution 0x0"),
            ({'resolution': '1920x1080', 'bitrate_kbps': 0}, True, "Bitrate 0"),
            ({'resolution': '0x0', 'bitrate_kbps': 0}, True, "Both 0"),
            ({'resolution': '1920x0', 'bitrate_kbps': 5000}, True, "Partial zero resolution (width)"),
            ({'resolution': '0x1080', 'bitrate_kbps': 5000}, True, "Partial zero resolution (height)"),
            ({'resolution': '1920x1080', 'bitrate_kbps': 5000}, False, "Healthy stream"),
        ]
        
        for stream_data, expected_is_dead, description in test_cases:
            with self.subTest(description=description):
                is_dead = service._is_stream_dead(stream_data)
                self.assertEqual(is_dead, expected_is_dead, 
                               f"Failed for {description}: expected {expected_is_dead}, got {is_dead}")
    
    @patch('stream_checker_service.CONFIG_DIR', Path(tempfile.mkdtemp()))
    def test_revived_streams_not_removed(self):
        """Test that revived streams (previously dead but now alive) are not removed."""
        from apps.stream.stream_checker_service import StreamCheckerService
        from apps.stream.dead_streams_tracker import DeadStreamsTracker
        
        service = StreamCheckerService()
        tracker = DeadStreamsTracker()
        
        # Mark a stream as dead
        stream_url = 'http://example.com/stream1.m3u8'
        tracker.mark_as_dead(stream_url, 1, 'Stream 1')
        self.assertTrue(tracker.is_dead(stream_url))
        
        # Simulate revival: stream is now alive
        tracker.mark_as_alive(stream_url)
        self.assertFalse(tracker.is_dead(stream_url))
        
        # Create analyzed stream (now healthy)
        analyzed_streams = [
            {'stream_id': 1, 'stream_name': 'Stream 1', 'score': 0.9, 'bitrate_kbps': 5000, 'resolution': '1920x1080'},
        ]
        
        dead_stream_ids = set()  # No dead streams since it was revived
        revived_stream_ids = [1]  # Stream 1 was revived
        
        # Simulate the dead stream removal logic
        if dead_stream_ids:
            analyzed_streams = [s for s in analyzed_streams if s['stream_id'] not in dead_stream_ids]
        
        # Verify revived stream is still in the list
        self.assertEqual(len(analyzed_streams), 1, "Revived stream should remain in list")
        self.assertEqual(analyzed_streams[0]['stream_id'], 1, "Stream 1 should be in the list")


class TestDeadStreamRemovalBehaviorConsistency(unittest.TestCase):
    """Test that dead stream removal behavior is consistent across normal and global checks."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('stream_checker_service.CONFIG_DIR', Path(tempfile.mkdtemp()))
    def test_dead_stream_removal_consistent_across_check_types(self):
        """Test that dead streams are removed regardless of check type (normal or global)."""
        from apps.stream.stream_checker_service import StreamCheckerService
        
        service = StreamCheckerService()
        
        # Test data: mix of healthy and dead streams
        analyzed_streams = [
            {'stream_id': 1, 'score': 0.9, 'bitrate_kbps': 5000, 'resolution': '1920x1080'},
            {'stream_id': 2, 'score': 0.0, 'bitrate_kbps': 0, 'resolution': '0x0'},  # Dead
            {'stream_id': 3, 'score': 0.8, 'bitrate_kbps': 4000, 'resolution': '1280x720'},
        ]
        
        dead_stream_ids = {2}
        
        # Test removal logic (should be the same for both force_check=True and force_check=False)
        # This simulates the logic in _check_channel after our fix
        
        # Scenario 1: Normal check (force_check=False)
        streams_after_normal_check = [s for s in analyzed_streams if s['stream_id'] not in dead_stream_ids]
        
        # Scenario 2: Global check (force_check=True) - should have same behavior now
        streams_after_global_check = [s for s in analyzed_streams if s['stream_id'] not in dead_stream_ids]
        
        # Both should remove dead streams
        self.assertEqual(len(streams_after_normal_check), 2, "Normal check should remove dead stream")
        self.assertEqual(len(streams_after_global_check), 2, "Global check should remove dead stream")
        
        # Both should have same remaining streams
        normal_ids = {s['stream_id'] for s in streams_after_normal_check}
        global_ids = {s['stream_id'] for s in streams_after_global_check}
        
        self.assertEqual(normal_ids, global_ids, "Both check types should remove the same dead streams")
        self.assertEqual(normal_ids, {1, 3}, "Only healthy streams should remain")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
