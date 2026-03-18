
import unittest
import json
from unittest.mock import MagicMock, patch
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock external dependencies
sys.modules['udi'] = MagicMock()
sys.modules['logging_config'] = MagicMock()
sys.modules['api_utils'] = MagicMock()
sys.modules['automated_stream_manager'] = MagicMock()
sys.modules['stream_checker_service'] = MagicMock()
sys.modules['scheduling_service'] = MagicMock()
sys.modules['channel_settings_manager'] = MagicMock()
sys.modules['dispatcharr_config'] = MagicMock()
sys.modules['channel_order_manager'] = MagicMock()
sys.modules['stream_stats_utils'] = MagicMock()

# Import the app to test
# Hack to mock the log_function_call decorator which is used in web_api.py
# This must be done BEFORE importing web_api
def mock_decorator(f):
    return f
sys.modules['logging_config'].log_function_call = mock_decorator

from web_api import app
from apps.stream.stream_session_manager import StreamInfo, SessionInfo

class TestApiStreamStatus(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('web_api.get_session_manager')
    def test_get_stream_session_includes_status(self, mock_get_manager):
        # Setup mock session with a stable stream
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager
        
        session_id = 'test_session_123'
        
        # Create a mock stream info with 'stable' status
        stream_info = StreamInfo(
            stream_id=1,
            url="http://test.com/stream",
            name="Test Stream",
            channel_id=100,
            status='stable'
        )
        
        # Create a mock session info
        session_info = SessionInfo(
            session_id=session_id,
            channel_id=100,
            channel_name="Test Channel",
            regex_filter=".*",
            created_at=1234567890,
            is_active=True,
            streams={1: stream_info}
        )
        
        mock_manager.get_session.return_value = session_info
        
        # Call the API
        response = self.app.get(f'/api/stream-sessions/{session_id}')
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        # Verify streams data
        self.assertIn('streams', data)
        self.assertEqual(len(data['streams']), 1)
        
        stream_data = data['streams'][0]
        self.assertEqual(stream_data['stream_id'], 1)
        
        # THIS IS THE KEY CHECK: 'status' should be present and equal to 'stable'
        # If the bug exists, this might fail or be missing
        self.assertIn('status', stream_data)
        self.assertEqual(stream_data['status'], 'stable')

if __name__ == '__main__':
    unittest.main()
