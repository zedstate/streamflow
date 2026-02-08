import sys
import os
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Mock dependencies before import
sys.modules['dotenv'] = MagicMock()
sys.modules['udi'] = MagicMock()
sys.modules['udi.manager'] = MagicMock()
sys.modules['udi.fetcher'] = MagicMock()
sys.modules['api_utils'] = MagicMock()
sys.modules['stream_stats_utils'] = MagicMock()

# Now import manager
from stream_session_manager import StreamSessionManager, SessionInfo, StreamInfo, CappedSlidingWindow

# Specific test for start_session creating scoring windows
def test_start_session_creates_scoring_windows():
    print("Testing start_session scoring window creation...")
    
    # Mock config dir
    with patch('stream_session_manager.CONFIG_DIR') as mock_config_dir:
        mock_config_dir.mkdir.return_value = None
        
        manager = StreamSessionManager()
        
        # Mock a session with one stream
        session_id = 'test_session'
        stream_id = 123
        
        stream = StreamInfo(
            stream_id=stream_id,
            url='http://example.com',
            name='Test Stream',
            channel_id=1,
            status='review' 
        )
        
        session = SessionInfo(
            session_id=session_id,
            channel_id=1,
            channel_name='Test Channel',
            regex_filter='.*',
            created_at=1000,
            is_active=False,
            streams={stream_id: stream},
            window_size=10
        )
        
        manager.sessions[session_id] = session
        manager.session_locks[session_id] = MagicMock()
        manager.session_locks[session_id].__enter__ = MagicMock()
        manager.session_locks[session_id].__exit__ = MagicMock()
        
        # Mock _discover_streams to prevent it from doing anything (simulating no *new* streams found)
        manager._discover_streams = MagicMock()
        manager._save_sessions = MagicMock()
        
        # Ensure scoring windows are empty initially
        manager.scoring_windows = {}
        
        # Call start_session
        manager.start_session(session_id)
        
        # Verify scoring window was created
        if session_id in manager.scoring_windows and stream_id in manager.scoring_windows[session_id]:
            window = manager.scoring_windows[session_id][stream_id]
            if isinstance(window, CappedSlidingWindow):
                print("SUCCESS: Scoring window created for stream")
            else:
                print("FAILURE: Object in scoring_windows is not CappedSlidingWindow")
        else:
            print("FAILURE: Scoring window not found in manager.scoring_windows")

if __name__ == "__main__":
    try:
        test_start_session_creates_scoring_windows()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
