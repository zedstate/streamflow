#!/usr/bin/env python3
"""
Unit test for stream revival timer reset.
"""

import unittest
import sys
import os
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock dotenv before imports
sys.modules['dotenv'] = MagicMock()

from stream_session_manager import StreamSessionManager, SessionInfo, StreamInfo

class TestStreamRevivalReset(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.old_config_dir = os.environ.get('CONFIG_DIR')
        os.environ['CONFIG_DIR'] = self.temp_dir
        
        self.config_dir_patcher = patch('stream_session_manager.CONFIG_DIR', Path(self.temp_dir))
        self.config_dir_mock = self.config_dir_patcher.start()
        
        # Mock dependencies
        with patch('stream_session_manager.get_udi_manager'):
            self.manager = StreamSessionManager()
            # Prevent calling _load_sessions which might fail or do unwanted things
            self.manager.sessions = {}
            self.manager.session_locks = {}

    def tearDown(self):
        self.config_dir_patcher.stop()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        if self.old_config_dir:
            os.environ['CONFIG_DIR'] = self.old_config_dir

    @patch('stream_session_manager.get_udi_manager')
    def test_revive_stream_resets_timers(self, mock_get_udi):
        """Test that reviving a stream resets low_speed_start_time and failure_count."""
        session_id = 'test_session'
        stream_id = 123
        chan_id = 99
        
        # Setup session and stream
        session = SessionInfo(
            session_id=session_id,
            channel_id=chan_id,
            channel_name="test",
            regex_filter=".*",
            created_at=time.time(),
            is_active=True,
            quarantined_stream_ids={stream_id}
        )
        
        stream = StreamInfo(
            url='http://test',
            name='test',
            stream_id=stream_id,
            channel_id=chan_id
        )
        stream.status = 'quarantined'
        stream.low_speed_start_time = time.time() - 1000 # Old timestamp
        stream.failure_count = 5
        
        session.streams = {stream_id: stream}
        self.manager.sessions = {session_id: session}
        
        # Initialize lock for this session
        import threading
        self.manager.session_locks = {session_id: threading.RLock()}
        
        # Mock UDI and API utils
        mock_udi = MagicMock()
        mock_get_udi.return_value = mock_udi
        
        with patch('api_utils.add_streams_to_channel') as mock_add:
            # Execute revival
            result = self.manager.revive_stream(session_id, stream_id)
            
            # Verify result
            self.assertTrue(result, "Revival should succeed")
            self.assertEqual(stream.status, 'review')
            
            # Verify resets
            self.assertIsNone(stream.low_speed_start_time, "low_speed_start_time should be reset to None")
            self.assertEqual(stream.failure_count, 0, "failure_count should be reset to 0")

if __name__ == '__main__':
    unittest.main()
