# Fix Summary: CHANNEL_NAME Variable in Regex Live Preview

## Issue Description

User reported that the `CHANNEL_NAME` variable doesn't work in regex patterns during live preview testing. When using patterns like:

```regex
^(?:PL|\s|PL-VIP|\s|PL(?: VIP)?:\s)((?:TVP )?(CHANNEL_NAME)(?: POLSKA)?(?: TV)?(?:.PL)?)(?:.TV)?(?:\s+(HD|4K|FHD|RAW|ᴴᴰ ◉|ᵁᴴᴰ))?$
```

The live preview would show **0 records**, even though the same pattern with a hardcoded channel name (e.g., "HBO 3") would work correctly.

## Root Cause

The `/api/test-regex-live` endpoint in `backend/web_api.py` was not substituting the `CHANNEL_NAME` variable before testing patterns against streams. This meant:

1. **During live preview**: `CHANNEL_NAME` was treated as literal text, resulting in no matches
2. **During actual stream matching**: The variable was correctly substituted in `automated_stream_manager.py`

This inconsistency made it impossible for users to test patterns with `CHANNEL_NAME` before applying them.

## Solution

Updated the `test_regex_pattern_live()` function in `backend/web_api.py` to substitute `CHANNEL_NAME` with the actual channel name before testing patterns.

### Code Changes

**File**: `backend/web_api.py`

```python
for pattern in regex_patterns:
    # Substitute CHANNEL_NAME variable with actual channel name
    # This matches the behavior in automated_stream_manager.py
    escaped_channel_name = re.escape(channel_name)
    substituted_pattern = pattern.replace('CHANNEL_NAME', escaped_channel_name)
    
    search_pattern = substituted_pattern if case_sensitive else substituted_pattern.lower()
    
    # Convert literal spaces in pattern to flexible whitespace regex (\s+)
    # This allows matching streams with different whitespace characters
    search_pattern = re.sub(r' +', r'\\s+', search_pattern)
    
    try:
        if re.search(search_pattern, search_name):
            matched = True
            matched_pattern = pattern
            break  # Only need one match
    except re.error as e:
        logger.warning(f"Invalid regex pattern '{pattern}': {e}")
        continue
```

### Key Features

1. **Variable Substitution**: `CHANNEL_NAME` is replaced with the actual channel name
2. **Special Character Escaping**: Channel names with special regex characters (e.g., `+`, `.`, `*`) are properly escaped using `re.escape()`
3. **Consistency**: Behavior now matches the actual stream matching in `automated_stream_manager.py`
4. **Live Feedback**: Users can see in real-time which streams will be matched

## Testing

### New Test File

Created `backend/tests/test_regex_live_preview.py` with 7 comprehensive test cases:

1. **test_channel_name_substitution_in_live_preview**: Basic variable substitution
2. **test_user_reported_pattern**: Tests the exact pattern reported by the user
3. **test_channel_name_with_special_characters**: Ensures special characters are escaped
4. **test_multiple_channel_name_occurrences**: Multiple `CHANNEL_NAME` in one pattern
5. **test_pattern_without_variable**: Patterns without variable remain unchanged
6. **test_empty_channel_name**: Edge case handling
7. **test_case_sensitivity**: Case-sensitive vs case-insensitive matching

### Test Results

```
✅ All 7 new tests PASSED
✅ All 9 existing tests PASSED
✅ Total: 16 tests passing
✅ Code review: No issues found
✅ Security scan: No alerts (CodeQL)
```

## Documentation Updates

Updated documentation to reflect the fix and provide troubleshooting guidance:

1. **docs/CHANNEL_CONFIGURATION_FEATURES.md**:
   - Added note about live preview automatically substituting `CHANNEL_NAME`
   - Documented special character escaping behavior

2. **docs/MASS_REGEX_ASSIGNMENT.md**:
   - Added "Live Preview Support" section
   - Added troubleshooting guide for common issues
   - Updated testing section with new test file

## Impact

### Before Fix
- Users couldn't test patterns with `CHANNEL_NAME` in live preview
- Live preview would always show 0 matches
- Users had to apply patterns blindly and hope they worked

### After Fix
- ✅ Live preview correctly shows matched streams
- ✅ Users can verify patterns before applying
- ✅ Consistent behavior between preview and actual matching
- ✅ Better user experience and confidence

## Backward Compatibility

✅ **Fully backward compatible**:
- All existing patterns continue to work
- No breaking changes to API
- Existing functionality preserved
- Only adds missing feature to live preview

## Files Changed

1. `backend/web_api.py` - Added variable substitution to live preview endpoint
2. `backend/tests/test_regex_live_preview.py` - New test file (7 tests)
3. `docs/CHANNEL_CONFIGURATION_FEATURES.md` - Documentation update
4. `docs/MASS_REGEX_ASSIGNMENT.md` - Documentation update and troubleshooting

## Verification

The fix can be verified by:

1. Opening the Channel Configuration page
2. Selecting a channel (e.g., "HBO 3")
3. Adding a regex pattern with `CHANNEL_NAME` (e.g., `.*CHANNEL_NAME.*`)
4. Observing that the live preview now shows matching streams
5. Verifying that the matches are correct for the channel name

## Related Issues

This fix addresses the user feedback:
> "so... it copy to other channels regex but "{channel_name}" is not working 
> example:
> ^(?:PL|\s|PL-VIP|\s|PL(?: VIP)?:\s)((?:TVP )?(HBO 3)(?: POLSKA)?(?: TV)?(?:.PL)?)(?:.TV)?(?:\s+(HD|4K|FHD|RAW|ᴴᴰ ◉|ᵁᴴᴰ))?$
> give what you see in screen
> with your 
> ^(?:PL|\s|PL-VIP|\s|PL(?: VIP)?:\s)((?:TVP )?(CHANNEL_NAME)(?: POLSKA)?(?: TV)?(?:.PL)?)(?:.TV)?(?:\s+(HD|4K|FHD|RAW|ᴴᴰ ◉|ᵁᴴᴰ))?$
> it gives 0 records"

## Conclusion

This fix ensures that the `CHANNEL_NAME` variable works correctly in both:
1. **Live regex preview** (now fixed)
2. **Actual stream matching** (was already working)

Users can now confidently use `CHANNEL_NAME` in their patterns and verify the results in real-time before applying them to channels.

---

## Additional Fix: Variable Format Change (Current Update)

### New Issue
The curly braces in `{CHANNEL_NAME}` were causing regex syntax conflicts and confusion.

### Root Cause
In regex syntax, curly braces `{}` have a special meaning (quantifiers like `{2,5}`). This was causing various issues:
- Regex validation errors
- User confusion
- Higher chance of broken regex rules

### Solution
Changed the variable format from `{CHANNEL_NAME}` to `CHANNEL_NAME` (without braces) to:
- Eliminate regex syntax conflicts
- Simplify the syntax for users
- Reduce chances of errors
- Make patterns easier to read and write

**Example in `automated_stream_manager.py`:**
```python
# Substitute CHANNEL_NAME with a placeholder for validation
validation_pattern = pattern.replace('CHANNEL_NAME', 'PLACEHOLDER')
re.compile(validation_pattern)
```

### Testing
Updated all tests to use the new `CHANNEL_NAME` format:
- Simple patterns: `.*CHANNEL_NAME.*`
- Complex patterns: `^(?:PL|\s|PL-VIP|\s|PL(?: VIP)?:\s)((?:TVP )?(CHANNEL_NAME)(?: POLSKA)?(?: TV)?(?:.PL)?)(?:.TV)?(?:\s+(HD|4K|FHD|RAW|ᴴᴰ ◉|ᵁᴴᴰ))?$`
- Multiple occurrences: `CHANNEL_NAME.*CHANNEL_NAME`

All tests pass successfully.
