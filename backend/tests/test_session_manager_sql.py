import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import logging
from database.connection import init_db, get_session
from database.models import MonitoringSession
from stream_session_manager import StreamSessionManager, SessionInfo, StreamInfo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Initializing Database...")
    init_db()
    
    manager = StreamSessionManager()
    
    logger.info("--- Testing Save Sessions ---")
    # Create a dummy session
    s_info = SessionInfo(
        session_id="test_sess_123",
        channel_id=1,
        channel_name="Test Channel",
        regex_filter=".*",
        created_at=time.time(),
        is_active=False
    )
    s_info.streams[991] = StreamInfo(
        stream_id=991,
        url="http://test.com",
        name="Test stream",
        channel_id=1,
        status="review"
    )
    manager.sessions["test_sess_123"] = s_info
    
    logger.info("Invoking _save_sessions...")
    manager._save_sessions()
    
    # Wait for the background thread to finish
    time.sleep(2)
    
    logger.info("--- Verifying in DB ---")
    session = get_session()
    try:
        rows = session.query(MonitoringSession).all()
        logger.info(f"Found {len(rows)} monitoring session rows in DB")
        for r in rows:
            logger.info(f"Row: {r.session_id} - Stream: {r.stream_id} - Status: {r.status}")
            if r.session_id == "test_sess_123_991":
                logger.info("✓ Found expected concatenated Session ID!")
                logger.info(f"Raw Info keys: {r.raw_info.keys() if r.raw_info else 'None'}")
    finally:
        session.close()

    logger.info("--- Testing Load Sessions ---")
    # Clear memory dictionary to force load
    manager.sessions = {}
    manager._load_sessions()
    logger.info(f"Reloaded {len(manager.sessions)} sessions")
    if "test_sess_123" in manager.sessions:
        logger.info("✓ Reassembled Session Info successfully!")
        loaded_sess = manager.sessions["test_sess_123"]
        logger.info(f"Loaded streams: {list(loaded_sess.streams.keys())}")
        if 991 in loaded_sess.streams:
             logger.info(f"✓ Found stream 991 with status {loaded_sess.streams[991].status}")

    logger.info("Verification FINISHED successfully")

if __name__ == "__main__":
    main()
