#!/usr/bin/env python3
"""
Test codec sanitization to ensure 'wrapped_avframe' and other invalid codec names
are properly filtered out and replaced with 'N/A'.
"""

import unittest
from unittest.mock import patch, Mock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.stream.stream_check_utils import _sanitize_codec_name, get_stream_info_and_bitrate


class TestCodecSanitization(unittest.TestCase):
    """Test cases for codec name sanitization."""
    
    def test_valid_codec_names(self):
        """Test that valid codec names pass through unchanged."""
        valid_codecs = ['h264', 'h265', 'hevc', 'avc', 'aac', 'mp3', 'vp9', 'av1']
        for codec in valid_codecs:
            with self.subTest(codec=codec):
                result = _sanitize_codec_name(codec)
                self.assertEqual(result, codec, f"Valid codec {codec} should not be filtered")
    
    def test_invalid_codec_names(self):
        """Test that invalid codec names are filtered out."""
        invalid_codecs = ['wrapped_avframe', 'none', 'unknown', 'null']
        for codec in invalid_codecs:
            with self.subTest(codec=codec):
                result = _sanitize_codec_name(codec)
                self.assertEqual(result, 'N/A', f"Invalid codec {codec} should be filtered to 'N/A'")
    
    def test_case_insensitive_filtering(self):
        """Test that filtering is case-insensitive."""
        variants = ['WRAPPED_AVFRAME', 'Wrapped_Avframe', 'None', 'UNKNOWN']
        for codec in variants:
            with self.subTest(codec=codec):
                result = _sanitize_codec_name(codec)
                self.assertEqual(result, 'N/A', f"Invalid codec {codec} (case variant) should be filtered")
    
    def test_empty_codec_name(self):
        """Test that empty codec names return 'N/A'."""
        for empty in ['', None]:
            with self.subTest(empty=empty):
                result = _sanitize_codec_name(empty)
                self.assertEqual(result, 'N/A', f"Empty codec {empty!r} should return 'N/A'")
    
    @patch('stream_check_utils.subprocess.run')
    def test_wrapped_avframe_extraction(self, mock_run):
        """Test extraction of actual codec from wrapped_avframe output."""
        # Simulate ffmpeg output with wrapped_avframe but actual codec in parentheses
        ffmpeg_output = """
Input #0, mpegts, from 'http://example.com/stream.m3u8':
  Duration: N/A, start: 0.000000, bitrate: N/A
    Stream #0:0(und): Video: wrapped_avframe (avc1 / 0x31637661), yuv420p, 1920x1080, 25 fps
    Stream #0:1(und): Audio: aac, 48000 Hz, stereo
frame=  750 time=00:00:30.00 bitrate=5000.0kbits/s speed=1.0x
Statistics: 18750000 bytes read
"""
        mock_result = Mock()
        mock_result.stderr = ffmpeg_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = get_stream_info_and_bitrate('http://example.com/test.m3u8', duration=30, timeout=30)
        
        # Should extract 'avc1' from parentheses, not 'wrapped_avframe', then normalize to 'h264'
        self.assertEqual(result['video_codec'], 'h264', 
                        "Should extract actual codec from parentheses and normalize avc1 to h264")
        self.assertEqual(result['audio_codec'], 'aac', "Should extract audio codec 'aac'")
        self.assertEqual(result['resolution'], '1920x1080', "Should extract resolution")
        self.assertEqual(result['fps'], 25.0, "Should extract FPS")
    
    @patch('stream_check_utils.subprocess.run')
    def test_wrapped_avframe_without_parentheses(self, mock_run):
        """Test that wrapped_avframe without parentheses is filtered to N/A."""
        # Simulate ffmpeg output with only wrapped_avframe and no actual codec in parentheses
        ffmpeg_output = """
Input #0, mpegts, from 'http://example.com/stream.m3u8':
  Duration: N/A, start: 0.000000, bitrate: N/A
    Stream #0:0: Video: wrapped_avframe, yuv420p, 1920x1080, 25 fps
    Stream #0:1: Audio: aac, 48000 Hz, stereo
frame=  750 time=00:00:30.00 bitrate=5000.0kbits/s speed=1.0x
Statistics: 18750000 bytes read
"""
        mock_result = Mock()
        mock_result.stderr = ffmpeg_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = get_stream_info_and_bitrate('http://example.com/test.m3u8', duration=30, timeout=30)
        
        # Should filter out 'wrapped_avframe' and return 'N/A'
        self.assertEqual(result['video_codec'], 'N/A', 
                        "Should filter 'wrapped_avframe' to 'N/A' when no actual codec in parentheses")
        self.assertEqual(result['audio_codec'], 'aac', "Should extract audio codec 'aac'")


if __name__ == '__main__':
    unittest.main()
