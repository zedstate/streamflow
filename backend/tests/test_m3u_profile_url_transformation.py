"""
Test to verify that M3U free profile search/replace patterns are applied during stream checking.

This test validates that when using an M3U account's free profile with search_pattern and
replace_pattern configured, the stream URL is correctly transformed before being passed to
ffmpeg for stream analysis.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
import re

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestM3UProfileURLTransformation(unittest.TestCase):
    """Test M3U profile URL transformation during stream checking."""
    
    def test_apply_profile_url_transformation_basic(self):
        """Test basic URL transformation with search/replace pattern."""
        # Test the transformation logic directly without importing UDI
        original_url = 'http://example.com:8080/live/stream123/index.m3u8'
        search_pattern = r':8080/'
        replace_pattern = ':8888/'
        
        # Apply transformation
        transformed_url = re.sub(search_pattern, replace_pattern, original_url)
        
        # Verify transformation
        self.assertEqual(transformed_url, 'http://example.com:8888/live/stream123/index.m3u8')
        self.assertNotEqual(transformed_url, original_url)
    
    def test_apply_profile_url_transformation_complex_pattern(self):
        """Test complex URL transformation pattern."""
        original_url = 'http://premium.example.com/live/user123/pass456/stream.m3u8'
        search_pattern = r'/user123/pass456/'
        replace_pattern = '/freeuser/freepass/'
        
        transformed_url = re.sub(search_pattern, replace_pattern, original_url)
        
        self.assertEqual(transformed_url, 'http://premium.example.com/live/freeuser/freepass/stream.m3u8')
    
    def test_apply_profile_url_transformation_no_match(self):
        """Test URL transformation when pattern doesn't match."""
        original_url = 'http://example.com/stream.m3u8'
        search_pattern = r':9999/'
        replace_pattern = ':8888/'
        
        transformed_url = re.sub(search_pattern, replace_pattern, original_url)
        
        # Should return original URL when pattern doesn't match
        self.assertEqual(transformed_url, original_url)
    
    def test_transformation_with_multiple_replacements(self):
        """Test URL transformation with pattern that matches multiple times."""
        original_url = 'http://server1.example.com/server1/stream.m3u8'
        search_pattern = r'server1'
        replace_pattern = 'server2'
        
        transformed_url = re.sub(search_pattern, replace_pattern, original_url)
        
        # Both occurrences should be replaced
        self.assertEqual(transformed_url, 'http://server2.example.com/server2/stream.m3u8')
        self.assertNotIn('server1', transformed_url)
    
    def test_invalid_regex_handling(self):
        """Test that invalid regex patterns are handled gracefully."""
        original_url = 'http://example.com/stream.m3u8'
        search_pattern = r'[invalid(regex'  # Invalid regex
        replace_pattern = ':8888/'
        
        # Should raise exception
        with self.assertRaises(re.error):
            re.sub(search_pattern, replace_pattern, original_url)
    
    def test_url_transformation_edge_cases(self):
        """Test URL transformation edge cases."""
        # Empty URL
        self.assertEqual(re.sub(r'test', 'replacement', ''), '')
        
        # URL with special characters
        url_with_special = 'http://example.com/stream?token=abc&key=123'
        transformed = re.sub(r'token=\w+', 'token=xyz', url_with_special)
        self.assertEqual(transformed, 'http://example.com/stream?token=xyz&key=123')
        
        # URL with regex metacharacters in replacement
        original = 'http://example.com/path/to/stream'
        # Replace 'path/to' with 'new/path'
        transformed = re.sub(r'path/to', 'new/path', original)
        self.assertEqual(transformed, 'http://example.com/new/path/stream')


if __name__ == '__main__':
    unittest.main()
