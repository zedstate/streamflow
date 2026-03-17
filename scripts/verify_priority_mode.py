#!/usr/bin/env python3
import requests
import json
import sys

API_BASE = "http://localhost:5000/api"

def create_priority_profile(name, mode):
    payload = {
        "name": name,
        "description": f"Test profile for {mode} priority",
        "m3u_update": {"enabled": True, "playlists": []},
        "stream_matching": {"enabled": True},
        "stream_checking": {
            "enabled": True,
            "allow_revive": True,
            "stream_limit": 0,
            "min_resolution": "any",
            "min_fps": 0,
            "min_bitrate": 0,
            "m3u_priority": [],
            "m3u_priority_mode": mode,
            "grace_period": False
        },
        "global_action": {"affected": True}
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

def verify_profile_mode(profile_id, expected_mode):
    try:
        response = requests.get(f"{API_BASE}/settings/automation/profiles")
        response.raise_for_status()
        profiles = response.json()
        
        profile = next((p for p in profiles if p['id'] == profile_id), None)
        if not profile:
            print(f"[-] Profile {profile_id} not found")
            return False
            
        actual_mode = profile.get('stream_checking', {}).get('m3u_priority_mode')
        if actual_mode == expected_mode:
            print(f"[SUCCESS] Profile {profile_id} has correct mode: {actual_mode}")
            return True
        else:
            print(f"[FAIL] Profile {profile_id} has mode {actual_mode}, expected {expected_mode}")
            return False
            
    except Exception as e:
        print(f"[-] Failed to verify profile {profile_id}: {e}")
        return False

def main():
    print("--- Verifying Priority Mode Persistence ---")
    
    # Test 1: Absolute Mode
    p1_id = create_priority_profile("Test Absolute", "absolute")
    if p1_id:
        verify_profile_mode(p1_id, "absolute")
        
    # Test 2: Same Resolution Mode
    p2_id = create_priority_profile("Test Same Res", "same_resolution")
    if p2_id:
        verify_profile_mode(p2_id, "same_resolution")

    # Test 3: Equal Mode
    p3_id = create_priority_profile("Test Equal", "equal")
    if p3_id:
        verify_profile_mode(p3_id, "equal")

if __name__ == "__main__":
    main()
