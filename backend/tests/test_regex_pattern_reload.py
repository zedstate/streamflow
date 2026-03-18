"""Test regex pattern reload functionality to ensure cached patterns are refreshed."""
import unittest
import sys
from pathlib import Path
import tempfile
import json
import shutil

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from automated_stream_manager import RegexChannelMatcher


class TestRegexPatternReload(unittest.TestCase):
    """Test that regex patterns are properly reloaded from the database."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary config file used to seed the initial DB state.
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_regex_config.json"
        
        # Create initial test configuration
        initial_config = {
            "patterns": {
                "1": {
                    "name": "Test Channel",
                    "regex": [".*TEST.*"],
                    "enabled": True
                }
            },
            "global_settings": {
                "case_sensitive": False,
                "require_exact_match": False
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(initial_config, f)
        
        self.matcher = RegexChannelMatcher(config_file=self.config_file)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_db(self, config: dict):
        """Import *config* into the DB (replaces all existing patterns)."""
        from database.manager import get_db_manager
        get_db_manager().import_channel_regex_configs_from_json(config, merge=False)
        if isinstance(config.get('global_settings'), dict):
            get_db_manager().set_system_setting(
                'channel_regex_global_settings', config['global_settings']
            )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_reload_picks_up_manual_changes(self):
        """Test that reload_patterns() picks up DB updates."""
        # Initial state - should have one pattern
        patterns = self.matcher.get_patterns()
        self.assertIn('1', patterns['patterns'])
        self.assertEqual(patterns['patterns']['1']['name'], 'Test Channel')
        
        # Update the DB (simulating an external change)
        updated_config = {
            "patterns": {
                "1": {
                    "name": "Updated Channel",
                    "regex": [".*UPDATED.*"],
                    "enabled": True
                },
                "2": {
                    "name": "New Channel",
                    "regex": [".*NEW.*"],
                    "enabled": True
                }
            },
            "global_settings": {
                "case_sensitive": False,
                "require_exact_match": False
            }
        }
        
        self._update_db(updated_config)
        
        # Before reload - should still have old data
        patterns = self.matcher.get_patterns()
        self.assertEqual(patterns['patterns']['1']['name'], 'Test Channel')
        self.assertNotIn('2', patterns['patterns'])
        
        # After reload - should have new data
        self.matcher.reload_patterns()
        patterns = self.matcher.get_patterns()
        self.assertEqual(patterns['patterns']['1']['name'], 'Updated Channel')
        self.assertIn('2', patterns['patterns'])
        self.assertEqual(patterns['patterns']['2']['name'], 'New Channel')
    
    def test_reload_removes_invalid_regex(self):
        """Test that reload automatically removes patterns with invalid regex."""
        # Insert an invalid regex pattern directly via the DAL
        from database.manager import get_db_manager
        db = get_db_manager()

        # Add a valid channel (already seeded as channel 1)
        db.upsert_channel_regex_config(
            channel_id=1,
            name='Valid Channel',
            enabled=True,
            match_by_tvg_id=False,
            regex_patterns=[{'pattern': '.*VALID.*', 'm3u_accounts': None}],
        )
        # Add a channel with an invalid pattern
        from database.models import ChannelRegexConfig, ChannelRegexPattern
        from database.connection import get_session
        session = get_session()
        cfg = ChannelRegexConfig(channel_id=2, name='Invalid Channel', enabled=True, match_by_tvg_id=False)
        session.add(cfg)
        session.flush()
        session.add(ChannelRegexPattern(
            channel_id=2,
            pattern='.*CBS.*WWAY(?!-',  # Invalid – missing closing paren
            m3u_accounts=None,
            step_order=0,
        ))
        session.commit()
        session.close()

        # Reload should remove the invalid pattern
        self.matcher.reload_patterns()
        patterns = self.matcher.get_patterns()
        
        # Valid pattern should remain
        self.assertIn('1', patterns['patterns'])
        self.assertEqual(patterns['patterns']['1']['name'], 'Valid Channel')
        
        # Invalid pattern should be removed
        self.assertNotIn('2', patterns['patterns'])
    
    def test_reload_handles_empty_db(self):
        """Test that reload handles an empty DB gracefully."""
        from database.manager import get_db_manager
        from database.models import ChannelRegexConfig
        from database.connection import get_session

        # Wipe all configs
        session = get_session()
        session.query(ChannelRegexConfig).delete()
        session.commit()
        session.close()

        self.matcher.reload_patterns()
        patterns = self.matcher.get_patterns()
        
        # Should have valid structure with empty patterns
        self.assertIn('patterns', patterns)
        self.assertIn('global_settings', patterns)
        self.assertEqual(patterns['patterns'], {})
    
    def test_multiple_reloads(self):
        """Test that multiple DB updates followed by reloads work correctly."""
        for version in range(1, 4):
            config = {
                "patterns": {
                    "1": {
                        "name": f"Version {version}",
                        "regex": [f".*V{version}.*"],
                        "enabled": True,
                    }
                },
                "global_settings": {"case_sensitive": False, "require_exact_match": False},
            }
            self._update_db(config)
            self.matcher.reload_patterns()
            patterns = self.matcher.get_patterns()
            self.assertEqual(patterns['patterns']['1']['name'], f'Version {version}')


if __name__ == '__main__':
    unittest.main()

