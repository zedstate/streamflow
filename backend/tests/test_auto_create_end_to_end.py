#!/usr/bin/env python3
"""
End-to-end test for auto-create rules functionality.

This test simulates the complete user workflow:
1. User creates an auto-create rule
2. EPG refresh processor runs
3. Scheduled events are created automatically
4. Events are executed when due
"""

import unittest
import tempfile
import time
import json
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone
import sys
import os

# Set minimal environment before importing
os.environ['DISPATCHARR_BASE_URL'] = 'http://test.local'
os.environ['DISPATCHARR_TOKEN'] = 'test_token'

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAutoCreateEndToEnd(unittest.TestCase):
    """End-to-end test for auto-create rules."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_complete_auto_create_workflow(self):
        """Test the complete workflow from rule creation to event creation."""
        with patch('scheduling_service.CONFIG_DIR', Path(self.temp_dir)):
            import scheduling_service
            scheduling_service.CONFIG_DIR = Path(self.temp_dir)
            scheduling_service.SCHEDULING_CONFIG_FILE = scheduling_service.CONFIG_DIR / 'scheduling_config.json'
            scheduling_service.SCHEDULED_EVENTS_FILE = scheduling_service.CONFIG_DIR / 'scheduled_events.json'
            scheduling_service.AUTO_CREATE_RULES_FILE = scheduling_service.CONFIG_DIR / 'auto_create_rules.json'
            scheduling_service._scheduling_service = None
            
            from scheduling_service import get_scheduling_service
            
            # Mock UDI
            with patch('scheduling_service.get_udi_manager') as mock_udi_factory:
                mock_udi = Mock()
                mock_udi.get_channel_by_id.return_value = {
                    'id': 1,
                    'name': 'Sports Channel',
                    'tvg_id': 'sports-1',
                    'logo_id': None
                }
                mock_udi.get_logo_by_id.return_value = None
                mock_udi_factory.return_value = mock_udi
                
                # Create mock EPG programs
                now = datetime.now(timezone.utc)
                mock_programs = [
                    {
                        'title': 'NBA Finals Game 1',
                        'start_time': (now + timedelta(hours=2)).isoformat(),
                        'end_time': (now + timedelta(hours=4)).isoformat(),
                        'tvg_id': 'sports-1'
                    },
                    {
                        'title': 'Tennis Match',
                        'start_time': (now + timedelta(hours=5)).isoformat(),
                        'end_time': (now + timedelta(hours=7)).isoformat(),
                        'tvg_id': 'sports-1'
                    },
                    {
                        'title': 'NBA Finals Game 2',
                        'start_time': (now + timedelta(hours=8)).isoformat(),
                        'end_time': (now + timedelta(hours=10)).isoformat(),
                        'tvg_id': 'sports-1'
                    }
                ]
                
                # Mock requests
                with patch('scheduling_service.fetch_data_from_url') as mock_fetch:
                    mock_fetch.return_value = mock_programs
                    
                    # Step 1: Initialize service
                    service = get_scheduling_service()
                    
                    # Step 2: Create an auto-create rule (simulating user action)
                    rule_data = {
                        'name': 'NBA Games Alert',
                        'channel_id': 1,
                        'regex_pattern': '^NBA Finals',
                        'minutes_before': 10
                    }
                    rule = service.create_auto_create_rule(rule_data)
                    
                    # Verify rule was created
                    self.assertIsNotNone(rule['id'])
                    self.assertEqual(rule['name'], 'NBA Games Alert')
                    
                    # Wait for background thread to complete
                    time.sleep(1)
                    
                    # Step 3: Verify scheduled events were created automatically
                    events = service.get_scheduled_events()
                    
                    # Should have created 2 events (for the 2 NBA Finals games)
                    self.assertEqual(len(events), 2, 
                        f"Expected 2 events, got {len(events)}. Events: {[e['program_title'] for e in events]}")
                    
                    # Verify event details
                    event_titles = [e['program_title'] for e in events]
                    self.assertIn('NBA Finals Game 1', event_titles)
                    self.assertIn('NBA Finals Game 2', event_titles)
                    self.assertNotIn('Tennis Match', event_titles)
                    
                    # Verify check times are correct (10 minutes before)
                    for event in events:
                        program_start = datetime.fromisoformat(event['program_start_time'].replace('Z', '+00:00'))
                        check_time = datetime.fromisoformat(event['check_time'].replace('Z', '+00:00'))
                        time_diff = (program_start - check_time).total_seconds() / 60
                        self.assertAlmostEqual(time_diff, 10, delta=1, 
                            msg=f"Check time should be 10 minutes before program start")
                    
                    # Step 4: Test that EPG refresh creates more events if new programs match
                    # Add a new NBA game to the EPG
                    mock_programs.append({
                        'title': 'NBA Finals Game 3',
                        'start_time': (now + timedelta(hours=12)).isoformat(),
                        'end_time': (now + timedelta(hours=14)).isoformat(),
                        'tvg_id': 'sports-1'
                    })
                    
                    # Trigger another EPG refresh
                    programs = service.fetch_epg_grid(force_refresh=True)
                    
                    # Verify new event was created
                    events = service.get_scheduled_events()
                    self.assertEqual(len(events), 3, "Should have created 3 events after second refresh")
                    
                    event_titles = [e['program_title'] for e in events]
                    self.assertIn('NBA Finals Game 3', event_titles)
    
    def test_no_duplicate_events_on_multiple_refreshes(self):
        """Test that multiple EPG refreshes don't create duplicate events."""
        with patch('scheduling_service.CONFIG_DIR', Path(self.temp_dir)):
            import scheduling_service
            scheduling_service.CONFIG_DIR = Path(self.temp_dir)
            scheduling_service.SCHEDULING_CONFIG_FILE = scheduling_service.CONFIG_DIR / 'scheduling_config.json'
            scheduling_service.SCHEDULED_EVENTS_FILE = scheduling_service.CONFIG_DIR / 'scheduled_events.json'
            scheduling_service.AUTO_CREATE_RULES_FILE = scheduling_service.CONFIG_DIR / 'auto_create_rules.json'
            scheduling_service._scheduling_service = None
            
            from scheduling_service import get_scheduling_service
            
            with patch('scheduling_service.get_udi_manager') as mock_udi_factory:
                mock_udi = Mock()
                mock_udi.get_channel_by_id.return_value = {
                    'id': 1,
                    'name': 'News Channel',
                    'tvg_id': 'news-1',
                    'logo_id': None
                }
                mock_udi.get_logo_by_id.return_value = None
                mock_udi_factory.return_value = mock_udi
                
                now = datetime.now(timezone.utc)
                mock_programs = [
                    {
                        'title': 'Breaking News',
                        'start_time': (now + timedelta(hours=1)).isoformat(),
                        'end_time': (now + timedelta(hours=2)).isoformat(),
                        'tvg_id': 'news-1'
                    }
                ]
                
                with patch('scheduling_service.fetch_data_from_url') as mock_fetch:
                    mock_fetch.return_value = mock_programs
                    
                    service = get_scheduling_service()
                    
                    # Create rule
                    rule_data = {
                        'name': 'Breaking News Alert',
                        'channel_id': 1,
                        'regex_pattern': 'Breaking News',
                        'minutes_before': 5
                    }
                    service.create_auto_create_rule(rule_data)
                    time.sleep(0.5)
                    
                    # First refresh
                    service.fetch_epg_grid(force_refresh=True)
                    events_after_first = service.get_scheduled_events()
                    self.assertEqual(len(events_after_first), 1)
                    
                    # Second refresh with same data
                    service.fetch_epg_grid(force_refresh=True)
                    events_after_second = service.get_scheduled_events()
                    
                    # Should still only have 1 event (no duplicates)
                    self.assertEqual(len(events_after_second), 1, 
                        "Should not create duplicate events on multiple refreshes")


if __name__ == '__main__':
    unittest.main()
