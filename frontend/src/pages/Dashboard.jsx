import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Progress } from '@/components/ui/progress.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Switch } from '@/components/ui/switch.jsx'
import { useToast } from '@/hooks/use-toast.js'
import { automationAPI, streamAPI, streamCheckerAPI, m3uAPI } from '@/services/api.js'
import { PlayCircle, RefreshCw, Search, Activity, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'

export default function Dashboard() {
  const [status, setStatus] = useState(null)
  const [streamCheckerStatus, setStreamCheckerStatus] = useState(null)
  const [playlists, setPlaylists] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState('')
  const [togglingPlaylist, setTogglingPlaylist] = useState(null)
  const { toast } = useToast()

  useEffect(() => {
    loadStatus()
    loadPlaylists()
    const interval = setInterval(() => {
      loadStatus()
      loadPlaylists()
    }, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadStatus = async () => {
    try {
      const [automationResponse, streamCheckerResponse] = await Promise.all([
        automationAPI.getStatus(),
        streamCheckerAPI.getStatus()
      ])
      setStatus(automationResponse.data)
      setStreamCheckerStatus(streamCheckerResponse.data)
    } catch (err) {
      console.error('Failed to load status:', err)
      toast({
        title: "Error",
        description: "Failed to load automation status",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const loadPlaylists = async () => {
    try {
      const response = await m3uAPI.getAccounts()
      // API returns { accounts: [], global_priority_mode: '' }
      setPlaylists(response.data.accounts || [])
    } catch (err) {
      console.error('Failed to load playlists:', err)
    }
  }

  const handleRefreshPlaylist = async () => {
    try {
      setActionLoading('playlist')
      await streamAPI.refreshPlaylist()
      toast({
        title: "Success",
        description: "Playlist refresh initiated successfully"
      })
      await loadStatus()
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to refresh playlist",
        variant: "destructive"
      })
    } finally {
      setActionLoading('')
    }
  }

  const handleDiscoverStreams = async () => {
    try {
      setActionLoading('discover')
      const response = await streamAPI.discoverStreams()
      toast({
        title: "Success",
        description: `Stream discovery completed. ${response.data.total_assigned} streams assigned.`
      })
      await loadStatus()
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to discover streams",
        variant: "destructive"
      })
    } finally {
      setActionLoading('')
    }
  }

  const handleTriggerGlobalAction = async () => {
    try {
      setActionLoading('global')
      await streamCheckerAPI.triggerGlobalAction()
      toast({
        title: "Success",
        description: "Global action triggered successfully"
      })
      await loadStatus()
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to trigger global action",
        variant: "destructive"
      })
    } finally {
      setActionLoading('')
    }
  }

  const handleTogglePlaylist = async (playlistId, currentlyEnabled) => {
    try {
      setTogglingPlaylist(playlistId)
      
      // Get current enabled accounts from status
      // Note: empty array means all accounts are enabled
      const currentEnabledAccounts = status?.config?.enabled_m3u_accounts || []
      let newEnabledAccounts
      
      if (currentEnabledAccounts.length === 0) {
        // Currently all are enabled (empty array)
        if (currentlyEnabled) {
          // Disable this playlist: create list of all other playlists
          newEnabledAccounts = playlists
            .filter(p => p.id !== playlistId)
            .map(p => p.id)
        } else {
          // This shouldn't happen when all are enabled
          newEnabledAccounts = []
        }
      } else {
        // Some playlists are explicitly enabled
        if (currentlyEnabled) {
          // Disable this playlist: remove it from the enabled list
          newEnabledAccounts = currentEnabledAccounts.filter(id => id !== playlistId)
        } else {
          // Enable this playlist: add it to the enabled list
          newEnabledAccounts = [...currentEnabledAccounts, playlistId]
          // If all are now enabled, use empty array to indicate "all enabled"
          if (newEnabledAccounts.length === playlists.length) {
            newEnabledAccounts = []
          }
        }
      }
      
      await automationAPI.updateConfig({ enabled_m3u_accounts: newEnabledAccounts })
      
      toast({
        title: "Success",
        description: `Playlist ${currentlyEnabled ? 'disabled' : 'enabled'} successfully`
      })
      
      await loadStatus()
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to toggle playlist",
        variant: "destructive"
      })
    } finally {
      setTogglingPlaylist(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  const isAutomationRunning = status?.running || false
  const isStreamCheckerRunning = streamCheckerStatus?.running || false
  const queueSize = streamCheckerStatus?.queue?.queue_size || 0
  const completed = streamCheckerStatus?.queue?.completed || 0
  const inProgress = streamCheckerStatus?.queue?.in_progress || 0
  const totalProcessed = completed; // Define totalProcessed based on completed streams
  
  // Calculate progress for the current batch
  const batchTotal = completed + inProgress + queueSize
  const queueProgress = batchTotal > 0 
    ? (completed / batchTotal) * 100
    : 0

  // Determine if actions should be disabled based on stream checker activity
  const isProcessing = streamCheckerStatus?.stream_checking_mode || false
  const shouldDisableActions = isProcessing || actionLoading !== ''

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Monitor and control your stream automation
        </p>
      </div>

      {/* Active Operations Alert */}
      {isProcessing && (
        <Alert className="border-blue-500 bg-blue-50 dark:bg-blue-950">
          <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
          <AlertDescription className="text-blue-900 dark:text-blue-100">
            <div className="font-medium mb-1">Stream checker is actively processing</div>
            <div className="text-sm">
              {completed} of {batchTotal} channels completed
              {inProgress > 0 && ` (${inProgress} in progress, ${queueSize} in queue)`}
            </div>
            <Progress value={queueProgress} className="mt-2 h-2" />
            <div className="text-xs mt-1 text-muted-foreground">Quick actions are temporarily disabled</div>
          </AlertDescription>
        </Alert>
      )}

      {/* Status Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Automation Status
            </CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <div className="text-2xl font-bold">
                {isAutomationRunning ? (
                  <Badge variant="default" className="bg-green-500">
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    Running
                  </Badge>
                ) : (
                  <Badge variant="secondary">
                    Stopped
                  </Badge>
                )}
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Background automation service
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Stream Checker
            </CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <div className="text-2xl font-bold">
                {streamCheckerStatus?.global_action_in_progress ? (
                  <Badge variant="default" className="bg-blue-500">
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    Global Check
                  </Badge>
                ) : streamCheckerStatus?.checking || (streamCheckerStatus?.queue?.in_progress > 0) ? (
                  <Badge variant="default" className="bg-green-500">
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    Normal Check
                  </Badge>
                ) : (
                  <Badge variant="secondary">
                    Idle
                  </Badge>
                )}
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Quality checking service
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Last Update
            </CardTitle>
            <RefreshCw className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {status?.last_playlist_update ? (
                new Date(status.last_playlist_update).toLocaleTimeString()
              ) : (
                'N/A'
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Most recent activity
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>
            Perform common operations on your stream management system
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-4">
          <Button
            onClick={handleRefreshPlaylist}
            disabled={shouldDisableActions}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            {actionLoading === 'playlist' ? 'Refreshing...' : 'Refresh Playlist'}
          </Button>

          <Button
            onClick={handleDiscoverStreams}
            disabled={shouldDisableActions}
            variant="outline"
          >
            <Search className="mr-2 h-4 w-4" />
            {actionLoading === 'discover' ? 'Discovering...' : 'Discover Streams'}
          </Button>

          <Button
            onClick={handleTriggerGlobalAction}
            disabled={shouldDisableActions}
            variant="outline"
          >
            <PlayCircle className="mr-2 h-4 w-4" />
            {actionLoading === 'global' ? 'Triggering...' : 'Trigger Global Action'}
          </Button>
        </CardContent>
      </Card>

      {/* System Information */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Automation Configuration</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between items-center">
                <dt className="text-muted-foreground">Update Interval:</dt>
                <dd>
                  <Badge variant="secondary">
                    {status?.config?.playlist_update_interval_minutes ? `${status.config.playlist_update_interval_minutes}m` : 'N/A'}
                  </Badge>
                </dd>
              </div>
              <div className="flex justify-between items-center">
                <dt className="text-muted-foreground">M3U Accounts:</dt>
                <dd>
                  <Badge variant="outline">
                    {playlists.length}
                  </Badge>
                </dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Stream Checker Status</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between items-center">
                <dt className="text-muted-foreground">Queue Size:</dt>
                <dd>
                  <Badge variant={queueSize > 0 ? "default" : "secondary"}>
                    {queueSize}
                  </Badge>
                </dd>
              </div>
              <div className="flex justify-between items-center">
                <dt className="text-muted-foreground">Active Workers:</dt>
                <dd>
                  <Badge variant={(streamCheckerStatus?.parallel?.max_workers || 0) > 0 ? "default" : "secondary"}>
                    {streamCheckerStatus?.parallel?.max_workers || 0}
                  </Badge>
                </dd>
              </div>
              <div className="flex justify-between items-center">
                <dt className="text-muted-foreground">Total Processed:</dt>
                <dd>
                  <Badge variant="outline">
                    {totalProcessed}
                  </Badge>
                </dd>
              </div>
              {queueSize > 0 && (
                <div className="pt-2">
                  <Label className="text-xs text-muted-foreground mb-2 block">Processing Progress</Label>
                  <Progress value={queueProgress} className="h-2" />
                </div>
              )}
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* Available Playlists */}
      <Card>
        <CardHeader>
          <CardTitle>Available Playlists</CardTitle>
          <CardDescription>
            Enable or disable M3U playlists for stream management
          </CardDescription>
        </CardHeader>
        <CardContent>
          {playlists.length === 0 ? (
            <p className="text-sm text-muted-foreground">No playlists available</p>
          ) : (
            <div className="space-y-3">
              {playlists.map((playlist) => {
                const enabledAccounts = status?.config?.enabled_m3u_accounts || []
                const isEnabled = enabledAccounts.length === 0 || enabledAccounts.includes(playlist.id)
                
                return (
                  <div key={playlist.id} className="flex items-center justify-between p-3 border rounded-lg">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium">{playlist.name}</h4>
                        <Badge variant={isEnabled ? "default" : "secondary"}>
                          {isEnabled ? "Enabled" : "Disabled"}
                        </Badge>
                      </div>
                      {playlist.url && (
                        <p className="text-xs text-muted-foreground mt-1 truncate max-w-md">
                          {playlist.url}
                        </p>
                      )}
                    </div>
                    <Switch
                      checked={isEnabled}
                      onCheckedChange={() => handleTogglePlaylist(playlist.id, isEnabled)}
                      disabled={togglingPlaylist === playlist.id}
                    />
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
