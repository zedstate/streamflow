#!/usr/bin/env python3
"""
Test script to verify channel profile fetching from Dispatcharr API.

This script tests the complete flow:
1. Environment configuration
2. Authentication
3. API call to /api/channels/profiles/
4. Response parsing and validation
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.udi.fetcher import UDIFetcher
from apps.config.dispatcharr_config import get_dispatcharr_config
from apps.core.logging_config import setup_logging

logger = setup_logging(__name__)


def test_profile_fetching():
    """Test channel profile fetching."""
    print("=" * 60)
    print("Testing Dispatcharr Channel Profile Fetching")
    print("=" * 60)
    
    # Check configuration
    print("\n1. Checking configuration...")
    config = get_dispatcharr_config()
    base_url = config.get_base_url()
    username = config.get_username()
    
    if not base_url:
        print("❌ ERROR: DISPATCHARR_BASE_URL not configured")
        print("   Please set it in .env file or environment variable")
        return False
    
    if not username:
        print("❌ ERROR: DISPATCHARR_USER not configured")
        print("   Please set it in .env file or environment variable")
        return False
    
    print(f"✓ Base URL: {base_url}")
    print(f"✓ Username: {username}")
    
    # Initialize fetcher
    print("\n2. Initializing UDI Fetcher...")
    fetcher = UDIFetcher()
    print("✓ Fetcher initialized")
    
    # Test profile fetching
    print("\n3. Fetching channel profiles...")
    print(f"   API Endpoint: {base_url}/api/channels/profiles/")
    
    profiles = fetcher.fetch_channel_profiles()
    
    if profiles is None:
        print("❌ ERROR: Received None response")
        print("   Possible causes:")
        print("   - Authentication failed")
        print("   - Network connection issue")
        print("   - Dispatcharr server not responding")
        return False
    
    if not isinstance(profiles, list):
        print(f"❌ ERROR: Unexpected response type: {type(profiles).__name__}")
        print(f"   Response: {profiles}")
        return False
    
    # Analyze results
    print(f"\n✓ Successfully fetched {len(profiles)} channel profiles")
    
    if len(profiles) == 0:
        print("\n⚠️  WARNING: No profiles found!")
        print("   Possible causes:")
        print("   - No channel profiles have been created in Dispatcharr")
        print("   - User account lacks permissions to view profiles")
        print("   - Profiles exist but API is not returning them")
        print("\n   Next steps:")
        print("   1. Log into Dispatcharr web interface")
        print("   2. Navigate to Channels > Profiles")
        print("   3. Create at least one channel profile if none exist")
        print("   4. Re-run this test")
        return True  # Not an error, just no data
    
    # Display profile details
    print("\n4. Profile Details:")
    print("-" * 60)
    for i, profile in enumerate(profiles, 1):
        print(f"\nProfile {i}:")
        print(f"  ID: {profile.get('id', 'N/A')}")
        print(f"  Name: {profile.get('name', 'N/A')}")
        channels = profile.get('channels', 'N/A')
        if isinstance(channels, str):
            print(f"  Channels: {channels[:100]}{'...' if len(channels) > 100 else ''}")
        else:
            print(f"  Channels: {channels}")
    
    print("\n" + "=" * 60)
    print("✓ Test completed successfully!")
    print("=" * 60)
    return True


def main():
    """Main entry point."""
    try:
        success = test_profile_fetching()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logger.exception("Test failed with exception")
        sys.exit(1)


if __name__ == "__main__":
    main()
