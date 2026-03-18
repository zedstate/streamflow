#!/usr/bin/env python3
"""
Test configurable dead stream detection thresholds.

This test verifies that dead stream detection properly respects
configurable thresholds for resolution, bitrate, and score.
"""

import unittest
from apps.core.stream_stats_utils import is_stream_dead


class TestConfigurableDeadStreamDetection(unittest.TestCase):
    """Test configurable dead stream detection."""
    
    def test_basic_dead_stream_zero_resolution(self):
        """Test that 0x0 resolution is always considered dead."""
        stream_data = {
            'stream_stats': {
                'resolution': '0x0',
                'ffmpeg_output_bitrate': '1000 kbps'
            }
        }
        
        # Should be dead even with no config (basic check)
        self.assertTrue(is_stream_dead(stream_data))
        
        # Should be dead even with high thresholds config
        config = {
            'min_resolution_width': 1920,
            'min_resolution_height': 1080,
            'min_bitrate_kbps': 5000,
            'min_score': 50
        }
        self.assertTrue(is_stream_dead(stream_data, config))
    
    def test_basic_dead_stream_zero_bitrate(self):
        """Test that 0 bitrate is always considered dead."""
        stream_data = {
            'stream_stats': {
                'resolution': '1920x1080',
                'ffmpeg_output_bitrate': '0'
            }
        }
        
        # Should be dead even with no config
        self.assertTrue(is_stream_dead(stream_data))
        
        # Should be dead even with config
        config = {
            'min_resolution_width': 0,
            'min_resolution_height': 0,
            'min_bitrate_kbps': 0,
            'min_score': 0
        }
        self.assertTrue(is_stream_dead(stream_data, config))
    
    def test_resolution_threshold_below_minimum(self):
        """Test that streams below minimum resolution are considered dead."""
        stream_data = {
            'stream_stats': {
                'resolution': '640x480',  # SD resolution
                'ffmpeg_output_bitrate': '2000 kbps'
            }
        }
        
        # Should NOT be dead with no threshold
        self.assertFalse(is_stream_dead(stream_data))
        
        # Should be dead with 720p minimum (1280x720)
        config = {
            'min_resolution_width': 1280,
            'min_resolution_height': 720,
            'min_bitrate_kbps': 0,
            'min_score': 0
        }
        self.assertTrue(is_stream_dead(stream_data, config))
    
    def test_resolution_threshold_above_minimum(self):
        """Test that streams above minimum resolution are NOT considered dead."""
        stream_data = {
            'stream_stats': {
                'resolution': '1920x1080',  # Full HD
                'ffmpeg_output_bitrate': '5000 kbps'
            }
        }
        
        # Should NOT be dead with 720p minimum
        config = {
            'min_resolution_width': 1280,
            'min_resolution_height': 720,
            'min_bitrate_kbps': 0,
            'min_score': 0
        }
        self.assertFalse(is_stream_dead(stream_data, config))
    
    def test_bitrate_threshold_below_minimum(self):
        """Test that streams below minimum bitrate are considered dead."""
        stream_data = {
            'stream_stats': {
                'resolution': '1920x1080',
                'ffmpeg_output_bitrate': '500 kbps'  # Low bitrate
            }
        }
        
        # Should NOT be dead with no threshold
        self.assertFalse(is_stream_dead(stream_data))
        
        # Should be dead with 1000 kbps minimum
        config = {
            'min_resolution_width': 0,
            'min_resolution_height': 0,
            'min_bitrate_kbps': 1000,
            'min_score': 0
        }
        self.assertTrue(is_stream_dead(stream_data, config))
    
    def test_bitrate_threshold_above_minimum(self):
        """Test that streams above minimum bitrate are NOT considered dead."""
        stream_data = {
            'stream_stats': {
                'resolution': '1920x1080',
                'ffmpeg_output_bitrate': '5000 kbps'  # High bitrate
            }
        }
        
        # Should NOT be dead with 1000 kbps minimum
        config = {
            'min_resolution_width': 0,
            'min_resolution_height': 0,
            'min_bitrate_kbps': 1000,
            'min_score': 0
        }
        self.assertFalse(is_stream_dead(stream_data, config))
    
    def test_score_threshold_below_minimum(self):
        """Test that streams below minimum score are considered dead."""
        stream_data = {
            'stream_stats': {
                'resolution': '1920x1080',
                'ffmpeg_output_bitrate': '5000 kbps'
            },
            'score': 30  # Low score
        }
        
        # Should NOT be dead with no threshold
        self.assertFalse(is_stream_dead(stream_data))
        
        # Should be dead with score minimum of 50
        config = {
            'min_resolution_width': 0,
            'min_resolution_height': 0,
            'min_bitrate_kbps': 0,
            'min_score': 50
        }
        self.assertTrue(is_stream_dead(stream_data, config))
    
    def test_score_threshold_above_minimum(self):
        """Test that streams above minimum score are NOT considered dead."""
        stream_data = {
            'stream_stats': {
                'resolution': '1920x1080',
                'ffmpeg_output_bitrate': '5000 kbps'
            },
            'score': 80  # High score
        }
        
        # Should NOT be dead with score minimum of 50
        config = {
            'min_resolution_width': 0,
            'min_resolution_height': 0,
            'min_bitrate_kbps': 0,
            'min_score': 50
        }
        self.assertFalse(is_stream_dead(stream_data, config))
    
    def test_multiple_thresholds_all_pass(self):
        """Test that stream passing all thresholds is NOT dead."""
        stream_data = {
            'stream_stats': {
                'resolution': '1920x1080',
                'ffmpeg_output_bitrate': '5000 kbps'
            },
            'score': 80
        }
        
        config = {
            'min_resolution_width': 1280,
            'min_resolution_height': 720,
            'min_bitrate_kbps': 1000,
            'min_score': 50
        }
        self.assertFalse(is_stream_dead(stream_data, config))
    
    def test_multiple_thresholds_one_fails(self):
        """Test that stream failing any threshold is dead."""
        # Good resolution and score, but low bitrate
        stream_data = {
            'stream_stats': {
                'resolution': '1920x1080',
                'ffmpeg_output_bitrate': '500 kbps'  # Below threshold
            },
            'score': 80
        }
        
        config = {
            'min_resolution_width': 1280,
            'min_resolution_height': 720,
            'min_bitrate_kbps': 1000,
            'min_score': 50
        }
        self.assertTrue(is_stream_dead(stream_data, config))
    
    def test_disabled_thresholds_with_zeros(self):
        """Test that zero thresholds disable checking."""
        stream_data = {
            'stream_stats': {
                'resolution': '640x480',  # Low resolution
                'ffmpeg_output_bitrate': '500 kbps'  # Low bitrate
            },
            'score': 20  # Low score
        }
        
        # All thresholds set to 0 (disabled)
        config = {
            'min_resolution_width': 0,
            'min_resolution_height': 0,
            'min_bitrate_kbps': 0,
            'min_score': 0
        }
        self.assertFalse(is_stream_dead(stream_data, config))
    
    def test_height_threshold_independent_of_width(self):
        """Test that height threshold is checked independently."""
        stream_data = {
            'stream_stats': {
                'resolution': '1920x360',  # Wide but short
                'ffmpeg_output_bitrate': '2000 kbps'
            }
        }
        
        # Width is good, but height is below threshold
        config = {
            'min_resolution_width': 1280,
            'min_resolution_height': 720,
            'min_bitrate_kbps': 0,
            'min_score': 0
        }
        self.assertTrue(is_stream_dead(stream_data, config))
    
    def test_width_threshold_independent_of_height(self):
        """Test that width threshold is checked independently."""
        stream_data = {
            'stream_stats': {
                'resolution': '640x1080',  # Tall but narrow
                'ffmpeg_output_bitrate': '2000 kbps'
            }
        }
        
        # Height is good, but width is below threshold
        config = {
            'min_resolution_width': 1280,
            'min_resolution_height': 720,
            'min_bitrate_kbps': 0,
            'min_score': 0
        }
        self.assertTrue(is_stream_dead(stream_data, config))


if __name__ == '__main__':
    unittest.main()
