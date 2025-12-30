#!/usr/bin/env python3
"""
Test suite for concurrent stream limiter.

Tests the AccountStreamLimiter and SmartStreamScheduler to ensure:
1. Per-account concurrent stream limits are enforced
2. Multiple accounts can check streams in parallel
3. The smart scheduler maximizes concurrency while respecting limits
"""

import unittest
import time
import threading
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from concurrent_stream_limiter import (
    AccountStreamLimiter,
    SmartStreamScheduler,
    get_account_limiter,
    get_smart_scheduler,
    initialize_account_limits
)


class TestAccountStreamLimiter(unittest.TestCase):
    """Test cases for AccountStreamLimiter."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.limiter = AccountStreamLimiter()
    
    def _acquire(self, account_id, timeout=None):
        """Helper to acquire and return just the boolean result."""
        acquired, _ = self.limiter.acquire(account_id, timeout=timeout)
        return acquired
    
    def test_set_account_limit(self):
        """Test setting account limits."""
        self.limiter.set_account_limit(1, 2)
        self.assertEqual(self.limiter.get_account_limit(1), 2)
        
        self.limiter.set_account_limit(2, 1)
        self.assertEqual(self.limiter.get_account_limit(2), 1)
    
    def test_unlimited_account(self):
        """Test that accounts with 0 limit are unlimited."""
        self.limiter.set_account_limit(1, 0)
        
        # Should be able to acquire many times
        for _ in range(100):
            self.assertTrue(self._acquire(1))
        
        # Releases should not fail
        for _ in range(100):
            self.limiter.release(1)
    
    def test_single_stream_limit(self):
        """Test account with max_streams=1."""
        self.limiter.set_account_limit(1, 1)
        
        # First acquire should succeed
        self.assertTrue(self._acquire(1, timeout=0.1))
        
        # Second acquire should timeout
        self.assertFalse(self._acquire(1, timeout=0.1))
        
        # After release, should be able to acquire again
        self.limiter.release(1)
        self.assertTrue(self._acquire(1, timeout=0.1))
    
    def test_multiple_stream_limit(self):
        """Test account with max_streams=2."""
        self.limiter.set_account_limit(1, 2)
        
        # First two acquires should succeed
        self.assertTrue(self._acquire(1, timeout=0.1))
        self.assertTrue(self._acquire(1, timeout=0.1))
        
        # Third acquire should timeout
        self.assertFalse(self._acquire(1, timeout=0.1))
        
        # After one release, should be able to acquire one more
        self.limiter.release(1)
        self.assertTrue(self._acquire(1, timeout=0.1))
    
    def test_multiple_accounts_independent(self):
        """Test that different accounts have independent limits."""
        self.limiter.set_account_limit(1, 1)
        self.limiter.set_account_limit(2, 2)
        
        # Account 1: max 1 stream
        self.assertTrue(self._acquire(1, timeout=0.1))
        self.assertFalse(self._acquire(1, timeout=0.1))
        
        # Account 2: max 2 streams (should still work)
        self.assertTrue(self._acquire(2, timeout=0.1))
        self.assertTrue(self._acquire(2, timeout=0.1))
        self.assertFalse(self._acquire(2, timeout=0.1))
    
    def test_custom_stream_always_allowed(self):
        """Test that custom streams (None account) are always allowed."""
        # Even without setting any limits
        for _ in range(100):
            self.assertTrue(self._acquire(None))
        
        # Releases should not fail
        for _ in range(100):
            self.limiter.release(None)
    
    def test_concurrent_access(self):
        """Test concurrent access to the limiter."""
        self.limiter.set_account_limit(1, 2)
        
        acquired_count = []
        lock = threading.Lock()
        
        def worker():
            """Worker thread that tries to acquire."""
            if self.limiter.acquire(1, timeout=1.0):
                with lock:
                    acquired_count.append(1)
                time.sleep(0.1)
                self.limiter.release(1)
        
        # Start 10 threads
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All threads should eventually acquire
        self.assertEqual(len(acquired_count), 10)


class TestSmartStreamScheduler(unittest.TestCase):
    """Test cases for SmartStreamScheduler."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.limiter = AccountStreamLimiter()
        self.scheduler = SmartStreamScheduler(self.limiter, global_limit=10)
    
    def test_empty_streams(self):
        """Test with no streams."""
        results = self.scheduler.check_streams_with_limits(
            streams=[],
            check_function=lambda **kwargs: {'result': 'ok'}
        )
        self.assertEqual(len(results), 0)
    
    def test_single_account_single_stream(self):
        """Test with one account and one stream."""
        self.limiter.set_account_limit(1, 1)
        
        def mock_check(**kwargs):
            time.sleep(0.1)
            return {'stream_id': kwargs['stream_id'], 'status': 'OK'}
        
        streams = [
            {'id': 1, 'name': 'Stream 1', 'url': 'http://test.com/1', 'm3u_account': 1}
        ]
        
        results = self.scheduler.check_streams_with_limits(
            streams=streams,
            check_function=mock_check
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['stream_id'], 1)
        self.assertEqual(results[0]['status'], 'OK')
    
    def test_single_account_respects_limit(self):
        """Test that single account limit is respected."""
        self.limiter.set_account_limit(1, 1)
        
        max_concurrent = [0]
        current_concurrent = [0]
        lock = threading.Lock()
        
        def mock_check(**kwargs):
            with lock:
                current_concurrent[0] += 1
                if current_concurrent[0] > max_concurrent[0]:
                    max_concurrent[0] = current_concurrent[0]
            
            time.sleep(0.2)  # Simulate work
            
            with lock:
                current_concurrent[0] -= 1
            
            return {'stream_id': kwargs['stream_id'], 'status': 'OK'}
        
        streams = [
            {'id': i, 'name': f'Stream {i}', 'url': f'http://test.com/{i}', 'm3u_account': 1}
            for i in range(5)
        ]
        
        results = self.scheduler.check_streams_with_limits(
            streams=streams,
            check_function=mock_check
        )
        
        self.assertEqual(len(results), 5)
        # With max_streams=1, should never have more than 1 concurrent
        self.assertEqual(max_concurrent[0], 1)
    
    def test_multiple_accounts_parallel(self):
        """Test that multiple accounts can run in parallel."""
        self.limiter.set_account_limit(1, 1)
        self.limiter.set_account_limit(2, 1)
        
        max_concurrent = [0]
        current_concurrent = [0]
        lock = threading.Lock()
        
        def mock_check(**kwargs):
            with lock:
                current_concurrent[0] += 1
                if current_concurrent[0] > max_concurrent[0]:
                    max_concurrent[0] = current_concurrent[0]
            
            time.sleep(0.2)  # Simulate work
            
            with lock:
                current_concurrent[0] -= 1
            
            return {'stream_id': kwargs['stream_id'], 'status': 'OK'}
        
        streams = [
            {'id': 1, 'name': 'Stream A1', 'url': 'http://test.com/a1', 'm3u_account': 1},
            {'id': 2, 'name': 'Stream A2', 'url': 'http://test.com/a2', 'm3u_account': 1},
            {'id': 3, 'name': 'Stream B1', 'url': 'http://test.com/b1', 'm3u_account': 2},
            {'id': 4, 'name': 'Stream B2', 'url': 'http://test.com/b2', 'm3u_account': 2},
        ]
        
        results = self.scheduler.check_streams_with_limits(
            streams=streams,
            check_function=mock_check
        )
        
        self.assertEqual(len(results), 4)
        # With 2 accounts each having max_streams=1, max concurrent should be 2
        self.assertEqual(max_concurrent[0], 2)
    
    def test_mixed_limits(self):
        """Test the example from requirements: A(1), B(2) with streams A1,A2,B1,B2,B3."""
        self.limiter.set_account_limit(1, 1)  # Account A: max 1
        self.limiter.set_account_limit(2, 2)  # Account B: max 2
        
        max_concurrent = [0]
        current_concurrent = [0]
        account_concurrent = {1: 0, 2: 0}
        max_account_concurrent = {1: 0, 2: 0}
        lock = threading.Lock()
        
        # Map stream IDs to account IDs
        stream_to_account = {1: 1, 2: 1, 3: 2, 4: 2, 5: 2}
        
        def mock_check(**kwargs):
            stream_id = kwargs.get('stream_id')
            account_id = stream_to_account.get(stream_id, 1)
            
            with lock:
                current_concurrent[0] += 1
                account_concurrent[account_id] += 1
                
                if current_concurrent[0] > max_concurrent[0]:
                    max_concurrent[0] = current_concurrent[0]
                if account_concurrent[account_id] > max_account_concurrent[account_id]:
                    max_account_concurrent[account_id] = account_concurrent[account_id]
            
            time.sleep(0.2)  # Simulate work
            
            with lock:
                current_concurrent[0] -= 1
                account_concurrent[account_id] -= 1
            
            return {'stream_id': kwargs['stream_id'], 'status': 'OK'}
        
        streams = [
            {'id': 1, 'name': 'Stream A1', 'url': 'http://test.com/a1', 'm3u_account': 1},
            {'id': 2, 'name': 'Stream A2', 'url': 'http://test.com/a2', 'm3u_account': 1},
            {'id': 3, 'name': 'Stream B1', 'url': 'http://test.com/b1', 'm3u_account': 2},
            {'id': 4, 'name': 'Stream B2', 'url': 'http://test.com/b2', 'm3u_account': 2},
            {'id': 5, 'name': 'Stream B3', 'url': 'http://test.com/b3', 'm3u_account': 2},
        ]
        
        results = self.scheduler.check_streams_with_limits(
            streams=streams,
            check_function=mock_check
        )
        
        self.assertEqual(len(results), 5)
        # Account A should never exceed 1 concurrent
        self.assertLessEqual(max_account_concurrent[1], 1)
        # Account B should never exceed 2 concurrent
        self.assertLessEqual(max_account_concurrent[2], 2)
        # Overall, should be able to run 3 streams concurrently (A1+B1+B2)
        self.assertEqual(max_concurrent[0], 3)
    
    def test_progress_callback(self):
        """Test that progress callback is called correctly."""
        self.limiter.set_account_limit(1, 2)
        
        progress_calls = []
        
        def progress_callback(completed, total, result):
            progress_calls.append((completed, total, result['stream_id']))
        
        def mock_check(**kwargs):
            return {'stream_id': kwargs['stream_id'], 'status': 'OK'}
        
        streams = [
            {'id': i, 'name': f'Stream {i}', 'url': f'http://test.com/{i}', 'm3u_account': 1}
            for i in range(3)
        ]
        
        results = self.scheduler.check_streams_with_limits(
            streams=streams,
            check_function=mock_check,
            progress_callback=progress_callback
        )
        
        self.assertEqual(len(results), 3)
        self.assertEqual(len(progress_calls), 3)
        
        # Verify all streams were reported
        reported_ids = [call[2] for call in progress_calls]
        self.assertEqual(sorted(reported_ids), [0, 1, 2])


class TestInitializeAccountLimits(unittest.TestCase):
    """Test cases for initialize_account_limits function."""
    
    def test_initialize_single_account(self):
        """Test initializing a single account."""
        limiter = get_account_limiter()
        limiter.clear()
        
        accounts = [
            {'id': 1, 'max_streams': 2}
        ]
        
        initialize_account_limits(accounts)
        
        self.assertEqual(limiter.get_account_limit(1), 2)
    
    def test_initialize_multiple_accounts(self):
        """Test initializing multiple accounts."""
        limiter = get_account_limiter()
        limiter.clear()
        
        accounts = [
            {'id': 1, 'max_streams': 1},
            {'id': 2, 'max_streams': 2},
            {'id': 3, 'max_streams': 0},  # Unlimited
        ]
        
        initialize_account_limits(accounts)
        
        self.assertEqual(limiter.get_account_limit(1), 1)
        self.assertEqual(limiter.get_account_limit(2), 2)
        self.assertEqual(limiter.get_account_limit(3), 0)


if __name__ == '__main__':
    unittest.main()
