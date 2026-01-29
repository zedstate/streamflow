# Health Check Buttons Feature

## Overview
This feature adds convenient health check buttons to the Regex Configuration section, allowing users to quickly check channel stream quality without navigating to the Stream Checker page.

## Implementation Date
December 24, 2024

## User Interface Changes

### Single Channel Health Check
- **Location**: Next to the expand/collapse button in each channel row in the Regex Configuration table
- **Icon**: Activity icon from lucide-react
- **Styling**:
  - Light mode: Blue border and text (`text-blue-600 border-blue-600`)
  - Dark mode: Green border and text (`dark:text-green-500 dark:border-green-500`)
  - Hover effect: Subtle background color change
- **Behavior**:
  - Clicking triggers an immediate health check for that specific channel
  - Button shows a loading spinner while checking is in progress
  - Button is disabled during the check to prevent duplicate requests
  - Toast notification shows check progress and results
  - Channel stats are automatically refreshed after check completes

### Bulk Health Check
- **Location**: In the action bar, next to "Add Regex to Selected" button
- **Icon**: Activity icon from lucide-react
- **Styling**: Same color scheme as single channel button
- **Behavior**:
  - Clicking queues all selected channels for health checks
  - Button is disabled when no channels are selected
  - Shows loading spinner during the queue operation
  - Toast notification confirms channels have been queued
  - Uses the existing stream checker queue system with priority 10

## Technical Details

### API Endpoints Used
1. **Single Channel Check**: `/api/stream-checker/check-single-channel`
   - Method: POST
   - Payload: `{ channel_id: number }`
   - Timeout: 120 seconds
   - Returns: Channel statistics including total streams, dead streams, avg resolution, avg bitrate

2. **Bulk Channel Check**: `/api/stream-checker/queue/add`
   - Method: POST
   - Payload: `{ channel_ids: number[], priority: number }`
   - Adds channels to the checking queue for processing

### State Management
- **checkingChannel**: Tracks which channel is currently being checked (for single checks)
- **bulkCheckingChannels**: Boolean flag for bulk operation in progress
- **selectedChannels**: Set of selected channel IDs for bulk operations

### Constants
- **BULK_HEALTH_CHECK_PRIORITY**: Set to 10 (standard priority for manual checks)
- **REGEX_TABLE_GRID_COLS**: Grid template for consistent column widths across header and rows

### User Experience Enhancements
1. **Tooltips**: Hover tooltips explain the button's function ("Health Check Channel")
2. **Loading States**: Clear visual feedback during operations
3. **Toast Notifications**: 
   - Start: "Channel Check Started" or "Bulk Health Check Started"
   - Success: Displays statistics for single checks or confirmation for bulk
   - Error: Shows error message if check fails or times out
4. **Automatic Refresh**: Channel data reloads after successful checks to show updated stats

## Code Changes

### Modified Files
- `frontend/src/pages/ChannelConfiguration.jsx`
  - Added Activity icon import
  - Added constants for grid layout and priority
  - Added `bulkCheckingChannels` state
  - Added `handleBulkHealthCheck` handler
  - Updated `RegexTableRow` component to accept health check props
  - Added health check button to table rows
  - Added bulk health check button to action bar
  - Updated grid column widths to accommodate new buttons

### Grid Layout Update
- Previous: `50px 80px 80px 1fr 200px 150px 100px`
- Updated: `50px 80px 80px 1fr 200px 150px 140px` (40px wider for two buttons)

## Benefits
1. **Improved Workflow**: Users can check channels without leaving the configuration page
2. **Bulk Operations**: Check multiple channels at once after mass regex assignment
3. **Visual Consistency**: Color-coded buttons match the app's theme system
4. **Accessibility**: Tooltips and clear icons improve usability
5. **Performance**: Reuses existing API endpoints and state management

## Future Enhancements
Potential improvements for future versions:
- Add progress bar for bulk operations
- Show queue position for bulk checks
- Add filter to show only channels with failed checks
- Add "Check All Visible" button
- Add keyboard shortcuts for power users
