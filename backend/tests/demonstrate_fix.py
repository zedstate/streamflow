#!/usr/bin/env python3
"""
Demonstration script showing how the active stream detection now works.

This script simulates the scenario from the issue where:
- Account 6 has profiles including profile 6
- Proxy status shows a channel using profile 6
- The system should correctly detect that account 6 has 1 active stream
"""

import sys
import os
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from udi.manager import UDIManager


def demonstrate_fix():
    """Demonstrate the fix for active stream detection."""
    print("=" * 80)
    print("Active Stream Detection Demonstration")
    print("=" * 80)
    print()
    
    # Create a UDI Manager instance
    manager = UDIManager()
    manager._initialized = True
    
    # Setup: Account 6 has profile 6 (as mentioned in the issue)
    manager._m3u_accounts_cache = [
        {
            'id': 6,
            'name': 'IPFS NewERA',
            'profiles': [
                {'id': 6, 'name': 'IPFS NewERA Default'},
                {'id': 7, 'name': 'IPFS NewERA Alternative'}
            ]
        },
        {
            'id': 5,
            'name': 'Other Account',
            'profiles': [
                {'id': 5, 'name': 'Other Profile'}
            ]
        }
    ]
    
    # Simulate the proxy status from the issue (simplified)
    proxy_status_from_issue = {
        'c4fa030c-a0b9-4df1-83fe-4680ed8f3c89': {
            'channel_id': 'c4fa030c-a0b9-4df1-83fe-4680ed8f3c89',
            'state': 'active',
            'stream_id': 11554,
            'stream_name': 'M+ LALIGA --> ELCANO',
            'm3u_profile_id': 6,
            'm3u_profile_name': 'IPFS NewERA Default',
            'client_count': 1,
            'clients': [
                {
                    'client_id': 'client_1767279803960_3331',
                    'user_agent': 'VLC/3.0.21 LibVLC/3.0.21'
                }
            ]
        }
    }
    
    print("Scenario from the issue:")
    print(f"  - Account 6 has profiles: {[p['name'] for p in manager._m3u_accounts_cache[0]['profiles']]}")
    print(f"  - Proxy status shows 1 active channel using profile 6")
    print()
    
    # Mock the proxy status method
    with patch.object(manager, '_get_proxy_status', return_value=proxy_status_from_issue):
        # Test the fix
        active_count = manager.get_active_streams_for_account(6)
        
        print("OLD BEHAVIOR (before fix):")
        print("  - Tried to match streams by m3u_account field")
        print("  - Could not correlate proxy status channel_id with database channels")
        print("  - Result: Account 6 has 0 active streams ❌")
        print()
        
        print("NEW BEHAVIOR (after fix):")
        print("  - Uses m3u_profile_id from proxy status")
        print("  - Maps profile 6 to account 6")
        print("  - Correctly detects active channel using that profile")
        print(f"  - Result: Account 6 has {active_count} active stream ✓")
        print()
    
    # Test with multiple active channels
    print("-" * 80)
    print("Additional test: Multiple channels from same account")
    print("-" * 80)
    print()
    
    multi_channel_status = {
        'channel-1': {
            'channel_id': 'channel-1',
            'state': 'active',
            'm3u_profile_id': 6,  # Account 6
            'client_count': 1
        },
        'channel-2': {
            'channel_id': 'channel-2',
            'state': 'active',
            'm3u_profile_id': 7,  # Also account 6
            'client_count': 1
        },
        'channel-3': {
            'channel_id': 'channel-3',
            'state': 'active',
            'm3u_profile_id': 5,  # Different account
            'client_count': 1
        }
    }
    
    with patch.object(manager, '_get_proxy_status', return_value=multi_channel_status):
        active_count_account_6 = manager.get_active_streams_for_account(6)
        active_count_account_5 = manager.get_active_streams_for_account(5)
        
        print(f"  - Account 6 has {active_count_account_6} active streams (profiles 6 and 7) ✓")
        print(f"  - Account 5 has {active_count_account_5} active stream (profile 5) ✓")
        print()
    
    print("=" * 80)
    print("Demonstration complete!")
    print("=" * 80)


if __name__ == '__main__':
    demonstrate_fix()
