import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

# Add backend directory to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from apps.stream.stream_session_manager import StreamSessionManager, SessionInfo

class TestSessionMatchingtLogic(unittest.TestCase):
    def setUp(self):
        # Reset singleton to ensure clean state
        if hasattr(StreamSessionManager, '_instance'):
            StreamSessionManager._instance = None
            
        # Create temp dir for config
        self.test_dir = tempfile.mkdtemp()
        self.config_dir_patcher = patch('stream_session_manager.CONFIG_DIR', new=Path(self.test_dir))
        self.config_dir_patcher.start()
        
        self.session_manager = StreamSessionManager()
        self.session_manager.sessions = {}
        
        # Mock UDI
        self.mock_udi = MagicMock()
        patcher = patch('stream_session_manager.get_udi_manager', return_value=self.mock_udi)
        self.mock_get_udi = patcher.start()
        self.addCleanup(patcher.stop)
        
        # Test streams
        self.streams = [
            {'id': 's1', 'name': 'Generic Stream 1', 'tvg_id': 'channel1.tv', 'url': 'http://test1'},
            {'id': 's2', 'name': 'Exact Match Stream', 'tvg_id': 'other.tv', 'url': 'http://test2'},
            {'id': 's3', 'name': 'Another Stream', 'tvg_id': 'channel1.tv', 'url': 'http://test3'},
            {'id': 's4', 'name': 'Random Stream', 'tvg_id': None, 'url': 'http://test4'}
        ]
        self.mock_udi.get_streams.return_value = self.streams

    def tearDown(self):
        self.config_dir_patcher.stop()
        shutil.rmtree(self.test_dir)

    def test_match_by_tvg_id_only(self):
        """Test matching only by TVG-ID (no regex)"""
        session = SessionInfo(
            session_id='test_session',
            channel_id=1,
            channel_name='Test Channel',
            created_at=datetime.now().isoformat(),
            is_active=True,
            regex_filter=None,  # No regex
            channel_tvg_id='channel1.tv',
            match_by_tvg_id=True
        )
        self.session_manager.sessions['test_session'] = session
        
        # Run discovery
        self.session_manager._discover_streams('test_session')
        
        # Verify streams in session - streams are stored in session.streams dict
        matched_streams = list(self.session_manager.sessions['test_session'].streams.values())
        matched_ids = [s.stream_id for s in matched_streams]
        
        # Should match s1 and s3 (same tvg_id)
        self.assertIn('s1', matched_ids)
        self.assertIn('s3', matched_ids)
        # Should NOT match s2 (different tvg_id) or s4 (no tvg_id), even if regex was default
        self.assertNotIn('s2', matched_ids)
        self.assertNotIn('s4', matched_ids)
        self.assertEqual(len(matched_ids), 2)

    def test_match_by_regex_only(self):
        """Test matching only by Regex (legacy behavior)"""
        session = SessionInfo(
            session_id='test_session',
            channel_id=2,
            channel_name='Test Channel 2',
            created_at=datetime.now().isoformat(),
            is_active=True,
            regex_filter='Exact Match',
            channel_tvg_id='channel2.tv',
            match_by_tvg_id=False
        )
        self.session_manager.sessions['test_session'] = session
        
        # Run discovery
        self.session_manager._discover_streams('test_session')
        
        # Verify streams
        matched_streams = list(self.session_manager.sessions['test_session'].streams.values())
        matched_ids = [s.stream_id for s in matched_streams]
        
        # Should match s2 only
        self.assertIn('s2', matched_ids)
        self.assertEqual(len(matched_ids), 1)

    def test_match_by_both_or_logic(self):
        """Test matching by TVG-ID OR Regex"""
        session = SessionInfo(
            session_id='test_session',
            channel_id=3,
            channel_name='Test Channel 3',
            created_at=datetime.now().isoformat(),
            is_active=True,
            regex_filter='Random',  # Matches s4
            channel_tvg_id='channel1.tv',  # Matches s1 and s3
            match_by_tvg_id=True
        )
        self.session_manager.sessions['test_session'] = session
        
        # Run discovery
        self.session_manager._discover_streams('test_session')
        
        # Verify streams
        matched_streams = list(self.session_manager.sessions['test_session'].streams.values())
        matched_ids = [s.stream_id for s in matched_streams]
        
        # Should match s1, s3 (tvg_id) and s4 (regex)
        self.assertIn('s1', matched_ids)
        self.assertIn('s3', matched_ids)
        self.assertIn('s4', matched_ids)
        self.assertNotIn('s2', matched_ids)
        self.assertEqual(len(matched_ids), 3)

    def test_no_rules_match_nothing(self):
        """Test behavior when no rules are present (regex=None, match_by_tvg_id=False)"""
        session = SessionInfo(
            session_id='test_session',
            channel_id=4,
            channel_name='Test Channel 4',
            created_at=datetime.now().isoformat(),
            is_active=True,
            regex_filter=None,  # No regex rules
            channel_tvg_id='channel4.tv',
            match_by_tvg_id=False # No TVG-ID matching
        )
        self.session_manager.sessions['test_session'] = session
        
        # Run discovery
        self.session_manager._discover_streams('test_session')
        
        # Verify streams
        matched_streams = list(self.session_manager.sessions['test_session'].streams.values())
        
        # Should match NOTHING because there are no rules
        # (Previously matched everything with '.*')
        self.assertEqual(len(matched_streams), 0)

if __name__ == '__main__':
    unittest.main()
