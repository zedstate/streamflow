import os
import sys
import time
import shutil

# Setup path
sys.path.insert(0, os.path.abspath('backend'))
from monitoring_hls_proxy import HLS_ROOT, hls_proxy_manager

stream_id = 9999
hls_dir = os.path.join(HLS_ROOT, f"stream_{stream_id}")

def setup_dummy_hls(seq_start, init_content=b"INIT1"):
    os.makedirs(hls_dir, exist_ok=True)
    
    # Write init
    with open(os.path.join(hls_dir, "init.mp4"), 'wb') as f:
        f.write(init_content)
        
    # Write segments
    for i in range(seq_start, seq_start + 3):
        with open(os.path.join(hls_dir, f"seg_{i}.m4s"), 'wb') as f:
            f.write(f"DATA{i}".encode())
            
    # Write playlist
    playlist = f"""#EXTM3U
#EXT-X-VERSION:7
#EXT-X-TARGETDURATION:2
#EXT-X-MEDIA-SEQUENCE:{seq_start}
#EXT-X-MAP:URI="init.mp4"
#EXTINF:2.0,
seg_{seq_start}.m4s
#EXTINF:2.0,
seg_{seq_start+1}.m4s
#EXTINF:2.0,
seg_{seq_start+2}.m4s
"""
    with open(os.path.join(hls_dir, "playlist.m3u8"), 'w') as f:
        f.write(playlist)

def test_proxy():
    print("Setting up initial HLS stream...")
    if os.path.exists(hls_dir):
        shutil.rmtree(hls_dir)
    setup_dummy_hls(0, b"INIT1")
    
    proxy = hls_proxy_manager.get_proxy(stream_id)
    
    # Wait for proxy to poll and load
    time.sleep(1.5)
    
    pl1 = proxy.generate_playlist()
    print("=== First Playlist ===")
    print(pl1)
    assert 'seg_0.m4s' in pl1
    assert 'seg_1.m4s' in pl1
    assert 'seg_2.m4s' in pl1
    
    print("\nSimulating stream restart (FFMPEG restarts writing at seq 0 again)...")
    # Note: to trigger the init_mtime check, we wait a bit to ensure mtime is different
    time.sleep(1)
    setup_dummy_hls(0, b"INIT2")
    
    # Wait for proxy to poll
    time.sleep(1.5)
    
    pl2 = proxy.generate_playlist()
    print("=== Second Playlist (After Restart) ===")
    print(pl2)
    assert '#EXT-X-DISCONTINUITY' in pl2
    assert '#EXT-X-MAP:URI="init_3.mp4"' in pl2
    assert 'seg_5.m4s' in pl2  # because 3 next segments were written
    
    print("\nVerifying segment and init mapping:")
    init0 = proxy.get_init(0)
    init3 = proxy.get_init(3)
    print(f"Init 0: {init0}")
    print(f"Init 3: {init3}")
    assert init0 == b"INIT1"
    assert init3 == b"INIT2"
    
    print("\nTest passed successfully!")
    hls_proxy_manager.remove_proxy(stream_id)

if __name__ == '__main__':
    test_proxy()
