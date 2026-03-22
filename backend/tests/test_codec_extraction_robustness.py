#!/usr/bin/env python3
"""
Test comprehensive codec extraction logic for robustness.

This test suite validates the improved codec extraction logic that handles
wrapped codecs like 'wrapped_avframe' by looking inside parentheses for
the actual codec name.
"""

import unittest
from unittest.mock import patch, Mock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.stream.stream_check_utils import _extract_codec_from_line, get_stream_info_and_bitrate


class TestCodecExtractionRobustness(unittest.TestCase):
    """Test cases for robust codec extraction from FFmpeg output."""
    
    def test_extract_normal_video_codec(self):
        """Test extraction of normal video codec without wrapper."""
        line = "Stream #0:0: Video: h264, yuv420p, 1920x1080, 25 fps"
        result = _extract_codec_from_line(line, 'Video')
        self.assertEqual(result, 'h264', "Should extract h264 directly")
    
    def test_extract_normal_audio_codec(self):
        """Test extraction of normal audio codec without wrapper."""
        line = "Stream #0:1: Audio: aac, 48000 Hz, stereo"
        result = _extract_codec_from_line(line, 'Audio')
        self.assertEqual(result, 'aac', "Should extract aac directly")
    
    def test_extract_wrapped_video_codec(self):
        """Test extraction of video codec from wrapped_avframe with parentheses."""
        line = "Stream #0:0(und): Video: wrapped_avframe (avc1 / 0x31637661), yuv420p, 1920x1080, 25 fps"
        result = _extract_codec_from_line(line, 'Video')
        self.assertEqual(result, 'avc1', "Should extract avc1 from parentheses")
    
    def test_extract_wrapped_audio_codec(self):
        """Test extraction of audio codec from wrapped_avframe with parentheses."""
        line = "Stream #0:1(und): Audio: wrapped_avframe (aac)"
        result = _extract_codec_from_line(line, 'Audio')
        self.assertEqual(result, 'aac', "Should extract aac from parentheses")
    
    def test_wrapped_codec_without_parentheses(self):
        """Test that wrapped codec without parentheses returns None."""
        line = "Stream #0:0: Video: wrapped_avframe, yuv420p, 1920x1080, 25 fps"
        result = _extract_codec_from_line(line, 'Video')
        self.assertIsNone(result, "Should return None when wrapper has no parentheses")
    
    def test_unknown_wrapper_with_codec(self):
        """Test extraction from 'unknown' wrapper."""
        line = "Stream #0:0: Video: unknown (hevc / 0x63766568), 1920x1080"
        result = _extract_codec_from_line(line, 'Video')
        self.assertEqual(result, 'hevc', "Should extract hevc from unknown wrapper")
    
    def test_ignore_hex_codes(self):
        """Test that hexadecimal codes are ignored in parentheses."""
        line = "Stream #0:0: Video: wrapped_avframe (0x31637661 / avc1), yuv420p"
        result = _extract_codec_from_line(line, 'Video')
        self.assertEqual(result, 'avc1', "Should skip 0x hex code and extract avc1")
    
    def test_complex_stream_with_language_tag(self):
        """Test extraction from complex stream with language tag."""
        line = "Stream #0:0(und): Video: wrapped_avframe (hvc1 / 0x31637668), yuv420p(tv, bt709), 3840x2160 [SAR 1:1 DAR 16:9], 60 fps, 60 tbr, 90k tbn (default)"
        result = _extract_codec_from_line(line, 'Video')
        self.assertEqual(result, 'hvc1', "Should extract hvc1 from complex stream")
    
    def test_codec_with_only_hex_in_parentheses(self):
        """Test that wrapper with only hex codes in parentheses returns None."""
        line = "Stream #0:0: Video: wrapped_avframe (0x12345678), yuv420p"
        result = _extract_codec_from_line(line, 'Video')
        self.assertIsNone(result, "Should return None when only hex codes in parentheses")
    
    def test_multiple_codecs_in_parentheses(self):
        """Test extraction when multiple codecs are in parentheses (takes first)."""
        line = "Stream #0:0: Video: wrapped_avframe (vp9 / vp09 / 0x39307076), yuv420p"
        result = _extract_codec_from_line(line, 'Video')
        self.assertEqual(result, 'vp9', "Should extract first valid codec (vp9)")
    
    def test_audio_with_sample_rate_and_channels(self):
        """Test audio extraction with sample rate and channel info."""
        line = "Stream #0:1(eng): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s"
        result = _extract_codec_from_line(line, 'Audio')
        self.assertEqual(result, 'aac', "Should extract aac codec")
    
    def test_hevc_codec(self):
        """Test extraction of HEVC codec."""
        line = "Stream #0:0: Video: hevc (Main 10), yuv420p10le(tv), 1920x1080, 30 fps"
        result = _extract_codec_from_line(line, 'Video')
        self.assertEqual(result, 'hevc', "Should extract hevc codec")
    
    def test_vp9_codec(self):
        """Test extraction of VP9 codec."""
        line = "Stream #0:0: Video: vp9, yuv420p(tv), 1920x1080, 60 fps"
        result = _extract_codec_from_line(line, 'Video')
        self.assertEqual(result, 'vp9', "Should extract vp9 codec")
    
    def test_hyphenated_codec_name(self):
        """Test extraction of codec with hyphen in name."""
        line = "Stream #0:0: Video: x264-high, yuv420p, 1920x1080, 30 fps"
        result = _extract_codec_from_line(line, 'Video')
        self.assertEqual(result, 'x264-high', "Should extract hyphenated codec name")
    
    def test_wrapped_hyphenated_codec(self):
        """Test extraction of hyphenated codec from wrapper."""
        line = "Stream #0:0: Video: wrapped_avframe (x264-high / 0x12345678), yuv420p"
        result = _extract_codec_from_line(line, 'Video')
        self.assertEqual(result, 'x264-high', "Should extract hyphenated codec from wrapper")
    
    @patch('stream_check_utils.subprocess.run')
    def test_integration_with_multiple_wrapped_streams(self, mock_run):
        """Test integration with FFmpeg output containing multiple wrapped streams."""
        ffmpeg_output = """
Input #0, mpegts, from 'http://example.com/stream.m3u8':
  Duration: N/A, start: 0.000000, bitrate: N/A
    Stream #0:0(und): Video: wrapped_avframe (hvc1 / 0x31637668), yuv420p10le(tv), 3840x2160, 60 fps
    Stream #0:1(eng): Audio: wrapped_avframe (mp4a / 0x6134706D), 48000 Hz, stereo
frame= 1800 time=00:00:30.00 bitrate=8000.0kbits/s speed=1.0x
Statistics: 30000000 bytes read
"""
        mock_result = Mock()
        mock_result.stderr = ffmpeg_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = get_stream_info_and_bitrate('http://example.com/test.m3u8', duration=30, timeout=30)
        
        # Should extract actual codecs from parentheses and normalize
        self.assertEqual(result['video_codec'], 'hevc', "Should extract and normalize hvc1 to hevc")
        self.assertEqual(result['audio_codec'], 'aac', "Should extract mp4a and normalize to aac (or return mp4a)")
        self.assertEqual(result['resolution'], '3840x2160', "Should extract resolution")
        self.assertEqual(result['fps'], 60.0, "Should extract FPS")
    
    @patch('stream_check_utils.subprocess.run')
    def test_integration_mixed_wrapped_and_normal(self, mock_run):
        """Test integration with mixed wrapped and normal codec streams."""
        ffmpeg_output = """
Input #0, mpegts, from 'http://example.com/stream.m3u8':
  Duration: N/A, start: 0.000000, bitrate: N/A
    Stream #0:0: Video: h264 (High), yuv420p, 1920x1080, 30 fps
    Stream #0:1(und): Audio: wrapped_avframe (aac / 0x636161), 44100 Hz, stereo
frame=  900 time=00:00:30.00 bitrate=5000.0kbits/s speed=1.0x
Statistics: 18750000 bytes read
"""
        mock_result = Mock()
        mock_result.stderr = ffmpeg_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = get_stream_info_and_bitrate('http://example.com/test.m3u8', duration=30, timeout=30)
        
        # Should handle mixed case correctly
        self.assertEqual(result['video_codec'], 'h264', "Should extract normal h264 codec")
        self.assertEqual(result['audio_codec'], 'aac', "Should extract aac from wrapped audio")
        self.assertEqual(result['resolution'], '1920x1080', "Should extract resolution")
        self.assertEqual(result['fps'], 30.0, "Should extract FPS")


if __name__ == '__main__':
    unittest.main()
