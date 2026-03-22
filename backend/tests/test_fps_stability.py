import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from apps.stream.stream_checker_service import StreamCheckerService
from apps.stream.stream_monitoring_service import StreamMonitoringService
from apps.stream.stream_session_manager import StreamInfo
from apps.stream.stream_check_utils import get_stream_info_and_bitrate

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

    def test_monitor_fps_rounding(self):
        from apps.stream.ffmpeg_stream_monitor import FFmpegStreamMonitor
        monitor = FFmpegStreamMonitor("http://url")
        
        # Test metadata line parsing
        monitor._parse_metadata("  Stream #0:0: Video: h264, 1920x1080, 24.8 fps")
        self.assertEqual(monitor.stats.fps, 25.0)
        
        # Test real-time stats parsing (speed compensated)
        monitor.stats.speed = 1.02
        monitor._parse_stats("frame=  100 fps= 25.4 q=28.0 size=    1152kB time=00:00:04.00 bitrate=2359.3kbits/s speed=1.02x")
        # 25.4 / 1.02 = 24.901 -> 25.0
        self.assertEqual(monitor.stats.fps, 25.0)

if __name__ == '__main__':
    unittest.main()
