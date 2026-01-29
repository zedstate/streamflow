#!/usr/bin/env python3
"""
Integration test demonstrating the fix for batch regex operations.

This script simulates the batch delete operation that was failing before the fix.
It creates a temporary configuration with regex patterns, then uses the RegexChannelMatcher
to delete patterns, showing that the delete_channel_pattern method now exists and works.
"""

import sys
import json
import tempfile
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from automated_stream_manager import RegexChannelMatcher


def test_batch_delete_integration():
    """Demonstrates the fix for the batch delete regex patterns issue."""
    
    print("=" * 70)
    print("Integration Test: Batch Delete Regex Patterns")
    print("=" * 70)
    
    # Create a temporary config file
    temp_dir = tempfile.mkdtemp()
    config_file = Path(temp_dir) / "channel_regex_config.json"
    
    # Create initial configuration with patterns
    initial_config = {
        "patterns": {
            "24": {
                "name": "Channel 24",
                "regex_patterns": [
                    {"pattern": ".*sports.*", "m3u_accounts": None},
                    {"pattern": ".*news.*", "m3u_accounts": None}
                ],
                "enabled": True
            },
            "25": {
                "name": "Channel 25",
                "regex_patterns": [
                    {"pattern": ".*movies.*", "m3u_accounts": None}
                ],
                "enabled": True
            },
            "26": {
                "name": "Channel 26",
                "regex_patterns": [
                    {"pattern": ".*series.*", "m3u_accounts": None}
                ],
                "enabled": True
            }
        },
        "global_settings": {
            "case_sensitive": True,
            "require_exact_match": False
        }
    }
    
    with open(config_file, 'w') as f:
        json.dump(initial_config, f, indent=2)
    
    print("\n✓ Created test configuration with patterns for channels 24, 25, 26")
    
    # Create RegexChannelMatcher instance
    matcher = RegexChannelMatcher(config_file)
    
    print("✓ Initialized RegexChannelMatcher")
    
    # Verify patterns exist before deletion
    print("\nBefore deletion:")
    for channel_id in ['24', '25', '26']:
        has_patterns = matcher.has_regex_patterns(channel_id)
        print(f"  Channel {channel_id}: {'Has patterns' if has_patterns else 'No patterns'}")
    
    # Simulate the batch delete operation that was failing
    print("\nSimulating batch delete operation...")
    channel_ids = [24, 25, 26]
    
    success_count = 0
    failed_channels = []
    
    for channel_id in channel_ids:
        try:
            # This was failing before with: 'RegexChannelMatcher' object has no attribute 'delete_channel_pattern'
            matcher.delete_channel_pattern(str(channel_id))
            success_count += 1
            print(f"  ✓ Successfully deleted patterns from channel {channel_id}")
        except Exception as e:
            print(f"  ✗ Error deleting patterns from channel {channel_id}: {e}")
            failed_channels.append({
                "channel_id": channel_id,
                "error": str(e)
            })
    
    # Verify patterns were deleted
    print("\nAfter deletion:")
    for channel_id in ['24', '25', '26']:
        has_patterns = matcher.has_regex_patterns(channel_id)
        print(f"  Channel {channel_id}: {'Has patterns' if has_patterns else 'No patterns'}")
    
    # Print results
    print("\n" + "=" * 70)
    print("Results:")
    print("=" * 70)
    print(f"Total channels processed: {len(channel_ids)}")
    print(f"Successfully deleted: {success_count}")
    print(f"Failed: {len(failed_channels)}")
    
    if failed_channels:
        print("\nFailed channels:")
        for fc in failed_channels:
            print(f"  - Channel {fc['channel_id']}: {fc['error']}")
        return False
    else:
        print("\n✅ All batch delete operations completed successfully!")
        print("✅ The fix is working correctly!")
        return True
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)


if __name__ == '__main__':
    success = test_batch_delete_integration()
    sys.exit(0 if success else 1)
