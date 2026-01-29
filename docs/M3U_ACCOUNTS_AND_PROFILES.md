# M3U Accounts and Profiles

## Overview

StreamFlow supports M3U accounts with multiple profiles, allowing you to maximize concurrent stream usage from a single M3U source.

## M3U Accounts vs Profiles

### M3U Account
An M3U account represents a connection to an M3U playlist source (e.g., IPTV provider).

**Properties:**
- `name`: Account name
- `server_url`: M3U playlist URL
- `max_streams`: Maximum concurrent streams at account level
- `account_type`: `STD` (standard M3U) or `XC` (Xtream Codes)
- `profiles`: List of profiles associated with this account

### M3U Account Profile
A profile is a variant way to access streams from the same M3U account, typically using different credentials or URL patterns.

**Properties:**
- `name`: Profile name (e.g., "Default", "Extra", "Free")
- `max_streams`: Maximum concurrent streams for this specific profile
- `is_active`: Whether this profile is available for use
- `is_default`: Whether this is the default profile for the account
- `search_pattern`: Regex pattern to match in stream URLs
- `replace_pattern`: Replacement pattern to transform URLs for this profile
- `account_id`: ID of the parent M3U account

**Common Use Cases:**
1. **Multiple Credentials**: Provider gives you 2 logins, each with 1 concurrent stream
   - Account: max_streams = 1
   - Profile 1 (user1/pass1): max_streams = 1
   - Profile 2 (user2/pass2): max_streams = 1
   - **Total capacity**: 2 concurrent streams

2. **Free + Premium**: Provider offers free streams alongside premium
   - Account: max_streams = 2
   - Profile 1 (Premium): max_streams = 2
   - Profile 2 (Free): max_streams = 1
   - **Total capacity**: 3 concurrent streams

## How Stream Checking Works

### Active Stream Detection

The system accurately tracks active streams using profile-to-account mapping:

**Key Mechanism:**
- Proxy status provides `m3u_profile_id` for each active channel
- System maps profile → account using internal lookup
- Counts active streams per account by aggregating profile usage
- Respects both per-profile and total account limits

**Why Profile Tracking Matters:**
When multiple streams from the same M3U account are active, the system must:
1. Identify which profile each stream is using
2. Count usage per profile against that profile's limit
3. Aggregate total usage against account capacity

**Example Scenario:**
```
Account "Provider1" (ID=3)
├─ Profile "Main" (ID=5): max_streams=1, active=1/1 ✓ At capacity
└─ Profile "Backup" (ID=6): max_streams=1, active=0/1 ✓ Available

Proxy Status:
- Channel 42: m3u_profile_id=5 (using "Main")
- New stream request → Uses Profile "Backup" (ID=6)
```

**Technical Implementation:**
```python
# From proxy status
proxy_status = {
    "channel_42": {
        "state": "active",
        "m3u_profile_id": 5,  # This is the key field
        "m3u_profile_name": "Main"
    }
}

# System lookup
profile_id = proxy_status["channel_42"]["m3u_profile_id"]  # 5
account_id = find_account_for_profile(profile_id)  # 3
# Result: Channel 42 counts toward Account 3's usage
```

### Profile Selection
When checking streams, the system:

1. **Finds Available Profile**: Looks for a profile in the account that has available slots
   - Checks each profile's `max_streams` limit
   - Counts currently active streams using that profile
   - Selects first profile with available capacity

2. **Applies URL Transformation**: If profile has `search_pattern` and `replace_pattern`
   - Applies regex transformation to stream URL
   - Example: Transform `user1/pass1` to `user2/pass2` in URL

3. **Tracks Profile Usage**: During playback
   - Proxy tracks which profile is being used via `m3u_profile_id`
   - System counts active streams per profile
   - Respects per-profile `max_streams` limits

### Concurrent Stream Limiting

The concurrent stream limiter works at two levels:

1. **Account Level**: Total capacity = sum of all active profile limits
   - Example: 2 profiles with 1 stream each = 2 total concurrent streams

2. **Profile Level**: Each profile has its own limit
   - Profile 1: 0/1 used → available
   - Profile 2: 1/1 used → at capacity
   - System will use Profile 1 for next stream

### Real-Time Tracking

The system uses `/proxy/ts/status` endpoint to track:
- Which channels are actively streaming
- Which profile each channel is using (`m3u_profile_id`)
- Number of clients connected to each channel

This real-time data ensures:
- Accurate concurrent stream counting
- Proper profile limit enforcement
- Intelligent profile selection for new streams

## Internal Storage (UDI)

### Data Models

**M3UAccount Model**:
```python
@dataclass
class M3UAccount:
    id: int
    name: str
    max_streams: int = 0
    profiles: List[M3UAccountProfile] = field(default_factory=list)
    # ... other fields
```

**M3UAccountProfile Model**:
```python
@dataclass
class M3UAccountProfile:
    id: int
    name: str
    max_streams: int = 0
    is_active: bool = True
    account_id: Optional[int] = None  # Parent account ID
    search_pattern: Optional[str] = None
    replace_pattern: Optional[str] = None
    # ... other fields
```

### Profile-to-Account Mapping

The UDI maintains profile-to-account relationships:
- Each profile stores its parent `account_id`
- `_find_account_for_profile()` method resolves profile → account
- Used for counting active streams per account

### Proxy Status Integration

```json
{
  "channels": [
    {
      "channel_id": "uuid",
      "state": "active",
      "m3u_profile_id": 4,
      "m3u_profile_name": "extra",
      "url": "https://provider.com/live/user2/pass2/stream.ts"
    }
  ]
}
```

The `m3u_profile_id` field indicates which profile is actively being used.

## Configuration

### Creating Profiles

Profiles can be created via Dispatcharr API:

```bash
POST /api/m3u/accounts/{account_id}/profiles/
{
  "name": "Extra Profile",
  "max_streams": 1,
  "is_active": true,
  "search_pattern": "user1/pass1",
  "replace_pattern": "user2/pass2"
}
```

### URL Transformation Patterns

**Search Pattern**: Regex pattern to find in stream URL
**Replace Pattern**: Replacement text (supports backreferences $1, $2, etc.)

**Example**:
- Original URL: `https://provider.com/live/user1/pass1/123.ts`
- Search: `user1/pass1`
- Replace: `user2/pass2`
- Result: `https://provider.com/live/user2/pass2/123.ts`

## Best Practices

1. **Profile Naming**: Use descriptive names like "Main", "Backup", "Free"
2. **Set Realistic Limits**: Configure `max_streams` according to provider limits
3. **Test URL Patterns**: Verify search/replace patterns work correctly
4. **Monitor Usage**: Check active streams per profile in dashboard
5. **Disable Unused Profiles**: Set `is_active=false` for profiles not in use

## Troubleshooting

### Profile Not Being Used
- Check `is_active` is true
- Verify profile has available slots (active < max_streams)
- Ensure URL pattern matches if using search/replace

### Exceeded Stream Limit
- Check combined limits of all active profiles
- Verify proxy status shows correct `m3u_profile_id`
- Review account and profile `max_streams` settings

### URL Transformation Not Working
- Test regex pattern in regex tester
- Check backreference syntax ($1, $2, not \1, \2)
- Verify pattern matches actual stream URLs
- Check logs for transformation errors

## API Endpoints

### List Profiles
```
GET /api/m3u/accounts/{account_id}/profiles/
```

### Get Profile
```
GET /api/m3u/accounts/{account_id}/profiles/{id}/
```

### Update Profile
```
PATCH /api/m3u/accounts/{account_id}/profiles/{id}/
{
  "max_streams": 2,
  "is_active": true
}
```

### Delete Profile
```
DELETE /api/m3u/accounts/{account_id}/profiles/{id}/
```

## Performance Optimization

### Smart Custom Stream Detection

The system uses intelligent API filtering to handle accounts with thousands of streams efficiently.

**Problem Scenario:**
- Account with 3000+ streams
- Need to check if account has any custom streams
- Original approach: Fetch all streams, filter in Python
- Result: 15+ second response times

**Optimized Approach:**

**Primary Method** - API Filtering:
```
GET /api/channels/streams/?is_custom=true&m3u_account={id}
```
- Lets database filter streams
- Returns only custom streams
- Fast even with 3000+ total streams

**Fallback Method** - Pagination:
```
GET /api/channels/streams/?m3u_account={id}&page_size=1
```
- If API doesn't support `is_custom` filter
- Fetch just 1 item to get total count
- Check `count > 0` instead of loading all streams

**Performance Impact:**
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Response Time (3000 streams) | 15+ sec | <1 sec | 15x faster |
| Memory Usage | High | Minimal | Significant reduction |
| Database Load | Full scan | Indexed query | Much lower |

**Implementation:**
```python
# Smart filtering in UDI fetcher
def has_custom_streams(account_id):
    # Try API filter first
    response = requests.get(
        f'/api/channels/streams/',
        params={'is_custom': 'true', 'm3u_account': account_id}
    )
    
    if response.status_code == 200:
        return response.json().get('count', 0) > 0
    
    # Fallback to pagination
    response = requests.get(
        f'/api/channels/streams/',
        params={'m3u_account': account_id, 'page_size': 1}
    )
    
    return response.json().get('count', 0) > 0
```

**Best Practices:**
1. Use API filters when available
2. Minimize data transfer with pagination
3. Cache results when possible
4. Use indexed database queries

## See Also

- [CHANGELOG](CHANGELOG.md) - Bug fixes and improvements history
- [Channel Group Management](CHANNEL_GROUP_MANAGEMENT.md)
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md)
- [Concurrent Stream Limits](CONCURRENT_STREAM_LIMITS.md)
