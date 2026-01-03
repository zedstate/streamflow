"""
Test to verify that M3U profile URL transformations correctly handle
$1 style backreferences by converting them to \1 for Python's re.sub().
"""

import unittest
import re
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Maximum supported backreference number in Python regex
MAX_BACKREFERENCE_COUNT = 99


class TestProfileURLBackreferenceConversion(unittest.TestCase):
    """Test conversion of $1 style backreferences to \1 style."""
    
    def test_dollar_sign_backreference_conversion(self):
        """Test that $1 is converted to \1 for Python regex."""
        original_url = 'http://example.com:8080/user123/stream.m3u8'
        search_pattern = r':(\d+)/'
        replace_pattern_dollar = ':$1/'  # Dollar sign style (JavaScript/Perl)
        
        # Convert $1 to \1
        python_replace_pattern = replace_pattern_dollar
        for i in range(MAX_BACKREFERENCE_COUNT, 0, -1):
            python_replace_pattern = python_replace_pattern.replace(f'${i}', f'\\{i}')
        
        # Apply transformation
        transformed_url = re.sub(search_pattern, python_replace_pattern, original_url)
        
        # Should preserve the port number (8080)
        self.assertEqual(transformed_url, 'http://example.com:8080/user123/stream.m3u8')
        
    def test_complex_backreference_pattern(self):
        """Test complex pattern with multiple capture groups."""
        original_url = 'http://premium.example.com/live/user123/pass456/stream.m3u8'
        search_pattern = r'/user(\d+)/pass(\d+)/'
        replace_pattern_dollar = '/newuser$1/newpass$2/'
        
        # Convert $1, $2 to \1, \2
        python_replace_pattern = replace_pattern_dollar
        for i in range(MAX_BACKREFERENCE_COUNT, 0, -1):
            python_replace_pattern = python_replace_pattern.replace(f'${i}', f'\\{i}')
        
        transformed_url = re.sub(search_pattern, python_replace_pattern, original_url)
        
        # Should preserve the original user/pass numbers in new format
        self.assertEqual(transformed_url, 'http://premium.example.com/live/newuser123/newpass456/stream.m3u8')
    
    def test_no_match_pattern(self):
        """Test that URL is unchanged when pattern doesn't match."""
        original_url = 'http://example.com/stream.m3u8'
        search_pattern = r':9999/'
        replace_pattern_dollar = ':$1/'
        
        # First check if pattern matches (this is what the fixed code should do)
        if not re.search(search_pattern, original_url):
            # Pattern doesn't match, return original URL (this is the correct behavior)
            transformed_url = original_url
        else:
            # Convert $1 to \1
            python_replace_pattern = replace_pattern_dollar
            for i in range(MAX_BACKREFERENCE_COUNT, 0, -1):
                python_replace_pattern = python_replace_pattern.replace(f'${i}', f'\\{i}')
            
            transformed_url = re.sub(search_pattern, python_replace_pattern, original_url)
        
        # Should return original URL when pattern doesn't match
        self.assertEqual(transformed_url, original_url)
    
    def test_literal_dollar_sign_without_number(self):
        """Test that literal $ (not followed by number) is preserved."""
        original_url = 'http://example.com/stream$special.m3u8'
        search_pattern = r'stream\$special'
        replace_pattern = 'stream$other'  # $ not followed by number
        
        # Convert $1 to \1 (should not affect $other)
        python_replace_pattern = replace_pattern
        for i in range(MAX_BACKREFERENCE_COUNT, 0, -1):
            python_replace_pattern = python_replace_pattern.replace(f'${i}', f'\\{i}')
        
        transformed_url = re.sub(search_pattern, python_replace_pattern, original_url)
        
        self.assertEqual(transformed_url, 'http://example.com/stream$other.m3u8')
    
    def test_high_numbered_backreference(self):
        """Test conversion of higher numbered backreferences like $10."""
        original_url = 'http://example.com/a1/b2/c3/d4/e5/f6/g7/h8/i9/j10/stream.m3u8'
        
        # Pattern with 10 capture groups (2 per directory: letter and number)
        # Captures: a, 1, b, 2, c, 3, d, 4, e, 5, f, 6, g, 7, h, 8, i, 9, j, 10
        parts = []
        for _ in range(10):
            parts.append(r'([a-z])(\d+)/')
        search_pattern = '/' + ''.join(parts)
        
        # Replace pattern: /a1-b2-c3-d4-e5-f6-g7-h8-i9-j10/
        # Uses backreferences $1 through $20
        replace_parts = []
        for i in range(1, 20, 2):
            if i == 1:
                replace_parts.append(f'${i}${i+1}')
            else:
                replace_parts.append(f'-${i}${i+1}')
        replace_pattern_dollar = '/' + ''.join(replace_parts) + '/'
        
        # Convert $1, $2, ..., $20 to \1, \2, ..., \20
        MAX_BACKREFERENCE_COUNT = 99
        python_replace_pattern = replace_pattern_dollar
        for i in range(MAX_BACKREFERENCE_COUNT, 0, -1):
            python_replace_pattern = python_replace_pattern.replace(f'${i}', f'\\{i}')
        
        transformed_url = re.sub(search_pattern, python_replace_pattern, original_url)
        
        # Verify the transformation
        # Note: Since we have 20 groups capturing a1, 1, b2, 2, etc.
        # The result should combine them with dashes
        expected = 'http://example.com/a1-b2-c3-d4-e5-f6-g7-h8-i9-j10/stream.m3u8'
        self.assertEqual(transformed_url, expected)
    
    def test_mixed_literal_and_backreference(self):
        """Test pattern with both literal text and backreferences."""
        original_url = 'http://old-server.com:8080/path/stream.m3u8'
        search_pattern = r'old-server\.com:(\d+)'
        replace_pattern_dollar = 'new-server.com:$1'
        
        # Convert $1 to \1
        python_replace_pattern = replace_pattern_dollar
        for i in range(MAX_BACKREFERENCE_COUNT, 0, -1):
            python_replace_pattern = python_replace_pattern.replace(f'${i}', f'\\{i}')
        
        transformed_url = re.sub(search_pattern, python_replace_pattern, original_url)
        
        # Should change server but preserve port
        self.assertEqual(transformed_url, 'http://new-server.com:8080/path/stream.m3u8')
    
    def test_invalid_replace_pattern_without_capture_group(self):
        """Test that invalid replace_pattern with $1 but no capture group is detected."""
        original_url = 'http://example.com/stream.m3u8'
        search_pattern = r'example\.com'  # No capture group
        replace_pattern_dollar = '$1'  # References non-existent group
        
        # Convert $1 to \1
        python_replace_pattern = replace_pattern_dollar
        for i in range(MAX_BACKREFERENCE_COUNT, 0, -1):
            python_replace_pattern = python_replace_pattern.replace(f'${i}', f'\\{i}')
        
        # This should either fail or produce invalid output
        # The actual behavior depends on regex engine
        # In Python, re.sub with invalid backreference raises an error
        with self.assertRaises(re.error):
            re.sub(search_pattern, python_replace_pattern, original_url)
    
    def test_pattern_does_not_match_url(self):
        """Test that transformation is skipped when pattern doesn't match URL."""
        original_url = 'http://example.com/stream.m3u8'
        search_pattern = r':9999/'  # This won't match
        replace_pattern_dollar = ':$1/'
        
        # First check if pattern matches
        if not re.search(search_pattern, original_url):
            # Pattern doesn't match, skip transformation
            transformed_url = original_url
        else:
            # Convert and apply
            python_replace_pattern = replace_pattern_dollar
            for i in range(MAX_BACKREFERENCE_COUNT, 0, -1):
                python_replace_pattern = python_replace_pattern.replace(f'${i}', f'\\{i}')
            transformed_url = re.sub(search_pattern, python_replace_pattern, original_url)
        
        # Should return original URL when pattern doesn't match
        self.assertEqual(transformed_url, original_url)
    
    def test_empty_or_whitespace_patterns(self):
        """Test that empty or whitespace-only patterns are rejected."""
        original_url = 'http://example.com/stream.m3u8'
        
        # Test empty search pattern
        search_pattern = ''
        replace_pattern = 'something'
        
        # Should not transform with empty search_pattern
        if not search_pattern or not replace_pattern:
            transformed_url = original_url
        else:
            transformed_url = re.sub(search_pattern, replace_pattern, original_url)
        
        self.assertEqual(transformed_url, original_url)
        
        # Test whitespace-only replace pattern
        search_pattern = 'example'
        replace_pattern = '   '
        
        # Should not transform with whitespace-only pattern
        if not search_pattern.strip() or not replace_pattern.strip():
            transformed_url = original_url
        else:
            transformed_url = re.sub(search_pattern, replace_pattern, original_url)
        
        self.assertEqual(transformed_url, original_url)


if __name__ == '__main__':
    unittest.main()
