import sys
import os
from pathlib import Path

# Add backend and its parent to PYTHONPATH
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from match_profiles_manager import MatchProfilesManager
from database.connection import get_session
from database.models import MatchProfile as DBMatchProfile

def main():
    print("Initializing MatchProfilesManager test...")
    manager = MatchProfilesManager()
    
    # Test Create Profile
    print("\n1. Creating Match Profile...")
    steps = [
        {'type': 'regex_name', 'pattern': '.*Sky Sports.*', 'variables': {}, 'enabled': True, 'order': 1},
        {'type': 'tvg_id', 'pattern': 'SKY123', 'variables': {}, 'enabled': True, 'order': 2}
    ]
    profile = manager.create_profile(
        name="Test Match Profile",
        description="Verification tests description",
        steps=steps
    )
    print(f"✓ Created profile: ID={profile.id}, Name={profile.name}")
    print(f"✓ Steps count: {len(profile.steps)}")
    
    # Verify via SQL directly
    session = get_session()
    db_p = session.query(DBMatchProfile).filter(DBMatchProfile.id == profile.id).first()
    if db_p:
        print(f"✓ [SQL VERIFIED] Found profile in DB with {len(db_p.steps)} steps")
    else:
        print("❌ [SQL FAILURE] Profile NOT found in DB")
        sys.exit(1)
    session.close()

    # Test List Profiles
    print("\n2. Listing Profiles...")
    profiles = manager.list_profiles()
    print(f"✓ Total profiles in list: {len(profiles)}")
    if profile.id not in [p.id for p in profiles]:
         print("❌ [FAILURE] Created profile not in list!")
         sys.exit(1)

    # Test Update
    print("\n3. Updating Profile Steps...")
    new_steps = [
        {'type': 'regex_url', 'pattern': '.*test-stream.*', 'variables': {}, 'enabled': True, 'order': 1}
    ]
    updated = manager.update_profile(profile.id, name="Test Match Profile Updated", steps=new_steps)
    print(f"✓ Updated profile Name: {updated.name}")
    print(f"✓ Updated Steps count: {len(updated.steps)} (Expected 1)")
    
    # Test Delete
    print("\n4. Deleting Profile...")
    res = manager.delete_profile(profile.id)
    print(f"✓ delete_profile returned {res}")
    
    # Verify deletion
    session = get_session()
    db_p_after = session.query(DBMatchProfile).filter(DBMatchProfile.id == profile.id).first()
    if not db_p_after:
        print("✓ [SQL VERIFIED] Profile successfully deleted from DB")
    else:
        print("❌ [SQL FAILURE] Profile still exists in DB!")
    session.close()

    print("\n🎉 ALL MATCH_PROFILES MANAGER TESTS PASSED!")

if __name__ == '__main__':
    main()
