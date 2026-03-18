"""
Test log_function_call decorator functionality.

This test verifies that the log_function_call can be used as a decorator
as well as a regular function.
"""

import os
import sys
import unittest
import logging
from io import StringIO
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.core.logging_config import setup_logging, log_function_call


class TestLogFunctionCallDecorator(unittest.TestCase):
    """Test log_function_call as a decorator."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Clear all existing handlers to start fresh
        logging.root.handlers = []
        
        # Create a string stream to capture log output
        self.log_stream = StringIO()
        handler = logging.StreamHandler(self.log_stream)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logging.root.addHandler(handler)
        
        # Enable debug mode
        os.environ['DEBUG_MODE'] = 'true'
        
        # Setup logging for the test module
        setup_logging(__name__)
    
    def tearDown(self):
        """Clean up after tests."""
        # Clear handlers
        logging.root.handlers = []
        # Reset DEBUG_MODE
        if 'DEBUG_MODE' in os.environ:
            del os.environ['DEBUG_MODE']
    
    def test_decorator_without_args(self):
        """Test using @log_function_call as a decorator without arguments."""
        
        @log_function_call
        def test_function(arg1, arg2, kwarg1=None):
            return arg1 + arg2
        
        result = test_function(1, 2, kwarg1='test')
        
        # Check that function works correctly
        self.assertEqual(result, 3)
        
        # Check that logging occurred
        log_output = self.log_stream.getvalue()
        self.assertIn("test_function", log_output)
        self.assertIn("→", log_output)  # Arrow indicator for function call
    
    def test_decorator_with_kwargs(self):
        """Test that decorator logs keyword arguments."""
        
        @log_function_call
        def test_function_with_kwargs(arg1, kwarg1=None, kwarg2=None):
            return arg1
        
        result = test_function_with_kwargs('value', kwarg1='test1', kwarg2='test2')
        
        # Check that function works correctly
        self.assertEqual(result, 'value')
        
        # Check that logging occurred with kwargs
        log_output = self.log_stream.getvalue()
        self.assertIn("test_function_with_kwargs", log_output)
        self.assertIn("kwarg1=test1", log_output)
        self.assertIn("kwarg2=test2", log_output)
    
    def test_decorator_no_log_in_non_debug_mode(self):
        """Test that decorator doesn't log when debug mode is off."""
        # Disable debug mode
        os.environ['DEBUG_MODE'] = 'false'
        
        # Clear handlers and stream
        logging.root.handlers = []
        self.log_stream = StringIO()
        handler = logging.StreamHandler(self.log_stream)
        handler.setLevel(logging.DEBUG)
        logging.root.addHandler(handler)
        
        # Reconfigure logging
        setup_logging(__name__)
        
        @log_function_call
        def test_function(arg1):
            return arg1 * 2
        
        result = test_function(5)
        
        # Check that function works correctly
        self.assertEqual(result, 10)
        
        # Check that no debug logging occurred
        log_output = self.log_stream.getvalue()
        # Should not have the function call arrow
        self.assertNotIn("→ test_function", log_output)
    
    def test_backward_compatibility_function_call(self):
        """Test that the original function call syntax still works."""
        logger = setup_logging('test_module')
        
        # Use the old way - passing logger and function name
        log_function_call(logger, 'my_function', param1='value1', param2=42)
        
        log_output = self.log_stream.getvalue()
        self.assertIn("my_function", log_output)
        self.assertIn("param1=value1", log_output)
        self.assertIn("param2=42", log_output)
    
    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""
        
        @log_function_call
        def documented_function(arg1):
            """This is a test function with documentation."""
            return arg1
        
        # Check that function metadata is preserved
        self.assertEqual(documented_function.__name__, 'documented_function')
        self.assertEqual(documented_function.__doc__, 'This is a test function with documentation.')


if __name__ == '__main__':
    unittest.main()
