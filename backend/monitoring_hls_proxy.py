import os
import time
import threading
import logging
from typing import Dict, List, Optional, Set
import m3u8

logger = logging.getLogger(__name__)

HLS_ROOT = "/tmp/streamflow_hls"

class StreamBuffer:
    def __init__(self, max_segments=30):
        self.buffer: Dict[int, bytes] = {}
        self.max_segments = max_segments
        self.lock = threading.Lock()
        
    def add(self, seq: int, data: bytes):
        with self.lock:
            self.buffer[seq] = data
            if len(self.buffer) > self.max_segments:
                keys = sorted(self.buffer.keys())
                to_remove = keys[:-self.max_segments]
                for k in to_remove:
                    del self.buffer[k]
                    
    def get(self, seq: int) -> Optional[bytes]:
        with self.lock:
            return self.buffer.get(seq)
            
    def keys(self) -> List[int]:
        with self.lock:
            return sorted(self.buffer.keys())

class MonitoringHLSProxy:
    """
    In-memory HLS Proxy for monitoring sessions.
    Reads FFmpeg outputs from disk and unifies them into a continuous M3U8 playlist with
    EXT-X-DISCONTINUITY tags upon FFmpeg restarts.
    """
    def __init__(self, stream_id: int, manager):
        self.stream_id = stream_id
        self.manager = manager
        self.hls_dir = os.path.join(HLS_ROOT, f"stream_{stream_id}")
        self.buffer = StreamBuffer(max_segments=30)
        
        self.init_files: Dict[int, bytes] = {} # Maps start_seq -> init.mp4 data
        self.current_init_data: Optional[bytes] = None
        
        self.running = False
        self.thread = None
        
        self.target_duration = 2.0
        self.manifest_version = 7
        
        # Mapping from original sequence (from ffmpeg) to our monotonic sequence
        self.next_internal_sequence = 0
        self.segment_durations: Dict[int, float] = {}
        self.discontinuities: Set[int] = set()
        
        # State tracking
        self.last_seen_original_seq = -1
        self.last_init_time = 0.0
        self.last_activity_time = time.time()
        self.linger_seconds = 60
        
    def start(self):
        self.running = True
        self.thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name=f"HLSProxy-{self.stream_id}"
        )
        self.thread.start()
        logger.info(f"Started HLS Proxy for stream {self.stream_id}")
        
    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        logger.info(f"Stopped HLS Proxy for stream {self.stream_id}")
        
    def record_activity(self):
        self.last_activity_time = time.time()

    def generate_playlist(self) -> str:
        self.record_activity()
        
        lines = [
            "#EXTM3U",
            f"#EXT-X-VERSION:{self.manifest_version}",
            f"#EXT-X-TARGETDURATION:{int(self.target_duration + 0.5)}"
        ]
        
        available_seqs = self.buffer.keys()
        
        if not available_seqs:
            lines.append("#EXT-X-MEDIA-SEQUENCE:0")
            return "\n".join(lines) + "\n"
            
        lines.append(f"#EXT-X-MEDIA-SEQUENCE:{available_seqs[0]}")
        
        current_map_seq = -1
        
        for seq in available_seqs:
            if seq in self.discontinuities:
                lines.append("#EXT-X-DISCONTINUITY")
            
            # Add EXT-X-MAP if it's the first segment or follows a discontinuity
            if current_map_seq == -1 or seq in self.discontinuities:
                # Find the corresponding init file for this sequence
                # It's either exactly seq, or the largest key <= seq
                map_seq = -1
                for k in sorted(self.init_files.keys()):
                    if k <= seq:
                        map_seq = k
                    else:
                        break
                        
                if map_seq != -1:
                    lines.append(f'#EXT-X-MAP:URI="init_{map_seq}.mp4"')
                    current_map_seq = seq
                
            duration = self.segment_durations.get(seq, 2.0)
            lines.append(f"#EXTINF:{duration:.3f},")
            lines.append(f"seg_{seq}.m4s")
            
        return "\n".join(lines) + "\n"
        
    def get_segment(self, seq: int) -> Optional[bytes]:
        self.record_activity()
        return self.buffer.get(seq)
        
    def get_init(self, seq: int) -> Optional[bytes]:
        self.record_activity()
        return self.init_files.get(seq)

    def _poll_loop(self):
        playlist_path = os.path.join(self.hls_dir, "playlist.m3u8")
        
        while self.running:
            try:
                # Check for lingering timeout
                if (time.time() - self.last_activity_time) > self.linger_seconds:
                    logger.info(f"HLS Proxy {self.stream_id} idle for {self.linger_seconds}s, shutting down")
                    self.running = False
                    self.manager.remove_proxy(self.stream_id)
                    break

                if not os.path.exists(playlist_path):
                    time.sleep(0.5)
                    continue
                
                try:
                    with open(playlist_path, 'r') as f:
                        manifest_data = f.read()
                except Exception as e:
                    time.sleep(0.5)
                    continue
                    
                manifest = m3u8.loads(manifest_data)
                
                if manifest.target_duration:
                    self.target_duration = manifest.target_duration
                if manifest.version:
                    self.manifest_version = manifest.version
                    
                if not manifest.segments:
                    time.sleep(0.5)
                    continue
                    
                current_original_seqs = []
                for s in manifest.segments:
                    try:
                        seq = int(s.uri.split('_')[-1].split('.')[0])
                        current_original_seqs.append(seq)
                    except ValueError:
                        pass
                
                if not current_original_seqs:
                    time.sleep(0.5)
                    continue
                    
                is_restart = False
                
                # Detect restarts by checking init.mp4 modification time
                init_path = os.path.join(self.hls_dir, "init.mp4")
                if os.path.exists(init_path):
                    init_mtime = os.path.getmtime(init_path)
                    if init_mtime > self.last_init_time:
                        self.last_init_time = init_mtime
                        is_restart = True
                        try:
                            with open(init_path, 'rb') as f:
                                self.current_init_data = f.read()
                        except Exception as e:
                            logger.error(f"Error reading init.mp4: {e}")
                            
                # Fallback restart detection: sequence numbers jumped significantly backwards
                if not is_restart and self.last_seen_original_seq != -1:
                    if min(current_original_seqs) <= 1 and self.last_seen_original_seq > 5:
                        is_restart = True
                        
                for segment in manifest.segments:
                    # Extract original seq from filename "seg_x.m4s"
                    try:
                        orig_seq = int(segment.uri.split('_')[-1].split('.')[0])
                    except ValueError:
                        continue
                        
                    if orig_seq > self.last_seen_original_seq or is_restart:
                        # NEW segment!
                        seg_path = os.path.join(self.hls_dir, segment.uri)
                        if os.path.exists(seg_path):
                            try:
                                with open(seg_path, 'rb') as f:
                                    seg_data = f.read()
                                
                                # Assign monotonic sequence
                                my_seq = self.next_internal_sequence
                                self.next_internal_sequence += 1
                                
                                if is_restart:
                                    self.discontinuities.add(my_seq)
                                    if self.current_init_data:
                                        self.init_files[my_seq] = self.current_init_data
                                        # Clean up old init files exceeding limit
                                        if len(self.init_files) > 10:
                                            oldest_map = sorted(self.init_files.keys())[0]
                                            del self.init_files[oldest_map]
                                            if oldest_map in self.discontinuities:
                                                self.discontinuities.remove(oldest_map)
                                    is_restart = False # Reset flag so only the FIRST segment gets it
                                    
                                elif not self.init_files and self.current_init_data:
                                    # Very first segment ever seen
                                    self.init_files[my_seq] = self.current_init_data
                                    
                                self.buffer.add(my_seq, seg_data)
                                self.segment_durations[my_seq] = float(segment.duration)
                                
                                self.last_seen_original_seq = orig_seq
                            except Exception as e:
                                logger.error(f"Error reading segment {seg_path}: {e}")
                                
            except Exception as e:
                logger.error(f"HLS Proxy loop error: {e}")
                
            time.sleep(0.5)

class MonitoringHLSProxyManager:
    def __init__(self):
        self.proxies: Dict[int, MonitoringHLSProxy] = {}
        self.lock = threading.Lock()
        
    def get_proxy(self, stream_id: int) -> MonitoringHLSProxy:
        with self.lock:
            if stream_id not in self.proxies:
                proxy = MonitoringHLSProxy(stream_id, self)
                proxy.start()
                self.proxies[stream_id] = proxy
            return self.proxies[stream_id]

    def remove_proxy(self, stream_id: int):
        with self.lock:
            if stream_id in self.proxies:
                self.proxies[stream_id].stop()
                del self.proxies[stream_id]

# Global instance
hls_proxy_manager = MonitoringHLSProxyManager()
