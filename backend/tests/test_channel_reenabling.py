#!/usr/bin/env python3
"""
Test for channel re-enabling functionality.

This test verifies that the re_enable_channels_with_working_streams function
correctly identifies and re-enables channels that were previously disabled
but now have working streams.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, patch, MagicMock
from empty_channel_manager import (
    re_enable_channels_with_working_streams,
    trigger_channel_re_enabling
)


def test_re_enable_channels_basic_logic():
    """Test basic logic of re-enabling channels with working streams."""
    
    # Mock the UDI manager
    mock_udi = Mock()
    
    # Mock channels - 3 channels total, 2 disabled
    mock_channels = [
        {'id': 1, 'name': 'Channel 1', 'streams': [101, 102]},  # Has working streams
        {'id': 2, 'name': 'Channel 2', 'streams': [201]},       # Has working stream
        {'id': 3, 'name': 'Channel 3', 'streams': []},          # No streams
    ]
    
    # Mock profile channels - channels 1 and 2 are disabled, 3 is enabled
    mock_profile_channels = {
        'channels': [
            {'channel_id': 1, 'enabled': False},  # Disabled but has working streams -> should re-enable
            {'channel_id': 2, 'enabled': False},  # Disabled but has working streams -> should re-enable
            {'channel_id': 3, 'enabled': True},   # Already enabled -> skip
        ]
    }
    
    # Mock streams
    mock_streams = {
        101: {'id': 101, 'url': 'http://stream1.com'},
        102: {'id': 102, 'url': 'http://stream2.com'},
        201: {'id': 201, 'url': 'http://stream3.com'},
    }
    
    # Mock dead streams tracker - no streams are dead
    mock_tracker = Mock()
    mock_tracker.is_dead.return_value = False
    
    mock_udi.get_channels.return_value = mock_channels
    mock_udi.get_profile_channels.return_value = mock_profile_channels
    mock_udi.get_stream_by_id.side_effect = lambda sid: mock_streams.get(sid)
    
    # Mock API responses
    mock_response = Mock()
    mock_response.status_code = 200
    
    with patch('empty_channel_manager.get_udi_manager', return_value=mock_udi), \
         patch('empty_channel_manager.DeadStreamsTracker', return_value=mock_tracker), \
         patch('empty_channel_manager._get_base_url', return_value='http://test.com'), \
         patch('empty_channel_manager.requests.patch', return_value=mock_response), \
         patch('udi.fetcher._get_auth_headers', return_value={}):
        
        # Run the function
        enabled_count, total_checked = re_enable_channels_with_working_streams(
            profile_id=1,
            snapshot_channel_ids=[1, 2, 3]
        )
        
        # Should re-enable 2 channels (1 and 2)
        assert enabled_count == 2, f"Expected 2 channels re-enabled, got {enabled_count}"
        assert total_checked == 2, f"Expected 2 channels checked (disabled only), got {total_checked}"
        
        print("✓ Test passed: re_enable_channels_basic_logic")


def test_trigger_channel_re_enabling_with_snapshot():
    """Test that trigger function only works when snapshot is enabled."""
    
    with patch('empty_channel_manager.should_disable_empty_channels') as mock_should_disable:
        # Test case 1: Snapshot enabled with channel IDs
        mock_should_disable.return_value = (True, 1, [1, 2, 3])
        
        with patch('empty_channel_manager.re_enable_channels_with_working_streams', return_value=(2, 2)) as mock_reenable:
            result = trigger_channel_re_enabling()
            assert result == (2, 2), "Should return result when snapshot is enabled"
            mock_reenable.assert_called_once()
        
        # Test case 2: Snapshot disabled (snapshot_channel_ids is None)
        mock_should_disable.return_value = (True, 1, None)
        result = trigger_channel_re_enabling()
        assert result is None, "Should return None when snapshot is disabled"
        
        # Test case 3: Feature disabled
        mock_should_disable.return_value = (False, None, None)
        result = trigger_channel_re_enabling()
        assert result is None, "Should return None when feature is disabled"
        
        print("✓ Test passed: trigger_channel_re_enabling_with_snapshot")


def test_only_reenables_channels_with_working_streams():
    """Test that only channels with at least one working stream are re-enabled."""
    
    mock_udi = Mock()
    
    # Mock channels - some with all dead streams, some with working streams
    mock_channels = [
        {'id': 1, 'name': 'Channel 1', 'streams': [101, 102]},  # Mixed: one working, one dead
        {'id': 2, 'name': 'Channel 2', 'streams': [201, 202]},  # All dead
    ]
    
    mock_profile_channels = {
        'channels': [
            {'channel_id': 1, 'enabled': False},  # Should re-enable (has working stream)
            {'channel_id': 2, 'enabled': False},  # Should NOT re-enable (all dead)
        ]
    }
    
    mock_streams = {
        101: {'id': 101, 'url': 'http://working.com'},
        102: {'id': 102, 'url': 'http://dead.com'},
        201: {'id': 201, 'url': 'http://dead1.com'},
        202: {'id': 202, 'url': 'http://dead2.com'},
    }
    
    # Mock dead streams tracker
    mock_tracker = Mock()
    def is_dead_mock(url):
        return 'dead' in url
    mock_tracker.is_dead.side_effect = is_dead_mock
    
    mock_udi.get_channels.return_value = mock_channels
    mock_udi.get_profile_channels.return_value = mock_profile_channels
    mock_udi.get_stream_by_id.side_effect = lambda sid: mock_streams.get(sid)
    
    mock_response = Mock()
    mock_response.status_code = 200
    
    with patch('empty_channel_manager.get_udi_manager', return_value=mock_udi), \
         patch('empty_channel_manager.DeadStreamsTracker', return_value=mock_tracker), \
         patch('empty_channel_manager._get_base_url', return_value='http://test.com'), \
         patch('empty_channel_manager.requests.patch', return_value=mock_response) as mock_patch, \
         patch('udi.fetcher._get_auth_headers', return_value={}):
        
        enabled_count, total_checked = re_enable_channels_with_working_streams(
            profile_id=1,
            snapshot_channel_ids=[1, 2]
        )
        
        # Should only re-enable channel 1
        assert enabled_count == 1, f"Expected 1 channel re-enabled, got {enabled_count}"
        assert total_checked == 2, f"Expected 2 channels checked, got {total_checked}"
        
        # Verify the API was only called once (for channel 1)
        assert mock_patch.call_count == 1
        
        print("✓ Test passed: only_reenables_channels_with_working_streams")


if __name__ == '__main__':
    print("\n=== Running Channel Re-enabling Tests ===\n")
    
    try:
        test_re_enable_channels_basic_logic()
        test_trigger_channel_re_enabling_with_snapshot()
        test_only_reenables_channels_with_working_streams()
        
        print("\n✅ All tests passed!\n")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
