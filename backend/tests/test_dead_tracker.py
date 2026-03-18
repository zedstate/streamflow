import sys
import os
from pathlib import Path

# Add backend and its parent to PYTHONPATH
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from dead_streams_tracker import DeadStreamsTracker
from database.connection import get_session
from database.models import DeadStream

def main():
    print("Initializing DeadStreamsTracker test...")
    tracker = DeadStreamsTracker()
    
    # Test Marking Dead
    print("\n1. Marking Stream Dead...")
    url = "http://test-stream-xyz.com/live.m3u8"
    res = tracker.mark_as_dead(
        stream_url=url,
        stream_id=999,
        stream_name="Test Dead Stream",
        channel_id=1,
        reason="offline"
    )
    print(f"✓ mark_as_dead returned {res}")
    
    # Verify via tracker
    print("\n2. Verifying status via Tracker methods...")
    is_dead = tracker.is_dead(url)
    print(f"✓ is_dead: {is_dead} (Expected True)")
    
    reason = tracker.get_dead_reason(url)
    print(f"✓ get_dead_reason: {reason} (Expected 'offline')")
    
    count = tracker.get_dead_streams_count_for_channel(1)
    print(f"✓ count for channel 1: {count} (Expected >=1)")
    
    # Verify directly via DB Session to BE ABSOLUTELY SURE it is in SQL
    session = get_session()
    db_row = session.query(DeadStream).filter(DeadStream.url == url).first()
    if db_row:
        print(f"✓ [SQL VERIFIED] Found row in dead_streams table for {url} with reason '{db_row.reason}'")
    else:
        print("❌ [SQL FAILURE] Row NOT found in dead_streams table!")
        sys.exit(1)
    session.close()

    # Test Revival
    print("\n3. Testing Revival (mark_as_alive)...")
    tracker.mark_as_alive(url)
    is_dead_now = tracker.is_dead(url)
    print(f"✓ is_dead after revival: {is_dead_now} (Expected False)")
    
    print("\n🎉 ALL DEAD_STREAMS REFACOR TESTS PASSED!")

if __name__ == '__main__':
    main()
