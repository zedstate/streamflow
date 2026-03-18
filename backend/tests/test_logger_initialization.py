"""Test logger initialization bug fix."""
import unittest
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


class TestLoggerInitialization(unittest.TestCase):
    """Test that logger is properly initialized before use."""
    
    def test_module_imports_successfully(self):
        """Test that automated_stream_manager module can be imported without errors."""
        # This test verifies the fix for the bug where logger was used before initialization
        try:
            import apps.automation.automated_stream_manager
            # If we get here, the module imported successfully
            self.assertTrue(True)
        except NameError as e:
            self.fail(f"NameError occurred during import: {e}")
        except Exception as e:
            self.fail(f"Unexpected error during import: {e}")
    
    def test_logger_exists_after_import(self):
        """Test that logger variable exists after importing the module."""
        import apps.automation.automated_stream_manager
        
        # Verify logger exists and is properly configured
        self.assertTrue(hasattr(automated_stream_manager, 'logger'))
        self.assertIsNotNone(automated_stream_manager.logger)
    
    def test_dead_streams_tracker_flag_exists(self):
        """Test that DEAD_STREAMS_TRACKER_AVAILABLE flag exists regardless of import success."""
        import apps.automation.automated_stream_manager
        
        # Verify the flag exists
        self.assertTrue(hasattr(automated_stream_manager, 'DEAD_STREAMS_TRACKER_AVAILABLE'))
        # Flag should be a boolean
        self.assertIsInstance(automated_stream_manager.DEAD_STREAMS_TRACKER_AVAILABLE, bool)


if __name__ == '__main__':
    unittest.main()
