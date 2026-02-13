import unittest
import tempfile
import shutil
from pathlib import Path
from backend.automated_stream_manager import RegexChannelMatcher

class TestTVGIDMatching(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "channel_regex_config.json"
        self.matcher = RegexChannelMatcher(config_file=self.config_path)
        # Mock channels data
        self.channels = [
            {'id': 'ch1', 'name': 'Channel 1', 'tvg_id': 'channel1.tv', 'enabled': True},
            {'id': 'ch2', 'name': 'Channel 2', 'tvg_id': 'channel2.tv', 'enabled': True},
            {'id': 'ch3', 'name': 'Channel 3', 'tvg_id': None, 'enabled': True}
        ]
        self.channel_tvg_map = {
            'ch1': 'channel1.tv',
            'ch2': 'channel2.tv'
        }
    
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    def test_match_by_tvg_id_enabled(self):
        # Enable TVG-ID matching for ch1
        self.matcher.set_match_by_tvg_id('ch1', True)
        
        # Stream matches ch1 via TVG-ID
        stream_tvg_id = 'channel1.tv'
        stream_name = 'Some Stream'
        
        matches = self.matcher.match_stream_to_channels(
            stream_name=stream_name,
            stream_m3u_account='acc1',
            stream_tvg_id=stream_tvg_id,
            channel_tvg_ids=self.channel_tvg_map
        )
        
        self.assertIn('ch1', matches)
        
        # Verify priority
        priorities = self.matcher.match_stream_to_channels_with_priority(
            stream_name=stream_name,
            stream_m3u_account='acc1',
            stream_tvg_id=stream_tvg_id,
            channel_tvg_ids=self.channel_tvg_map
        )
        
        ch1_match = next((m for m in priorities if m['channel_id'] == 'ch1'), None)
        self.assertIsNotNone(ch1_match)
        self.assertEqual(ch1_match['priority'], 1000)

    def test_match_by_tvg_id_disabled(self):
        # Disable TVG-ID matching for ch1
        self.matcher.set_match_by_tvg_id('ch1', False)
        
        # Stream would match ch1 via TVG-ID, but feature is disabled
        stream_tvg_id = 'channel1.tv'
        stream_name = 'Some Stream'
        
        matches = self.matcher.match_stream_to_channels(
            stream_name=stream_name,
            stream_m3u_account='acc1',
            stream_tvg_id=stream_tvg_id,
            channel_tvg_ids=self.channel_tvg_map
        )
        
        self.assertNotIn('ch1', matches)

    def test_mixed_matching(self):
        # Enable TVG-ID matching for ch1
        self.matcher.set_match_by_tvg_id('ch1', True)
        
        # Add regex for ch2 manually
        if 'patterns' not in self.matcher.channel_patterns:
            self.matcher.channel_patterns['patterns'] = {}
        
        self.matcher.channel_patterns['patterns']['ch2'] = {
            'name': 'Channel 2',
            'regex_patterns': [{'pattern': 'Regex Match', 'm3u_accounts': None, 'priority': 10}],
            'enabled': True,
            'match_by_tvg_id': False
        }
        
        stream_tvg_id = 'channel1.tv'
        stream_name = 'Regex Match' # Matches ch2 regex
        
        matches = self.matcher.match_stream_to_channels(
            stream_name=stream_name,
            stream_m3u_account='acc1',
            stream_tvg_id=stream_tvg_id,
            channel_tvg_ids=self.channel_tvg_map
        )
        
        self.assertIn('ch1', matches) # TVG-ID match
        self.assertIn('ch2', matches) # Regex match
        
        priorities = self.matcher.match_stream_to_channels_with_priority(
            stream_name=stream_name,
            stream_m3u_account='acc1',
            stream_tvg_id=stream_tvg_id,
            channel_tvg_ids=self.channel_tvg_map
        )
        
        ch1_match = next((m for m in priorities if m['channel_id'] == 'ch1'), None)
        ch2_match = next((m for m in priorities if m['channel_id'] == 'ch2'), None)
        
        self.assertIsNotNone(ch1_match)
        self.assertEqual(ch1_match['priority'], 1000)
        
        self.assertIsNotNone(ch2_match)
        self.assertEqual(ch2_match['priority'], 10)

    def test_tvg_id_missing(self):
        self.matcher.set_match_by_tvg_id('ch1', True)
        
        # Stream missing TVG-ID
        matches = self.matcher.match_stream_to_channels(
            stream_name='Stream',
            stream_m3u_account='acc1',
            stream_tvg_id=None,
            channel_tvg_ids=self.channel_tvg_map
        )
        self.assertNotIn('ch1', matches)
        
        # Channel missing TVG-ID (ch3)
        self.matcher.set_match_by_tvg_id('ch3', True)
        matches = self.matcher.match_stream_to_channels(
            stream_name='Stream',
            stream_m3u_account='acc1',
            stream_tvg_id='some.id',
            channel_tvg_ids=self.channel_tvg_map
        )
        self.assertNotIn('ch3', matches)

if __name__ == '__main__':
    unittest.main()
