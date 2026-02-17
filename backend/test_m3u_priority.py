import json
from typing import Dict, List, Optional, Any, Tuple

class MockUDI:
    def __init__(self, streams):
        self.streams = {s['id']: s for s in streams}
    
    def get_stream_by_id(self, stream_id):
        return self.streams.get(stream_id)

def calculate_stream_score(stream_data: Dict) -> float:
    """Reproduction of _calculate_stream_score logic."""
    weights = {'bitrate': 0.40, 'resolution': 0.35, 'fps': 0.15, 'codec': 0.10, 'hdr': 0.10}
    score = 0.0
    
    # Bitrate
    bitrate = stream_data.get('bitrate_kbps', 0)
    score += min(bitrate / 8000, 1.0) * weights['bitrate']
    
    # Resolution
    res = stream_data.get('resolution', 'N/A')
    res_score = 0.3
    if 'x' in str(res):
        height = int(res.split('x')[1])
        if height >= 2160: res_score = 1.0
        elif height >= 1080: res_score = 0.85
        elif height >= 720: res_score = 0.7
        elif height >= 576: res_score = 0.5
    score += res_score * weights['resolution']
    
    # FPS
    fps = stream_data.get('fps', 0)
    score += min(fps / 60, 1.0) * weights['fps']
    
    # Codec
    codec = stream_data.get('video_codec', '').lower()
    codec_score = 0.5
    if 'h265' in codec or 'hevc' in codec: codec_score = 1.0
    elif 'h264' in codec or 'avc' in codec: codec_score = 0.8
    score += codec_score * weights['codec']
    
    return round(score, 2)

def get_resolution_tier(resolution: str) -> int:
    if 'x' not in str(resolution): return 5
    height = int(resolution.split('x')[1])
    if height >= 2160: return 0
    if height >= 1080: return 1
    if height >= 720:  return 2
    if height >= 576:  return 3
    return 4

def generate_stream_sort_key(stream_data: Dict, udi: MockUDI, priority_m3u_ids: List[int] = None, priority_mode: str = 'absolute') -> Tuple:
    account_rank = 100
    stream_id = stream_data.get('stream_id')
    if priority_m3u_ids and stream_id:
        stream = udi.get_stream_by_id(stream_id)
        if stream:
            m3u_id = stream.get('m3u_account')
            if m3u_id in priority_m3u_ids:
                account_rank = priority_m3u_ids.index(m3u_id)
    
    res_tier = get_resolution_tier(stream_data.get('resolution'))
    match_rank = 1000
    quality_score = -stream_data.get('score', 0.0)
    
    if priority_mode == 'same_resolution':
        return (res_tier, account_rank, match_rank, quality_score)
    elif priority_mode == 'equal':
        return (res_tier, match_rank, quality_score)
    else: # 'absolute'
        return (account_rank, res_tier, match_rank, quality_score)

# Realistic Mock Data
streams_info = [
    {"id": 1, "m3u_account": 101, "name": "Stream 1 (Acc 101, 1080p)"},
    {"id": 2, "m3u_account": 101, "name": "Stream 2 (Acc 101, 720p)"},
    {"id": 3, "m3u_account": 102, "name": "Stream 3 (Acc 102, 2160p)"},
    {"id": 4, "m3u_account": 102, "name": "Stream 4 (Acc 102, 1080p)"},
    {"id": 5, "m3u_account": 103, "name": "Stream 5 (Acc 103, 1080p)"},
]

check_results_base = [
    {"stream_id": 1, "resolution": "1920x1080", "bitrate_kbps": 6000, "fps": 30, "video_codec": "h264"},
    {"stream_id": 2, "resolution": "1280x720", "bitrate_kbps": 4000, "fps": 60, "video_codec": "h264"},
    {"stream_id": 3, "resolution": "3840x2160", "bitrate_kbps": 15000, "fps": 24, "video_codec": "hevc"},
    {"stream_id": 4, "resolution": "1920x1080", "bitrate_kbps": 8000, "fps": 60, "video_codec": "hevc"},
    {"stream_id": 5, "resolution": "1920x1080", "bitrate_kbps": 9000, "fps": 30, "video_codec": "hevc"},
]

# Calculate scores dynamically
check_results = []
for res in check_results_base:
    res['score'] = calculate_stream_score(res)
    check_results.append(res)

udi = MockUDI(streams_info)
priority_m3u_ids = [101, 102]

def run_test(mode):
    print(f"\n--- Testing Priority Mode: {mode} ---")
    sorted_results = sorted(check_results, key=lambda x: generate_stream_sort_key(x, udi, priority_m3u_ids, mode))
    for i, res in enumerate(sorted_results):
        stream = udi.get_stream_by_id(res['stream_id'])
        key = generate_stream_sort_key(res, udi, priority_m3u_ids, mode)
        print(f"{i+1}. {stream['name']} | Res: {res['resolution']} | Score: {res['score']} | Sort Key: {key}")

run_test('absolute')
run_test('same_resolution')
run_test('equal')
