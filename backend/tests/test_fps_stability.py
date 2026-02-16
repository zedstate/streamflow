import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from stream_checker_service import StreamCheckerService
from stream_monitoring_service import StreamMonitoringService
from stream_session_manager import StreamInfo
from stream_check_utils import get_stream_info_and_bitrate

class TestFPSStability(unittest.TestCase):
    
    def test_fps_rounding_in_utils(self):
        # Mock subprocess.run to return fluctuating FPS in stderr
        mock_result = MagicMock()
        # Must include "Input #" to trigger parsing in get_stream_info_and_bitrate
        mock_result.stderr = "Input #0, hls, from 'http://dummy.ts':\n  Stream #0:0: Video: h264, 1920x1080, 24.8 fps\n"
        mock_result.returncode = 0
        
        with patch('subprocess.run', return_value=mock_result):
            with patch('stream_check_utils._get_ffmpeg_extra_args', return_value=[]):
                # Analyze a dummy URL
                result = get_stream_info_and_bitrate("http://dummy.ts", duration=1)
                # 24.8 should round to 25.0 (0 decimals)
                self.assertEqual(result['fps'], 25.0)

        # Test another fluctuation
        mock_result.stderr = "Input #0, hls, from 'http://dummy.ts':\n  Stream #0:0: Video: h264, 1920x1080, 25.2 fps\n"
        with patch('subprocess.run', return_value=mock_result):
            with patch('stream_check_utils._get_ffmpeg_extra_args', return_value=[]):
                result = get_stream_info_and_bitrate("http://dummy.ts", duration=1)
                # 25.2 should also round to 25.0
                self.assertEqual(result['fps'], 25.0)

    def test_monitoring_sort_stability(self):
        # Create two StreamInfo objects with slightly different raw FPS
        # that should result in same rounded FPS
        
        info1 = StreamInfo(url="url1", stream_id=1, name="s1", channel_id=1)
        info1.width = 1920
        info1.height = 1080
        info1.fps = 24.8
        
        info2 = StreamInfo(url="url2", stream_id=2, name="s2", channel_id=1)
        info2.width = 1920
        info2.height = 1080
        info2.fps = 25.2
        
        # Mock dependencies
        with patch('stream_monitoring_service.get_udi_manager'):
            with patch('stream_monitoring_service.get_session_manager'):
                with patch('stream_monitoring_service.get_screenshot_service'):
                    with patch('stream_monitoring_service.DeadStreamsTracker'):
                        service = StreamMonitoringService()
                
        # Sort key logic from stream_monitoring_service.py:
        # (status_priority, score, res_score, fps)
        # We've updated fps = round(float(info.fps or 0), 1)
        
        key1 = service._calculate_monitoring_sort_key(info1)
        key2 = service._calculate_monitoring_sort_key(info2)
        
        # They should be equal because FPS rounds to 25.0
        self.assertEqual(key1, key2)
        self.assertEqual(key1[3], 25.0)

if __name__ == '__main__':
    unittest.main()
