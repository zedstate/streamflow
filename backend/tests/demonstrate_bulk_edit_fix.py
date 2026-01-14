#!/usr/bin/env python3
"""
Integration test demonstrating the fix for bulk edit regex patterns.

This script simulates the bulk edit operation and shows that it now works
correctly with both old and new pattern formats.
"""

import sys
import json
import tempfile
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from automated_stream_manager import RegexChannelMatcher


def test_bulk_edit_new_format():
    """Test bulk edit with new pattern format."""
    
    print("\n" + "=" * 70)
    print("Test 1: Bulk Edit with New Pattern Format")
    print("=" * 70)
    
    temp_dir = tempfile.mkdtemp()
    config_file = Path(temp_dir) / "test_config.json"
    
    # Create config with new format
    config = {
        "patterns": {
            "1": {
                "name": "Channel 1",
                "regex_patterns": [
                    {"pattern": ".*test.*", "m3u_accounts": None},
                    {"pattern": ".*common.*", "m3u_accounts": None}
                ],
                "enabled": True
            },
            "2": {
                "name": "Channel 2",
                "regex_patterns": [
                    {"pattern": ".*common.*", "m3u_accounts": None},
                    {"pattern": ".*unique.*", "m3u_accounts": None}
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
        json.dump(config, f, indent=2)
    
    matcher = RegexChannelMatcher(config_file)
    
    print("\n✓ Created configuration with common pattern '.*common.*' in channels 1 and 2")
    
    # Show original patterns
    print("\nOriginal patterns:")
    for channel_id in ['1', '2']:
        patterns = matcher.get_patterns()['patterns'][channel_id]['regex_patterns']
        pattern_strings = [p['pattern'] for p in patterns]
        print(f"  Channel {channel_id}: {pattern_strings}")
    
    # Simulate bulk edit - replace '.*common.*' with '.*updated.*'
    print("\nEditing pattern '.*common.*' -> '.*updated.*' across all channels...")
    
    for channel_id in ['1', '2']:
        patterns = matcher.get_patterns()['patterns'][channel_id]
        regex_patterns = patterns.get('regex_patterns', [])
        
        # Find and replace
        updated_patterns = []
        for pattern_obj in regex_patterns:
            if pattern_obj.get('pattern') == '.*common.*':
                updated_patterns.append({
                    "pattern": '.*updated.*',
                    "m3u_accounts": pattern_obj.get('m3u_accounts')
                })
            else:
                updated_patterns.append(pattern_obj)
        
        # Update
        matcher.add_channel_pattern(
            channel_id,
            patterns['name'],
            updated_patterns,
            patterns.get('enabled', True)
        )
    
    print("✓ Bulk edit completed")
    
    # Show updated patterns
    print("\nUpdated patterns:")
    for channel_id in ['1', '2']:
        patterns = matcher.get_patterns()['patterns'][channel_id]['regex_patterns']
        pattern_strings = [p['pattern'] for p in patterns]
        print(f"  Channel {channel_id}: {pattern_strings}")
    
    # Verify
    all_patterns = matcher.get_patterns()
    for channel_id in ['1', '2']:
        channel_patterns = all_patterns['patterns'][channel_id]['regex_patterns']
        pattern_strings = [p['pattern'] for p in channel_patterns]
        
        if '.*common.*' in pattern_strings:
            print(f"\n✗ ERROR: Old pattern still exists in channel {channel_id}")
            return False
        
        if '.*updated.*' not in pattern_strings:
            print(f"\n✗ ERROR: New pattern not found in channel {channel_id}")
            return False
    
    print("\n✅ Test 1 PASSED: Bulk edit with new format works correctly!")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    return True


def test_bulk_edit_old_format():
    """Test bulk edit with old pattern format (backward compatibility)."""
    
    print("\n" + "=" * 70)
    print("Test 2: Bulk Edit with Old Pattern Format (Backward Compatibility)")
    print("=" * 70)
    
    temp_dir = tempfile.mkdtemp()
    config_file = Path(temp_dir) / "test_config_old.json"
    
    # Create config with old format
    config = {
        "patterns": {
            "1": {
                "name": "Channel 1",
                "regex": [".*test.*", ".*common.*"],
                "enabled": True,
                "m3u_accounts": None
            },
            "2": {
                "name": "Channel 2",
                "regex": [".*common.*", ".*unique.*"],
                "enabled": True,
                "m3u_accounts": None
            }
        },
        "global_settings": {
            "case_sensitive": True,
            "require_exact_match": False
        }
    }
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    matcher = RegexChannelMatcher(config_file)
    
    print("\n✓ Created configuration with old format (using 'regex' field)")
    print("  (System should auto-migrate to new format)")
    
    # Show original patterns
    print("\nOriginal patterns (after auto-migration):")
    for channel_id in ['1', '2']:
        patterns = matcher.get_patterns()['patterns'][channel_id]['regex_patterns']
        pattern_strings = [p['pattern'] for p in patterns]
        print(f"  Channel {channel_id}: {pattern_strings}")
    
    # Simulate bulk edit
    print("\nEditing pattern '.*common.*' -> '.*new.*' across all channels...")
    
    for channel_id in ['1', '2']:
        patterns = matcher.get_patterns()['patterns'][channel_id]
        regex_patterns = patterns.get('regex_patterns', [])
        
        # Find and replace
        updated_patterns = []
        for pattern_obj in regex_patterns:
            if pattern_obj.get('pattern') == '.*common.*':
                updated_patterns.append({
                    "pattern": '.*new.*',
                    "m3u_accounts": pattern_obj.get('m3u_accounts')
                })
            else:
                updated_patterns.append(pattern_obj)
        
        # Update
        matcher.add_channel_pattern(
            channel_id,
            patterns['name'],
            updated_patterns,
            patterns.get('enabled', True)
        )
    
    print("✓ Bulk edit completed")
    
    # Show updated patterns
    print("\nUpdated patterns:")
    for channel_id in ['1', '2']:
        patterns = matcher.get_patterns()['patterns'][channel_id]['regex_patterns']
        pattern_strings = [p['pattern'] for p in patterns]
        print(f"  Channel {channel_id}: {pattern_strings}")
    
    # Verify
    all_patterns = matcher.get_patterns()
    for channel_id in ['1', '2']:
        channel_patterns = all_patterns['patterns'][channel_id]['regex_patterns']
        pattern_strings = [p['pattern'] for p in channel_patterns]
        
        if '.*common.*' in pattern_strings:
            print(f"\n✗ ERROR: Old pattern still exists in channel {channel_id}")
            return False
        
        if '.*new.*' not in pattern_strings:
            print(f"\n✗ ERROR: New pattern not found in channel {channel_id}")
            return False
    
    print("\n✅ Test 2 PASSED: Bulk edit with old format works correctly!")
    print("  (Backward compatibility confirmed)")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    return True


if __name__ == '__main__':
    print("=" * 70)
    print("Integration Test: Bulk Edit Regex Patterns")
    print("=" * 70)
    
    test1_passed = test_bulk_edit_new_format()
    test2_passed = test_bulk_edit_old_format()
    
    print("\n" + "=" * 70)
    print("Final Results:")
    print("=" * 70)
    print(f"Test 1 (New Format): {'✅ PASSED' if test1_passed else '✗ FAILED'}")
    print(f"Test 2 (Old Format): {'✅ PASSED' if test2_passed else '✗ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n✅ ALL TESTS PASSED - Bulk edit operations are working correctly!")
        sys.exit(0)
    else:
        print("\n✗ SOME TESTS FAILED")
        sys.exit(1)
