# UI Preview: Health Check Buttons

## Visual Description

### Before Changes
The Regex Configuration table had a single expand/collapse button (chevron icon) in the Actions column for each channel.

### After Changes

#### 1. Individual Channel Row
Each channel row now has **two buttons** in the Actions column:

```
+----------------------------------------------------------------+
| # | Logo | Channel Name | Group | Patterns | Actions          |
+----------------------------------------------------------------+
| 1 | [📺] | ESPN         | Sports| 2 patterns| [❤️] [▼]        |
+----------------------------------------------------------------+
```

- **Health Check Button** (left): 
  - Icon: Activity/heartbeat icon
  - Color: Blue in light mode, Green in dark mode
  - Tooltip: "Health Check Channel"
  - When clicked: Runs immediate health check for that channel
  - During check: Shows loading spinner
  
- **Expand Button** (right):
  - Icon: ChevronDown (rotates when expanded)
  - Function: Shows/hides channel regex patterns and settings

#### 2. Action Bar (Above Table)
The action bar now includes a **fourth button** for bulk operations:

```
+------------------------------------------------------------------+
| [Select All] [Deselect All] [Add Regex to Selected] [❤️ Health Check Selected] |
+------------------------------------------------------------------+
```

- **Health Check Selected Button**:
  - Icon: Activity icon
  - Color: Blue in light mode, Green in dark mode
  - Text: "Health Check Selected"
  - Enabled: Only when channels are selected
  - When clicked: Queues all selected channels for health checks
  - During operation: Shows loading spinner

### Color Scheme

#### Light Mode
- Button border: Blue (`border-blue-600`)
- Button text: Blue (`text-blue-600`)
- Hover background: Light blue (`hover:bg-blue-50`)

#### Dark Mode
- Button border: Green (`dark:border-green-500`)
- Button text: Green (`dark:text-green-500`)
- Hover background: Dark green (`dark:hover:bg-green-950`)

### User Interactions

#### Single Channel Health Check
1. User hovers over health check button → Tooltip appears
2. User clicks button → Button shows spinner
3. Toast notification: "Channel Check Started"
4. After check completes → Toast shows results
5. Channel stats update automatically
6. Button returns to normal state

#### Bulk Health Check
1. User selects multiple channels via checkboxes
2. Badge shows "X selected"
3. User clicks "Health Check Selected" button
4. Button shows spinner
5. Toast notification: "Queuing X channels for checking..."
6. Toast confirms: "X channels queued for health check"
7. Channels are processed by the stream checker queue

### Accessibility Features
- Tooltips on hover for guidance
- Clear loading states with spinners
- Disabled states prevent double-clicks
- Color contrast meets accessibility standards
- Icon-only buttons have descriptive tooltips

## Layout Details

### Column Widths
- Checkbox: 50px
- Channel #: 80px
- Logo: 80px
- Channel Name: 1fr (flexible)
- Group: 200px
- Patterns: 150px
- Actions: 140px (increased from 100px to fit two buttons)

### Spacing
- Gap between buttons: 8px (gap-2)
- Button padding: 12px horizontal, 8px vertical
- Icon size: 16px × 16px (h-4 w-4)

## Example Workflow

### Scenario 1: Quick Single Channel Check
```
User sees a channel "CNN" with outdated stats
↓
Clicks the health check button (❤️) next to CNN
↓
Button shows loading spinner
↓
2 minutes later, toast shows: "Checked 5 streams. Dead: 1. Avg Resolution: 1080p"
↓
CNN's stats update in the table
```

### Scenario 2: Bulk Check After Regex Assignment
```
User adds regex pattern to 10 channels
↓
Selects all 10 channels using checkboxes
↓
Clicks "Health Check Selected" button
↓
Toast: "Queuing 10 channels for checking..."
↓
Channels are added to the stream checker queue
↓
User can check queue status in Stream Checker page
```
