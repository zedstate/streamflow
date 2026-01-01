# Active Stream Detection Fix

## Issue
StreamFlow was unable to detect active streams for M3U accounts. When checking account limits, the system would incorrectly report "Account 6 has 0 active streams" even when streams were actively being watched.

**Example from issue:**
```
streamflow  | 2026-01-01 16:44:36 - DEBUG - [udi.manager:get_active_streams_for_account:1122] - Account 6 has 0 active streams
```

However, the `/proxy/ts/status` endpoint showed an active channel:
```json
{
    "channels": [
        {
            "channel_id": "c4fa030c-a0b9-4df1-83fe-4680ed8f3c89",
            "state": "active",
            "stream_id": 11554,
            "m3u_profile_id": 6,
            "m3u_profile_name": "IPFS NewERA Default",
            "client_count": 1,
            "clients": [...]
        }
    ],
    "count": 1
}
```

## Root Cause

The active stream detection logic had a fundamental mismatch in how it correlated proxy status with M3U accounts:

1. **Proxy status returns**: `m3u_profile_id` - which profile is being used by the active channel
2. **Old code checked**: `stream.get('m3u_account')` - which account a stream belongs to
3. **Problem**: The code tried to match channel IDs from proxy status with stream IDs in the database, but:
   - Channel IDs in proxy status are UUIDs (e.g., `"c4fa030c-a0b9-4df1-83fe-4680ed8f3c89"`)
   - The correlation was based on the wrong field (`m3u_account` instead of profile)

```python
# Old (broken) logic:
for channel_id, status in active_channels.items():
    channel = self._channels_by_id.get(channel_id)  # Often fails - UUID vs int
    for stream_id in channel.get('streams', []):
        stream = self._streams_by_id.get(stream_id)
        if stream and stream.get('m3u_account') == account_id:  # Wrong correlation
            active_count += 1
```

## Solution

Updated the correlation logic to use `m3u_profile_id` from proxy status:

1. **Get proxy status**: Fetch real-time channel status from `/proxy/ts/status`
2. **Extract profile ID**: Read `m3u_profile_id` from each active channel
3. **Map to account**: Use existing `_find_account_for_profile()` to map profile → account
4. **Count matches**: Count how many active channels use profiles from the target account

```python
# New (working) logic:
for channel_id_str, status in proxy_status.items():
    if not self._is_channel_status_active(status):
        continue
    
    profile_id = status.get('m3u_profile_id')  # Get profile from proxy status
    if not profile_id:
        continue
    
    profile_account_id = self._find_account_for_profile(profile_id)  # Map to account
    if profile_account_id == account_id:  # Match!
        active_count += 1
```

## Changes Made

### 1. Updated `udi/manager.py`
- **Method**: `_count_active_streams(account_id)`
  - Now uses `m3u_profile_id` from proxy status
  - Maps profiles to accounts using `_find_account_for_profile()`
  - Correctly counts active streams for each account

- **Updated docstrings**:
  - `get_active_streams_for_account()`: Clarifies it uses real-time proxy status
  - `get_active_streams_for_profile()`: Clarifies it uses profile correlation

### 2. Removed Legacy Code in `udi/fetcher.py`
As requested, removed support for deprecated proxy status formats:
- ❌ Legacy dict format: `{"100": {...}, "200": {...}}`
- ❌ Legacy list format: `[{...}, {...}]`
- ✅ Only standard format: `{"channels": [...], "count": N}`

### 3. Updated Tests
- **Modified**: `test_fetcher_proxy_status_parsing.py`
  - Removed tests for legacy formats
  - Updated test names to reflect "standard format" instead of "new format"
  - Added `m3u_profile_id` field to test data

- **Added**: `test_active_stream_detection.py`
  - 9 comprehensive tests for profile correlation logic
  - Tests multiple profiles per account
  - Tests unknown profiles and missing fields
  - Tests active/inactive state handling

## Testing

All tests pass successfully:
```bash
# Proxy status parsing tests
python3 tests/test_fetcher_proxy_status_parsing.py
# Result: 7 tests passed

# Active stream detection tests  
python3 tests/test_active_stream_detection.py
# Result: 9 tests passed

# Existing UDI tests
python3 tests/test_udi.py
# Result: 38 tests passed
```

## Demonstration

The fix correctly detects active streams:

**Before Fix:**
- Proxy status shows channel using profile 6
- System reports: "Account 6 has 0 active streams" ❌

**After Fix:**
- Proxy status shows channel using profile 6  
- Profile 6 belongs to Account 6
- System reports: "Account 6 has 1 active stream" ✓

See `backend/tests/demonstrate_fix.py` for a working demonstration.

## Benefits

1. **Accurate stream limits**: M3U account stream limits now work correctly
2. **Real-time detection**: Uses live proxy status instead of potentially stale database values
3. **Cleaner code**: Removed deprecated format support, simplified logic
4. **Better logging**: Clear debug messages show profile → account mapping

## Files Changed

- `backend/udi/manager.py`: Updated `_count_active_streams()` and docstrings
- `backend/udi/fetcher.py`: Removed legacy format support
- `backend/tests/test_fetcher_proxy_status_parsing.py`: Updated tests
- `backend/tests/test_active_stream_detection.py`: New comprehensive tests
- `backend/tests/demonstrate_fix.py`: Demonstration script

## Related Endpoints

- **Proxy status**: `GET /proxy/ts/status` - Returns active channel information
- **M3U accounts**: `GET /api/channels/m3u-accounts/` - Lists M3U accounts with profiles
- **Streams**: `GET /api/channels/streams/` - Lists streams with profile IDs

## Technical Details

### M3U Account → Profile → Active Channel Relationship

```
M3U Account (id: 6)
  ├── Profile (id: 6, name: "IPFS NewERA Default")
  └── Profile (id: 7, name: "IPFS NewERA Alternative")

Active Channel (from /proxy/ts/status)
  ├── channel_id: "c4fa030c-a0b9-4df1-83fe-4680ed8f3c89"
  ├── state: "active"
  └── m3u_profile_id: 6  ← Links to profile, which links to account

Result: Account 6 has 1 active stream ✓
```

### Why This Matters

M3U providers often have concurrent stream limits (e.g., "max 2 streams"). StreamFlow needs to:
1. Track how many streams are currently active
2. Prevent exceeding the account's stream limit
3. Make intelligent decisions about which streams to use

Without accurate detection, the system could:
- Exceed stream limits (violating provider terms)
- Fail to detect when streams are in use
- Make incorrect assumptions about available capacity
