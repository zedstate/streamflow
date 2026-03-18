#!/usr/bin/env python3
"""
Test that stream stats updates and dead stream detection happen AFTER
all parallel checks complete, ensuring proper pipeline ordering:
gather stats in parallel -> when all checks finish -> push the info.

This test verifies the fix for the concurrency issue where stream removal
from Dispatcharr channels wasn't working properly.
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestParallelCheckPipeline(unittest.TestCase):
    """Test cases for parallel check pipeline ordering."""
    
    def test_progress_callback_does_not_update_stats(self):
        """
        Test that the progress callback does NOT call _update_stream_stats.
        
        This is the key fix for the concurrency issue - stats should be updated
        AFTER all parallel checks complete, not during individual stream completion.
        """
        # This is a design verification test - we verify that the progress_callback
        # in _check_channel_concurrent does not call _update_stream_stats
        
        # Read the source code to verify the fix
        import inspect
        from apps.stream.stream_checker_service import StreamCheckerService
        
        # Get the source code of _check_channel_concurrent
        source = inspect.getsource(StreamCheckerService._check_channel_concurrent)
        
        # Verify that progress_callback does NOT call _update_stream_stats
        # The old code had: self._update_stream_stats(result)
        # The new code should have a comment explaining why we DON'T do this
        
        # Check if the progress_callback function is defined
        self.assertIn('def progress_callback', source, 
                     "progress_callback should be defined in _check_channel_concurrent")
        
        # Verify the comment about NOT updating stats in the callback
        lines = source.split('\n')
        progress_callback_start = None
        for i, line in enumerate(lines):
            if 'def progress_callback' in line:
                progress_callback_start = i
                break
        
        self.assertIsNotNone(progress_callback_start, 
                           "Could not find progress_callback definition")
        
        # Check the next ~20 lines after progress_callback definition
        callback_section = '\n'.join(lines[progress_callback_start:progress_callback_start + 20])
        
        # Verify that _update_stream_stats is NOT called in progress_callback
        # Look for the pattern "self._update_stream_stats" in the callback section
        # It should NOT be present (or should be commented out)
        has_update_call = 'self._update_stream_stats(result)' in callback_section
        
        self.assertFalse(has_update_call, 
                        "progress_callback should NOT call _update_stream_stats - "
                        "stats should be updated after all parallel checks complete")
        
        # Verify there's a comment explaining this
        has_comment = 'DO NOT update stream stats' in callback_section or \
                     'wait until all checks complete' in callback_section or \
                     'prevents race conditions' in callback_section
        
        self.assertTrue(has_comment,
                       "progress_callback should have a comment explaining why "
                       "_update_stream_stats is not called")
    
    def test_stats_updated_in_results_processing(self):
        """
        Test that _update_stream_stats is called in the results processing loop,
        AFTER all parallel checks have completed.
        """
        import inspect
        from apps.stream.stream_checker_service import StreamCheckerService
        
        # Get the source code of _check_channel_concurrent
        source = inspect.getsource(StreamCheckerService._check_channel_concurrent)
        
        # Find the results processing section
        # This should be after "results = parallel_checker.check_streams_parallel"
        lines = source.split('\n')
        
        results_assignment = None
        process_results_comment = None
        
        for i, line in enumerate(lines):
            if 'results = parallel_checker.check_streams_parallel' in line:
                results_assignment = i
            # Look for the comment that marks the results processing section
            if results_assignment and 'Process results' in line and 'ALL checks are complete' in line:
                process_results_comment = i
                break
        
        self.assertIsNotNone(results_assignment, 
                           "Could not find parallel_checker.check_streams_parallel call")
        self.assertIsNotNone(process_results_comment, 
                           "Could not find 'Process results - ALL checks are complete' comment")
        
        # Verify the comment comes AFTER parallel check
        self.assertGreater(process_results_comment, results_assignment,
                          "Results processing should come after parallel check completes")
        
        # Check that _update_stream_stats is called after the comment
        # Look at the section from process_results_comment to process_results_comment + 30 lines
        results_section = '\n'.join(lines[process_results_comment:process_results_comment + 30])
        
        has_update_stats = 'self._update_stream_stats(analyzed)' in results_section
        
        self.assertTrue(has_update_stats,
                       "_update_stream_stats should be called in the results "
                       "processing loop (after all parallel checks complete)")
        
        # Verify the comment explaining stats are pushed after checks
        has_push_comment = 'we can safely push the info' in results_section or \
                          'correct place to update stats' in results_section
        
        self.assertTrue(has_push_comment,
                       "Results processing should have a comment explaining "
                       "stats are safely pushed after all checks complete")


if __name__ == '__main__':
    unittest.main()
