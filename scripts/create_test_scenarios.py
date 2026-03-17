#!/usr/bin/env python3
import requests
import json
import sys

API_BASE = "http://localhost:5000/api"

def create_profile(name, description, parsing_config, checking_config, global_config):
    payload = {
        "name": name,
        "description": description,
        "m3u_update": parsing_config,
        "stream_matching": {"enabled": True},  # Default
        "stream_checking": checking_config,
        "global_action": global_config
    }
    
    try:
        response = requests.post(f"{API_BASE}/settings/automation/profiles", json=payload)
        response.raise_for_status()
        data = response.json()
        print(f"[+] Created profile '{name}': ID {data['id']}")
        return data['id']
    except Exception as e:
        print(f"[-] Failed to create profile '{name}': {e}")
        if hasattr(e, 'response') and e.response:
             print(f"    Response: {e.response.text}")
        return None

def assign_profile(channel_id, profile_id):
    payload = {
        "channel_id": channel_id,
        "profile_id": profile_id
    }
    try:
        response = requests.post(f"{API_BASE}/settings/automation/assign/channel", json=payload)
        response.raise_for_status()
        print(f"[+] Assigned profile {profile_id} to channel {channel_id}")
    except Exception as e:
        print(f"[-] Failed to assign profile to channel {channel_id}: {e}")

def verify_effective_profile(channel_id, expected_profile_id):
    try:
        response = requests.get(f"{API_BASE}/settings/automation/effective/{channel_id}")
        response.raise_for_status()
        data = response.json()
        effective_id = data.get('effective_profile_id')
        source = data.get('source')
        
        if effective_id == expected_profile_id:
            print(f"[SUCCESS] Channel {channel_id} has effective profile {effective_id} (Source: {source})")
        else:
            print(f"[FAIL] Channel {channel_id} has effective profile {effective_id}, expected {expected_profile_id}")
            
    except Exception as e:
        print(f"[-] Failed to verify effective profile for channel {channel_id}: {e}")

def main():
    print("--- Creating Test Automation Scenarios ---")
    
    # Scenario 1: Sports Premium
    # High bitrate, 1080p+, Priority: TG_1 (9) > TG_2 (10)
    sports_profile_id = create_profile(
        "Sports Premium",
        "High quality for main sports events",
        {"enabled": True, "playlists": []},
        {
            "enabled": True,
            "allow_revive": False,
            "stream_limit": 5,
            "min_resolution": "1080p",
            "min_fps": 50,
            "min_bitrate": 4000,
            "m3u_priority": [9, 10],  # TG_1, TG_2
            "grace_period": False
        },
        {"affected": True}
    )
    
    # Scenario 2: Fallback Reliable
    # Any resolution, allow revive, Priority: TDTChannels (7)
    fallback_profile_id = create_profile(
        "Fallback Reliable",
        "Low requirements, aims for uptime",
        {"enabled": True, "playlists": [7]}, # Only update from TDT
        {
            "enabled": True,
            "allow_revive": True,  # Revive dead streams
            "stream_limit": 0,    # No limit
            "min_resolution": "any",
            "min_fps": 0,
            "min_bitrate": 0,
            "m3u_priority": [7, 9, 10],  # TDT first
            "grace_period": True
        },
        {"affected": True}
    )

    # Scenario 3: Manual Maintenance
    # Excluded from global runs
    manual_profile_id = create_profile(
        "Manual Only",
        "Excluded from global automation cycles",
        {"enabled": False, "playlists": []},
        {
            "enabled": True,
            "allow_revive": False,
            "stream_limit": 0,
            "min_resolution": "any",
             "min_fps": 0,
            "min_bitrate": 0,
            "m3u_priority": [],
            "grace_period": False
        },
        {"affected": False} # Not affected by global run
    )

    if not all([sports_profile_id, fallback_profile_id, manual_profile_id]):
        print("[-] One or more profiles failed to create. Aborting assignment.")
        return

    print("\n--- Assigning Profiles ---")
    # Assign Sports Premium to M+ LaLiga (ID: 1)
    assign_profile(1, sports_profile_id)
    
    # Assign Fallback Reliable to DAZN F1 (ID: 16)
    assign_profile(16, fallback_profile_id)
    
    # Assign Manual Only to M+ LaLiga 2 (ID: 2)
    assign_profile(2, manual_profile_id)

    print("\n--- Verifying Assignments ---")
    verify_effective_profile(1, sports_profile_id)
    verify_effective_profile(16, fallback_profile_id)
    verify_effective_profile(2, manual_profile_id)

if __name__ == "__main__":
    main()
