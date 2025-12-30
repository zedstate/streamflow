#!/usr/bin/env python3
"""
Concurrent Stream Limiter for StreamFlow.

This module provides intelligent concurrent stream limiting based on M3U account
stream limits. It ensures that when checking multiple streams in parallel, the
system respects each account's maximum concurrent stream limit.

Example:
    Account A has max_streams=1, Account B has max_streams=2
    Channel has streams: A1, A2, B1, B2, B3
    
    The limiter will ensure:
    - Only 1 stream from Account A is checked at a time
    - Up to 2 streams from Account B can be checked concurrently
    - Overall: A1, B1, B2 can run in parallel (3 total)
    - When A1 completes, A2 can start
    - When B1 or B2 completes, B3 can start
"""

import threading
import time
from collections import defaultdict
from typing import Dict, List, Optional, Any, Callable
from concurrent.futures import ThreadPoolExecutor, Future
from logging_config import setup_logging

logger = setup_logging(__name__)


class AccountStreamLimiter:
    """
    Manages concurrent stream limits per M3U account.
    
    Uses semaphores to enforce per-account concurrency limits while allowing
    maximum parallelism across different accounts. Also considers active viewers
    from the UDI when determining available slots.
    """
    
    def __init__(self, udi_manager=None):
        """Initialize the account stream limiter.
        
        Args:
            udi_manager: Optional UDI manager instance for checking active viewers
        """
        self.account_semaphores: Dict[int, threading.Semaphore] = {}
        self.account_limits: Dict[int, int] = {}
        self.lock = threading.Lock()
        self.udi_manager = udi_manager
        logger.info("AccountStreamLimiter initialized")
    
    def set_account_limit(self, account_id: int, max_streams: int):
        """
        Set the maximum concurrent streams for an account.
        
        Args:
            account_id: M3U account ID
            max_streams: Maximum concurrent streams (0 = unlimited)
        """
        with self.lock:
            # Store the limit
            self.account_limits[account_id] = max_streams
            
            # Create or update semaphore
            if max_streams > 0:
                # Create semaphore with the specified limit
                self.account_semaphores[account_id] = threading.Semaphore(max_streams)
                logger.debug(f"Set limit for account {account_id}: {max_streams} concurrent streams")
            else:
                # Unlimited - remove semaphore if it exists
                if account_id in self.account_semaphores:
                    del self.account_semaphores[account_id]
                logger.debug(f"Set limit for account {account_id}: unlimited concurrent streams")
    
    def get_account_limit(self, account_id: int) -> int:
        """
        Get the maximum concurrent streams for an account.
        
        Args:
            account_id: M3U account ID
            
        Returns:
            Maximum concurrent streams (0 = unlimited)
        """
        return self.account_limits.get(account_id, 0)
    
    def get_available_slots(self, account_id: int) -> int:
        """
        Get the number of available stream slots for an account.
        
        Considers both active viewers (from UDI) and currently checking streams.
        
        Args:
            account_id: M3U account ID
            
        Returns:
            Number of available slots (0 if at limit, -1 if unlimited)
        """
        limit = self.get_account_limit(account_id)
        
        if limit == 0:
            # Unlimited
            return -1
        
        # Get active streams from UDI if available
        active_count = 0
        if self.udi_manager:
            try:
                active_count = self.udi_manager.get_active_streams_for_account(account_id)
            except Exception as e:
                logger.warning(f"Could not get active streams for account {account_id}: {e}")
        
        # Available slots = limit - active streams
        available = limit - active_count
        return max(0, available)
    
    def acquire(self, account_id: Optional[int], timeout: float = None) -> tuple[bool, str]:
        """
        Acquire permission to check a stream from the given account.
        
        Considers active viewers (from UDI) when determining if a slot is available.
        
        Args:
            account_id: M3U account ID (None for custom streams)
            timeout: Maximum time to wait in seconds (None = wait forever)
            
        Returns:
            Tuple of (acquired: bool, reason: str)
            - (True, 'acquired') if slot was acquired
            - (False, 'active_viewers') if limit reached due to active viewers
            - (False, 'timeout') if timed out waiting for semaphore
        """
        if account_id is None:
            # Custom stream with no account - always allow
            return (True, 'acquired')
        
        # Check if we have available slots considering active viewers
        available_slots = self.get_available_slots(account_id)
        
        if available_slots != -1 and available_slots <= 0:
            # No slots available due to active viewers
            logger.warning(f"Cannot acquire slot for account {account_id}: limit reached with active viewers")
            return (False, 'active_viewers')
        
        with self.lock:
            semaphore = self.account_semaphores.get(account_id)
        
        if semaphore is None:
            # No limit set for this account (or unlimited)
            return (True, 'acquired')
        
        # Try to acquire the semaphore
        acquired = semaphore.acquire(blocking=True, timeout=timeout)
        
        if acquired:
            logger.debug(f"Acquired stream slot for account {account_id}")
            return (True, 'acquired')
        else:
            logger.warning(f"Timeout acquiring stream slot for account {account_id}")
            return (False, 'timeout')
    
    def release(self, account_id: Optional[int]):
        """
        Release a stream slot for the given account.
        
        Args:
            account_id: M3U account ID (None for custom streams)
        """
        if account_id is None:
            # Custom stream with no account - nothing to release
            return
        
        with self.lock:
            semaphore = self.account_semaphores.get(account_id)
        
        if semaphore is not None:
            semaphore.release()
            logger.debug(f"Released stream slot for account {account_id}")
    
    def clear(self):
        """Clear all account limits and semaphores."""
        with self.lock:
            self.account_semaphores.clear()
            self.account_limits.clear()
        logger.info("Cleared all account limits")


class SmartStreamScheduler:
    """
    Smart scheduler for parallel stream checking with per-account limits.
    
    This scheduler organizes streams by account and ensures that:
    1. Account limits are respected (max concurrent streams per account)
    2. Overall parallelism is maximized across different accounts
    3. Streams are scheduled efficiently to minimize total checking time
    """
    
    def __init__(self, account_limiter: AccountStreamLimiter, global_limit: int = 10):
        """
        Initialize the smart stream scheduler.
        
        Args:
            account_limiter: AccountStreamLimiter instance
            global_limit: Global maximum concurrent streams (default: 10)
        """
        self.account_limiter = account_limiter
        self.global_limit = global_limit
        logger.info(f"SmartStreamScheduler initialized with global_limit={global_limit}")
    
    def check_streams_with_limits(
        self,
        streams: List[Dict[str, Any]],
        check_function: Callable,
        progress_callback: Optional[Callable] = None,
        stagger_delay: float = 0.0,
        **check_params
    ) -> List[Dict[str, Any]]:
        """
        Check multiple streams in parallel with per-account concurrent limits.
        
        This method intelligently schedules stream checks to respect both:
        - Per-account concurrent stream limits
        - Global concurrent stream limit
        
        Args:
            streams: List of stream dictionaries to check (must include 'm3u_account')
            check_function: Function to call for each stream
            progress_callback: Optional callback after each stream completes
            stagger_delay: Delay between starting tasks (default: 0.0)
            **check_params: Additional parameters for check_function
            
        Returns:
            List of stream analysis results
        """
        if not streams:
            logger.info("No streams to check")
            return []
        
        total_streams = len(streams)
        logger.info(f"Starting smart parallel check of {total_streams} streams")
        
        # Group streams by account for better logging
        account_groups = defaultdict(list)
        for stream in streams:
            account_id = stream.get('m3u_account')
            account_groups[account_id].append(stream)
        
        logger.info(f"Streams grouped by account: {dict((k, len(v)) for k, v in account_groups.items())}")
        for account_id, account_streams in account_groups.items():
            limit = self.account_limiter.get_account_limit(account_id) if account_id else 0
            limit_str = "unlimited" if limit == 0 else str(limit)
            logger.info(f"  Account {account_id}: {len(account_streams)} streams, limit={limit_str}")
        
        results = []
        completed_count = 0
        lock = threading.Lock()
        
        # Use ThreadPoolExecutor with global limit
        with ThreadPoolExecutor(max_workers=self.global_limit) as executor:
            futures: Dict[Future, Dict[str, Any]] = {}
            
            def submit_stream_check(stream: Dict[str, Any]):
                """Submit a stream check with account limit enforcement."""
                account_id = stream.get('m3u_account')
                
                # Acquire account slot before submitting to executor
                # This ensures we don't exceed per-account limits
                acquired, reason = self.account_limiter.acquire(account_id, timeout=300)
                
                if not acquired:
                    if reason == 'active_viewers':
                        # Quota fully consumed by active viewers - use cached stats
                        logger.info(f"Skipping check for stream {stream['id']} - quota consumed by active viewers, using cached stats")
                        
                        # Get cached stream stats from UDI
                        if self.account_limiter.udi_manager:
                            try:
                                cached_stream = self.account_limiter.udi_manager.get_stream_by_id(stream['id'])
                                if cached_stream and cached_stream.get('stream_stats'):
                                    # Return a result with cached stats
                                    return {
                                        'stream_id': stream['id'],
                                        'stream_name': stream.get('name', 'Unknown'),
                                        'stream_url': stream.get('url', ''),
                                        'cached': True,
                                        'skipped_reason': 'quota_consumed_by_active_viewers',
                                        **cached_stream.get('stream_stats', {})
                                    }
                                else:
                                    logger.warning(f"No cached stats available for stream {stream['id']}, skipping")
                            except Exception as e:
                                logger.error(f"Error retrieving cached stats for stream {stream['id']}: {e}")
                        return None
                    else:
                        # Timeout - skip stream
                        logger.error(f"Timeout acquiring slot for account {account_id}, skipping stream {stream['id']}")
                        return None
                
                def wrapped_check():
                    """Wrapper that ensures semaphore is released."""
                    try:
                        result = check_function(
                            stream_url=stream.get('url', ''),
                            stream_id=stream['id'],
                            stream_name=stream.get('name', 'Unknown'),
                            **check_params
                        )
                        return result
                    finally:
                        # Always release the account slot when done
                        self.account_limiter.release(account_id)
                
                # Submit to executor
                future = executor.submit(wrapped_check)
                return future
            
            # Submit all streams with stagger delay
            for stream in streams:
                if stagger_delay > 0 and futures:
                    time.sleep(stagger_delay)
                
                future_or_result = submit_stream_check(stream)
                if future_or_result is not None:
                    if isinstance(future_or_result, dict):
                        # This is a cached result, not a future
                        with lock:
                            results.append(future_or_result)
                            completed_count += 1
                        logger.debug(f"Using cached stats for stream {stream['id']}")
                    else:
                        # This is a future for async check
                        futures[future_or_result] = stream
                        logger.debug(f"Submitted stream {stream['id']} for checking")
            
            # Process completed tasks as they finish (in completion order for better parallelism)
            from concurrent.futures import as_completed
            for future in as_completed(futures):
                stream = futures[future]
                try:
                    # Wait for completion
                    result = future.result()
                    
                    with lock:
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
                    with lock:
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
        
        logger.info(f"Completed smart parallel check of {completed_count}/{total_streams} streams")
        return results


# Global instance
_account_limiter = None
_smart_scheduler = None
_limiter_lock = threading.RLock()  # Use RLock to allow recursive locking


def get_account_limiter() -> AccountStreamLimiter:
    """
    Get or create the global account limiter instance.
    
    Returns:
        AccountStreamLimiter instance
    """
    global _account_limiter
    with _limiter_lock:
        if _account_limiter is None:
            # Import UDI manager here to avoid circular imports
            from udi import get_udi_manager
            udi_manager = get_udi_manager()
            _account_limiter = AccountStreamLimiter(udi_manager=udi_manager)
        return _account_limiter


def get_smart_scheduler(global_limit: int = 10) -> SmartStreamScheduler:
    """
    Get or create the global smart scheduler instance.
    
    Args:
        global_limit: Global maximum concurrent streams
        
    Returns:
        SmartStreamScheduler instance
    """
    global _smart_scheduler
    with _limiter_lock:
        account_limiter = get_account_limiter()
        if _smart_scheduler is None or _smart_scheduler.global_limit != global_limit:
            _smart_scheduler = SmartStreamScheduler(account_limiter, global_limit=global_limit)
        return _smart_scheduler


def initialize_account_limits(accounts: List[Dict[str, Any]]):
    """
    Initialize account limits from M3U account data.
    
    Args:
        accounts: List of M3U account dictionaries with 'id' and 'max_streams' fields
    """
    limiter = get_account_limiter()
    
    for account in accounts:
        account_id = account.get('id')
        max_streams = account.get('max_streams', 0)
        
        if account_id is not None:
            limiter.set_account_limit(account_id, max_streams)
    
    logger.info(f"Initialized limits for {len(accounts)} accounts")
