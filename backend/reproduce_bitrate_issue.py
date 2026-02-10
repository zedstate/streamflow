
import re
import time
from dataclasses import dataclass

# Mock FFmpegStats
@dataclass
class FFmpegStats:
    url: str
    speed: float = 0.0
    bitrate: float = 0.0  # kbps
    fps: float = 0.0
    width: int = 0
    height: int = 0
    time: float = 0.0  # seconds
    last_updated: float = 0.0
    is_alive: bool = False
    error_message: str = None
    total_size: int = 0  # bytes
    start_time: float = 0.0

BITS_PER_BYTE = 8
BYTES_TO_KBPS = 1000

class MockFFmpegMonitor:
    def __init__(self):
        self.stats = FFmpegStats(url="test_stream")
        
    def _parse_stats(self, output: str):
        # COPY OF LOGIC FROM ffmpeg_stream_monitor.py
        
        # Speed (e.g., "speed=1.02x")
        speed_match = re.search(r'speed=\s*(\d+(?:\.\d+)?)x?', output)
        if speed_match:
            self.stats.speed = float(speed_match.group(1))
        
        # Bitrate (e.g., "bitrate= 406.1kbits/s")
        bitrate_found = False
        bitrate_match = re.search(r'bitrate=\s*([0-9.]+)\s*([kmg]?)bits/s', output, re.IGNORECASE)
        if bitrate_match:
            value = float(bitrate_match.group(1))
            unit = bitrate_match.group(2).lower()
            
            # Convert to kbps
            if unit == 'm':
                value *= 1000
            elif unit == 'g':
                value *= 1000000
            # 'k' or empty defaults to kbps
            
            self.stats.bitrate = value
            bitrate_found = True
        
        # Size (e.g., "size= 12345kB") - for calculating bitrate if not provided
        size_match = re.search(r'size=\s*([0-9.]+)\s*([kmg]?)B', output, re.IGNORECASE)
        if size_match:
            value = float(size_match.group(1))
            unit = size_match.group(2).lower()
            
            # Convert to bytes
            if unit == 'k':
                value *= 1024
            elif unit == 'm':
                value *= 1024 * 1024
            elif unit == 'g':
                value *= 1024 * 1024 * 1024
            
            self.stats.total_size = int(value)
            
            # NEW FIXED LOGIC:
            # Calculate bitrate from size and time if explicit bitrate not available
            # We check !bitrate_found rather than stats.bitrate == 0 to allow updates 
            # if the stream stays in "bitrate=N/A" state but size/time keep growing.
            if not bitrate_found and self.stats.time > 0:
                # bitrate = (total_size * BITS_PER_BYTE) / time / BYTES_TO_KBPS (to get kbps)
                self.stats.bitrate = (self.stats.total_size * BITS_PER_BYTE) / self.stats.time / BYTES_TO_KBPS
        
        # Time (e.g., "time=00:01:23.45")
        time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', output)
        if time_match:
            hours = float(time_match.group(1))
            minutes = float(time_match.group(2))
            seconds = float(time_match.group(3))
            self.stats.time = hours * 3600 + minutes * 60 + seconds

def test_latching_issue():
    monitor = MockFFmpegMonitor()
    
    # 1. First line: broken bitrate, small time/size -> Bad calculation?
    # Or just explicit 0?
    
    # Let's verify what happens if bitrate is N/A
    line1 = "frame=  123 fps= 25 q=-0.0 size=       0kB time=00:00:00.10 bitrate=N/A speed=   1x"
    monitor._parse_stats(line1)
    print(f"Line 1 (Size 0): Bitrate={monitor.stats.bitrate} (Expected 0 since size is 0)")
    
    # 2. Second line: Stream loading... still N/A bitrate, but size increasing
    line2 = "frame=  123 fps= 25 q=-0.0 size=    1000kB time=00:00:10.00 bitrate=N/A speed=   1x"
    monitor._parse_stats(line2)
    print(f"Line 2 (Size 1000kB, 10s): Bitrate={monitor.stats.bitrate}")
    # Calculation: 1000kB = 1024000 bytes. * 8 = 8192000 bits. / 10s = 819200 bps = 819.2 kbps.
    
    # 3. Third line: Stream playing fine, but ffmpeg still says N/A bitrate
    line3 = "frame=  123 fps= 25 q=-0.0 size=    2000kB time=00:00:20.00 bitrate=N/A speed=   1x"
    monitor._parse_stats(line3)
    print(f"Line 3 (Size 2000kB, 20s): Bitrate={monitor.stats.bitrate}")
    
    # 4. NOW: What if line 1 calculated a non-zero but WRONG bitrate?
    # e.g. a burst of data at start but time is small?
    line4_bad_start = "frame= 1 fps=1 size=100kB time=00:00:00.01 bitrate=N/A speed=1x"
    monitor2 = MockFFmpegMonitor()
    monitor2._parse_stats(line4_bad_start)
    print(f"Monitor 2 Line 1: Bitrate={monitor2.stats.bitrate}")
    # 100kB = 102400 bytes = 819200 bits. / 0.01s = 81,920,000 bps = 81,920 kbps. HUGE.
    
    # Monitor 2, Line 2: Normalized
    line5_normal = "frame= 100 fps=25 size=1000kB time=00:00:10.00 bitrate=N/A speed=1x"
    monitor2._parse_stats(line5_normal)
    print(f"Monitor 2 Line 2: Bitrate={monitor2.stats.bitrate}")
    # Should be ~819 kbps.
    # But if it's latched?
    
    if monitor2.stats.bitrate > 10000:
        print("FAIL: Bitrate stuck at high initial value!")
    else:
        print("PASS: Bitrate updated.")

if __name__ == "__main__":
    test_latching_issue()
