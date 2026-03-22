import sys
import os
from pathlib import Path

# Add backend and its parent to PYTHONPATH
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

# Also add specifically backend/database to sys.path if needed
# sys.path.append(str(backend_dir / 'database'))

print(f"PYTHONPATH: {sys.path}")

try:
    from apps.database.connection import init_db, get_session, DB_PATH
    from apps.database.models import Channel, Stream, ChannelGroup
    
    # Delete DB file if exists to ensure repeatable test
    print(f"Cleaning up old DB at {DB_PATH}...")
    if DB_PATH.exists():
        DB_PATH.unlink()
        print("✓ Reset test database.")
        
    print("Initializing Database...")
    init_db()
    print("✓ Database Initialized.")
    
    session = get_session()
    
    # Test insertion
    print("Testing Insertion...")
    group = ChannelGroup(id=1, name="Test Group")
    session.add(group)
    session.flush()
    
    channel = Channel(id=101, name="Test Channel", channel_group_id=1)
    session.add(channel)
    session.flush()
    
    stream = Stream(id=1001, name="Test Stream", url="http://example.com/stream.m3u8")
    session.add(stream)
    session.flush()
    
    print(f"✓ Inserted Group: {group.name}, Channel: {channel.name}, Stream: {stream.name}")
    session.commit()
    print("✓ Transaction Committed.")
    
    # Query back using ORM
    queried_channel = session.query(Channel).filter_by(id=101).first()
    print(f"✓ Queries Channel: {queried_channel.name} (Group: {queried_channel.group.name if queried_channel.group else 'None'})")
    
    session.close()

    # Test DatabaseManager (DAL)
    print("\nTesting DatabaseManager DAL...")
    from apps.database.manager import get_db_manager
    db_manager = get_db_manager()
    
    channels = db_manager.get_channels(as_dict=True)
    print(f"✓ DAL get_channels() returned {len(channels)} dicts.")
    if channels:
        print(f"✓ Channel Dict: {channels[0]}")
        
    streams = db_manager.get_streams(as_dict=True)
    print(f"✓ DAL get_streams() returned {len(streams)} dicts.")
    
    print("Verification SUCCESS")
    
except Exception as e:
    print(f"❌ Verification FAILED: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
