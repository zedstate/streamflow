
import unittest
from unittest.mock import MagicMock, patch
import time
from stream_monitoring_service import StreamMonitoringService, SessionInfo

class TestEvaluationInterval(unittest.TestCase):
    @patch('stream_monitoring_service.get_session_manager')
    @patch('stream_monitoring_service.get_screenshot_service')
    @patch('stream_monitoring_service.get_udi_manager')
    def setUp(self, mock_get_udi, mock_get_screenshot, mock_get_manager):
        self.mock_session_manager = MagicMock()
        mock_get_manager.return_value = self.mock_session_manager
        
        # Reset singleton logic for test
        StreamMonitoringService._instance = None
        self.service = StreamMonitoringService()
        self.service.session_manager = self.mock_session_manager
        
        # Mock _evaluate_session_streams to track calls
        self.service._evaluate_session_streams = MagicMock()
        self.service._monitor_session = MagicMock()
        self.service._check_session_auto_stop = MagicMock()
        self.service._manage_quarantine_lifecycle = MagicMock()

    def test_evaluation_interval(self):
        # Create a session with 2000ms interval
        session = MagicMock(spec=SessionInfo)
        session.session_id = "test_session_interval"
        session.evaluation_interval_ms = 2000
        session.is_active = True
        
        # Setup session manager to return this session
        self.mock_session_manager.get_active_sessions.return_value = [session]
        
        # Simulate worker loop iterations manually
        # Iteration 1: t=0. Should trigger (since last_eval is 0)
        with patch('time.time', return_value=1700000000.0):
            # Extract logic from _monitor_worker loop body
            current_time = 1700000000.0
            last_eval = self.service.last_evaluation_times.get(session.session_id, 0)
            eval_interval_sec = session.evaluation_interval_ms / 1000.0
            
            if current_time - last_eval >= eval_interval_sec:
                self.service._evaluate_session_streams(session.session_id)
                self.service.last_evaluation_times[session.session_id] = current_time
        
        self.service._evaluate_session_streams.assert_called_once()
        self.service._evaluate_session_streams.reset_mock()
        
        # Iteration 2: t=1.0. Should NOT trigger (interval 2.0s)
        with patch('time.time', return_value=1700000001.0):
            current_time = 1700000001.0
            last_eval = self.service.last_evaluation_times.get(session.session_id, 0)
            eval_interval_sec = session.evaluation_interval_ms / 1000.0
            
            if current_time - last_eval >= eval_interval_sec:
                self.service._evaluate_session_streams(session.session_id)
                self.service.last_evaluation_times[session.session_id] = current_time
                
        self.service._evaluate_session_streams.assert_not_called()
        
        # Iteration 3: t=2.1. Should trigger
        with patch('time.time', return_value=1700000002.1):
            current_time = 1700000002.1
            last_eval = self.service.last_evaluation_times.get(session.session_id, 0)
            eval_interval_sec = session.evaluation_interval_ms / 1000.0
            
            if current_time - last_eval >= eval_interval_sec:
                self.service._evaluate_session_streams(session.session_id)
                self.service.last_evaluation_times[session.session_id] = current_time
                
        self.service._evaluate_session_streams.assert_called_once()
        print("Evaluation interval test passed!")

if __name__ == '__main__':
    unittest.main()
