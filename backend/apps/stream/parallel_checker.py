#!/usr/bin/env python3
"""
Parallel stream checking using thread pool.

This module provides parallel stream checking functionality without using Celery/Redis.
It uses Python's ThreadPoolExecutor for concurrent stream analysis.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Callable
from apps.core.logging_config import setup_logging

logger = setup_logging(__name__)


class ParallelStreamChecker:
    """
    Thread-based parallel stream checker.
    
    Provides concurrent stream checking with configurable worker pool size.
    """
    
    def __init__(self, max_workers: int = 10):
        """
        Initialize the parallel stream checker.
        
        Args:
            max_workers: Maximum number of concurrent workers (default: 10)
        """
        self.max_workers = max_workers
        logger.info(f"ParallelStreamChecker initialized with {max_workers} workers")
    
    def check_streams_parallel(
        self,
        streams: List[Dict[str, Any]],
        check_function: Callable,
        progress_callback: Optional[Callable] = None,
        stagger_delay: float = 0.0,
        **check_params
    ) -> List[Dict[str, Any]]:
        """
        Check multiple streams in parallel using a thread pool.
        
        Args:
            streams: List of stream dictionaries to check
            check_function: Function to call for each stream (should accept stream params)
            progress_callback: Optional callback function called after each stream completes
                              Signature: callback(completed_count, total_count, stream_result)
            stagger_delay: Delay in seconds between submitting tasks (default: 0.0)
            **check_params: Additional parameters to pass to check_function
            
        Returns:
            List of stream analysis results
        """
        if not streams:
            logger.info("No streams to check")
            return []
        
        total_streams = len(streams)
        logger.info(f"Starting parallel check of {total_streams} streams with {self.max_workers} workers")
        
        results = []
        completed_count = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks to the executor
            future_to_stream = {}
            
            for stream in streams:
                # Apply stagger delay before submitting each task
                if stagger_delay > 0 and future_to_stream:
                    time.sleep(stagger_delay)
                
                future = executor.submit(
                    check_function,
                    stream_url=stream.get('url', ''),
                    stream_id=stream['id'],
                    stream_name=stream.get('name', 'Unknown'),
                    **check_params
                )
                future_to_stream[future] = stream
                logger.debug(f"Submitted stream {stream['id']} for checking")
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_stream):
                stream = future_to_stream[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed_count += 1
                    
                    logger.debug(
                        f"Completed {completed_count}/{total_streams}: "
                        f"Stream {stream['id']} - {stream.get('name', 'Unknown')}"
                    )
                    
                    # Call progress callback if provided
                    if progress_callback:
                        progress_callback(completed_count, total_streams, result)
                        
                except Exception as e:
                    logger.error(
                        f"Error checking stream {stream['id']} ({stream.get('name', 'Unknown')}): {e}",
                        exc_info=True
                    )
                    # Create a failed result entry
                    results.append({
                        'stream_id': stream['id'],
                        'stream_name': stream.get('name', 'Unknown'),
                        'stream_url': stream.get('url', ''),
                        'status': 'ERROR',
                        'error': str(e),
                        'resolution': '0x0',
                        'bitrate_kbps': 0,
                        'fps': 0,
                        'video_codec': 'N/A',
                        'audio_codec': 'N/A'
                    })
                    completed_count += 1
        
        logger.info(f"Completed parallel check of {completed_count}/{total_streams} streams")
        return results


# Global instance
_parallel_checker = None


def get_parallel_checker(max_workers: int = 10) -> ParallelStreamChecker:
    """
    Get or create the global parallel checker instance.
    
    Args:
        max_workers: Maximum number of concurrent workers
        
    Returns:
        ParallelStreamChecker instance
    """
    global _parallel_checker
    if _parallel_checker is None or _parallel_checker.max_workers != max_workers:
        _parallel_checker = ParallelStreamChecker(max_workers=max_workers)
    return _parallel_checker
