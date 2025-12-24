"""
Test for bulk regex pattern assignment fix.

This test validates that the add_bulk_regex_patterns endpoint
correctly uses get_channel_by_id method from UDI manager.
"""
import unittest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


class TestBulkRegexFix(unittest.TestCase):
    """Test that bulk regex pattern assignment uses correct UDI method."""
    
    def test_udi_manager_has_get_channel_by_id(self):
        """Verify that UDI manager has get_channel_by_id method."""
        from udi.manager import UDIManager
        
        # Create a UDI manager instance
        udi = UDIManager()
        
        # Verify the method exists
        self.assertTrue(hasattr(udi, 'get_channel_by_id'))
        self.assertTrue(callable(getattr(udi, 'get_channel_by_id')))
    
    def test_udi_manager_no_get_channel_method(self):
        """Verify that UDI manager does NOT have get_channel method (without _by_id)."""
        from udi.manager import UDIManager
        
        # Create a UDI manager instance
        udi = UDIManager()
        
        # Verify the incorrect method does not exist
        self.assertFalse(hasattr(udi, 'get_channel'))
    
    @patch('web_api.get_udi_manager')
    @patch('web_api.get_regex_matcher')
    def test_add_bulk_regex_uses_correct_method(self, mock_matcher, mock_udi_manager):
        """Test that add_bulk_regex_patterns uses get_channel_by_id."""
        # Import here to ensure patches are in place
        from web_api import add_bulk_regex_patterns
        from flask import Flask
        import json
        
        # Create a test Flask app
        app = Flask(__name__)
        
        # Mock UDI manager
        mock_udi = MagicMock()
        mock_udi.get_channel_by_id.return_value = {
            'id': 1,
            'name': 'Test Channel'
        }
        mock_udi_manager.return_value = mock_udi
        
        # Mock regex matcher
        mock_regex = MagicMock()
        mock_regex.validate_regex_patterns.return_value = (True, None)
        mock_regex.get_patterns.return_value = {'patterns': {}}
        mock_matcher.return_value = mock_regex
        
        # Test data
        test_data = {
            'channel_ids': [1],
            'regex_patterns': ['.*test.*']
        }
        
        with app.test_request_context(
            '/api/regex/bulk',
            method='POST',
            data=json.dumps(test_data),
            content_type='application/json'
        ):
            try:
                # Call the function
                response = add_bulk_regex_patterns()
                
                # Verify get_channel_by_id was called (not get_channel)
                mock_udi.get_channel_by_id.assert_called_with(1)
                
                # Verify get_channel was NOT called (this would be the bug)
                self.assertFalse(hasattr(mock_udi, 'get_channel') and mock_udi.get_channel.called)
                
            except AttributeError as e:
                # If we get AttributeError, it means the code is trying to call
                # a method that doesn't exist, which was the original bug
                if "'get_channel'" in str(e):
                    self.fail("Code is still using get_channel instead of get_channel_by_id")
                raise


if __name__ == '__main__':
    unittest.main()
