import sys
import os
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from ffmpeg_stream_monitor import FFmpegStreamMonitor

def test_command_generation():
    url = "http://example.com/stream"
    stream_id = 123
    
    monitor = FFmpegStreamMonitor(url=url, stream_id=stream_id)
    
    with patch('subprocess.Popen') as mock_popen:
        mock_popen.return_value = MagicMock()
        monitor.start()
        
        # Check the command called
        args, kwargs = mock_popen.call_args
        cmd = args[0]
        
        print(f"Generated command: {' '.join(cmd)}")
        
        # Verify tee muxer and ports
        assert '-f' in cmd
        assert 'tee' in cmd
        assert 'udp://127.0.0.1:10123' in cmd[cmd.index('tee')+1]
        assert 'udp://127.0.0.1:20123' in cmd[cmd.index('tee')+1]
        assert '[f=null]-' in cmd[cmd.index('tee')+1]
        
        print("Command verification PASSED")

if __name__ == "__main__":
    try:
        test_command_generation()
    except Exception as e:
        print(f"Command verification FAILED: {e}")
        sys.exit(1)
