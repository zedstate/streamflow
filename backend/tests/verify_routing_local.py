import subprocess
import time
import os
import fcntl

def test_ffmpeg_routing_local():
    url = "/tmp/dummy.ts"
    port_a = 15000
    port_b = 25000
    
    # Use global ffmpeg
    # Command matches what we put in backend/ffmpeg_stream_monitor.py
    cmd = [
        'ffmpeg',
        '-hide_banner',
        '-i', url,
        '-map', '0', '-c', 'copy', '-f', 'mpegts', f'udp://127.0.0.1:{port_a}',
        '-map', '0', '-c', 'copy', '-f', 'mpegts', f'udp://127.0.0.1:{port_b}',
        '-map', '0', '-c', 'copy', '-f', 'null', '-'
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    
    # Start listeners FIRST to catch the stream
    def start_listener(port):
        return subprocess.Popen(
            ['ffmpeg', '-hide_banner', '-i', f'udp://127.0.0.1:{port}', '-t', '5', '-f', 'null', '-'],
            stderr=subprocess.PIPE
        )
    
    sidecar_a = start_listener(port_a)
    sidecar_b = start_listener(port_b)
    
    # Small delay for listeners to init
    time.sleep(1)
    
    # Start the primary router
    primary = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0
    )
    
    print("Monitoring progress...")
    start_time = time.time()
    stats_found = False
    
    # Non-blocking setup for stderr
    fd = primary.stderr.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    
    while time.time() - start_time < 10:
        try:
            chunk = primary.stderr.read(1024)
            if chunk:
                text = chunk.decode('utf-8', errors='ignore')
                if 'speed=' in text:
                    stats_found = True
        except IOError:
            pass
            
        if primary.poll() is not None:
            break
            
        time.sleep(0.5)
    
    primary.terminate()
    
    # Give listeners time to finish
    time.sleep(2)
    sidecar_a.terminate()
    sidecar_b.terminate()
    
    # Check if listeners saw any data
    out_a, err_a = sidecar_a.communicate()
    out_b, err_b = sidecar_b.communicate()
    
    text_a = err_a.decode('utf-8', errors='ignore')
    text_b = err_b.decode('utf-8', errors='ignore')
    
    data_a = 'fps=' in text_a or 'frame=' in text_a
    data_b = 'fps=' in text_b or 'frame=' in text_b
    
    print(f"Data on Port A: {data_a}")
    print(f"Data on Port B: {data_b}")
    print(f"Stats on Stderr: {stats_found}")
    
    if data_a and data_b and stats_found:
        print("Verification SUCCESS")
    else:
        if not data_a: print(f"DEBUG Port A: {text_a}")
        if not data_b: print(f"DEBUG Port B: {text_b}")
        print("Verification FAILED")

if __name__ == "__main__":
    test_ffmpeg_routing_local()
