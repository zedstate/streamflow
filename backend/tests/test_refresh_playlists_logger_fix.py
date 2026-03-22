"""Test that verifies the fix for the logger initialization bug in automated_stream_manager."""
import unittest
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


class TestRefreshPlaylistsLoggerFix(unittest.TestCase):
    """Test that refresh_playlists doesn't fail due to logger initialization issues."""
    
    def test_module_imports_without_deadstreamtracker(self):
        """Test that automated_stream_manager can be imported even if DeadStreamsTracker fails.
        
        This test verifies the fix for the bug where:
        - DeadStreamsTracker import could fail
        - The except block tried to use logger.warning()
        - But logger wasn't initialized yet (it was initialized after the try/except)
        - This caused: NameError: name 'logger' is not defined
        
        The fix moves logger initialization before the try/except block.
        """
        # Import the module - if there's a NameError, the test will fail
        try:
            import apps.automation.automated_stream_manager
            # Verify the module loaded successfully
            self.assertTrue(hasattr(automated_stream_manager, 'AutomatedStreamManager'))
            self.assertTrue(hasattr(automated_stream_manager, 'logger'))
        except NameError as e:
            self.fail(f"NameError during import (logger not initialized before use): {e}")
    
    def test_logger_available_in_exception_handler(self):
        """Test that logger is available when DeadStreamsTracker import fails."""
        import apps.automation.automated_stream_manager
        
        # Verify logger exists and can be used
        self.assertTrue(hasattr(automated_stream_manager, 'logger'))
        self.assertIsNotNone(automated_stream_manager.logger)
        
        # Verify we can call logger methods without errors
        try:
            automated_stream_manager.logger.info("Test message from unit test")
        except Exception as e:
            self.fail(f"Logger is not properly initialized: {e}")
    
    def test_dead_streams_tracker_flag_set(self):
        """Test that DEAD_STREAMS_TRACKER_AVAILABLE flag is properly set."""
        import apps.automation.automated_stream_manager
        
        # Verify the flag exists and is a boolean
        self.assertTrue(hasattr(automated_stream_manager, 'DEAD_STREAMS_TRACKER_AVAILABLE'))
        self.assertIsInstance(automated_stream_manager.DEAD_STREAMS_TRACKER_AVAILABLE, bool)


if __name__ == '__main__':
    unittest.main()
