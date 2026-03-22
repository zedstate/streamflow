#!/usr/bin/env python3
"""
Unit tests for the has_custom_streams() function.

This module tests that has_custom_streams() correctly identifies
the presence of custom streams using the UDI cache.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
import tempfile

# Set up CONFIG_DIR before importing modules
os.environ['CONFIG_DIR'] = tempfile.mkdtemp()

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestHasCustomStreamsPerformance(unittest.TestCase):
    """Test the has_custom_streams() function using UDI."""
    
    @patch('api_utils.get_udi_manager')
    def test_returns_true_when_custom_stream_exists(self, mock_get_udi):
        """Test that has_custom_streams returns True when custom stream exists in UDI cache."""
        from apps.core.api_utils import has_custom_streams
        
        # Mock UDI manager to have custom streams
        mock_udi = MagicMock()
        mock_udi.has_custom_streams.return_value = True
        mock_get_udi.return_value = mock_udi
        
        result = has_custom_streams()
        
        # Should return True
        self.assertTrue(result)
        # Should call UDI has_custom_streams
        mock_udi.has_custom_streams.assert_called_once()
    
    @patch('api_utils.get_udi_manager')
    def test_returns_false_when_no_custom_streams(self, mock_get_udi):
        """Test that has_custom_streams returns False when no custom streams in UDI cache."""
        from apps.core.api_utils import has_custom_streams
        
        # Mock UDI manager with no custom streams
        mock_udi = MagicMock()
        mock_udi.has_custom_streams.return_value = False
        mock_get_udi.return_value = mock_udi
        
        result = has_custom_streams()
        
        # Should return False
        self.assertFalse(result)
    
    @patch('api_utils.get_udi_manager')
    def test_uses_udi_cache_not_api(self, mock_get_udi):
        """Test that has_custom_streams uses UDI cache, not direct API calls."""
        from apps.core.api_utils import has_custom_streams
        
        # Mock UDI manager
        mock_udi = MagicMock()
        mock_udi.has_custom_streams.return_value = False
        mock_get_udi.return_value = mock_udi
        
        has_custom_streams()
        
        # Should only call UDI manager's method
        mock_get_udi.assert_called_once()
        mock_udi.has_custom_streams.assert_called_once()


if __name__ == '__main__':
    unittest.main()
