import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import logging
from database.connection import init_db
from automation_config_manager import get_automation_config_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Initializing Database...")
    init_db()
    
    manager = get_automation_config_manager()
    
    logger.info("--- Testing Global Settings ---")
    globals_data = manager.get_global_settings()
    logger.info(f"Global Settings: {globals_data}")
    
    logger.info("--- Testing Updating Global Settings ---")
    res = manager.update_global_settings(regular_automation_enabled=True)
    logger.info(f"Update Result: {res}")
    
    logger.info("--- Testing Get All Profiles ---")
    profiles = manager.get_all_profiles()
    logger.info(f"Found {len(profiles)} profiles")
    for p in profiles:
        logger.info(f"Profile: {p['id']} - {p['name']}")

    logger.info("--- Testing Create Profile ---")
    test_profile_data = {
        "name": "SQL Verify Profile",
        "description": "Created during SQL verification tests",
        "m3u_update": {"enabled": True, "playlists": []},
        "stream_checking": {"enabled": True}
    }
    pid = manager.create_profile(test_profile_data)
    logger.info(f"Created profile ID: {pid}")

    if pid:
        logger.info("--- Testing Get Single Profile ---")
        p = manager.get_profile(pid)
        logger.info(f"Fetched profile: {p}")

        logger.info("--- Testing Update Profile ---")
        res_update = manager.update_profile(pid, {"name": "SQL Verify Profile Updated"})
        logger.info(f"Update Result: {res_update}")
        
        p_updated = manager.get_profile(pid)
        logger.info(f"Fetched profile after update: {p_updated}")

        logger.info("--- Testing Delete Profile ---")
        res_del = manager.delete_profile(pid)
        logger.info(f"Delete Result: {res_del}")
        
        p_deleted = manager.get_profile(pid)
        logger.info(f"Fetched profile after delete (should be None): {p_deleted}")

    logger.info("Verification FINISHED successfully")

if __name__ == "__main__":
    main()
