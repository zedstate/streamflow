#!/usr/bin/env python3
import threading
import time
from concurrent_stream_limiter import SmartStreamScheduler, AccountStreamLimiter

class MockUDI:
    def check_stream_can_run(self, stream):
        return True, "acquired"
    def get_stream_by_id(self, id):
        return None

def dummy_check(stream_url, stream_id, stream_name, **kwargs):
    time.sleep(2)  # Simulate slow check
    return {"status": "OK", "stream_id": stream_id}

def verify_parallel_abort():
    print("Testing parallel abort...")
    limiter = AccountStreamLimiter()
    limiter.set_account_limit(1, 10)  # Setup some limit
    scheduler = SmartStreamScheduler(limiter, global_limit=5)
    
    abort_event = threading.Event()
    
    streams = [
        {"id": i, "m3u_account": 1, "name": f"Stream {i}", "url": f"http://test{i}"}
        for i in range(1, 6)
    ]
    
    # Trigger abort after 1 second
    def delayed_abort():
        time.sleep(1)
        print("  Triggering abort...")
        abort_event.set()
        
    abort_thread = threading.Thread(target=delayed_abort)
    abort_thread.start()
    
    start_time = time.time()
    results = scheduler.check_streams_with_limits(
        streams=streams,
        check_function=dummy_check,
        abort_event=abort_event
    )
    duration = time.time() - start_time
    
    print(f"  Finished in {duration:.2f} seconds")
    print(f"  Got {len(results)} results (expected < 5 due to abort)")
    
    abort_thread.join()
    
    if len(results) < 5:
        print("✓ Parallel abort test PASSED")
        return True
    else:
        print("✗ Parallel abort test FAILED")
        return False

if __name__ == "__main__":
    passed = verify_parallel_abort()
    if passed:
        print("\nAll Clear Queue verification tests PASSED")
    else:
        print("\nSome tests FAILED")
