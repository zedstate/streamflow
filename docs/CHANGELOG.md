# Changelog

This document tracks significant bug fixes and improvements to StreamFlow.

## Bug Fixes

### Automation Service Auto-Start (2024)

**Problem:** Automation service would not auto-start after completing the setup wizard.

**Root Cause:** The auto-start logic only ran during server initialization, not during the setup wizard API completion.

**Solution:** Enhanced the `update_stream_checker_config()` endpoint to trigger auto-start when the wizard completes successfully. The endpoint now:
1. Validates configuration
2. Saves settings
3. Triggers automation service start if wizard is complete

**Impact:** Setup wizard now properly starts the automation service without requiring manual intervention.

**Files Changed:**
- `backend/web_api.py` - Added auto-start trigger in config update endpoint

---

### Stream Checker Progress Display (2024)

**Problem:** Incomplete progress display when checking a single channel with multiple M3U accounts.

**Root Cause:** Duplicate parallel checks caused race conditions:
1. Explicit check via button click
2. Auto-triggered check from settings update
Both tried to execute simultaneously, causing:
- Duplicate API calls
- Conflicting progress updates
- Incomplete/confusing UI state

**Solution:** Added `skip_check_trigger` parameter to prevent duplicate checks:
- Settings update sets `skip_check_trigger=True` when an explicit check is already in progress
- Prevents redundant concurrent checks on the same channel
- Maintains clean progress tracking

**Impact:** Single channel checks now display accurate progress without race conditions.

**Files Changed:**
- `backend/web_api.py` - Added skip check trigger parameter
- Channel checker service - Respects skip trigger flag

---

### M3U Account Stream Limit Detection (2024)

**Problem:** Stream limits not properly enforced when multiple streams from the same M3U account were active.

**Root Cause:** Wrong field correlation in proxy status:
- Code was checking `stream.m3u_account` against `proxy_status.m3u_account`
- Proxy status actually uses `m3u_profile_id` (not account ID)
- This caused incorrect active stream counting

**Solution:** Implemented proper profile-to-account mapping:
1. Proxy status provides `m3u_profile_id` for active channels
2. System maps profile → account using `_find_account_for_profile()`
3. Counts active streams per account by summing profile usage
4. Respects per-profile limits and total account capacity

**Impact:** Stream limits now work correctly with M3U account profiles.

**Files Changed:**
- `backend/udi/manager.py` - Added profile mapping logic
- `backend/concurrent_stream_limiter.py` - Profile-aware limiting

**Reference:** See `M3U_ACCOUNTS_AND_PROFILES.md` for detailed explanation.

---

### Batch Regex Editing - Duplication Prevention (2024)

**Problem:** When editing existing regex patterns, they would duplicate instead of updating.

**Root Cause:** Edit operation was adding new regex objects rather than updating existing ones.

**Solution:**
- Check if pattern already exists before adding
- Update existing pattern if found
- Only add new pattern if it doesn't exist

**Impact:** Editing regex patterns now updates in place without creating duplicates.

**Related Fix:** Reduced excessive logging during batch operations to prevent log spam.

**Files Changed:**
- Backend regex management - Added deduplication logic
- Logging configuration - Reduced verbosity for batch operations

**Reference:** See `MASS_REGEX_EDIT.md` for feature documentation.

---

### Channel Name Variable in Live Preview (2024)

**Problem:** `CHANNEL_NAME` variable not working in live preview regex testing.

**Updates Made:**
1. **Initial**: Added variable substitution for CHANNEL_NAME
2. **Format Change**: Removed brackets `{CHANNEL_NAME}` → `CHANNEL_NAME` for consistency  
3. **Special Characters**: Added resilience for special regex characters in channel names

**Solution:** Proper escaping and whitespace handling:
- Escape special characters in channel names (e.g., `[`, `]`, `(`, `)`)
- Handle whitespace variations
- Substitute variable before regex matching

**Impact:** Users can now use `CHANNEL_NAME` in patterns and see accurate live preview results.

**Files Changed:**
- Preview handler - Added variable substitution and escaping
- Regex pattern processor - Special character handling

**Reference:** See `CHANNEL_CONFIGURATION_FEATURES.md` for usage examples.

---

### Regex Whitespace Flexibility (2024)

**Problem:** Users had to match exact whitespace in channel names (e.g., "TVP 1" with single space wouldn't match "TVP  1" with double space).

**Root Cause:** Literal space matching in regex patterns.

**Solution:** Flexible whitespace matching:
- Convert literal spaces to `\s+` pattern during matching
- Matches any whitespace variation (space, tab, multiple spaces)
- Transparent to users - they write patterns with normal spaces

**Example:**
- User writes: `TVP 1`
- System converts: `TVP\s+1`
- Matches: "TVP 1", "TVP  1", "TVP   1", etc.

**Impact:** User-friendly pattern matching that works with various whitespace characters.

**Files Changed:**
- Regex pattern processor - Added space-to-\s+ conversion
- Pattern matching engine - Whitespace normalization

**Reference:** See `CHANNEL_CONFIGURATION_FEATURES.md` for pattern matching rules.

---

### M3U Account API Performance (2024)

**Problem:** `/api/m3u-accounts` endpoint was slow with 3000+ streams (15+ second response times).

**Root Cause:** Fetching all streams just to check for custom stream existence:
- Loaded entire stream list for each account
- Performed filtering in Python
- Unnecessary data transfer

**Solution:** Smart API filtering with fallback:
1. **Primary**: Use API filter `?is_custom=true&m3u_account={id}`
2. **Fallback**: If API doesn't support filter, paginate with `?m3u_account={id}&page_size=1`
3. **Result**: Check `count > 0` instead of loading all streams

**Impact:**
- Response time: 15s → <1s for large accounts
- Reduced memory usage
- Better scalability

**Files Changed:**
- `backend/udi/fetcher.py` - Added smart filtering logic
- M3U account endpoint - Optimized custom stream detection

**Reference:** See `M3U_ACCOUNTS_AND_PROFILES.md` performance section.

---

## Feature Improvements

### M3U Account Profile Support (2026-01-15)

**Enhancement:** Complete support for M3U account profiles with proper differentiation.

**Changes:**
1. Fixed profile data model to extract `account_id` from nested API responses
2. Enhanced logging with profile names and usage tracking
3. Added comprehensive documentation

**Impact:** System now correctly handles multiple profiles per M3U account, respecting per-profile stream limits.

**Reference:** See `M3U_ACCOUNTS_AND_PROFILES.md`

---

## See Also

- [Features](FEATURES.md) - Complete feature list
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md) - Architecture overview
- [M3U Accounts and Profiles](M3U_ACCOUNTS_AND_PROFILES.md) - Profile system details
