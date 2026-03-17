import subprocess
import time

def test_ffmpeg_tee():
    # Use the orchestrator URL provided by the user
    url = "http://orchestrator:8000/ace/getstream?id=c6a824a81b36f6c3529826477caf2ad94b45776d"
    port_a = 15000
    port_b = 25000
    
    # Try different tee syntax
    # Option 1: Original (with null output for stats preservation)
    # The [f=null]- part might be the issue if tee doesn't like it.
    # Let's try [f=null]null
    tee_outputs = f"[f=mpegts]udp://127.0.0.1:{port_a}|[f=mpegts]udp://127.0.0.1:{port_b}|[f=null]null"
    
    cmd = [
        'ffmpeg',
        '-hide_banner',
        '-i', url,
        '-c', 'copy',
        '-f', 'tee', tee_outputs
    ]
    
    print(f"Running: {' '.join(cmd)}")
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    # Wait a bit and check for errors
    time.sleep(5)
    
    if process.poll() is not None:
        print(f"Process exited with code {process.returncode}")
        stdout, stderr = process.communicate()
        print(f"Stderr: {stderr}")
    else:
        print("Process is still running (Success?)")
        process.terminate()

if __name__ == "__main__":
    test_ffmpeg_tee()
