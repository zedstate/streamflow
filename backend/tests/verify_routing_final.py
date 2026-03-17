import subprocess
import time
import os
import fcntl
import socket

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return False
        except socket.error:
            return True

def test_ffmpeg_routing_final():
    url = "/tmp/dummy.ts"
    # Use ports that are highly unlikely to be in use
    port_a = 18888
    port_b = 28888
    
    print(f"Ensuring ports {port_a} and {port_b} are free...")
    if is_port_in_use(port_a): print(f"ERROR: Port {port_a} busy")
    if is_port_in_use(port_b): print(f"ERROR: Port {port_b} busy")

    cmd = [
        'ffmpeg',
        '-hide_banner',
        '-re', # Read at native frame rate for simulation
        '-i', url,
        '-map', '0', '-c', 'copy', '-f', 'mpegts', f'udp://127.0.0.1:{port_a}',
        '-map', '0', '-c', 'copy', '-f', 'mpegts', f'udp://127.0.0.1:{port_b}',
        '-map', '0', '-c', 'copy', '-f', 'null', '-'
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    
    def start_listener(port):
        return subprocess.Popen(
            ['ffmpeg', '-hide_banner', '-i', f'udp://127.0.0.1:{port}', '-t', '3', '-f', 'null', '-'],
            stderr=subprocess.PIPE
        )
    
    sidecar_a = start_listener(port_a)
    sidecar_b = start_listener(port_b)
    
    time.sleep(1)
    
    primary = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0
    )
    
    print("Monitoring...")
    start_time = time.time()
    stats_found = False
    
    fd = primary.stderr.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    
    while time.time() - start_time < 8:
        try:
            chunk = primary.stderr.read(4096)
            if chunk:
                text = chunk.decode('utf-8', errors='ignore')
                if 'speed=' in text:
                    stats_found = True
        except IOError:
            pass
        if primary.poll() is not None: break
        time.sleep(0.5)
    
    primary.terminate()
    time.sleep(2)
    sidecar_a.terminate()
    sidecar_b.terminate()
    
    _, err_a = sidecar_a.communicate()
    _, err_b = sidecar_b.communicate()
    
    text_a = err_a.decode('utf-8', errors='ignore')
    text_b = err_b.decode('utf-8', errors='ignore')
    
    data_a = 'fps=' in text_a or 'frame=' in text_a
    data_b = 'fps=' in text_b or 'frame=' in text_b
    
    print(f"Data A: {data_a}")
    print(f"Data B: {data_b}")
    print(f"Stats: {stats_found}")
    
    if data_a and data_b and stats_found:
        print("VERIFICATION SUCCESS")
    else:
        print("VERIFICATION FAILED")

if __name__ == "__main__":
    test_ffmpeg_routing_final()
吐
