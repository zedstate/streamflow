import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Checkbox } from '@/components/ui/checkbox.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog.jsx'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog.jsx'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion.jsx'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Separator } from '@/components/ui/separator.jsx'
import { useToast } from '@/hooks/use-toast.js'
import { channelsAPI, regexAPI, streamCheckerAPI, channelOrderAPI, automationAPI, m3uAPI } from '@/services/api.js'
import { CheckCircle, Edit, Plus, Trash2, Loader2, Search, X, Download, Upload, GripVertical, Save, RotateCcw, ArrowUpDown, MoreVertical, Eye, ChevronDown, Info, Activity, Edit2, ArrowRight } from 'lucide-react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger, DropdownMenuCheckboxItem } from '@/components/ui/dropdown-menu.jsx'
import { Switch } from '@/components/ui/switch.jsx'
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip.jsx'
import {
  DndContext,

  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

// Constants for localStorage keys
const CHANNEL_STATS_PREFIX = 'streamflow_channel_stats_'
const CHANNEL_LOGO_PREFIX = 'streamflow_channel_logo_'

// Constants for grid layout
const REGEX_TABLE_GRID_COLS = '50px 80px 80px 1fr 180px 120px 150px 140px'

// Constants for stream checker priorities
const BULK_HEALTH_CHECK_PRIORITY = 10

// M3U account filtering - exclude 'custom' account as it's not a real source
const CUSTOM_ACCOUNT_NAME = 'custom'

// Helper function to normalize pattern data (supports both old and new formats)
const normalizePatternData = (channelPatterns) => {
  if (!channelPatterns) return []

  // New format: regex_patterns is array of {pattern, m3u_accounts}
  if (channelPatterns.regex_patterns && Array.isArray(channelPatterns.regex_patterns)) {
    return channelPatterns.regex_patterns.map(p => ({
      pattern: p.pattern || p,
      m3u_accounts: p.m3u_accounts || null
    }))
  }

  // Old format: regex is array of strings, m3u_accounts is channel-level
  if (channelPatterns.regex && Array.isArray(channelPatterns.regex)) {
    const channelM3uAccounts = channelPatterns.m3u_accounts || null
    return channelPatterns.regex.map(pattern => ({
      pattern: pattern,
      m3u_accounts: channelM3uAccounts
    }))
  }

  return []
}

function ChannelCard({ channel, patterns, onEditRegex, onDeletePattern, onCheckChannel, loading, channelSettings, onUpdateSettings }) {
  const [stats, setStats] = useState(null)
  const [loadingStats, setLoadingStats] = useState(true)
  const [expanded, setExpanded] = useState(false)
  const [logoUrl, setLogoUrl] = useState(null)
  const [logoError, setLogoError] = useState(false)
  const { toast } = useToast()

  const matchingMode = channelSettings?.matching_mode || 'enabled'
  const checkingMode = channelSettings?.checking_mode || 'enabled'
  const matchingModeSource = channelSettings?.matching_mode_source || 'default'
  const checkingModeSource = channelSettings?.checking_mode_source || 'default'
  const isMatchingInherited = matchingModeSource === 'group'
  const isCheckingInherited = checkingModeSource === 'group'

  const handleMatchingModeChange = async (value) => {
    try {
      await onUpdateSettings(channel.id, { matching_mode: value })
      toast({
        title: "Success",
        description: "Matching mode updated successfully"
      })
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to update matching mode",
        variant: "destructive"
      })
    }
  }

  const handleCheckingModeChange = async (value) => {
    try {
      await onUpdateSettings(channel.id, { checking_mode: value })
      toast({
        title: "Success",
        description: "Checking mode updated successfully"
      })
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to update checking mode",
        variant: "destructive"
      })
    }
  }

  useEffect(() => {
    // Try to load stats from localStorage first for instant display
    const cachedStats = localStorage.getItem(`${CHANNEL_STATS_PREFIX}${channel.id}`)
    if (cachedStats) {
      try {
        const parsed = JSON.parse(cachedStats)
        setStats(parsed)
        setLoadingStats(false) // Show cached data immediately
      } catch (e) {
        console.error('Failed to parse cached stats:', e)
      }
    }
    // Always fetch fresh stats in background to keep data current
    loadStats()
  }, [channel.id])

  // Fetch logo when logo_id is available
  useEffect(() => {
    const loadLogo = () => {
      // Try cached logo first from localStorage
      const cachedLogo = localStorage.getItem(`${CHANNEL_LOGO_PREFIX}${channel.id}`)
      if (cachedLogo) {
        setLogoUrl(cachedLogo)
      }

      // Set logo URL if logo_id is available using the cached endpoint
      // This endpoint will serve cached logos or download them on first request
      if (channel.logo_id) {
        const logoUrl = channelsAPI.getLogoCached(channel.logo_id)
        setLogoUrl(logoUrl)
        localStorage.setItem(`${CHANNEL_LOGO_PREFIX}${channel.id}`, logoUrl)
      }
    }
    loadLogo()
  }, [channel.id, channel.logo_id])

  const loadStats = async () => {
    try {
      setLoadingStats(true)
      const response = await channelsAPI.getChannelStats(channel.id)
      setStats(response.data)
      // Cache stats in localStorage
      localStorage.setItem(`${CHANNEL_STATS_PREFIX}${channel.id}`, JSON.stringify(response.data))
    } catch (err) {
      console.error('Failed to load channel stats:', err)
    } finally {
      setLoadingStats(false)
    }
  }

  const channelPatterns = patterns[channel.id] || patterns[String(channel.id)]

  return (
    <Card className="w-full">
      <CardContent className="p-0">
        <div className="flex items-center gap-3 p-3">
          {/* Channel Logo */}
          <div className="w-24 h-12 flex-shrink-0 bg-muted rounded-md flex items-center justify-center overflow-hidden">
            {logoUrl && !logoError ? (
              <img
                src={logoUrl}
                alt={channel.name}
                className="w-full h-full object-contain"
                onError={() => setLogoError(true)}
              />
            ) : (
              <span className="text-2xl font-bold text-muted-foreground">
                {channel.name?.charAt(0) || '?'}
              </span>
            )}
          </div>

          {/* Channel Info */}
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-base truncate">{channel.name}</h3>
            <div className="flex flex-wrap gap-3 mt-1 text-sm">
              {loadingStats ? (
                <span className="text-muted-foreground">Loading stats...</span>
              ) : stats ? (
                <>
                  <div className="flex items-center gap-1">
                    <span className="text-muted-foreground">Streams:</span>
                    <span className="font-medium">{stats.total_streams ?? 0}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="text-muted-foreground">Dead:</span>
                    <span className="font-medium text-destructive">{stats.dead_streams ?? 0}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="text-muted-foreground">Avg.Resolution:</span>
                    <span className="font-medium">{stats.most_common_resolution || 'Unknown'}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="text-muted-foreground">Avg Bitrate:</span>
                    <span className="font-medium">{stats.average_bitrate > 0 ? `${stats.average_bitrate} Kbps` : 'N/A'}</span>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-1">
                    <span className="text-muted-foreground">Streams:</span>
                    <span className="font-medium text-muted-foreground">--</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="text-muted-foreground">Dead:</span>
                    <span className="font-medium text-muted-foreground">--</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="text-muted-foreground">Avg.Resolution:</span>
                    <span className="font-medium text-muted-foreground">--</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="text-muted-foreground">Avg Bitrate:</span>
                    <span className="font-medium text-muted-foreground">--</span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-2 flex-shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setExpanded(!expanded)}
            >
              <Edit className="h-4 w-4 mr-2" />
              Edit Regex
            </Button>
            <Button
              size="sm"
              onClick={() => onCheckChannel(channel.id)}
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <CheckCircle className="h-4 w-4 mr-2" />
              )}
              Check Channel
            </Button>
          </div>
        </div>

        {/* Expandable Regex Section */}
        {expanded && (
          <div className="border-t p-4 bg-muted/50 space-y-4">
            {/* Channel Settings */}
            <div className="grid grid-cols-2 gap-4 pb-4 border-b">
              <div className="space-y-2">
                <Label htmlFor={`matching-mode-${channel.id}`} className="text-sm font-medium">
                  Stream Matching
                  {isMatchingInherited && (
                    <Badge variant="outline" className="ml-2 text-xs">From Group</Badge>
                  )}
                </Label>
                <Select value={matchingMode} onValueChange={handleMatchingModeChange}>
                  <SelectTrigger id={`matching-mode-${channel.id}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="enabled">Enabled</SelectItem>
                    <SelectItem value="disabled">Disabled</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  {matchingMode === 'enabled'
                    ? 'Channel will be included in stream matching'
                    : 'Channel will be excluded from stream matching'}
                  {isMatchingInherited && ' (inherited from group)'}
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor={`checking-mode-${channel.id}`} className="text-sm font-medium">
                  Stream Checking
                  {isCheckingInherited && (
                    <Badge variant="outline" className="ml-2 text-xs">From Group</Badge>
                  )}
                </Label>
                <Select value={checkingMode} onValueChange={handleCheckingModeChange}>
                  <SelectTrigger id={`checking-mode-${channel.id}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="enabled">Enabled</SelectItem>
                    <SelectItem value="disabled">Disabled</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  {checkingMode === 'enabled'
                    ? 'Channel streams will be quality checked'
                    : 'Channel streams will not be quality checked'}
                  {isCheckingInherited && ' (inherited from group)'}
                </p>
              </div>
            </div>

            {/* Regex Patterns */}
            <div>
              <div className="flex justify-between items-center mb-3">
                <h4 className="font-medium text-sm">Regex Patterns</h4>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onEditRegex(channel.id, null)}
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Pattern
                </Button>
              </div>

              {(() => {
                const normalizedPatterns = normalizePatternData(channelPatterns)
                return normalizedPatterns.length > 0 ? (
                  <div className="space-y-2">
                    {normalizedPatterns.map((patternObj, index) => (
                      <div key={index} className="flex items-center justify-between gap-2 p-2 bg-background rounded-md">
                        <code className="text-sm flex-1 break-all">{patternObj.pattern}</code>
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => onEditRegex(channel.id, index)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => onDeletePattern(channel.id, index)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No regex patterns configured</p>
                )
              })()}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function SortableChannelItem({ channel }) {
  const [logoUrl, setLogoUrl] = useState(null)
  const [logoError, setLogoError] = useState(false)

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: channel.id })

  useEffect(() => {
    const loadLogo = () => {
      // Try cached logo first from localStorage
      const cachedLogo = localStorage.getItem(`${CHANNEL_LOGO_PREFIX}${channel.id}`)
      if (cachedLogo) {
        setLogoUrl(cachedLogo)
        return // Use cached version, don't fetch again
      }

      // Only fetch from API if not cached and logo_id is available
      if (channel.logo_id) {
        const logoUrl = channelsAPI.getLogoCached(channel.logo_id)
        setLogoUrl(logoUrl)
        localStorage.setItem(`${CHANNEL_LOGO_PREFIX}${channel.id}`, logoUrl)
      }
    }
    loadLogo()
  }, [channel.id, channel.logo_id])

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 p-4 bg-card border rounded-lg ${isDragging ? 'shadow-lg' : 'shadow-sm'
        }`}
    >
      <div
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing touch-none"
      >
        <GripVertical className="h-5 w-5 text-muted-foreground" />
      </div>

      {/* Channel Logo */}
      <div className="w-20 h-10 flex-shrink-0 bg-muted rounded-md flex items-center justify-center overflow-hidden">
        {logoUrl && !logoError ? (
          <img
            src={logoUrl}
            alt={channel.name}
            className="w-full h-full object-contain"
            onError={() => setLogoError(true)}
          />
        ) : (
          <span className="text-xl font-bold text-muted-foreground">
            {channel.name?.charAt(0) || '?'}
          </span>
        )}
      </div>

      <div className="flex-1 flex items-center gap-4">
        <Badge variant="outline" className="font-mono">
          #{channel.channel_number || 'N/A'}
        </Badge>
        <div className="flex-1 min-w-0">
          <div className="font-medium truncate">{channel.name}</div>
          <div className="text-xs text-muted-foreground">ID: {channel.id}</div>
        </div>
      </div>
    </div>
  )
}

function RegexTableRow({ channel, group, groups, profiles, patterns, selectedChannels, onToggleChannel, onEditRegex, onDeletePattern, expandedRowId, onToggleExpanded, onCheckChannel, checkingChannel, m3uAccounts, onUpdateMatchSettings, onPreviewMatch }) {
  const [logoUrl, setLogoUrl] = useState(null)
  const [logoError, setLogoError] = useState(false)
  const { toast } = useToast()

  // Use parent-controlled expanded state
  const expanded = expandedRowId === channel.id
  const isChecking = checkingChannel === channel.id

  const channelPatterns = patterns[channel.id] || patterns[String(channel.id)]
  const matchByTvgId = channelPatterns?.match_by_tvg_id || false
  const patternCount = normalizePatternData(channelPatterns).length

  // Load channel logo
  useEffect(() => {
    const loadLogo = () => {
      // Check localStorage cache first
      const cachedUrl = localStorage.getItem(`${CHANNEL_LOGO_PREFIX}${channel.id}`)
      if (cachedUrl) {
        setLogoUrl(cachedUrl)
        return
      }

      // Fetch logo if logo_id is available
      if (channel.logo_id) {
        const logoUrl = channelsAPI.getLogoCached(channel.logo_id)
        setLogoUrl(logoUrl)
        localStorage.setItem(`${CHANNEL_LOGO_PREFIX}${channel.id}`, logoUrl)
      }
    }
    loadLogo()
  }, [channel.id, channel.logo_id])



  return (
    <div key={channel.id}>
      <div className={`grid gap-4 p-4 hover:bg-muted/50 transition-colors`} style={{ gridTemplateColumns: REGEX_TABLE_GRID_COLS }}>
        <div className="flex items-center justify-center">
          <Checkbox
            checked={selectedChannels.has(channel.id)}
            onCheckedChange={() => onToggleChannel(channel.id)}
          />
        </div>
        <div className="flex items-center text-sm font-medium">
          {channel.channel_number || '-'}
        </div>
        <div className="flex items-center">
          <div className="w-16 h-10 flex-shrink-0 bg-muted rounded-md flex items-center justify-center overflow-hidden">
            {logoUrl && !logoError ? (
              <img
                src={logoUrl}
                alt={channel.name}
                className="w-full h-full object-contain"
                onError={() => setLogoError(true)}
              />
            ) : (
              <span className="text-lg font-bold text-muted-foreground">
                {channel.name?.charAt(0) || '?'}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center">
          <span className="font-medium truncate">{channel.name}</span>
        </div>
        <div className="flex items-center text-sm text-muted-foreground truncate">
          {group?.name || '-'}
        </div>
        <div className="flex items-center">
          {(() => {
            const profileId = channel.automation_profile_id
            const profile = profiles?.find(p => p.id === profileId)

            if (profile) {
              return (
                <Badge variant="outline" className="text-xs font-normal">
                  {profile.name}
                </Badge>
              )
            }

            // Fallback/Debug: Show ID if present but profile not found
            if (profileId) {
              return (
                <span className="text-xs text-muted-foreground" title={`Profile ID: ${profileId}`}>
                  {profileId === 'default' ? 'Default' : 'Unknown Profile'}
                </span>
              )
            }

            return <span className="text-sm text-muted-foreground">-</span>
          })()}
        </div>
        <div className="flex items-center">
          {patternCount > 0 ? (
            <Badge variant="secondary">{patternCount} pattern{patternCount > 1 ? 's' : ''}</Badge>
          ) : (
            <span className="text-sm text-muted-foreground">No patterns</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onPreviewMatch(channel.id, 'global')}
              >
                <Eye className="h-4 w-4 text-muted-foreground" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Global Channel Preview</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onCheckChannel(channel.id)}
                disabled={isChecking}
                className="text-blue-600 dark:text-green-500 border-blue-600 dark:border-green-500 hover:bg-blue-50 dark:hover:bg-green-950"
              >
                {isChecking ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Activity className="h-4 w-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Health Check Channel</p>
            </TooltipContent>
          </Tooltip>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onToggleExpanded(channel.id)}
          >
            <ChevronDown className={`h-4 w-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Expanded Section */}
      {expanded && (
        <div className="border-t p-4 bg-muted/50 space-y-4">


          {/* Regex Patterns */}
          <div>
            {/* Match Settings */}
            <div className="flex items-center justify-between mb-4 p-3 bg-muted rounded-md">
              <div className="flex items-center space-x-2">
                <Switch
                  id={`tvg-match-${channel.id}`}
                  checked={matchByTvgId}
                  onCheckedChange={(checked) => onUpdateMatchSettings(channel.id, { match_by_tvg_id: checked })}
                />
                <Label htmlFor={`tvg-match-${channel.id}`} className="flex flex-col cursor-pointer">
                  <span className="font-medium">Match by TVG-ID</span>
                  <span className="font-normal text-xs text-muted-foreground">
                    Automatically match streams with TVG-ID "{channel.tvg_id || 'N/A'}"
                  </span>
                </Label>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => onPreviewMatch(channel.id, 'tvg_only')}
                disabled={!channel.tvg_id}
                title={!channel.tvg_id ? "No TVG-ID set" : "Preview only TVG-ID matches (ignoring profile/regex)"}
              >
                <Eye className="h-4 w-4 mr-2" />
                Preview Results
              </Button>
            </div>

            <div className="flex justify-between items-center mb-3">
              <h4 className="font-medium text-sm">Regex Patterns</h4>
              <Button
                size="sm"
                variant="outline"
                onClick={() => onEditRegex(channel.id, null)}
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Pattern
              </Button>
            </div>

            {(() => {
              const normalizedPatterns = normalizePatternData(channelPatterns)
              return normalizedPatterns.length > 0 ? (
                <div className="space-y-2">
                  {normalizedPatterns.map((patternObj, index) => {
                    // Get M3U account names if m3u_accounts are specified for this pattern
                    const accountNames = patternObj.m3u_accounts && patternObj.m3u_accounts.length > 0
                      ? patternObj.m3u_accounts.map(id => {
                        const acc = m3uAccounts?.find(account => account.id === id)
                        return acc ? acc.name : `Account ${id}`
                      }).join(', ')
                      : 'All M3U Accounts'

                    return (
                      <div key={index} className="space-y-1">
                        <div className="flex items-center justify-between gap-2 p-2 bg-background rounded-md">
                          <div className="flex-1 space-y-1">
                            <code className="text-sm break-all">{patternObj.pattern}</code>
                            <div className="text-xs text-muted-foreground">
                              M3U Sources: {accountNames}
                            </div>
                          </div>
                          <div className="flex gap-1">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => onEditRegex(channel.id, index)}
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => onDeletePattern(channel.id, index)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No regex patterns configured</p>
              )
            })()}
          </div>
        </div>
      )}
    </div>
  )
}


export default function ChannelConfiguration() {
  const [channels, setChannels] = useState([])
  const [patterns, setPatterns] = useState({})

  const [loading, setLoading] = useState(true)
  const [checkingChannel, setCheckingChannel] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingChannelId, setEditingChannelId] = useState(null)
  const [editingPatternIndex, setEditingPatternIndex] = useState(null)
  const [newPattern, setNewPattern] = useState('')
  const [testingPattern, setTestingPattern] = useState(false)
  const [testResults, setTestResults] = useState(null)
  const [testRequestIdRef] = useState({ current: 0 })
  const [previewResultsOpen, setPreviewResultsOpen] = useState(false)
  const [previewTitle, setPreviewTitle] = useState('')
  const { toast } = useToast()

  // Pagination state for Regex Configuration
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage, setItemsPerPage] = useState(20)

  // Pagination state for Channel Order
  const [orderCurrentPage, setOrderCurrentPage] = useState(1)
  const [orderItemsPerPage, setOrderItemsPerPage] = useState(20)

  // Channel ordering state
  const [orderedChannels, setOrderedChannels] = useState([])
  const [originalChannelOrder, setOriginalChannelOrder] = useState([])
  const [hasOrderChanges, setHasOrderChanges] = useState(false)
  const [savingOrder, setSavingOrder] = useState(false)
  const [sortBy, setSortBy] = useState('custom')

  const [groups, setGroups] = useState([])

  const [pendingChanges, setPendingChanges] = useState({})
  const [activeTab, setActiveTab] = useState('regex')

  // Multi-select state for bulk regex assignment
  const [selectedChannels, setSelectedChannels] = useState(new Set())
  const [filterByGroup, setFilterByGroup] = useState('all')
  const [sortByGroup, setSortByGroup] = useState(false)
  const [bulkDialogOpen, setBulkDialogOpen] = useState(false)
  const [bulkPattern, setBulkPattern] = useState('')

  // Automation Profile state
  const [profiles, setProfiles] = useState([])
  const [assignProfileId, setAssignProfileId] = useState('')

  // M3U account filtering state for regex patterns
  const [m3uAccounts, setM3uAccounts] = useState([])  // All M3U accounts
  const [selectedM3uAccounts, setSelectedM3uAccounts] = useState([])  // For individual regex dialog
  const [bulkSelectedM3uAccounts, setBulkSelectedM3uAccounts] = useState([])  // For bulk regex dialog
  const [patternPriority, setPatternPriority] = useState(0)  // Priority for individual regex dialog

  // Profile filter state
  const [profileFilterActive, setProfileFilterActive] = useState(false)
  const [profileFilterInfo, setProfileFilterInfo] = useState(null)

  // Expanded row state - to ensure only one action menu is open at a time
  const [expandedRowId, setExpandedRowId] = useState(null)

  // Bulk health check state
  const [bulkCheckingChannels, setBulkCheckingChannels] = useState(false)

  // Delete confirmation dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)

  // Edit common regex dialog state
  const [editCommonDialogOpen, setEditCommonDialogOpen] = useState(false)
  const [commonPatterns, setCommonPatterns] = useState([])
  const [loadingCommonPatterns, setLoadingCommonPatterns] = useState(false)
  const [editingCommonPattern, setEditingCommonPattern] = useState(null)
  const [newCommonPattern, setNewCommonPattern] = useState('')
  const [newCommonPatternM3uAccounts, setNewCommonPatternM3uAccounts] = useState(null) // null = all playlists, array = selected playlists
  const [newCommonPatternPriority, setNewCommonPatternPriority] = useState(0) // Priority for common pattern editing
  const [selectedCommonPatterns, setSelectedCommonPatterns] = useState(new Set())
  const [commonPatternsSearch, setCommonPatternsSearch] = useState('')

  // Mass edit state
  const [massEditMode, setMassEditMode] = useState(false)
  const [massEditFindPattern, setMassEditFindPattern] = useState('')
  const [massEditReplacePattern, setMassEditReplacePattern] = useState('')
  const [massEditUseRegex, setMassEditUseRegex] = useState(false)
  const [massEditM3uAccounts, setMassEditM3uAccounts] = useState(null) // null = keep existing, array = update to selected
  const [massEditPriority, setMassEditPriority] = useState(null) // null = keep existing, number = update to value
  const [massEditPreview, setMassEditPreview] = useState(null)
  const [loadingMassEditPreview, setLoadingMassEditPreview] = useState(false)

  // Update settings only mode (for playlist/priority changes without find & replace)
  const [updateOnlyMode, setUpdateOnlyMode] = useState(false)

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)

      // Load all channels directly
      const channelsResponse = await channelsAPI.getChannels()
      const channelsToLoad = channelsResponse.data || []

      const [patternsResponse, groupsResponse, orderResponse, m3uAccountsResponse, profilesResponse] = await Promise.all([
        regexAPI.getPatterns(),
        channelsAPI.getGroups(),
        channelOrderAPI.getOrder().catch(() => ({ data: { order: [] } })), // Handle case where no order is saved
        m3uAPI.getAccounts().catch(() => ({ data: { accounts: [] } })), // Load M3U accounts
        automationAPI.getProfiles().catch(() => ({ data: [] }))
      ])

      setChannels(channelsToLoad)
      setPatterns(patternsResponse.data.patterns || {})
      setGroups(groupsResponse.data || [])
      setProfiles(profilesResponse.data || [])


      // Set M3U accounts (filter out custom account as it's not a real source)
      const accounts = m3uAccountsResponse.data?.accounts || m3uAccountsResponse.data || []
      setM3uAccounts(accounts.filter(acc => acc.name?.toLowerCase() !== CUSTOM_ACCOUNT_NAME))

      // Initialize ordered channels
      const channelData = channelsToLoad
      const savedOrder = orderResponse.data?.order || []

      let orderedList = []

      if (savedOrder.length > 0) {
        // Apply saved custom order
        // Create a map for quick lookup
        const channelMap = new Map(channelData.map(ch => [ch.id, ch]))

        // First, add channels in the saved order (only if they're in our filtered list)
        orderedList = savedOrder
          .map(id => channelMap.get(id))
          .filter(ch => ch !== undefined) // Filter out any channels that don't exist or are filtered out

        // Then add any new channels that weren't in the saved order (sorted by channel number)
        const orderedIds = new Set(orderedList.map(ch => ch.id))
        const newChannels = channelData
          .filter(ch => !orderedIds.has(ch.id))
          .sort((a, b) => {
            const numA = parseFloat(a.channel_number) || 999999
            const numB = parseFloat(b.channel_number) || 999999
            return numA - numB
          })

        orderedList = [...orderedList, ...newChannels]
      } else {
        // No saved order, sort by channel_number
        orderedList = [...channelData].sort((a, b) => {
          const numA = parseFloat(a.channel_number) || 999999
          const numB = parseFloat(b.channel_number) || 999999
          return numA - numB
        })
      }

      setOrderedChannels(orderedList)
      setOriginalChannelOrder(orderedList)
      setHasOrderChanges(false)
    } catch (err) {
      console.error('Failed to load data:', err)
      toast({
        title: "Error",
        description: "Failed to load channel data",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleCheckChannel = async (channelId) => {
    try {
      setCheckingChannel(channelId)

      // Show starting notification
      toast({
        title: "Channel Check Started",
        description: "Checking channel streams... This may take a few minutes.",
      })

      const response = await streamCheckerAPI.checkSingleChannel(channelId)

      if (response.data.success) {
        const stats = response.data.stats
        toast({
          title: "Channel Check Complete",
          description: `Checked ${stats.total_streams} streams. Dead: ${stats.dead_streams}. Avg Resolution: ${stats.avg_resolution}, Avg Bitrate: ${stats.avg_bitrate}`,
        })
        // Reload the channel data to show updated stats
        loadData()
      } else {
        toast({
          title: "Check Failed",
          description: response.data.error || "Failed to check channel",
          variant: "destructive"
        })
      }
    } catch (err) {
      console.error('Error checking channel:', err)
      // Check if it's a timeout error
      if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        toast({
          title: "Check Taking Longer Than Expected",
          description: "The channel check is still running. Please check back in a few minutes.",
          variant: "default"
        })
      } else {
        toast({
          title: "Error",
          description: err.response?.data?.error || "Failed to check channel",
          variant: "destructive"
        })
      }
    } finally {
      setCheckingChannel(null)
    }
  }

  const handleBulkHealthCheck = async () => {
    if (selectedChannels.size === 0) {
      toast({
        title: "No Channels Selected",
        description: "Please select at least one channel",
        variant: "destructive"
      })
      return
    }

    try {
      setBulkCheckingChannels(true)

      // Show starting notification
      toast({
        title: "Bulk Health Check Started",
        description: `Queuing ${selectedChannels.size} channel${selectedChannels.size !== 1 ? 's' : ''} for checking...`,
      })

      const response = await streamCheckerAPI.addToQueue({
        channel_ids: Array.from(selectedChannels),
        priority: BULK_HEALTH_CHECK_PRIORITY,
        force_check: true  // Enable force check to bypass 2-hour immunity
      })

      toast({
        title: "Channels Queued",
        description: response.data.message || `${selectedChannels.size} channel${selectedChannels.size !== 1 ? 's' : ''} queued for health check`,
      })
    } catch (err) {
      console.error('Error queuing channels for health check:', err)
      toast({
        title: "Error",
        description: err.response?.data?.error || "Failed to queue channels for health check",
        variant: "destructive"
      })
    } finally {
      setBulkCheckingChannels(false)
    }
  }

  const handleBatchAssignProfile = async (profileId) => {
    if (selectedChannels.size === 0) {
      toast({
        title: "No Channels Selected",
        description: "Please select at least one channel",
        variant: "destructive"
      })
      return
    }

    try {
      setLoading(true)
      const channelIds = Array.from(selectedChannels)
      const targetProfileId = profileId === 'none' ? null : profileId

      // Use generic batch assignment endpoint
      await automationAPI.assignChannels(channelIds, targetProfileId)

      toast({
        title: "Success",
        description: `Profile ${targetProfileId ? 'assigned to' : 'removed from'} ${channelIds.length} channels`,
      })

      // Reload settings to update UI
      loadData()
    } catch (err) {
      console.error('Failed to batch assign profile:', err)
      toast({
        title: "Error",
        description: "Failed to assign profile to channels",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
      setAssignProfileId('') // Reset selection
    }
  }

  const handleUpdateMatchSettings = async (channelId, settings) => {
    try {
      await regexAPI.updateMatchSettings(channelId, settings)

      // Update patterns state locally to reflect change immediately
      setPatterns(prev => {
        const channelPattern = prev[channelId] || prev[String(channelId)] || {}
        return {
          ...prev,
          [channelId]: {
            ...channelPattern,
            ...settings
          }
        }
      })

      toast({
        title: "Success",
        description: "Match settings updated successfully"
      })
    } catch (err) {
      console.error('Failed to update match settings:', err)
      toast({
        title: "Error",
        description: "Failed to update match settings",
        variant: "destructive"
      })
    }
  }




  const handleEditRegex = (channelId, patternIndex) => {
    setEditingChannelId(channelId)
    setEditingPatternIndex(patternIndex)

    // If editing an existing pattern, load it
    if (patternIndex !== null) {
      const channelPatterns = patterns[channelId] || patterns[String(channelId)]

      // Support both new and old format
      if (channelPatterns?.regex_patterns && channelPatterns.regex_patterns[patternIndex]) {
        // New format with per-pattern m3u_accounts and priority
        const patternObj = channelPatterns.regex_patterns[patternIndex]
        setNewPattern(patternObj.pattern || '')
        setSelectedM3uAccounts(patternObj.m3u_accounts || [])
        setPatternPriority(patternObj.priority || 0)
      } else if (channelPatterns && channelPatterns.regex && channelPatterns.regex[patternIndex]) {
        // Old format - pattern is a string, m3u_accounts is channel-level
        setNewPattern(channelPatterns.regex[patternIndex])
        // Load channel-level M3U account selection (if any)
        if (channelPatterns.m3u_accounts) {
          setSelectedM3uAccounts(channelPatterns.m3u_accounts)
        } else {
          setSelectedM3uAccounts([])  // Empty means all M3U accounts
        }
        setPatternPriority(0)  // Default priority for old format
      }
    } else {
      setNewPattern('')
      setSelectedM3uAccounts([])  // Default to all M3U accounts for new patterns
      setPatternPriority(0)  // Default priority for new patterns
    }

    setTestResults(null)
    setDialogOpen(true)
  }

  const handleCloseDialog = () => {
    setDialogOpen(false)
    setEditingChannelId(null)
    setEditingPatternIndex(null)
    setNewPattern('')
    setTestResults(null)
    setSelectedM3uAccounts([])  // Reset M3U account selection
    setPatternPriority(0)  // Reset priority
  }

  const handleTestPattern = useCallback(async (mode = 'regex_only', loadMore = false, channelId = null) => {
    // Determine context based on mode and optional channelId
    let contextChannelId = channelId || editingChannelId
    let contextPattern = newPattern
    let contextPriority = patternPriority
    let contextM3uAccounts = selectedM3uAccounts

    // If testing from outside match dialog (e.g. TVG preview or Global preview), we rely on passed channelId
    if (!contextChannelId) return

    // Increment request ID to track this request
    const requestId = ++testRequestIdRef.current
    const currentMaxMatches = loadMore && testResults ? (testResults.max_matches || 50) + 50 : 50

    try {
      setTestingPattern(true)
      const channel = channels.find(ch => ch.id === contextChannelId)
      const profile = profiles.find(p => p.id === channel?.automation_profile_id)
      const channelPatternConfig = patterns[contextChannelId] || patterns[String(contextChannelId)] || {}

      // Prepare request data based on mode
      let requestData = {
        channel_name: channel?.name || '',
        tvg_id: channel?.tvg_id,
        max_matches: currentMaxMatches
      }

      if (mode === 'tvg_only') {
        requestData.match_by_tvg_id = true
        requestData.regex_patterns = []
        requestData.match_priority_order = ['tvg']
      } else if (mode === 'regex_only') {
        // Test ONLY the current pattern being edited
        requestData.match_by_tvg_id = false
        requestData.regex_patterns = [{
          pattern: contextPattern,
          priority: contextPriority,
          m3u_accounts: contextM3uAccounts.length > 0 ? contextM3uAccounts : undefined
        }]
        requestData.match_priority_order = ['regex']
      } else if (mode === 'global') {
        // Full channel configuration test
        requestData.match_by_tvg_id = channelPatternConfig.match_by_tvg_id || false

        // Reconstruct regex patterns from stored config
        let regexPatterns = []
        if (channelPatternConfig.regex_patterns) {
          regexPatterns = channelPatternConfig.regex_patterns
        } else if (channelPatternConfig.regex) {
          regexPatterns = channelPatternConfig.regex.map(p => ({
            pattern: p,
            m3u_accounts: channelPatternConfig.m3u_accounts,
            priority: 0
          }))
        }

        requestData.regex_patterns = regexPatterns
        requestData.match_priority_order = profile?.stream_matching?.match_priority_order || ['tvg', 'regex']
      }

      const response = await regexAPI.testMatchLive(requestData)

      // Only update state if this is still the latest request
      if (requestId !== testRequestIdRef.current) return

      const matches = response.data.matches || []

      setTestResults({
        valid: true,
        matches: matches,
        match_count: matches.length,
        total_matches: response.data.total_matches,
        max_matches: currentMaxMatches,
        has_more: matches.length >= currentMaxMatches,
        mode: mode, // Store mode to know how to load more
        channelId: contextChannelId // Store channel ID for load more context
      })

    } catch (err) {
      if (requestId !== testRequestIdRef.current) return

      if (err.response?.data?.error) {
        setTestResults({
          valid: false,
          error: err.response.data.error
        })
      } else {
        toast({
          title: "Error",
          description: "Failed to test pattern",
          variant: "destructive"
        })
      }
    } finally {
      if (requestId === testRequestIdRef.current) {
        setTestingPattern(false)
      }
    }
  }, [newPattern, editingChannelId, channels, selectedM3uAccounts, toast, patterns, profiles, patternPriority, testResults])

  const handlePreviewMatch = useCallback((channelId, mode) => {
    setTestResults(null)

    let title = "Match Preview"
    if (mode === 'tvg_only') title = "TVG-ID Match Preview"
    else if (mode === 'global') title = "Global Channel Match Preview"

    setPreviewTitle(title)
    setPreviewResultsOpen(true)

    // Trigger test immediately
    handleTestPattern(mode, false, channelId)
  }, [handleTestPattern])

  // Test pattern on every change with debouncing
  useEffect(() => {
    if (!newPattern || !editingChannelId || !dialogOpen) {
      setTestResults(null)
      return
    }

    const timer = setTimeout(() => {
      handleTestPattern()
    }, 500) // 500ms debounce

    return () => clearTimeout(timer)
    // Only depend on the actual values, not the function
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [newPattern, editingChannelId, dialogOpen, selectedM3uAccounts])

  const handleSavePattern = async () => {
    if (!newPattern.trim() || !editingChannelId) {
      toast({
        title: "Error",
        description: "Pattern cannot be empty",
        variant: "destructive"
      })
      return
    }

    try {
      const channelPatterns = patterns[editingChannelId] || patterns[String(editingChannelId)]
      const channel = channels.find(ch => ch.id === editingChannelId)

      // Build regex_patterns array in new format with per-pattern m3u_accounts
      let updatedRegexPatterns = []

      // Get existing patterns in new format
      if (channelPatterns?.regex_patterns) {
        // Already in new format
        updatedRegexPatterns = [...channelPatterns.regex_patterns]
      } else if (channelPatterns?.regex) {
        // Convert from old format
        const oldM3uAccounts = channelPatterns.m3u_accounts
        updatedRegexPatterns = channelPatterns.regex.map(p => ({
          pattern: p,
          m3u_accounts: oldM3uAccounts,
          priority: 0
        }))
      }

      if (editingPatternIndex !== null) {
        // Editing existing pattern
        updatedRegexPatterns[editingPatternIndex] = {
          pattern: newPattern,
          m3u_accounts: selectedM3uAccounts.length > 0 ? selectedM3uAccounts : null,
          priority: patternPriority
        }
      } else {
        // Adding new pattern
        updatedRegexPatterns.push({
          pattern: newPattern,
          m3u_accounts: selectedM3uAccounts.length > 0 ? selectedM3uAccounts : null,
          priority: patternPriority
        })
      }

      // Send in new format
      await regexAPI.addPattern({
        channel_id: editingChannelId,
        name: channel?.name || '',
        regex: updatedRegexPatterns,  // Send array of objects with per-pattern m3u_accounts
        enabled: channelPatterns?.enabled !== false
      })

      toast({
        title: "Success",
        description: editingPatternIndex !== null ? "Pattern updated successfully" : "Pattern added successfully"
      })

      // Update patterns state directly instead of reloading the entire page
      setPatterns(prevPatterns => ({
        ...prevPatterns,
        [editingChannelId]: {
          ...channelPatterns,
          regex_patterns: updatedRegexPatterns,
          enabled: channelPatterns?.enabled !== false
        }
      }))

      handleCloseDialog()
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to save pattern",
        variant: "destructive"
      })
    }
  }

  const handleDeletePattern = async (channelId, patternIndex) => {
    try {
      const channelPatterns = patterns[channelId] || patterns[String(channelId)]
      const channel = channels.find(ch => ch.id === channelId)

      // Get regex patterns in the appropriate format
      let regexPatterns = []
      if (channelPatterns?.regex_patterns) {
        regexPatterns = channelPatterns.regex_patterns
      } else if (channelPatterns?.regex) {
        // Convert old format
        const oldM3uAccounts = channelPatterns.m3u_accounts
        regexPatterns = channelPatterns.regex.map(p => ({
          pattern: p,
          m3u_accounts: oldM3uAccounts
        }))
      } else {
        return // No patterns to delete
      }

      const updatedRegexPatterns = regexPatterns.filter((_, index) => index !== patternIndex)

      if (updatedRegexPatterns.length === 0) {
        // If no patterns left, delete the entire pattern config
        await regexAPI.deletePattern(channelId)

        // Update state to remove patterns
        setPatterns(prevPatterns => {
          const newPatterns = { ...prevPatterns }
          delete newPatterns[channelId]
          delete newPatterns[String(channelId)]
          return newPatterns
        })
      } else {
        // Update with remaining patterns
        await regexAPI.addPattern({
          channel_id: channelId,
          name: channel?.name || '',
          regex: updatedRegexPatterns,  // Send array of objects
          enabled: channelPatterns.enabled !== false
        })

        // Update patterns state directly
        setPatterns(prevPatterns => ({
          ...prevPatterns,
          [channelId]: {
            ...channelPatterns,
            regex_patterns: updatedRegexPatterns,
            enabled: channelPatterns.enabled !== false
          }
        }))
      }

      toast({
        title: "Success",
        description: "Pattern deleted successfully"
      })
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to delete pattern",
        variant: "destructive"
      })
    }
  }

  // Bulk assignment handlers
  const handleToggleChannel = (channelId) => {
    setSelectedChannels(prev => {
      const newSet = new Set(prev)
      if (newSet.has(channelId)) {
        newSet.delete(channelId)
      } else {
        newSet.add(channelId)
      }
      return newSet
    })
  }

  const handleSelectAll = () => {
    const visibleChannelIds = filteredChannels.map(ch => ch.id)
    setSelectedChannels(new Set(visibleChannelIds))
  }

  const handleDeselectAll = () => {
    setSelectedChannels(new Set())
  }

  const handleBulkAddPattern = async () => {
    if (selectedChannels.size === 0) {
      toast({
        title: "No Channels Selected",
        description: "Please select at least one channel",
        variant: "destructive"
      })
      return
    }

    if (!bulkPattern.trim()) {
      toast({
        title: "No Pattern Provided",
        description: "Please enter a regex pattern",
        variant: "destructive"
      })
      return
    }

    try {
      const response = await regexAPI.bulkAddPatterns({
        channel_ids: Array.from(selectedChannels),
        regex_patterns: [bulkPattern],
        m3u_accounts: bulkSelectedM3uAccounts.length > 0 ? bulkSelectedM3uAccounts : null  // null = all M3U accounts
      })

      toast({
        title: "Success",
        description: response.data.message || `Added pattern to ${response.data.success_count} channels`,
      })

      // Reload data and clear selection
      await loadData()
      setSelectedChannels(new Set())
      setBulkDialogOpen(false)
      setBulkPattern('')
      setBulkSelectedM3uAccounts([])  // Reset bulk M3U account selection
    } catch (err) {
      toast({
        title: "Error",
        description: err.response?.data?.error || "Failed to add patterns",
        variant: "destructive"
      })
    }
  }

  const handleBulkDelete = async () => {
    if (selectedChannels.size === 0) {
      toast({
        title: "No Channels Selected",
        description: "Please select at least one channel",
        variant: "destructive"
      })
      return
    }

    try {
      const response = await regexAPI.bulkDeletePatterns({
        channel_ids: Array.from(selectedChannels)
      })

      toast({
        title: "Success",
        description: response.data.message || `Deleted patterns from ${response.data.success_count} channels`,
      })

      // Reload data and close dialog
      await loadData()
      setDeleteDialogOpen(false)
    } catch (err) {
      toast({
        title: "Error",
        description: err.response?.data?.error || "Failed to delete patterns",
        variant: "destructive"
      })
    }
  }

  const handleOpenEditCommon = async () => {
    if (selectedChannels.size === 0) {
      toast({
        title: "No Channels Selected",
        description: "Please select at least one channel",
        variant: "destructive"
      })
      return
    }

    try {
      setLoadingCommonPatterns(true)
      setEditCommonDialogOpen(true)

      const response = await regexAPI.getCommonPatterns({
        channel_ids: Array.from(selectedChannels)
      })

      setCommonPatterns(response.data.patterns || [])
    } catch (err) {
      toast({
        title: "Error",
        description: err.response?.data?.error || "Failed to load common patterns",
        variant: "destructive"
      })
      setEditCommonDialogOpen(false)
    } finally {
      setLoadingCommonPatterns(false)
    }
  }

  const handleEditCommonPattern = async () => {
    if (!editingCommonPattern || !newCommonPattern.trim()) {
      toast({
        title: "Error",
        description: "Please enter a new pattern",
        variant: "destructive"
      })
      return
    }

    try {
      // Filter to only include channels that are currently selected
      // This ensures we only edit patterns in the selected channels, even if the pattern
      // exists in other channels that were not selected
      const selectedChannelIdsSet = new Set(Array.from(selectedChannels).map(id => String(id)))
      const channelsToEdit = editingCommonPattern.channel_ids.filter(id =>
        selectedChannelIdsSet.has(String(id))
      )

      if (channelsToEdit.length === 0) {
        toast({
          title: "Error",
          description: "No selected channels have this pattern",
          variant: "destructive"
        })
        return
      }

      const response = await regexAPI.bulkEditPattern({
        channel_ids: channelsToEdit,
        old_pattern: editingCommonPattern.pattern,
        new_pattern: newCommonPattern,
        new_m3u_accounts: newCommonPatternM3uAccounts,  // Include playlist selection
        new_priority: newCommonPatternPriority  // Include priority
      })

      toast({
        title: "Success",
        description: response.data.message || `Updated pattern in ${response.data.success_count} channels`,
      })

      // Reload data and common patterns
      await loadData()

      // Reload common patterns to show updated list
      const patternsResponse = await regexAPI.getCommonPatterns({
        channel_ids: Array.from(selectedChannels)
      })
      setCommonPatterns(patternsResponse.data.patterns || [])

      // Close edit mode
      setEditingCommonPattern(null)
      setNewCommonPattern('')
      setNewCommonPatternM3uAccounts(null)
      setNewCommonPatternPriority(0)
    } catch (err) {
      toast({
        title: "Error",
        description: err.response?.data?.error || "Failed to edit pattern",
        variant: "destructive"
      })
    }
  }

  const handleBulkMatchSettings = async (enabled) => {
    if (selectedChannels.size === 0) return

    try {
      const response = await regexAPI.updateBulkMatchSettings({
        channel_ids: Array.from(selectedChannels),
        settings: { match_by_tvg_id: enabled }
      })

      toast({
        title: "Success",
        description: response.data.message || `Updated settings for ${response.data.success_count} channels`
      })

      // Reload to reflect changes
      loadData()
    } catch (err) {
      toast({
        title: "Error",
        description: err.response?.data?.error || "Failed to update match settings",
        variant: "destructive"
      })
    }
  }

  const handleDeleteSingleCommonPattern = async (patternInfo) => {
    try {
      // Delete this pattern from all selected channels
      const selectedChannelIdsSet = new Set(Array.from(selectedChannels).map(id => String(id)))
      const channelsToDelete = patternInfo.channel_ids.filter(id =>
        selectedChannelIdsSet.has(String(id))
      )

      if (channelsToDelete.length === 0) {
        toast({
          title: "Error",
          description: "No selected channels have this pattern",
          variant: "destructive"
        })
        return
      }

      // Delete pattern from each channel
      let successCount = 0
      for (const channelId of channelsToDelete) {
        try {
          const channelPatterns = patterns[channelId] || patterns[String(channelId)]
          const channel = channels.find(ch => ch.id === channelId || ch.id === String(channelId))

          // Normalize to new format
          let regexPatterns = normalizePatternData(channelPatterns)

          // Remove the pattern
          const updatedPatterns = regexPatterns.filter(p => p.pattern !== patternInfo.pattern)

          if (updatedPatterns.length === 0) {
            // Delete entire channel pattern config
            await regexAPI.deletePattern(channelId)
          } else {
            // Update with remaining patterns
            await regexAPI.addPattern({
              channel_id: channelId,
              name: channel?.name || '',
              regex: updatedPatterns,
              enabled: channelPatterns?.enabled !== false
            })
          }
          successCount++
        } catch (err) {
          console.error(`Failed to delete pattern from channel ${channelId}:`, err)
        }
      }

      toast({
        title: "Success",
        description: `Deleted pattern from ${successCount} channel${successCount !== 1 ? 's' : ''}`
      })

      // Reload data and common patterns
      await loadData()
      const patternsResponse = await regexAPI.getCommonPatterns({
        channel_ids: Array.from(selectedChannels)
      })
      setCommonPatterns(patternsResponse.data.patterns || [])
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to delete pattern",
        variant: "destructive"
      })
    }
  }

  const handleDeleteSelectedCommonPatterns = async () => {
    if (selectedCommonPatterns.size === 0) {
      toast({
        title: "No Patterns Selected",
        description: "Please select at least one pattern to delete",
        variant: "destructive"
      })
      return
    }

    try {
      const patternsToDelete = commonPatterns.filter((_, idx) => selectedCommonPatterns.has(idx))
      let totalSuccess = 0

      for (const patternInfo of patternsToDelete) {
        const selectedChannelIdsSet = new Set(Array.from(selectedChannels).map(id => String(id)))
        const channelsToDelete = patternInfo.channel_ids.filter(id =>
          selectedChannelIdsSet.has(String(id))
        )

        for (const channelId of channelsToDelete) {
          try {
            const channelPatterns = patterns[channelId] || patterns[String(channelId)]
            const channel = channels.find(ch => ch.id === channelId || ch.id === String(channelId))

            let regexPatterns = normalizePatternData(channelPatterns)
            const updatedPatterns = regexPatterns.filter(p => p.pattern !== patternInfo.pattern)

            if (updatedPatterns.length === 0) {
              await regexAPI.deletePattern(channelId)
            } else {
              await regexAPI.addPattern({
                channel_id: channelId,
                name: channel?.name || '',
                regex: updatedPatterns,
                enabled: channelPatterns?.enabled !== false
              })
            }
            totalSuccess++
          } catch (err) {
            console.error(`Failed to delete pattern from channel ${channelId}:`, err)
          }
        }
      }

      toast({
        title: "Success",
        description: `Deleted ${selectedCommonPatterns.size} pattern${selectedCommonPatterns.size !== 1 ? 's' : ''} from ${totalSuccess} channel instance${totalSuccess !== 1 ? 's' : ''}`
      })

      // Clear selection and reload
      setSelectedCommonPatterns(new Set())
      await loadData()
      const patternsResponse = await regexAPI.getCommonPatterns({
        channel_ids: Array.from(selectedChannels)
      })
      setCommonPatterns(patternsResponse.data.patterns || [])
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to delete patterns",
        variant: "destructive"
      })
    }
  }

  // Mass edit handlers
  const handleMassEditPreview = async () => {
    if (!massEditFindPattern.trim()) {
      toast({
        title: "Error",
        description: "Please enter a find pattern",
        variant: "destructive"
      })
      return
    }

    try {
      setLoadingMassEditPreview(true)
      const response = await regexAPI.massEditPreview({
        channel_ids: Array.from(selectedChannels),
        find_pattern: massEditFindPattern,
        replace_pattern: massEditReplacePattern,
        use_regex: massEditUseRegex
      })

      setMassEditPreview(response.data)

      if (response.data.total_patterns_affected === 0) {
        toast({
          title: "No Changes",
          description: "No patterns will be affected by this find/replace operation",
        })
      }
    } catch (err) {
      toast({
        title: "Error",
        description: err.response?.data?.error || "Failed to preview mass edit",
        variant: "destructive"
      })
      setMassEditPreview(null)
    } finally {
      setLoadingMassEditPreview(false)
    }
  }

  const handleApplyMassEdit = async () => {
    if (!massEditFindPattern.trim()) {
      toast({
        title: "Error",
        description: "Please enter a find pattern",
        variant: "destructive"
      })
      return
    }

    try {
      const response = await regexAPI.massEdit({
        channel_ids: Array.from(selectedChannels),
        find_pattern: massEditFindPattern,
        replace_pattern: massEditReplacePattern,
        use_regex: massEditUseRegex,
        new_m3u_accounts: massEditM3uAccounts
      })

      toast({
        title: "Success",
        description: response.data.message || `Updated ${response.data.success_count} channels`,
      })

      // Reset mass edit mode
      setMassEditMode(false)
      setMassEditFindPattern('')
      setMassEditReplacePattern('')
      setMassEditUseRegex(false)
      setMassEditM3uAccounts(null)
      setMassEditPreview(null)

      // Reload data and common patterns
      await loadData()
      const patternsResponse = await regexAPI.getCommonPatterns({
        channel_ids: Array.from(selectedChannels)
      })
      setCommonPatterns(patternsResponse.data.patterns || [])
    } catch (err) {
      toast({
        title: "Error",
        description: err.response?.data?.error || "Failed to apply mass edit",
        variant: "destructive"
      })
    }
  }

  // Handler for toggling expanded row - ensures only one row is expanded at a time
  const handleToggleExpanded = (channelId) => {
    setExpandedRowId(prevId => prevId === channelId ? null : channelId)
  }

  // Filter channels based on search query and group filter
  // Use orderedChannels as the base to ensure consistent ordering between tabs
  const filteredChannels = orderedChannels.filter(channel => {
    // Apply group filter
    if (filterByGroup !== 'all' && channel.channel_group_id !== parseInt(filterByGroup)) {
      return false
    }

    // Then apply search filter
    if (!searchQuery.trim()) return true

    const query = searchQuery.toLowerCase()
    const channelName = (channel.name || '').toLowerCase()
    const channelNumber = channel.channel_number ? String(channel.channel_number) : ''
    const channelId = String(channel.id)

    // Get group name for search
    const group = groups.find(g => g.id === channel.channel_group_id)
    const groupName = group ? group.name.toLowerCase() : ''

    return channelName.includes(query) ||
      channelNumber.includes(query) ||
      channelId.includes(query) ||
      groupName.includes(query)
  })

  // Sort by group if enabled
  const displayChannels = sortByGroup
    ? [...filteredChannels].sort((a, b) => {
      const groupA = groups.find(g => g.id === a.channel_group_id)?.name || ''
      const groupB = groups.find(g => g.id === b.channel_group_id)?.name || ''
      return groupA.localeCompare(groupB) || (a.channel_number || 0) - (b.channel_number || 0)
    })
    : filteredChannels

  // Filter ordered channels - simplify since group visibility is removed
  const visibleOrderedChannels = orderedChannels

  // Calculate pagination for Regex Configuration
  const totalPages = Math.ceil(displayChannels.length / itemsPerPage)
  const startIndex = (currentPage - 1) * itemsPerPage
  const endIndex = startIndex + itemsPerPage
  const paginatedChannels = displayChannels.slice(startIndex, endIndex)

  // Calculate pagination for Channel Order
  const orderTotalPages = Math.ceil(visibleOrderedChannels.length / orderItemsPerPage)
  const orderStartIndex = (orderCurrentPage - 1) * orderItemsPerPage
  const orderEndIndex = orderStartIndex + orderItemsPerPage
  const paginatedOrderedChannels = visibleOrderedChannels.slice(orderStartIndex, orderEndIndex)


  // Reset to first page when search changes
  useEffect(() => {
    setCurrentPage(1)
  }, [searchQuery, filterByGroup, sortByGroup])


  const clearSearch = () => {
    setSearchQuery('')
  }

  // Channel ordering handlers
  const handleDragEnd = (event) => {
    const { active, over } = event

    if (over && active.id !== over.id) {
      setOrderedChannels((items) => {
        const oldIndex = items.findIndex((item) => item.id === active.id)
        const newIndex = items.findIndex((item) => item.id === over.id)
        const newOrder = arrayMove(items, oldIndex, newIndex)
        setHasOrderChanges(true)
        return newOrder
      })
    }
  }

  const handleSort = (value) => {
    setSortBy(value)

    let sorted = [...orderedChannels]

    switch (value) {
      case 'channel_number':
        sorted.sort((a, b) => {
          const numA = parseFloat(a.channel_number) || 999999
          const numB = parseFloat(b.channel_number) || 999999
          return numA - numB
        })
        break
      case 'name':
        sorted.sort((a, b) => a.name.localeCompare(b.name))
        break
      case 'id':
        sorted.sort((a, b) => a.id - b.id)
        break
      case 'custom':
        // Keep current order
        return
    }

    setOrderedChannels(sorted)
    setHasOrderChanges(JSON.stringify(sorted) !== JSON.stringify(originalChannelOrder))
  }

  const handleSaveOrder = async () => {
    try {
      setSavingOrder(true)

      // Create order array with channel IDs
      const order = orderedChannels.map(ch => ch.id)

      await channelOrderAPI.setOrder(order)

      setOriginalChannelOrder([...orderedChannels])
      setHasOrderChanges(false)

      toast({
        title: "Success",
        description: "Channel order saved successfully"
      })
    } catch (err) {
      console.error('Failed to save order:', err)
      toast({
        title: "Error",
        description: "Failed to save channel order",
        variant: "destructive"
      })
    } finally {
      setSavingOrder(false)
    }
  }

  const handleResetOrder = () => {
    setOrderedChannels([...originalChannelOrder])
    setHasOrderChanges(false)
    setSortBy('custom')
    toast({
      title: "Reset",
      description: "Changes have been discarded"
    })
  }

  const handleExportPatterns = () => {
    try {
      // Create a JSON blob with the current patterns
      const dataStr = JSON.stringify({ patterns }, null, 2)
      const dataBlob = new Blob([dataStr], { type: 'application/json' })

      // Create download link
      const url = URL.createObjectURL(dataBlob)
      const link = document.createElement('a')
      link.href = url
      link.download = `channel_regex_patterns_${new Date().toISOString().split('T')[0]}.json`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)

      toast({
        title: "Success",
        description: "Regex patterns exported successfully"
      })
    } catch (err) {
      console.error('Export error:', err)
      toast({
        title: "Error",
        description: "Failed to export patterns",
        variant: "destructive"
      })
    }
  }

  const handleImportPatterns = (event) => {
    const file = event.target.files[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = async (e) => {
      try {
        const importedData = JSON.parse(e.target.result)

        // Validate the imported data structure
        if (!importedData.patterns || typeof importedData.patterns !== 'object') {
          throw new Error('Invalid file format: missing patterns object')
        }

        // Import the patterns using the API
        await regexAPI.importPatterns(importedData)

        toast({
          title: "Success",
          description: `Imported ${Object.keys(importedData.patterns).length} channel patterns`
        })

        // Reload data to show imported patterns
        await loadData()
      } catch (err) {
        console.error('Import error:', err)
        toast({
          title: "Error",
          description: err.response?.data?.error || "Failed to import patterns",
          variant: "destructive"
        })
      }
    }

    reader.onerror = () => {
      toast({
        title: "Error",
        description: "Failed to read file",
        variant: "destructive"
      })
    }

    reader.readAsText(file)

    // Reset the input so the same file can be imported again
    event.target.value = ''
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <TooltipProvider>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Channel Configuration</h1>
          <p className="text-muted-foreground">
            View and manage channel regex patterns, settings, and ordering
          </p>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="regex">Regex Configuration</TabsTrigger>
            <TabsTrigger value="ordering">Channel Order</TabsTrigger>
          </TabsList>

          <TabsContent value="regex" className="space-y-6">
            {/* Search Bar and Export/Import Buttons */}
            <div className="flex items-center gap-2">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search channels by name, number, or ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-10"
                />
                {searchQuery && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="absolute right-1 top-1/2 transform -translate-y-1/2 h-7 w-7 p-0"
                    onClick={clearSearch}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
              {searchQuery && (
                <Badge variant="secondary">
                  {filteredChannels.length} of {channels.length} channels
                </Badge>
              )}

              {/* Profile Filter Info */}
              {profileFilterActive && profileFilterInfo && !searchQuery && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="outline" className="gap-1 cursor-help">
                      <Info className="h-3 w-3" />
                      {profileFilterInfo.channelCount} channels
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p className="font-semibold mb-1">Profile Filter Active</p>
                    <p className="text-sm">{profileFilterInfo.message}</p>
                    {profileFilterInfo.isEmpty && (
                      <p className="text-sm text-muted-foreground mt-1">
                        Go to the Profiles tab to refresh profile data.
                      </p>
                    )}
                  </TooltipContent>
                </Tooltip>
              )}

              {/* Export/Import Buttons */}
              <div className="flex items-center gap-2 ml-auto">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleExportPatterns}
                >
                  <Download className="h-4 w-4 mr-2" />
                  Export Regex
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => document.getElementById('import-file-input').click()}
                >
                  <Upload className="h-4 w-4 mr-2" />
                  Import Regex
                </Button>
                <input
                  id="import-file-input"
                  type="file"
                  accept=".json"
                  onChange={handleImportPatterns}
                  style={{ display: 'none' }}
                />
              </div>
            </div>

            <div className="space-y-4">
              {/* Filter and Action Bar */}
              <Card>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-4 flex-1">
                      {/* Group Filter */}
                      <div className="flex items-center gap-2">
                        <Label htmlFor="group-filter" className="text-sm whitespace-nowrap">Filter Group:</Label>
                        <Select value={filterByGroup} onValueChange={setFilterByGroup}>
                          <SelectTrigger id="group-filter" className="h-9 w-[200px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all">All Groups</SelectItem>
                            {groups.map(group => (
                              <SelectItem key={group.id} value={String(group.id)}>
                                {group.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Sort by Group */}
                      <div className="flex items-center gap-2">
                        <Checkbox
                          id="sort-by-group"
                          checked={sortByGroup}
                          onCheckedChange={setSortByGroup}
                        />
                        <Label htmlFor="sort-by-group" className="text-sm whitespace-nowrap cursor-pointer">
                          Sort by Group
                        </Label>
                      </div>
                    </div>

                    {/* Selection Actions */}
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">
                        {selectedChannels.size} selected
                      </Badge>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setBulkDialogOpen(true)}
                            disabled={selectedChannels.size === 0}
                          >
                            <Plus className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>Add Regex to Selected</p>
                        </TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={handleBulkHealthCheck}
                            disabled={selectedChannels.size === 0 || bulkCheckingChannels}
                            className="text-blue-600 dark:text-green-500 border-blue-600 dark:border-green-500 hover:bg-blue-50 dark:hover:bg-green-950"
                          >
                            {bulkCheckingChannels ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Activity className="h-4 w-4" />
                            )}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>Health Check Selected</p>
                        </TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={handleOpenEditCommon}
                            disabled={selectedChannels.size === 0}
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>Edit Common Regex</p>
                        </TooltipContent>
                      </Tooltip>

                      <div className="mx-2 h-6 w-px bg-border" />

                      {/* Bulk Match Settings */}
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="outline" size="sm" disabled={selectedChannels.size === 0}>
                            <Activity className="h-4 w-4 mr-2" />
                            Match Settings
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent>
                          <DropdownMenuLabel>Batch Actions</DropdownMenuLabel>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onClick={() => handleBulkMatchSettings(true)}>
                            Enable Match by TVG-ID
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleBulkMatchSettings(false)}>
                            Disable Match by TVG-ID
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>

                      <div className="mx-2 h-6 w-px bg-border" />

                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-medium hidden sm:inline-block">Assign Profile:</span>
                        <Select
                          value={assignProfileId}
                          onValueChange={(value) => {
                            setAssignProfileId(value)
                            handleBatchAssignProfile(value)
                          }}
                          disabled={selectedChannels.size === 0}
                        >
                          <SelectTrigger className="w-[180px] h-8">
                            <SelectValue placeholder="Select Profile" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">None (Clear)</SelectItem>
                            {profiles.map(profile => (
                              <SelectItem key={profile.id} value={profile.id.toString()}>
                                {profile.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => setDeleteDialogOpen(true)}
                            disabled={selectedChannels.size === 0}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>Delete Selected Regex</p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Pagination info and controls at top */}
              {displayChannels.length > 0 && (
                <div className="flex items-center justify-between">
                  <div className="text-sm text-muted-foreground">
                    Showing {startIndex + 1}-{Math.min(endIndex, displayChannels.length)} of {displayChannels.length} channels
                  </div>
                  <div className="flex items-center gap-2">
                    <Label htmlFor="items-per-page" className="text-sm whitespace-nowrap">Items per page:</Label>
                    <Select
                      value={itemsPerPage.toString()}
                      onValueChange={(value) => {
                        setItemsPerPage(Number(value))
                        setCurrentPage(1)
                      }}
                    >
                      <SelectTrigger className="h-9 w-[100px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="10">10</SelectItem>
                        <SelectItem value="20">20</SelectItem>
                        <SelectItem value="50">50</SelectItem>
                        <SelectItem value="100">100</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}

              {displayChannels.length === 0 ? (
                <Card>
                  <CardContent className="p-8 text-center">
                    <p className="text-muted-foreground">
                      {searchQuery ? `No channels found matching "${searchQuery}"` : 'No channels available'}
                    </p>
                    {searchQuery && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-4"
                        onClick={clearSearch}
                      >
                        Clear search
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ) : (
                <>
                  {/* Table Header */}
                  <Card>
                    <CardContent className="p-0">
                      <div className="border-b bg-muted/50">
                        <div className={`gap-4 p-4 font-medium text-sm`} style={{ gridTemplateColumns: REGEX_TABLE_GRID_COLS, display: 'grid' }}>
                          <div className="flex items-center justify-center">
                            <Checkbox
                              checked={filteredChannels.length > 0 && filteredChannels.every(ch => selectedChannels.has(ch.id))}
                              onCheckedChange={(checked) => {
                                const newSet = new Set(selectedChannels)
                                filteredChannels.forEach(ch => {
                                  if (checked) {
                                    newSet.add(ch.id)
                                  } else {
                                    newSet.delete(ch.id)
                                  }
                                })
                                setSelectedChannels(newSet)
                              }}
                            />
                          </div>
                          <div>#</div>
                          <div>Logo</div>
                          <div>Channel Name</div>
                          <div>Channel Group</div>
                          <div>Profile</div>
                          <div>Regex Patterns</div>
                          <div>Actions</div>
                        </div>
                      </div>

                      {/* Table Rows */}
                      <div className="divide-y">
                        {paginatedChannels.map(channel => {
                          const group = groups.find(g => g.id === channel.channel_group_id)


                          return (
                            <RegexTableRow
                              key={channel.id}
                              channel={channel}
                              group={group}
                              groups={groups}
                              profiles={profiles}
                              patterns={patterns}
                              selectedChannels={selectedChannels}
                              onToggleChannel={handleToggleChannel}
                              onEditRegex={handleEditRegex}
                              onDeletePattern={handleDeletePattern}
                              expandedRowId={expandedRowId}
                              onToggleExpanded={handleToggleExpanded}
                              onCheckChannel={handleCheckChannel}
                              checkingChannel={checkingChannel}
                              m3uAccounts={m3uAccounts}
                              onUpdateMatchSettings={handleUpdateMatchSettings}
                              onPreviewMatch={handlePreviewMatch}
                            />
                          )
                        })}
                      </div>
                    </CardContent>
                  </Card>
                </>
              )}

              {/* Pagination controls at bottom */}
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2 pt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(1)}
                    disabled={currentPage === 1}
                  >
                    First
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(currentPage - 1)}
                    disabled={currentPage === 1}
                  >
                    Previous
                  </Button>
                  <div className="flex items-center gap-1">
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      // Show pages around current page
                      let pageNum
                      if (totalPages <= 5) {
                        pageNum = i + 1
                      } else if (currentPage <= 3) {
                        pageNum = i + 1
                      } else if (currentPage >= totalPages - 2) {
                        pageNum = totalPages - 4 + i
                      } else {
                        pageNum = currentPage - 2 + i
                      }

                      return (
                        <Button
                          key={pageNum}
                          variant={currentPage === pageNum ? "default" : "outline"}
                          size="sm"
                          onClick={() => setCurrentPage(pageNum)}
                          className="w-9"
                        >
                          {pageNum}
                        </Button>
                      )
                    })}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(currentPage + 1)}
                    disabled={currentPage === totalPages}
                  >
                    Next
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(totalPages)}
                    disabled={currentPage === totalPages}
                  >
                    Last
                  </Button>
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="ordering" className="space-y-6">
            {hasOrderChanges && (
              <Alert>
                <AlertDescription className="flex items-center justify-between">
                  <span>You have unsaved changes</span>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={handleResetOrder}>
                      <RotateCcw className="h-4 w-4 mr-2" />
                      Reset
                    </Button>
                    <Button size="sm" onClick={handleSaveOrder} disabled={savingOrder}>
                      {savingOrder && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      <Save className="h-4 w-4 mr-2" />
                      Save Changes
                    </Button>
                  </div>
                </AlertDescription>
              </Alert>
            )}

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Channel List</CardTitle>
                    <CardDescription>
                      {visibleOrderedChannels.length} visible channels ({orderedChannels.length} total) - Drag and drop within the current page to reorder
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
                    <Select value={sortBy} onValueChange={handleSort}>
                      <SelectTrigger className="w-[200px]">
                        <SelectValue placeholder="Sort by..." />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="custom">Custom Order</SelectItem>
                        <SelectItem value="channel_number">Channel Number</SelectItem>
                        <SelectItem value="name">Name (A-Z)</SelectItem>
                        <SelectItem value="id">ID</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Pagination info and controls at top */}
                {visibleOrderedChannels.length > 0 && (
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-muted-foreground">
                      Showing {orderStartIndex + 1}-{Math.min(orderEndIndex, visibleOrderedChannels.length)} of {visibleOrderedChannels.length} channels
                    </div>
                    <div className="flex items-center gap-2">
                      <Label htmlFor="order-items-per-page" className="text-sm whitespace-nowrap">Items per page:</Label>
                      <Select
                        value={orderItemsPerPage.toString()}
                        onValueChange={(value) => {
                          setOrderItemsPerPage(Number(value))
                          setOrderCurrentPage(1)
                        }}
                      >
                        <SelectTrigger className="h-9 w-[100px]" id="order-items-per-page">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="10">10</SelectItem>
                          <SelectItem value="20">20</SelectItem>
                          <SelectItem value="50">50</SelectItem>
                          <SelectItem value="100">100</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                )}

                {visibleOrderedChannels.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No channels available
                  </div>
                ) : (
                  <>
                    <DndContext
                      sensors={sensors}
                      collisionDetection={closestCenter}
                      onDragEnd={handleDragEnd}
                    >
                      <SortableContext
                        items={paginatedOrderedChannels.map(ch => ch.id)}
                        strategy={verticalListSortingStrategy}
                      >
                        <div className="space-y-2">
                          {paginatedOrderedChannels.map((channel) => (
                            <SortableChannelItem key={channel.id} channel={channel} />
                          ))}
                        </div>
                      </SortableContext>
                    </DndContext>

                    {/* Pagination controls at bottom */}
                    {orderTotalPages > 1 && (
                      <div className="flex items-center justify-center gap-2 pt-4">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setOrderCurrentPage(1)}
                          disabled={orderCurrentPage === 1}
                        >
                          First
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setOrderCurrentPage(orderCurrentPage - 1)}
                          disabled={orderCurrentPage === 1}
                        >
                          Previous
                        </Button>
                        <div className="flex items-center gap-1">
                          {Array.from({ length: Math.min(5, orderTotalPages) }, (_, i) => {
                            let pageNum
                            if (orderTotalPages <= 5) {
                              pageNum = i + 1
                            } else if (orderCurrentPage <= 3) {
                              pageNum = i + 1
                            } else if (orderCurrentPage >= orderTotalPages - 2) {
                              pageNum = orderTotalPages - 4 + i
                            } else {
                              pageNum = orderCurrentPage - 2 + i
                            }

                            return (
                              <Button
                                key={pageNum}
                                variant={orderCurrentPage === pageNum ? "default" : "outline"}
                                size="sm"
                                onClick={() => setOrderCurrentPage(pageNum)}
                                className="w-9"
                              >
                                {pageNum}
                              </Button>
                            )
                          })}
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setOrderCurrentPage(orderCurrentPage + 1)}
                          disabled={orderCurrentPage === orderTotalPages}
                        >
                          Next
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setOrderCurrentPage(orderTotalPages)}
                          disabled={orderCurrentPage === orderTotalPages}
                        >
                          Last
                        </Button>
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>

            {hasOrderChanges && (
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={handleResetOrder}>
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Reset Changes
                </Button>
                <Button onClick={handleSaveOrder} disabled={savingOrder} size="lg">
                  {savingOrder && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  <Save className="h-4 w-4 mr-2" />
                  Save Order
                </Button>
              </div>
            )}
          </TabsContent>
        </Tabs>

        {/* Regex Pattern Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="sm:max-w-[600px]">
            <DialogHeader>
              <DialogTitle>
                {editingPatternIndex !== null ? 'Edit' : 'Add'} Regex Pattern
              </DialogTitle>
              <DialogDescription>
                Enter a regex pattern to match streams for this channel. Use CHANNEL_NAME to insert the channel name.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="pattern">Regex Pattern</Label>
                <Input
                  id="pattern"
                  placeholder="e.g., .*ESPN.*|.*Sports.*"
                  value={newPattern}
                  onChange={(e) => setNewPattern(e.target.value)}
                  className="font-mono"
                />
              </div>

              {/* M3U Account Selection */}
              <div className="space-y-2">
                <Label>Apply to M3U Accounts (Sources)</Label>
                <div className="text-xs text-muted-foreground mb-2">
                  Select which M3U account sources this regex should match streams from. Leave empty for all sources.
                </div>
                <div className="border rounded-md p-3 max-h-48 overflow-y-auto space-y-2">
                  {m3uAccounts.length === 0 ? (
                    <div className="text-sm text-muted-foreground italic">No M3U accounts available</div>
                  ) : (
                    <>
                      <div className="flex items-center space-x-2 pb-2 border-b">
                        <Checkbox
                          id="select-all-m3u-accounts"
                          checked={selectedM3uAccounts.length === 0}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setSelectedM3uAccounts([])  // Empty = all M3U accounts
                            } else {
                              // When unchecking "All", select first M3U account if available
                              if (m3uAccounts.length > 0) {
                                setSelectedM3uAccounts([m3uAccounts[0].id])
                              }
                            }
                          }}
                        />
                        <label htmlFor="select-all-m3u-accounts" className="text-sm font-medium cursor-pointer">
                          All M3U Accounts
                        </label>
                      </div>
                      {m3uAccounts.map(account => (
                        <div key={account.id} className="flex items-center space-x-2">
                          <Checkbox
                            id={`m3u-account-${account.id}`}
                            checked={selectedM3uAccounts.includes(account.id)}
                            onCheckedChange={(checked) => {
                              if (checked) {
                                setSelectedM3uAccounts(prev =>
                                  prev.length === 0 ? [account.id] : [...prev, account.id]
                                )
                              } else {
                                setSelectedM3uAccounts(selectedM3uAccounts.filter(id => id !== account.id))
                              }
                            }}
                          />
                          <label htmlFor={`m3u-account-${account.id}`} className={`text-sm cursor-pointer ${selectedM3uAccounts.length === 0 ? 'text-muted-foreground' : ''}`}>
                            {account.name}
                          </label>
                        </div>
                      ))}
                    </>
                  )}
                </div>
              </div>

              {/* Priority Input */}
              <div className="space-y-2">
                <Label htmlFor="pattern-priority">Priority</Label>
                <div className="text-xs text-muted-foreground mb-2">
                  Among streams from the same playlist, higher priority patterns score better (0 = default priority).
                </div>
                <Input
                  id="pattern-priority"
                  type="number"
                  min="0"
                  max="100"
                  value={patternPriority}
                  onChange={(e) => setPatternPriority(parseInt(e.target.value) || 0)}
                  className="w-32"
                />
              </div>

              {/* Live Test Results */}
              <MatchResultsList
                results={testResults}
                loading={testingPattern}
                onLoadMore={() => handleTestPattern(testResults?.mode || 'regex_only', true, testResults?.channelId)}
                maxHeight="max-h-60"
              />
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={handleCloseDialog}>
                Cancel
              </Button>
              <Button onClick={handleSavePattern} disabled={!newPattern.trim()}>
                {editingPatternIndex !== null ? 'Update' : 'Add'} Pattern
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Bulk Pattern Assignment Dialog */}
        <Dialog open={bulkDialogOpen} onOpenChange={setBulkDialogOpen}>
          <DialogContent className="sm:max-w-[600px]">
            <DialogHeader>
              <DialogTitle>Add Regex Pattern to Multiple Channels</DialogTitle>
              <DialogDescription>
                This pattern will be added to {selectedChannels.size} selected channel{selectedChannels.size !== 1 ? 's' : ''}. Use CHANNEL_NAME to insert each channel's name into the pattern.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="bulk-pattern">Regex Pattern</Label>
                <Input
                  id="bulk-pattern"
                  placeholder="e.g., .*CHANNEL_NAME.*"
                  value={bulkPattern}
                  onChange={(e) => setBulkPattern(e.target.value)}
                  className="font-mono"
                />
                <p className="text-xs text-muted-foreground">
                  Use CHANNEL_NAME to create a pattern that works for all selected channels
                </p>
              </div>

              {/* M3U Account Selection for Bulk */}
              <div className="space-y-2">
                <Label>Apply to M3U Accounts (Sources)</Label>
                <div className="text-xs text-muted-foreground mb-2">
                  Select which M3U account sources this regex should match streams from. Leave empty for all sources.
                </div>
                <div className="border rounded-md p-3 max-h-48 overflow-y-auto space-y-2">
                  {m3uAccounts.length === 0 ? (
                    <div className="text-sm text-muted-foreground italic">No M3U accounts available</div>
                  ) : (
                    <>
                      <div className="flex items-center space-x-2 pb-2 border-b">
                        <Checkbox
                          id="bulk-select-all-m3u-accounts"
                          checked={bulkSelectedM3uAccounts.length === 0}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setBulkSelectedM3uAccounts([])  // Empty = all M3U accounts
                            } else {
                              // When unchecking "All", select first M3U account if available
                              if (m3uAccounts.length > 0) {
                                setBulkSelectedM3uAccounts([m3uAccounts[0].id])
                              }
                            }
                          }}
                        />
                        <label htmlFor="bulk-select-all-m3u-accounts" className="text-sm font-medium cursor-pointer">
                          All M3U Accounts
                        </label>
                      </div>
                      {m3uAccounts.map(account => (
                        <div key={account.id} className="flex items-center space-x-2">
                          <Checkbox
                            id={`bulk-m3u-account-${account.id}`}
                            checked={bulkSelectedM3uAccounts.includes(account.id)}
                            onCheckedChange={(checked) => {
                              if (checked) {
                                setBulkSelectedM3uAccounts(prev =>
                                  prev.length === 0 ? [account.id] : [...prev, account.id]
                                )
                              } else {
                                setBulkSelectedM3uAccounts(bulkSelectedM3uAccounts.filter(id => id !== account.id))
                              }
                            }}
                          />
                          <label htmlFor={`bulk-m3u-account-${account.id}`} className={`text-sm cursor-pointer ${bulkSelectedM3uAccounts.length === 0 ? 'text-muted-foreground' : ''}`}>
                            {account.name}
                          </label>
                        </div>
                      ))}
                    </>
                  )}
                </div>
              </div>

              <div className="border rounded-md p-3 bg-muted/50">
                <div className="text-sm font-medium mb-2">Example:</div>
                <div className="text-xs text-muted-foreground space-y-1">
                  <div>Pattern: <code className="bg-background px-1 rounded">.*CHANNEL_NAME.*</code></div>
                  <div>For channel "ESPN", matches: <code className="bg-background px-1 rounded">.*ESPN.*</code></div>
                  <div>For channel "CNN", matches: <code className="bg-background px-1 rounded">.*CNN.*</code></div>
                </div>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => {
                setBulkDialogOpen(false)
                setBulkPattern('')
                setBulkSelectedM3uAccounts([])  // Reset bulk M3U account selection
              }}>
                Cancel
              </Button>
              <Button onClick={handleBulkAddPattern} disabled={!bulkPattern.trim()}>
                Add to {selectedChannels.size} Channel{selectedChannels.size !== 1 ? 's' : ''}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete Regex Patterns</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to delete all regex patterns from {selectedChannels.size} selected channel{selectedChannels.size !== 1 ? 's' : ''}? This action cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleBulkDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Edit Common Regex Dialog */}
        <Dialog open={editCommonDialogOpen} onOpenChange={(open) => {
          setEditCommonDialogOpen(open)
          if (!open) {
            // Reset state when closing
            setSelectedCommonPatterns(new Set())
            setCommonPatternsSearch('')
            setNewCommonPatternPriority(0)
          }
        }}>
          <DialogContent className="sm:max-w-[90vw] lg:max-w-[1200px] max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Edit Common Regex Patterns</DialogTitle>
              <DialogDescription>
                These are the regex patterns shared across the {selectedChannels.size} selected channel{selectedChannels.size !== 1 ? 's' : ''}. Editing or deleting a pattern will affect it ONLY in the selected channels.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              {/* Search bar */}
              {commonPatterns.length > 0 && (
                <div className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search patterns..."
                      value={commonPatternsSearch}
                      onChange={(e) => setCommonPatternsSearch(e.target.value)}
                      className="pl-9"
                    />
                  </div>
                  {selectedCommonPatterns.size > 0 && (
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setMassEditMode(!massEditMode)}
                      >
                        <Edit className="h-4 w-4 mr-2" />
                        Edit Selected ({selectedCommonPatterns.size})
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={handleDeleteSelectedCommonPatterns}
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        Delete Selected ({selectedCommonPatterns.size})
                      </Button>
                    </div>
                  )}
                </div>
              )}

              {/* Mass Edit Section */}
              {massEditMode && selectedCommonPatterns.size > 0 && (
                <Card className="border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">Mass Find & Replace</CardTitle>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setMassEditMode(false)
                          setMassEditFindPattern('')
                          setMassEditReplacePattern('')
                          setMassEditUseRegex(false)
                          setMassEditM3uAccounts(null)
                          setMassEditPreview(null)
                        }}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Find/Replace Inputs */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="mass-edit-find">Find Pattern</Label>
                        <Input
                          id="mass-edit-find"
                          value={massEditFindPattern}
                          onChange={(e) => setMassEditFindPattern(e.target.value)}
                          placeholder="Enter text or regex to find"
                          className="font-mono"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="mass-edit-replace">Replace With</Label>
                        <Input
                          id="mass-edit-replace"
                          value={massEditReplacePattern}
                          onChange={(e) => setMassEditReplacePattern(e.target.value)}
                          placeholder="Enter replacement text"
                          className="font-mono"
                        />
                      </div>
                    </div>

                    {/* Options */}
                    <div className="space-y-3">
                      <div className="flex items-center gap-2">
                        <Checkbox
                          id="mass-edit-use-regex"
                          checked={massEditUseRegex}
                          onCheckedChange={setMassEditUseRegex}
                        />
                        <label htmlFor="mass-edit-use-regex" className="text-sm cursor-pointer">
                          Use Regular Expression
                        </label>
                      </div>
                      {massEditUseRegex && (
                        <Alert className="bg-blue-50 dark:bg-blue-950/50 border-blue-200 dark:border-blue-800">
                          <Info className="h-4 w-4" />
                          <AlertDescription className="text-xs">
                            <strong>Regex replacement supports backreferences:</strong>
                            <ul className="list-disc list-inside mt-1 space-y-0.5">
                              <li><code className="bg-background px-1 rounded">{`\\g<0>`}</code> - Full match (equivalent to $0)</li>
                              <li><code className="bg-background px-1 rounded">{`\\1, \\2, ...`}</code> - Capture groups</li>
                              <li><code className="bg-background px-1 rounded">{`\\g<name>`}</code> - Named groups</li>
                            </ul>
                            <div className="mt-2">
                              <strong>Example:</strong> Find: <code className="bg-background px-1 rounded">{`(\\w+)_HD`}</code>, Replace: <code className="bg-background px-1 rounded">{`\\1_4K`}</code> → Changes ESPN_HD to ESPN_4K
                            </div>
                          </AlertDescription>
                        </Alert>
                      )}
                    </div>

                    {/* M3U Account Selection */}
                    <div className="space-y-2">
                      <Label>Update Playlists (Optional)</Label>
                      <div className="space-y-2 border rounded-lg p-3">
                        <div className="flex items-center gap-2">
                          <Checkbox
                            id="mass-edit-keep-playlists"
                            checked={massEditM3uAccounts === null}
                            onCheckedChange={(checked) => {
                              setMassEditM3uAccounts(checked ? null : [])
                            }}
                          />
                          <label htmlFor="mass-edit-keep-playlists" className="text-sm cursor-pointer">
                            Keep Existing Playlists
                          </label>
                        </div>

                        {massEditM3uAccounts !== null && (
                          <>
                            <Separator />
                            <div className="flex items-center gap-2">
                              <Checkbox
                                id="mass-edit-all-playlists"
                                checked={massEditM3uAccounts.length === 0}
                                onCheckedChange={(checked) => {
                                  if (checked) {
                                    setMassEditM3uAccounts([])
                                  } else {
                                    // Select first available playlist when unchecking "All"
                                    const availablePlaylists = m3uAccounts.filter(acc => acc.id !== 'custom')
                                    setMassEditM3uAccounts(availablePlaylists.length > 0 ? [availablePlaylists[0].id] : [])
                                  }
                                }}
                              />
                              <label htmlFor="mass-edit-all-playlists" className="text-sm cursor-pointer">
                                All Playlists
                              </label>
                            </div>

                            {m3uAccounts.filter(acc => acc.id !== 'custom').map(account => (
                              <div key={account.id} className="flex items-center gap-2">
                                <Checkbox
                                  id={`mass-edit-playlist-${account.id}`}
                                  checked={massEditM3uAccounts.length > 0 && massEditM3uAccounts.includes(account.id)}
                                  onCheckedChange={(checked) => {
                                    if (checked) {
                                      setMassEditM3uAccounts(prev => [...prev, account.id])
                                    } else {
                                      setMassEditM3uAccounts(prev => prev.filter(id => id !== account.id))
                                    }
                                  }}
                                />
                                <label htmlFor={`mass-edit-playlist-${account.id}`} className="text-sm cursor-pointer">
                                  {account.name}
                                </label>
                              </div>
                            ))}
                          </>
                        )}
                      </div>
                    </div>

                    {/* Preview Button */}
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        onClick={handleMassEditPreview}
                        disabled={!massEditFindPattern.trim() || loadingMassEditPreview}
                      >
                        {loadingMassEditPreview ? (
                          <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            Loading Preview...
                          </>
                        ) : (
                          <>
                            <Eye className="h-4 w-4 mr-2" />
                            Preview Changes
                          </>
                        )}
                      </Button>
                      <Button
                        onClick={handleApplyMassEdit}
                        disabled={!massEditFindPattern.trim() || !massEditPreview || massEditPreview.total_patterns_affected === 0}
                      >
                        <Save className="h-4 w-4 mr-2" />
                        Apply Changes
                      </Button>
                    </div>

                    {/* Preview Results */}
                    {massEditPreview && (
                      <div className="space-y-3 border rounded-lg p-4 bg-background">
                        <div className="flex items-center justify-between">
                          <h4 className="font-semibold">Preview Results</h4>
                          <div className="text-sm text-muted-foreground">
                            {massEditPreview.total_patterns_affected} pattern{massEditPreview.total_patterns_affected !== 1 ? 's' : ''} in {massEditPreview.total_channels_affected} channel{massEditPreview.total_channels_affected !== 1 ? 's' : ''}
                          </div>
                        </div>

                        <div className="max-h-[300px] overflow-y-auto space-y-2">
                          {massEditPreview.affected_channels.map(channelInfo => (
                            <div key={channelInfo.channel_id} className="border rounded p-3 space-y-2">
                              <div className="font-medium text-sm">
                                {channelInfo.channel_name}
                                <span className="text-muted-foreground ml-2">({channelInfo.total_affected} pattern{channelInfo.total_affected !== 1 ? 's' : ''})</span>
                              </div>
                              <div className="space-y-1">
                                {channelInfo.affected_patterns.map((patternChange, idx) => (
                                  <div key={idx} className="text-xs font-mono bg-muted p-2 rounded space-y-1">
                                    <div className="flex items-center gap-2">
                                      <span className="text-red-600 dark:text-red-400 line-through">{patternChange.old_pattern}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                      <ArrowRight className="h-3 w-3" />
                                      <span className="text-green-600 dark:text-green-400">{patternChange.new_pattern}</span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              <div className="max-h-[500px] overflow-y-auto">
                {loadingCommonPatterns ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : commonPatterns.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No common patterns found across selected channels
                  </div>
                ) : (
                  <>
                    {/* Select All Checkbox */}
                    {(() => {
                      const filterPattern = (p) =>
                        p.pattern.toLowerCase().includes(commonPatternsSearch.toLowerCase())

                      const filteredData = commonPatterns
                        .map((p, idx) => ({ pattern: p, index: idx }))
                        .filter(({ pattern }) => filterPattern(pattern))

                      const filteredPatterns = filteredData.map(({ pattern }) => pattern)
                      const filteredIndices = filteredData.map(({ index }) => index)

                      const allFilteredSelected = filteredIndices.length > 0 &&
                        filteredIndices.every(idx => selectedCommonPatterns.has(idx))

                      return filteredPatterns.length > 0 && (
                        <>
                          <div className="flex items-center space-x-2 pb-3 border-b mb-3">
                            <Checkbox
                              id="select-all-common-patterns"
                              checked={allFilteredSelected}
                              onCheckedChange={(checked) => {
                                if (checked) {
                                  // Select all filtered patterns
                                  setSelectedCommonPatterns(new Set(filteredIndices))
                                } else {
                                  // Deselect all
                                  setSelectedCommonPatterns(new Set())
                                }
                              }}
                            />
                            <label htmlFor="select-all-common-patterns" className="text-sm font-medium cursor-pointer">
                              Select All {commonPatternsSearch ? `(${filteredPatterns.length} filtered)` : `(${commonPatterns.length})`}
                            </label>
                          </div>

                          <div className="space-y-3">
                            {filteredData.map(({ pattern: patternInfo, index: actualIndex }) => {
                              return (
                                <div key={actualIndex} className="border rounded-lg p-4 space-y-3">
                                  {editingCommonPattern && editingCommonPattern.pattern === patternInfo.pattern ? (
                                    // Edit mode
                                    <div className="space-y-3">
                                      <div className="space-y-2">
                                        <Label>New Pattern</Label>
                                        <Input
                                          value={newCommonPattern}
                                          onChange={(e) => setNewCommonPattern(e.target.value)}
                                          className="font-mono"
                                          placeholder="Enter new pattern"
                                        />
                                      </div>

                                      {/* M3U Account filter */}
                                      <div className="space-y-2">
                                        <Label>Playlists (M3U Accounts)</Label>
                                        <div className="space-y-2 border rounded-lg p-3">
                                          <div className="flex items-center gap-2">
                                            <Checkbox
                                              id="all-playlists-edit"
                                              checked={newCommonPatternM3uAccounts === null}
                                              onCheckedChange={(checked) => {
                                                if (checked) {
                                                  setNewCommonPatternM3uAccounts(null)
                                                } else {
                                                  // When unchecking "All", select first M3U account if available
                                                  const availableAccounts = m3uAccounts.filter(acc => acc.id !== 'custom')
                                                  if (availableAccounts.length > 0) {
                                                    setNewCommonPatternM3uAccounts([availableAccounts[0].id])
                                                  }
                                                }
                                              }}
                                            />
                                            <label
                                              htmlFor="all-playlists-edit"
                                              className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                                            >
                                              All Playlists
                                            </label>
                                          </div>

                                          {m3uAccounts.filter(acc => acc.id !== 'custom').map(account => (
                                            <div key={account.id} className="flex items-center gap-2">
                                              <Checkbox
                                                id={`playlist-edit-${account.id}`}
                                                checked={newCommonPatternM3uAccounts !== null && newCommonPatternM3uAccounts.includes(account.id)}
                                                onCheckedChange={(checked) => {
                                                  if (checked) {
                                                    setNewCommonPatternM3uAccounts(prev =>
                                                      prev === null ? [account.id] : [...prev, account.id]
                                                    )
                                                  } else {
                                                    setNewCommonPatternM3uAccounts(prev => {
                                                      if (prev === null) return []
                                                      const updated = prev.filter(id => id !== account.id)
                                                      // Return null when all unchecked to mean "all playlists" (backend convention)
                                                      return updated.length === 0 ? null : updated
                                                    })
                                                  }
                                                }}
                                              />
                                              <label
                                                htmlFor={`playlist-edit-${account.id}`}
                                                className={`text-sm leading-none cursor-pointer ${newCommonPatternM3uAccounts === null ? 'text-muted-foreground' : ''}`}
                                              >
                                                {account.name}
                                              </label>
                                            </div>
                                          ))}
                                        </div>
                                      </div>

                                      {/* Priority Input */}
                                      <div className="space-y-2">
                                        <Label htmlFor="common-pattern-priority">Priority</Label>
                                        <div className="text-xs text-muted-foreground mb-2">
                                          Among streams from the same playlist, higher priority patterns score better (0 = default).
                                        </div>
                                        <Input
                                          id="common-pattern-priority"
                                          type="number"
                                          min="0"
                                          max="100"
                                          value={newCommonPatternPriority}
                                          onChange={(e) => setNewCommonPatternPriority(parseInt(e.target.value) || 0)}
                                          className="w-32"
                                        />
                                      </div>

                                      <div className="flex gap-2 justify-end">
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          onClick={() => {
                                            setEditingCommonPattern(null)
                                            setNewCommonPattern('')
                                            setNewCommonPatternM3uAccounts(null)
                                            setNewCommonPatternPriority(0)
                                          }}
                                        >
                                          Cancel
                                        </Button>
                                        <Button
                                          size="sm"
                                          onClick={handleEditCommonPattern}
                                          disabled={!newCommonPattern.trim()}
                                        >
                                          Save
                                        </Button>
                                      </div>
                                    </div>
                                  ) : (
                                    // View mode
                                    <>
                                      <div className="flex items-start gap-3">
                                        <Checkbox
                                          checked={selectedCommonPatterns.has(actualIndex)}
                                          onCheckedChange={(checked) => {
                                            setSelectedCommonPatterns(prev => {
                                              const newSet = new Set(prev)
                                              if (checked) {
                                                newSet.add(actualIndex)
                                              } else {
                                                newSet.delete(actualIndex)
                                              }
                                              return newSet
                                            })
                                          }}
                                        />
                                        <div className="flex-1 min-w-0">
                                          <code className="text-sm break-all block">{patternInfo.pattern}</code>
                                          <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                                            <span>Used in {patternInfo.count} of {selectedChannels.size} channels ({patternInfo.percentage}%)</span>
                                          </div>
                                        </div>
                                        <div className="flex gap-1">
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => {
                                              setEditingCommonPattern(patternInfo)
                                              setNewCommonPattern(patternInfo.pattern)
                                            }}
                                          >
                                            <Edit2 className="h-4 w-4" />
                                          </Button>
                                          <Button
                                            size="sm"
                                            variant="destructive"
                                            onClick={() => handleDeleteSingleCommonPattern(patternInfo)}
                                          >
                                            <Trash2 className="h-4 w-4" />
                                          </Button>
                                        </div>
                                      </div>
                                    </>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        </>
                      )
                    })()}

                    {commonPatterns.filter(p =>
                      p.pattern.toLowerCase().includes(commonPatternsSearch.toLowerCase())
                    ).length === 0 && commonPatternsSearch && (
                        <div className="text-center py-8 text-muted-foreground">
                          No patterns match your search
                        </div>
                      )}
                  </>
                )}
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => {
                setEditCommonDialogOpen(false)
                setEditingCommonPattern(null)
                setNewCommonPattern('')
                setSelectedCommonPatterns(new Set())
                setCommonPatternsSearch('')
                setNewCommonPatternPriority(0)
              }}>
                Close
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <MatchPreviewDialog
          open={previewResultsOpen}
          onOpenChange={setPreviewResultsOpen}
          title={previewTitle}
          results={testResults}
          loading={testingPattern}
          onLoadMore={() => handleTestPattern(testResults?.mode, true, testResults?.channelId)}
        />
      </div>
    </TooltipProvider >
  )
}

// Match Results List Component
function MatchResultsList({ results, loading, onLoadMore, maxHeight = "max-h-[60vh]" }) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground animate-in fade-in duration-200">
        <Loader2 className="h-4 w-4 animate-spin" />
        Testing pattern...
      </div>
    )
  }

  if (!results) return null

  return (
    <div className="space-y-2 animate-in fade-in slide-in-from-top-2 duration-300">
      <div className="border rounded-md p-3 bg-muted/50 transition-all">
        {results.valid ? (
          <>
            <div className="flex items-center gap-2 text-sm font-medium text-green-600 mb-2 animate-in fade-in duration-200">
              <CheckCircle className="h-4 w-4" />
              Valid pattern - {results.total_matches || results.matches?.length || 0} matches found
            </div>
            {results.matches && results.matches.length > 0 && (
              <div className={`space-y-1 ${maxHeight} overflow-y-auto pr-1`}>
                {results.matches.map((match, idx) => (
                  <div
                    key={idx}
                    className="p-2 border-b last:border-0 rounded-sm hover:bg-muted/50 text-sm animate-in fade-in slide-in-from-left-1 duration-200"
                    style={{ animationDelay: `${Math.min(idx * 20, 300)}ms` }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate text-xs sm:text-sm" title={match.stream_name}>
                          {match.stream_name}
                        </div>
                        <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                          {match.m3u_account_name && (
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5 font-normal text-muted-foreground border-muted-foreground/30">
                              {match.m3u_account_name}
                            </Badge>
                          )}
                          <Badge
                            variant={match.source === 'tvg_id' ? 'default' : 'secondary'}
                            className={`text-[10px] px-1.5 py-0 h-5 font-medium uppercase ${match.source === 'tvg_id' ? 'bg-blue-600 hover:bg-blue-700' : ''}`}
                          >
                            {match.source === 'tvg_id' ? 'TVG-ID' : 'REGEX'}
                          </Badge>
                          {match.source === 'regex' && match.matched_pattern && (
                            <span className="text-[10px] text-muted-foreground font-mono truncate max-w-[120px] bg-background/50 px-1 rounded border border-border/50" title={match.matched_pattern}>
                              /{match.matched_pattern}/
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-0.5 min-w-[3rem]">
                        <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-wider">Priority</span>
                        <span className={`text-xs font-mono font-medium ${match.priority > 0 ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'}`}>
                          {match.priority}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}

                {results.has_more && (
                  <div className="pt-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full text-primary hover:bg-primary/10 h-8 text-xs font-medium"
                      onClick={onLoadMore}
                      disabled={loading}
                    >
                      {loading ? (
                        <>
                          <Loader2 className="h-3 w-3 mr-2 animate-spin" />
                          Loading matches...
                        </>
                      ) : (
                        <>
                          Load More Matches (Showing {results.matches.length})
                        </>
                      )}
                    </Button>
                  </div>
                )}

                {!results.has_more && results.total_matches > results.matches.length && (
                  <div className="text-center py-2 text-xs text-muted-foreground italic">
                    End of results ({results.matches.length} matches shown)
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          <div className="text-sm text-destructive">
            {results.error || 'Invalid pattern'}
          </div>
        )}
      </div>
    </div>
  )
}

// Preview Dialog Component
function MatchPreviewDialog({ open, onOpenChange, title, results, loading, onLoadMore }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[700px] max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Preview stream matching results based on current configuration.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-hidden py-2">
          <MatchResultsList
            results={results}
            loading={loading}
            onLoadMore={onLoadMore}
          />
        </div>

        <DialogFooter className="mt-auto">
          <Button onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
