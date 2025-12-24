#!/usr/bin/env python3
"""
Unit tests for global priority mode fallback behavior.

This module tests that when an M3U account doesn't have an explicit priority_mode set,
it should fall back to the global_priority_mode instead of defaulting to 'disabled'.

This fixes the bug where setting global priority mode to "all_streams" didn't work
for accounts without explicit priority_mode settings.
"""

import unittest
import os
import sys
import tempfile
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGlobalPriorityModeFallback(unittest.TestCase):
    """Test that accounts without explicit priority_mode use global_priority_mode as fallback."""
    
    def setUp(self):
        """Set up test with a temporary config directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.old_config_dir = os.environ.get('CONFIG_DIR')
        os.environ['CONFIG_DIR'] = self.temp_dir
    
    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        
        # Restore original CONFIG_DIR
        if self.old_config_dir:
            os.environ['CONFIG_DIR'] = self.old_config_dir
        elif 'CONFIG_DIR' in os.environ:
            del os.environ['CONFIG_DIR']
    
    def test_fallback_to_global_priority_mode(self):
        """Test that accounts without explicit priority_mode use global_priority_mode."""
        from m3u_priority_config import M3UPriorityConfig
        
        config = M3UPriorityConfig()
        
        # Set global priority mode to "all_streams"
        result = config.set_global_priority_mode('all_streams')
        self.assertTrue(result, "Setting global priority mode should succeed")
        
        # Account 1 has no explicit priority_mode set
        # It should fall back to global_priority_mode
        account_1_mode = config.get_priority_mode(1)
        self.assertEqual(account_1_mode, 'all_streams',
                        "Account without explicit priority_mode should use global setting")
        
        # Account 2 also has no explicit priority_mode set
        account_2_mode = config.get_priority_mode(2)
        self.assertEqual(account_2_mode, 'all_streams',
                        "Another account without explicit priority_mode should use global setting")
    
    def test_explicit_priority_mode_overrides_global(self):
        """Test that explicit account priority_mode overrides global setting."""
        from m3u_priority_config import M3UPriorityConfig
        
        config = M3UPriorityConfig()
        
        # Set global priority mode to "all_streams"
        config.set_global_priority_mode('all_streams')
        
        # Set explicit priority_mode for account 1 to "disabled"
        result = config.set_priority_mode(1, 'disabled')
        self.assertTrue(result, "Setting account priority mode should succeed")
        
        # Account 1 should use its explicit setting, not the global one
        account_1_mode = config.get_priority_mode(1)
        self.assertEqual(account_1_mode, 'disabled',
                        "Account with explicit priority_mode should use its own setting")
        
        # Account 2 has no explicit setting, should use global
        account_2_mode = config.get_priority_mode(2)
        self.assertEqual(account_2_mode, 'all_streams',
                        "Account without explicit priority_mode should use global setting")
    
    def test_default_global_priority_mode_is_disabled(self):
        """Test that default global_priority_mode is 'disabled'."""
        from m3u_priority_config import M3UPriorityConfig
        
        config = M3UPriorityConfig()
        
        # Don't set any global or account-specific priority mode
        # Default should be 'disabled'
        global_mode = config.get_global_priority_mode()
        self.assertEqual(global_mode, 'disabled',
                        "Default global_priority_mode should be 'disabled'")
        
        account_mode = config.get_priority_mode(1)
        self.assertEqual(account_mode, 'disabled',
                        "Account without explicit mode should use default global mode 'disabled'")
    
    def test_changing_global_priority_mode_affects_accounts(self):
        """Test that changing global priority mode affects accounts without explicit settings."""
        from m3u_priority_config import M3UPriorityConfig
        
        config = M3UPriorityConfig()
        
        # Initially, global mode is 'disabled'
        account_1_mode = config.get_priority_mode(1)
        self.assertEqual(account_1_mode, 'disabled')
        
        # Change global mode to 'same_resolution'
        config.set_global_priority_mode('same_resolution')
        
        # Account 1 should now return 'same_resolution'
        account_1_mode = config.get_priority_mode(1)
        self.assertEqual(account_1_mode, 'same_resolution',
                        "Account should reflect new global priority mode")
        
        # Change global mode to 'all_streams'
        config.set_global_priority_mode('all_streams')
        
        # Account 1 should now return 'all_streams'
        account_1_mode = config.get_priority_mode(1)
        self.assertEqual(account_1_mode, 'all_streams',
                        "Account should reflect updated global priority mode")
    
    def test_mixed_explicit_and_global_modes(self):
        """Test behavior with a mix of explicit and global priority modes."""
        from m3u_priority_config import M3UPriorityConfig
        
        config = M3UPriorityConfig()
        
        # Set global mode to 'all_streams'
        config.set_global_priority_mode('all_streams')
        
        # Set explicit modes for some accounts
        config.set_priority_mode(1, 'disabled')
        config.set_priority_mode(2, 'same_resolution')
        # Account 3 has no explicit mode
        
        # Verify each account returns the correct mode
        self.assertEqual(config.get_priority_mode(1), 'disabled',
                        "Account 1 should use explicit 'disabled'")
        self.assertEqual(config.get_priority_mode(2), 'same_resolution',
                        "Account 2 should use explicit 'same_resolution'")
        self.assertEqual(config.get_priority_mode(3), 'all_streams',
                        "Account 3 should use global 'all_streams'")
        self.assertEqual(config.get_priority_mode(4), 'all_streams',
                        "Account 4 should use global 'all_streams'")


if __name__ == '__main__':
    unittest.main()
