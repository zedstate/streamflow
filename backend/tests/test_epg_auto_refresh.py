#!/usr/bin/env python3
"""
Test EPG auto-refresh functionality.

These tests verify that:
1. The EPG refresh processor starts automatically
2. EPG data is fetched periodically
3. Programs are matched to auto-create rules
4. Scheduled events are created automatically
"""

import unittest
import tempfile
import time
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone
import sys
import os

# Set minimal environment before importing
os.environ['DISPATCHARR_BASE_URL'] = 'http://test.local'
os.environ['DISPATCHARR_TOKEN'] = 'test_token'

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEPGAutoRefresh(unittest.TestCase):
    """Test that EPG auto-refresh creates scheduled events from auto-create rules."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_epg_refresh_triggers_auto_create(self):
        """Test that EPG refresh automatically creates events from auto-create rules."""
        with patch('web_api.CONFIG_DIR', Path(self.temp_dir)):
            with patch('scheduling_service.CONFIG_DIR', Path(self.temp_dir)):
                # Reload module constants with patched CONFIG_DIR
                import scheduling_service
                scheduling_service.CONFIG_DIR = Path(self.temp_dir)
                scheduling_service.SCHEDULING_CONFIG_FILE = scheduling_service.CONFIG_DIR / 'scheduling_config.json'
                scheduling_service.SCHEDULED_EVENTS_FILE = scheduling_service.CONFIG_DIR / 'scheduled_events.json'
                scheduling_service.AUTO_CREATE_RULES_FILE = scheduling_service.CONFIG_DIR / 'auto_create_rules.json'
                
                from scheduling_service import get_scheduling_service, SchedulingService
                
                # Reset singleton
                scheduling_service._scheduling_service = None
                
                # Create mock EPG programs
                now = datetime.now(timezone.utc)
                mock_programs = [
                    {
                        'title': 'Breaking News at 5',
                        'start_time': (now + timedelta(hours=1)).isoformat(),
                        'end_time': (now + timedelta(hours=2)).isoformat(),
                        'tvg_id': 'test-channel-1'
                    },
                    {
                        'title': 'Regular Show',
                        'start_time': (now + timedelta(hours=2)).isoformat(),
                        'end_time': (now + timedelta(hours=3)).isoformat(),
                        'tvg_id': 'test-channel-1'
                    },
                    {
                        'title': 'Breaking News Special',
                        'start_time': (now + timedelta(hours=3)).isoformat(),
                        'end_time': (now + timedelta(hours=4)).isoformat(),
                        'tvg_id': 'test-channel-1'
                    }
                ]
                
                # Create an auto-create rule
                rule = {
                    'id': 'test-rule-1',
                    'name': 'Breaking News Alert',
                    'channel_id': 1,
                    'channel_name': 'Test Channel',
                    'channel_logo_url': None,
                    'tvg_id': 'test-channel-1',
                    'regex_pattern': '^Breaking News',
                    'minutes_before': 5,
                    'created_at': datetime.now().isoformat()
                }
                
                # Save the rule to file
                rule_file = Path(self.temp_dir) / 'auto_create_rules.json'
                with open(rule_file, 'w') as f:
                    json.dump([rule], f)
                
                # Mock UDI
                with patch('scheduling_service.get_udi_manager') as mock_udi_factory:
                    mock_udi = Mock()
                    mock_udi.get_channel_by_id.return_value = {
                        'id': 1,
                        'name': 'Test Channel',
                        'tvg_id': 'test-channel-1',
                        'logo_id': None
                    }
                    mock_udi.get_logo_by_id.return_value = None
                    mock_udi_factory.return_value = mock_udi
                    
                    # Mock fetch_data_from_url to return EPG data
                    with patch('scheduling_service.fetch_data_from_url') as mock_fetch:
                        mock_fetch.return_value = mock_programs
                        
                        # Initialize service (this loads the rule)
                        service = get_scheduling_service()
                        
                        # Verify rule is loaded
                        rules = service.get_auto_create_rules()
                        self.assertEqual(len(rules), 1, "Rule should be loaded")
                        
                        # Verify no events exist yet
                        events = service.get_scheduled_events()
                        self.assertEqual(len(events), 0, "No events should exist initially")
                        
                        # Call fetch_epg_grid (this is what the EPG refresh processor does)
                        service.fetch_epg_grid(force_refresh=True)
                        
                        # Verify events were created (this confirms EPG data was fetched and processed)
                        events = service.get_scheduled_events()
                        self.assertEqual(len(events), 2, "Should have created 2 events for matching programs")
                        
                        # Verify events match the expected programs
                        event_titles = [e['program_title'] for e in events]
                        self.assertIn('Breaking News at 5', event_titles)
                        self.assertIn('Breaking News Special', event_titles)
                        self.assertNotIn('Regular Show', event_titles)
    
    def test_epg_refresh_processor_starts(self):
        """Test that EPG refresh processor can start successfully."""
        with patch('web_api.CONFIG_DIR', Path(self.temp_dir)):
            with patch('scheduling_service.CONFIG_DIR', Path(self.temp_dir)):
                from web_api import (
                    start_epg_refresh_processor,
                    stop_epg_refresh_processor
                )
                
                # Mock the scheduling service
                with patch('web_api.get_scheduling_service') as mock_service:
                    mock_instance = Mock()
                    mock_instance.get_config.return_value = {'epg_refresh_interval_minutes': 60}
                    mock_instance.fetch_epg_grid.return_value = []
                    mock_service.return_value = mock_instance
                    
                    # Start the processor
                    success = start_epg_refresh_processor()
                    self.assertTrue(success, "Processor should start successfully")
                    
                    try:
                        # Wait a bit for the thread to initialize
                        time.sleep(1)
                        
                        # Verify the processor is running
                        from web_api import epg_refresh_thread, epg_refresh_running
                        self.assertIsNotNone(epg_refresh_thread, "Thread should be created")
                        self.assertTrue(epg_refresh_running, "Thread should be marked as running")
                        self.assertTrue(epg_refresh_thread.is_alive(), "Thread should be alive")
                        
                    finally:
                        # Stop the processor
                        success = stop_epg_refresh_processor()
                        self.assertTrue(success, "Processor should stop successfully")
    
    def test_multiple_rules_create_events(self):
        """Test that multiple auto-create rules work together."""
        with patch('web_api.CONFIG_DIR', Path(self.temp_dir)):
            with patch('scheduling_service.CONFIG_DIR', Path(self.temp_dir)):
                import scheduling_service
                scheduling_service.CONFIG_DIR = Path(self.temp_dir)
                scheduling_service.SCHEDULING_CONFIG_FILE = scheduling_service.CONFIG_DIR / 'scheduling_config.json'
                scheduling_service.SCHEDULED_EVENTS_FILE = scheduling_service.CONFIG_DIR / 'scheduled_events.json'
                scheduling_service.AUTO_CREATE_RULES_FILE = scheduling_service.CONFIG_DIR / 'auto_create_rules.json'
                scheduling_service._scheduling_service = None
                
                from scheduling_service import get_scheduling_service
                
                # Create mock EPG programs for different channels
                now = datetime.now(timezone.utc)
                mock_programs = [
                    {
                        'title': 'Breaking News',
                        'start_time': (now + timedelta(hours=1)).isoformat(),
                        'end_time': (now + timedelta(hours=2)).isoformat(),
                        'tvg_id': 'channel-1'
                    },
                    {
                        'title': 'Sports Tonight',
                        'start_time': (now + timedelta(hours=2)).isoformat(),
                        'end_time': (now + timedelta(hours=3)).isoformat(),
                        'tvg_id': 'channel-2'
                    }
                ]
                
                # Create multiple auto-create rules
                rules = [
                    {
                        'id': 'rule-1',
                        'name': 'News Rule',
                        'channel_id': 1,
                        'channel_name': 'Channel 1',
                        'channel_logo_url': None,
                        'tvg_id': 'channel-1',
                        'regex_pattern': '^Breaking News',
                        'minutes_before': 5,
                        'created_at': datetime.now().isoformat()
                    },
                    {
                        'id': 'rule-2',
                        'name': 'Sports Rule',
                        'channel_id': 2,
                        'channel_name': 'Channel 2',
                        'channel_logo_url': None,
                        'tvg_id': 'channel-2',
                        'regex_pattern': 'Sports',
                        'minutes_before': 10,
                        'created_at': datetime.now().isoformat()
                    }
                ]
                
                # Save rules to file
                rule_file = Path(self.temp_dir) / 'auto_create_rules.json'
                with open(rule_file, 'w') as f:
                    json.dump(rules, f)
                
                # Mock UDI
                with patch('scheduling_service.get_udi_manager') as mock_udi_factory:
                    mock_udi = Mock()
                    
                    def get_channel(channel_id):
                        return {
                            'id': channel_id,
                            'name': f'Channel {channel_id}',
                            'tvg_id': f'channel-{channel_id}',
                            'logo_id': None
                        }
                    
                    mock_udi.get_channel_by_id.side_effect = get_channel
                    mock_udi.get_logo_by_id.return_value = None
                    mock_udi_factory.return_value = mock_udi
                    
                    # Mock requests
                    with patch('scheduling_service.fetch_data_from_url') as mock_fetch:
                        mock_fetch.return_value = mock_programs
                        
                        # Initialize service and fetch EPG
                        service = get_scheduling_service()
                        programs = service.fetch_epg_grid(force_refresh=True)
                        
                        # Verify both events were created
                        events = service.get_scheduled_events()
                        self.assertEqual(len(events), 2, "Should have created 2 events (one per rule)")
                        
                        # Verify event details
                        event_titles = {e['program_title'] for e in events}
                        self.assertIn('Breaking News', event_titles)
                        self.assertIn('Sports Tonight', event_titles)


if __name__ == '__main__':
    unittest.main()
