#!/usr/bin/env python3
"""
Test that live regex preview properly handles streams with the same name from different providers.

This test verifies the logic for including M3U account names in matched stream results,
ensuring users can distinguish between same-named streams from different providers.
"""

import unittest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLiveRegexProviderDifferentiation(unittest.TestCase):
    """Test live regex preview with same-named streams from different providers."""
    
    def test_m3u_account_map_creation(self):
        """Test that M3U account IDs are correctly mapped to names."""
        # Sample M3U accounts data (what get_m3u_accounts would return)
        m3u_accounts_list = [
            {'id': 1, 'name': 'Provider One'},
            {'id': 2, 'name': 'Provider Two'},
            {'id': 3, 'name': 'Provider Three'},
        ]
        
        # Create the map as done in web_api.py
        m3u_account_map = {acc.get('id'): acc.get('name', f'Account {acc.get("id")}') 
                          for acc in m3u_accounts_list if acc.get('id') is not None}
        
        # Verify the mapping
        self.assertEqual(m3u_account_map[1], 'Provider One')
        self.assertEqual(m3u_account_map[2], 'Provider Two')
        self.assertEqual(m3u_account_map[3], 'Provider Three')
    
    def test_m3u_account_map_with_missing_name(self):
        """Test that M3U accounts without names get default names."""
        # M3U account without a name
        m3u_accounts_list = [
            {'id': 1},  # No name provided
            {'id': 2, 'name': ''},  # Empty name
        ]
        
        m3u_account_map = {acc.get('id'): acc.get('name', f'Account {acc.get("id")}') 
                          for acc in m3u_accounts_list if acc.get('id') is not None}
        
        # Verify default name is used
        self.assertEqual(m3u_account_map[1], 'Account 1')
        # Empty string is still considered a name (not None)
        self.assertEqual(m3u_account_map[2], '')
    
    def test_matched_stream_includes_m3u_account_name(self):
        """Test that matched stream objects include M3U account name."""
        # Simulate the matched stream creation logic from web_api.py
        m3u_account_map = {
            1: 'Provider One',
            2: 'Provider Two'
        }
        
        # Sample stream data
        stream = {
            'id': 101,
            'name': 'ESPN HD',
            'm3u_account': 1
        }
        
        # Create matched stream object as done in web_api.py
        stream_id = stream.get('id')
        stream_name = stream.get('name', '')
        m3u_account_id = stream.get('m3u_account')
        matched_pattern = 'ESPN.*'
        
        matched_stream = {
            "stream_id": stream_id,
            "stream_name": stream_name,
            "matched_pattern": matched_pattern,
            "m3u_account": m3u_account_id,
            "m3u_account_name": m3u_account_map.get(m3u_account_id) if m3u_account_id else None
        }
        
        # Verify the matched stream has all required fields
        self.assertEqual(matched_stream['stream_id'], 101)
        self.assertEqual(matched_stream['stream_name'], 'ESPN HD')
        self.assertEqual(matched_stream['m3u_account'], 1)
        self.assertEqual(matched_stream['m3u_account_name'], 'Provider One')
    
    def test_matched_stream_without_m3u_account(self):
        """Test that streams without M3U account (e.g., custom streams) are handled."""
        m3u_account_map = {
            1: 'Provider One'
        }
        
        # Custom stream with no M3U account
        stream = {
            'id': 999,
            'name': 'Custom Stream',
            'm3u_account': None
        }
        
        stream_id = stream.get('id')
        stream_name = stream.get('name', '')
        m3u_account_id = stream.get('m3u_account')
        matched_pattern = 'Custom.*'
        
        matched_stream = {
            "stream_id": stream_id,
            "stream_name": stream_name,
            "matched_pattern": matched_pattern,
            "m3u_account": m3u_account_id,
            "m3u_account_name": m3u_account_map.get(m3u_account_id) if m3u_account_id else None
        }
        
        # Verify the stream has None for M3U account fields
        self.assertEqual(matched_stream['stream_id'], 999)
        self.assertEqual(matched_stream['stream_name'], 'Custom Stream')
        self.assertIsNone(matched_stream['m3u_account'])
        self.assertIsNone(matched_stream['m3u_account_name'])
    
    def test_same_named_streams_from_different_providers_are_distinguishable(self):
        """Test that same-named streams from different providers have different provider names."""
        m3u_account_map = {
            1: 'Provider One',
            2: 'Provider Two'
        }
        
        # Two streams with the same name but different providers
        streams = [
            {'id': 1, 'name': 'ESPN HD', 'm3u_account': 1},
            {'id': 2, 'name': 'ESPN HD', 'm3u_account': 2}
        ]
        
        matched_streams = []
        for stream in streams:
            m3u_account_id = stream.get('m3u_account')
            matched_streams.append({
                "stream_id": stream['id'],
                "stream_name": stream['name'],
                "matched_pattern": 'ESPN.*',
                "m3u_account": m3u_account_id,
                "m3u_account_name": m3u_account_map.get(m3u_account_id) if m3u_account_id else None
            })
        
        # Both streams have the same name
        self.assertEqual(matched_streams[0]['stream_name'], 'ESPN HD')
        self.assertEqual(matched_streams[1]['stream_name'], 'ESPN HD')
        
        # But they have different M3U account IDs
        self.assertEqual(matched_streams[0]['m3u_account'], 1)
        self.assertEqual(matched_streams[1]['m3u_account'], 2)
        
        # And different M3U account names
        self.assertEqual(matched_streams[0]['m3u_account_name'], 'Provider One')
        self.assertEqual(matched_streams[1]['m3u_account_name'], 'Provider Two')
        
        # This allows users to distinguish between them in the UI


if __name__ == '__main__':
    unittest.main()
