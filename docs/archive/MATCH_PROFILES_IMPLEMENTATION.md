# Match Profiles Implementation Guide

## Overview

This document describes the Match Profiles feature implementation for StreamFlow. Match Profiles enable granular control over stream-to-channel matching through a visual pipeline/building blocks system.

## Current Status

### ✅ Completed (Backend)

1. **Data Models** (`backend/udi/models.py`)
   - `MatchProfileStep`: Individual steps in a match profile pipeline
   - `MatchProfile`: Container for match steps with metadata
   - Extended `Channel` model with `match_profile_id` field
   - Extended `ChannelGroup` model with `match_profile_id` field

2. **Storage Layer** (`backend/udi/storage.py`)
   - Added `match_profiles.json` file storage
   - Thread-safe CRUD operations
   - Methods: `load_match_profiles()`, `save_match_profiles()`, `get_match_profile()`, `update_match_profile()`, `delete_match_profile()`

3. **Business Logic** (`backend/match_profiles_manager.py`)
   - `MatchProfilesManager` class for profile management
   - Variable substitution: `{channel_name}`, `{channel_group}`, `{m3u_account_name}`
   - Profile testing with detailed results
   - Singleton pattern via `get_match_profiles_manager()`

4. **API Endpoints** (`backend/web_api.py`)
   - `GET /api/match-profiles` - List all profiles
   - `GET /api/match-profiles/{id}` - Get specific profile
   - `POST /api/match-profiles` - Create new profile
   - `PUT/PATCH /api/match-profiles/{id}` - Update profile
   - `DELETE /api/match-profiles/{id}` - Delete profile
   - `POST /api/match-profiles/{id}/test` - Test profile against stream data

### 🔄 Next Steps

#### 1. Frontend Implementation (High Priority)

**Match Profile Studio Page**
- Location: `frontend/src/pages/MatchProfileStudio.jsx`
- Should be accessible from Channel Configuration section
- Features needed:
  - List view of all match profiles
  - Create/Edit/Delete profile operations
  - Visual pipeline builder for steps
  - Test panel to preview matching

**Visual Pipeline Builder Component**
- Use drag-and-drop for step ordering (consider `@dnd-kit/core` already in dependencies)
- Step types:
  - Regex: Stream Name (input: regex pattern)
  - TVG-ID (input: exact match value)
  - Regex: Stream URL (input: regex pattern)
- Variable insertion buttons for dynamic variables
- Enable/disable toggle for each step

**Profile Assignment UI**
- Add "Match Profile" dropdown to Channel edit dialog
- Add "Match Profile" dropdown to Channel Group settings
- Show which channels/groups use each profile

#### 2. Integration with Existing Matching Logic

**Update `automated_stream_manager.py`**
- Modify `RegexChannelMatcher` to check for match profiles
- Priority: Match profiles > Legacy regex patterns
- Fallback to legacy regex if no profile assigned

**Workflow:**
1. Check if channel has `match_profile_id`
2. If yes, load profile and apply variables
3. Test stream against profile steps
4. If no profile or no match, fall back to legacy regex

#### 3. Testing

**Unit Tests** (Create in `backend/tests/`)
- `test_match_profiles.py`:
  - Test profile CRUD operations
  - Test variable substitution
  - Test pattern matching (regex name, TVG-ID, regex URL)
  - Test profile assignment to channels/groups

**Integration Tests**
- Test API endpoints
- Test profile integration with stream matching
- Test UI interactions (if frontend testing is set up)

#### 4. Documentation Updates

**User Documentation** (`docs/MATCH_PROFILES.md`)
- Feature overview
- How to create match profiles
- Step types explained
- Dynamic variables guide
- Best practices
- Migration from legacy regex

**API Documentation** (`docs/API.md`)
- Add match profiles endpoints
- Request/response examples
- Error codes

**Update Existing Docs**
- `docs/CHANNEL_CONFIGURATION_FEATURES.md` - Add Match Profile Studio section
- `docs/FEATURES.md` - Add Match Profiles feature
- `README.md` - Mention match profiles

## Technical Details

### Data Structure

**MatchProfileStep:**
```json
{
  "id": "step1",
  "type": "regex_name",
  "pattern": ".*{channel_name}.*",
  "variables": {},
  "enabled": true,
  "order": 0
}
```

**MatchProfile:**
```json
{
  "id": 1,
  "name": "Sports Channels",
  "description": "Match sports streams to sports channels",
  "steps": [
    {
      "id": "step1",
      "type": "regex_name",
      "pattern": ".*{channel_name}.*",
      "variables": {},
      "enabled": true,
      "order": 0
    },
    {
      "id": "step2",
      "type": "tvg_id",
      "pattern": "{channel_group}.sports",
      "variables": {},
      "enabled": true,
      "order": 1
    }
  ],
  "enabled": true,
  "created_at": "2025-01-01T00:00:00",
  "updated_at": "2025-01-01T00:00:00"
}
```

### Match Types

1. **regex_name**: Regex pattern matching on stream name
   - Case-insensitive
   - Supports dynamic variables
   - Example: `.*{channel_name}.*` matches streams with channel name

2. **tvg_id**: Exact match on TVG-ID
   - Supports dynamic variables
   - Example: `{channel_group}.us` for group-based matching

3. **regex_url**: Regex pattern matching on stream URL
   - Case-insensitive
   - Supports dynamic variables
   - Example: `.*provider1.*` for provider-specific URLs

### Dynamic Variables

These placeholders are replaced at match time:
- `{channel_name}`: The name of the channel being matched
- `{channel_group}`: The name of the channel's group
- `{m3u_account_name}`: The name of the M3U account providing the stream

### Matching Logic

Steps are evaluated in order. The profile matches if **any** step matches (OR logic).

**Example:**
```python
# Profile with 2 steps
steps = [
    {"type": "regex_name", "pattern": "ESPN"},
    {"type": "tvg_id", "pattern": "ESPN.us"}
]

# Stream data
stream = {
    "name": "ESPN HD",
    "tvg_id": "ESPN.us",
    "url": "http://example.com/stream"
}

# Result: MATCH (both steps match)
# Even if only one step matched, overall result would be MATCH
```

### API Usage Examples

**Create Profile:**
```bash
curl -X POST http://localhost:5000/api/match-profiles \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sports Profile",
    "description": "Match sports streams",
    "steps": [
      {
        "id": "step1",
        "type": "regex_name",
        "pattern": ".*{channel_name}.*",
        "enabled": true,
        "order": 0
      }
    ]
  }'
```

**Test Profile:**
```bash
curl -X POST http://localhost:5000/api/match-profiles/1/test \
  -H "Content-Type: application/json" \
  -d '{
    "stream_name": "ESPN Sports HD",
    "stream_tvg_id": "ESPN.us",
    "channel_name": "ESPN",
    "channel_group": "Sports"
  }'
```

**Response:**
```json
{
  "matched": true,
  "reason": "At least one step matched",
  "steps_results": [
    {
      "step_id": "step1",
      "type": "regex_name",
      "pattern": ".*ESPN.*",
      "matched": true,
      "reason": "Stream name 'ESPN Sports HD' matches pattern '.*ESPN.*'"
    }
  ]
}
```

## Frontend Implementation Suggestions

### Match Profile Studio Layout

```
┌──────────────────────────────────────────────────────────────┐
│  Match Profile Studio                                        │
├──────────────────────────────────────────────────────────────┤
│  [+ New Profile]                                   [Search] │
├──────────────────────────────────────────────────────────────┤
│  Profiles List (left sidebar)         Profile Editor (main)  │
│  ┌─────────────────────────┐         ┌───────────────────┐ │
│  │ ▶ Sports Profile         │         │ Name: [________] │ │
│  │ ▶ News Channels          │         │ Desc: [________] │ │
│  │ ▶ Movie Channels         │         │                   │ │
│  └─────────────────────────┘         │ Pipeline Builder:│ │
│                                        │ ┌───────────────┐│ │
│                                        │ │ Step 1 ▲▼ [x]││ │
│                                        │ │ Type: Regex   ││ │
│                                        │ │ Pattern: [...] │ │
│                                        │ └───────────────┘│ │
│                                        │ [+ Add Step]     │ │
│                                        │                   │ │
│                                        │ Test Panel:      │ │
│                                        │ Stream: [_____]  │ │
│                                        │ [Test]  Results  │ │
│                                        └───────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### ShadCN Components to Use

- **Card**: For profile list items and step containers
- **Button**: For actions (Add Step, Test, Save, Delete)
- **Input**: For pattern entry and test data
- **Select**: For step type selection
- **Switch**: For enable/disable toggles
- **Badge**: For showing matched/not matched status
- **Accordion**: For collapsible step details
- **Dialog**: For profile creation/deletion confirmations
- **Tabs**: If splitting between "My Profiles" and "Assignments"

### State Management

```jsx
const [profiles, setProfiles] = useState([]);
const [selectedProfile, setSelectedProfile] = useState(null);
const [steps, setSteps] = useState([]);
const [testResults, setTestResults] = useState(null);
```

### API Service Methods

Create in `frontend/src/services/matchProfilesService.js`:
```javascript
export const matchProfilesService = {
  listProfiles: () => api.get('/api/match-profiles'),
  getProfile: (id) => api.get(`/api/match-profiles/${id}`),
  createProfile: (data) => api.post('/api/match-profiles', data),
  updateProfile: (id, data) => api.patch(`/api/match-profiles/${id}`, data),
  deleteProfile: (id) => api.delete(`/api/match-profiles/${id}`),
  testProfile: (id, testData) => api.post(`/api/match-profiles/${id}/test`, testData)
};
```

## Migration Path from Legacy Regex

For users with existing channel_regex_config.json patterns:

1. Create a migration tool to convert legacy patterns to match profiles
2. Generate one profile per channel with existing patterns
3. Assign profiles to respective channels
4. Mark legacy regex as deprecated but keep for backward compatibility
5. Provide UI to "Migrate to Match Profiles" button

**Migration Logic:**
```python
# Pseudo-code
legacy_pattern = {"regex": [".*ESPN.*", ".*Sports.*"], "enabled": True}

# Convert to match profile
match_profile = {
    "name": f"Channel {channel_id} Legacy",
    "steps": [
        {"type": "regex_name", "pattern": pattern, "order": i}
        for i, pattern in enumerate(legacy_pattern["regex"])
    ],
    "enabled": legacy_pattern["enabled"]
}
```

## Known Considerations

1. **Performance**: Profile matching may be slower than simple regex. Consider caching resolved patterns.
2. **Validation**: Add regex pattern validation on frontend and backend
3. **Error Handling**: Show user-friendly errors for invalid regex patterns
4. **Backwards Compatibility**: Keep legacy regex working until full migration
5. **UI/UX**: Pipeline builder should be intuitive - consider tooltips and examples
6. **Documentation**: In-app help/tooltips for dynamic variables

## Questions for Design Decisions

1. Should profiles support AND logic in addition to OR? (Currently OR only)
2. Should there be a limit on number of steps per profile?
3. Should profiles be shareable/exportable between instances?
4. Should there be predefined template profiles?
5. How to handle conflicts when both channel and group have different profiles?

## Files to Review/Modify

### Backend
- ✅ `backend/udi/models.py` - Data models (done)
- ✅ `backend/udi/storage.py` - Storage layer (done)
- ✅ `backend/match_profiles_manager.py` - Business logic (done)
- ✅ `backend/web_api.py` - API endpoints (done)
- ⏳ `backend/automated_stream_manager.py` - Integration with matching
- ⏳ `backend/tests/test_match_profiles.py` - Tests

### Frontend
- ⏳ `frontend/src/pages/MatchProfileStudio.jsx` - New page
- ⏳ `frontend/src/components/MatchProfileBuilder.jsx` - Pipeline builder
- ⏳ `frontend/src/components/MatchProfileStep.jsx` - Step component
- ⏳ `frontend/src/services/matchProfilesService.js` - API service
- ⏳ `frontend/src/App.jsx` - Add route for studio

### Documentation
- ⏳ `docs/MATCH_PROFILES.md` - Feature documentation
- ⏳ `docs/API.md` - API documentation
- ⏳ `docs/CHANNEL_CONFIGURATION_FEATURES.md` - Update
- ⏳ `docs/FEATURES.md` - Update
- ⏳ `README.md` - Update

## Testing Checklist

- [ ] Create profile via API
- [ ] Update profile via API
- [ ] Delete profile via API
- [ ] List profiles via API
- [ ] Test profile matching with all three step types
- [ ] Test variable substitution
- [ ] Test profile assignment to channel
- [ ] Test profile assignment to channel group
- [ ] Test conflict resolution (channel vs group profile)
- [ ] Test frontend CRUD operations
- [ ] Test pipeline builder drag-and-drop
- [ ] Test profile testing panel
- [ ] Verify data persistence after restart
- [ ] Verify backward compatibility with legacy regex

## Summary

The backend implementation for Match Profiles is complete. The next agent should focus on:
1. Creating the frontend Match Profile Studio page
2. Integrating profiles with the existing stream matching logic
3. Adding comprehensive tests
4. Updating documentation

The foundation is solid and extensible. The API is RESTful and follows existing patterns in the codebase.
