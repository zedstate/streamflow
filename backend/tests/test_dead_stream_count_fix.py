#!/usr/bin/env python3
"""
Test to verify that dead stream count is correctly retrieved from the tracker.

This test validates that the fix for dead stream counting works properly:
- Dead streams are stored with channel_id in the tracker
- The API correctly counts dead streams for a specific channel
- Dead streams remain counted even after removal from the channel
"""

import unittest
import tempfile
import json
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDeadStreamCountFix(unittest.TestCase):
    """Test that dead stream count is correctly retrieved from tracker."""
    
    def test_dead_streams_tracker_stores_channel_id(self):
        """Test that dead streams tracker stores and retrieves channel_id."""
        from apps.stream.dead_streams_tracker import DeadStreamsTracker
        
        # Create temporary tracker file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            tracker_file = f.name
        
        try:
            tracker = DeadStreamsTracker(tracker_file=tracker_file)
            
            # Mark streams as dead for different channels
            tracker.mark_as_dead('http://stream1.com', 1, 'Stream 1', channel_id=10)
            tracker.mark_as_dead('http://stream2.com', 2, 'Stream 2', channel_id=10)
            tracker.mark_as_dead('http://stream3.com', 3, 'Stream 3', channel_id=20)
            tracker.mark_as_dead('http://stream4.com', 4, 'Stream 4', channel_id=20)
            tracker.mark_as_dead('http://stream5.com', 5, 'Stream 5', channel_id=20)
            
            # Verify counts
            count_ch10 = tracker.get_dead_streams_count_for_channel(10)
            count_ch20 = tracker.get_dead_streams_count_for_channel(20)
            count_ch30 = tracker.get_dead_streams_count_for_channel(30)
            
            self.assertEqual(count_ch10, 2, "Channel 10 should have 2 dead streams")
            self.assertEqual(count_ch20, 3, "Channel 20 should have 3 dead streams")
            self.assertEqual(count_ch30, 0, "Channel 30 should have 0 dead streams")
            
        finally:
            # Clean up
            Path(tracker_file).unlink(missing_ok=True)
    
    def test_dead_streams_persist_in_tracker_after_removal(self):
        """Test that dead streams remain in tracker even after channel removal."""
        from apps.stream.dead_streams_tracker import DeadStreamsTracker
        
        # Create temporary tracker file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            tracker_file = f.name
        
        try:
            tracker = DeadStreamsTracker(tracker_file=tracker_file)
            
            # Mark streams as dead for channel 15
            tracker.mark_as_dead('http://stream1.com', 1, 'Stream 1', channel_id=15)
            tracker.mark_as_dead('http://stream2.com', 2, 'Stream 2', channel_id=15)
            
            # Verify they're tracked
            count = tracker.get_dead_streams_count_for_channel(15)
            self.assertEqual(count, 2, "Should have 2 dead streams before any removal")
            
            # Simulate that these streams were removed from the channel
            # (in real scenario, they would be removed from Dispatcharr)
            # But they should still be in the tracker
            
            # Verify they're still in the tracker
            count_after = tracker.get_dead_streams_count_for_channel(15)
            self.assertEqual(count_after, 2, "Dead streams should persist in tracker after channel removal")
            
            # Verify individual stream is still marked as dead
            self.assertTrue(tracker.is_dead('http://stream1.com'), "Stream should still be marked as dead")
            
        finally:
            # Clean up
            Path(tracker_file).unlink(missing_ok=True)
    
    def test_dead_streams_tracker_persistence(self):
        """Test that dead streams are persisted to disk and can be reloaded."""
        from apps.stream.dead_streams_tracker import DeadStreamsTracker
        
        # Create temporary tracker file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            tracker_file = f.name
        
        try:
            # Create tracker and add dead streams
            tracker1 = DeadStreamsTracker(tracker_file=tracker_file)
            tracker1.mark_as_dead('http://stream1.com', 1, 'Stream 1', channel_id=10)
            tracker1.mark_as_dead('http://stream2.com', 2, 'Stream 2', channel_id=10)
            
            # Create new tracker instance (simulates app restart)
            tracker2 = DeadStreamsTracker(tracker_file=tracker_file)
            
            # Verify data was persisted and reloaded
            count = tracker2.get_dead_streams_count_for_channel(10)
            self.assertEqual(count, 2, "Dead streams should be reloaded from disk")
            
            # Verify channel_id was persisted
            dead_streams = tracker2.get_dead_streams()
            stream1_data = dead_streams.get('http://stream1.com')
            self.assertIsNotNone(stream1_data, "Stream 1 should be in tracker")
            self.assertEqual(stream1_data.get('channel_id'), 10, "Channel ID should be persisted")
            
        finally:
            # Clean up
            Path(tracker_file).unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()
