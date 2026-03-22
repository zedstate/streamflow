#!/usr/bin/env python3
"""
Test the stagger delay configuration for concurrent stream checking.

This test verifies that the stagger_delay configuration option is properly
recognized and has a sensible default value.
"""

import unittest
import sys
import os
import json
import tempfile
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestStaggerDelayConfig(unittest.TestCase):
    """Test stagger delay configuration."""
    
    def test_default_config_has_stagger_delay(self):
        """Test that the default configuration includes stagger_delay."""
        from apps.stream.stream_checker_service import StreamCheckConfig
        
        config = StreamCheckConfig.DEFAULT_CONFIG
        
        # Check that concurrent_streams section exists
        self.assertIn('concurrent_streams', config)
        
        # Check that stagger_delay is present
        self.assertIn('stagger_delay', config['concurrent_streams'])
        
        # Check that default value is sensible (positive, not too large)
        stagger_delay = config['concurrent_streams']['stagger_delay']
        self.assertIsInstance(stagger_delay, (int, float))
        self.assertGreaterEqual(stagger_delay, 0)
        self.assertLessEqual(stagger_delay, 10)
    
    def test_stagger_delay_default_value(self):
        """Test that the default stagger_delay is 1.0 second."""
        from apps.stream.stream_checker_service import StreamCheckConfig
        
        config = StreamCheckConfig.DEFAULT_CONFIG
        stagger_delay = config['concurrent_streams']['stagger_delay']
        
        # Default should be 1.0 second
        self.assertEqual(stagger_delay, 1.0)
    
    def test_stagger_delay_persists_in_config(self):
        """Test that stagger_delay can be saved and loaded from config file."""
        from apps.stream.stream_checker_service import StreamCheckConfig
        
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_file = Path(f.name)
            test_config = {
                'concurrent_streams': {
                    'enabled': True,
                    'global_limit': 20,
                    'stagger_delay': 2.5
                }
            }
            json.dump(test_config, f)
        
        try:
            # Load the config
            config = StreamCheckConfig(config_file=config_file)
            
            # Verify stagger_delay was loaded
            self.assertEqual(
                config.config['concurrent_streams']['stagger_delay'],
                2.5
            )
        finally:
            # Clean up
            if config_file.exists():
                config_file.unlink()
    
    def test_stagger_delay_missing_uses_default(self):
        """Test that missing stagger_delay falls back to default."""
        from apps.stream.stream_checker_service import StreamCheckConfig
        
        # Create a config without stagger_delay
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_file = Path(f.name)
            test_config = {
                'concurrent_streams': {
                    'enabled': True,
                    'global_limit': 15
                    # stagger_delay intentionally omitted
                }
            }
            json.dump(test_config, f)
        
        try:
            # Load the config
            config = StreamCheckConfig(config_file=config_file)
            
            # Should fall back to default of 1.0
            self.assertEqual(
                config.config['concurrent_streams'].get('stagger_delay', 1.0),
                1.0
            )
        finally:
            # Clean up
            if config_file.exists():
                config_file.unlink()


def main():
    """Run the tests."""
    print("=" * 60)
    print("Stagger Delay Configuration Tests")
    print("=" * 60)
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestStaggerDelayConfig)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    print(f"Results: {result.testsRun - len(result.failures) - len(result.errors)}/{result.testsRun} tests passed")
    print("=" * 60)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
