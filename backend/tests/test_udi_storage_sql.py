import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import logging
from database.connection import init_db
from udi.storage import UDIStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Initializing Database...")
    init_db()
    
    storage = UDIStorage()
    
    logger.info("--- Testing Metadata load/save ---")
    storage.save_metadata({"version": 1.0, "test": True})
    metadata = storage.load_metadata()
    logger.info(f"Loaded Metadata: {metadata}")

    logger.info("--- Testing Save Channel ---")
    test_channels = [
        {
            "id": 9999,
            "name": "SQL Test Channel",
            "channel_number": 99,
            "streams": [] # No stream links for now
        }
    ]
    res_save = storage.save_channels(test_channels)
    logger.info(f"Save Channels Result: {res_save}")
    
    logger.info("--- Testing Load Channels ---")
    channels = storage.load_channels()
    logger.info(f"Loaded {len(channels)} channels")
    found = False
    for c in channels:
        if c['id'] == 9999:
            logger.info(f"Found saved channel: {c}")
            found = True
            break
    
    if not found:
        logger.error("Saved channel 9999 was NOT found in load_channels!")
        sys.exit(1)

    logger.info("--- Testing Get Channel by ID ---")
    c_by_id = storage.get_channel_by_id(9999)
    logger.info(f"Fetched channel 9999: {c_by_id}")

    logger.info("--- Testing Profile Channels ---")
    storage.save_profile_channels({1: {"test_val": 42}})
    prof_ch = storage.load_profile_channels()
    logger.info(f"Loaded Profile Channels: {prof_ch}")

    logger.info("Verification FINISHED successfully")

if __name__ == "__main__":
    main()
