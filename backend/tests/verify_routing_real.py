import subprocess
import time
import os
import fcntl
import socket

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def test_ffmpeg_routing_real():
    # Real URL for testing
    url = "http://orchestrator:8000/ace/getstream?id=c6a824a81b36f6c3529826477caf2ad94b45776d"
    port_a = 16000 # Use different ports to avoid "already in use" from previous failed tests
    port_b = 26000
    
    print(f"Checking ports {port_a} and {port_b}...")
    if is_port_in_use(port_a): print(f"WARNING: Port {port_a} is busy")
    if is_port_in_use(port_b): print(f"WARNING: Port {port_b} is busy")

    # Command from ffmpeg_stream_monitor.py
    cmd = [
        'ffmpeg',
        '-hide_banner',
        '-i', url,
        '-map', '0', '-c', 'copy', '-f', 'mpegts', f'udp://127.0.0.1:{port_a}',
        '-map', '0', '-c', 'copy', '-f', 'mpegts', f'udp://127.0.0.1:{port_b}',
        '-map', '0', '-c', 'copy', '-f', 'null', '-'
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    
    # Start listeners FIRST
    # We use -timeout to ensure they don't hang forever if no data comes
    def start_listener(port):
        # We use a very short timeout just to see if we get ANY packets
        return subprocess.Popen(
            ['ffmpeg', '-hide_banner', '-i', f'udp://127.0.0.1:{port}?timeout=3000000', '-t', '5', '-f', 'null', '-'],
            stderr=subprocess.PIPE
        )
    
    sidecar_a = start_listener(port_a)
    sidecar_b = start_listener(port_b)
    
    time.sleep(2)
    
    primary = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0
    )
    
    print("Monitoring stream for 20 seconds...")
    start_time = time.time()
    stats_found = False
    
    # Non-blocking setup
    fd = primary.stderr.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    
    while time.time() - start_time < 20:
        try:
            chunk = primary.stderr.read(4096)
            if chunk:
                text = chunk.decode('utf-8', errors='ignore')
                if 'speed=' in text:
                    stats_found = True
                    # print(f"Progress: {text.strip().splitlines()[-1]}")
        except IOError:
            pass
            
        if primary.poll() is not None:
            print(f"Primary process exited early with code {primary.returncode}")
            break
            
        time.sleep(1)
    
    primary.terminate()
    print("Stopping listeners...")
    time.sleep(3)
    sidecar_a.terminate()
    sidecar_b.terminate()
    
    _, err_a = sidecar_a.communicate()
    _, err_b = sidecar_b.communicate()
    
    text_a = err_a.decode('utf-8', errors='ignore')
    text_b = err_b.decode('utf-8', errors='ignore')
    
    data_a = 'fps=' in text_a or 'frame=' in text_a
    data_b = 'fps=' in text_b or 'frame=' in text_b
    
    print(f"\nRESULTS:")
    print(f"Data on Sidecar (Port {port_a}): {data_a}")
    print(f"Data on Screenshot (Port {port_b}): {data_b}")
    print(f"Telemetry (speed=): {stats_found}")
    
    if data_a and data_b and stats_found:
        print("\nALL SYSTEMS GO - TEST PASSED")
    else:
        print("\nTEST FAILED - Checking logs:")
        if not data_a: print(f"Sidecar Error: {text_a}")
        if not data_b: print(f"Screenshot Error: {text_b}")

if __name__ == "__main__":
    test_ffmpeg_routing_real()
