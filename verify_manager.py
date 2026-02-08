import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from stream_session_manager import StreamSessionManager

try:
    manager = StreamSessionManager()
    if hasattr(manager, '_last_streams_refresh'):
        print("SUCCESS: manager has _last_streams_refresh")
        print(f"Value: {manager._last_streams_refresh}")
    else:
        print("FAILURE: manager missing _last_streams_refresh")
except Exception as e:
    print(f"ERROR: {e}")
