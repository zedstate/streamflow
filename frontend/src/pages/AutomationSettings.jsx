import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Switch } from '@/components/ui/switch.jsx'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert.jsx'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select.jsx'
import { Loader2, AlertCircle, CheckCircle2, Trash2, Plus } from 'lucide-react'
import { useToast } from '@/hooks/use-toast.js'
import { automationAPI, streamCheckerAPI, dispatcharrAPI } from '@/services/api.js'

// Default values for automation controls
const DEFAULT_AUTOMATION_CONTROLS = {
  auto_m3u_updates: true,
  auto_stream_matching: true,
  auto_quality_checking: true,
  scheduled_global_action: false
}

export default function AutomationSettings() {
  const [config, setConfig] = useState(null)
  const [streamCheckerConfig, setStreamCheckerConfig] = useState(null)
  const [dispatcharrConfig, setDispatcharrConfig] = useState(null)
  const [testingConnection, setTestingConnection] = useState(false)
  const [connectionTestResult, setConnectionTestResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  
  const { toast } = useToast()

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      setLoading(true)
      const [automationResponse, streamCheckerResponse, dispatcharrResponse] = await Promise.all([
        automationAPI.getConfig(),
        streamCheckerAPI.getConfig(),
        dispatcharrAPI.getConfig()
      ])
      setConfig(automationResponse.data)
      setStreamCheckerConfig(streamCheckerResponse.data)
      setDispatcharrConfig(dispatcharrResponse.data)
    } catch (err) {
      console.error('Failed to load config:', err)
      toast({
        title: "Error",
        description: "Failed to load automation configuration",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      await Promise.all([
        automationAPI.updateConfig(config),
        streamCheckerAPI.updateConfig(streamCheckerConfig),
        dispatcharrAPI.updateConfig(dispatcharrConfig)
      ])
      toast({
        title: "Success",
        description: "Configuration saved successfully",
      })
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to save configuration",
        variant: "destructive"
      })
    } finally {
      setSaving(false)
    }
  }

  const handleConfigChange = (field, value) => {
    if (field.includes('.')) {
      const [parent, child] = field.split('.')
      setConfig(prev => ({
        ...prev,
        [parent]: {
          ...prev[parent],
          [child]: value
        }
      }))
    } else {
      setConfig(prev => ({
        ...prev,
        [field]: value
      }))
    }
  }

  const handleStreamCheckerConfigChange = (field, value) => {
    if (field.includes('.')) {
      const parts = field.split('.')
      if (parts.length === 2) {
        const [parent, child] = parts
        setStreamCheckerConfig(prev => ({
          ...prev,
          [parent]: {
            ...(prev[parent] || {}),
            [child]: value
          }
        }))
      } else if (parts.length === 3) {
        const [parent, child, grandchild] = parts
        setStreamCheckerConfig(prev => ({
          ...prev,
          [parent]: {
            ...(prev[parent] || {}),
            [child]: {
              ...(prev[parent]?.[child] || {}),
              [grandchild]: value
            }
          }
        }))
      }
    } else {
      setStreamCheckerConfig(prev => ({
        ...prev,
        [field]: value
      }))
    }
  }

  const handleDispatcharrConfigChange = (field, value) => {
    setDispatcharrConfig(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const handleTestConnection = async () => {
    try {
      setTestingConnection(true)
      setConnectionTestResult(null)
      
      const response = await dispatcharrAPI.testConnection(dispatcharrConfig)
      setConnectionTestResult({
        success: true,
        message: 'Connection successful!',
        ...response.data
      })
      
      toast({
        title: "Success",
        description: "Successfully connected to Dispatcharr"
      })
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Failed to connect to Dispatcharr'
      setConnectionTestResult({
        success: false,
        message: errorMsg
      })
      toast({
        title: "Connection Failed",
        description: errorMsg,
        variant: "destructive"
      })
    } finally {
      setTestingConnection(false)
    }
  }


  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!config || !streamCheckerConfig) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>
          Failed to load configuration
        </AlertDescription>
      </Alert>
    )
  }

  const automationControls = streamCheckerConfig?.automation_controls || {}
  
  // Always use individual controls (legacy pipeline mode no longer supported)
  const usingIndividualControls = true
  
  // Determine which settings to show based on pipeline mode or individual controls
  const showScheduleSettings = usingIndividualControls 
    ? automationControls.scheduled_global_action
    : ['pipeline_1_5', 'pipeline_2_5', 'pipeline_3'].includes(pipelineMode)
  const showUpdateInterval = usingIndividualControls
    ? automationControls.auto_m3u_updates
    : ['pipeline_1', 'pipeline_1_5', 'pipeline_2', 'pipeline_2_5'].includes(pipelineMode)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Automation Settings</h1>
        <p className="text-muted-foreground">
          Configure Dispatcharr connection, automation features, scheduling, and parameters
        </p>
      </div>

      <Tabs defaultValue="connection" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="connection">Connection</TabsTrigger>
          <TabsTrigger value="automation">Automation</TabsTrigger>
          <TabsTrigger value="scheduling">Scheduling</TabsTrigger>
          <TabsTrigger value="queue">Queue</TabsTrigger>
        </TabsList>
        
        <TabsContent value="connection" className="space-y-6">
          {/* Dispatcharr Configuration */}
          <Card>
            <CardHeader>
              <CardTitle>Dispatcharr Connection</CardTitle>
              <CardDescription>
                Configure connection settings to the Dispatcharr API
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="base_url">Base URL</Label>
                <Input
                  id="base_url"
                  type="url"
                  value={dispatcharrConfig?.base_url || ''}
                  onChange={(e) => handleDispatcharrConfigChange('base_url', e.target.value)}
                  placeholder="http://localhost:9191"
                />
                <p className="text-sm text-muted-foreground">The base URL for your Dispatcharr instance</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  type="text"
                  value={dispatcharrConfig?.username || ''}
                  onChange={(e) => handleDispatcharrConfigChange('username', e.target.value)}
                  placeholder="admin"
                />
                <p className="text-sm text-muted-foreground">Your Dispatcharr username</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={dispatcharrConfig?.password || ''}
                  onChange={(e) => handleDispatcharrConfigChange('password', e.target.value)}
                  placeholder={dispatcharrConfig?.has_password ? '••••••••' : 'Enter password'}
                />
                <p className="text-sm text-muted-foreground">
                  {dispatcharrConfig?.has_password ? 'Leave blank to keep existing password' : 'Your Dispatcharr password'}
                </p>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <Button 
                  onClick={handleTestConnection} 
                  disabled={testingConnection}
                  variant="outline"
                >
                  {testingConnection && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Test Connection
                </Button>
                {connectionTestResult && (
                  <div className="flex items-center gap-2">
                    {connectionTestResult.success ? (
                      <>
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                        <span className="text-sm text-green-600">{connectionTestResult.message}</span>
                      </>
                    ) : (
                      <>
                        <AlertCircle className="h-4 w-4 text-destructive" />
                        <span className="text-sm text-destructive">{connectionTestResult.message}</span>
                      </>
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Save Button */}
          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={saving} size="lg">
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Settings
            </Button>
          </div>
        </TabsContent>
        
        <TabsContent value="automation" className="space-y-6">
          {/* Individual Automation Controls */}
          <Card>
            <CardHeader>
              <CardTitle>Automation Features</CardTitle>
              <CardDescription>
                Enable or disable individual automation features. Toggle each feature independently to customize your automation workflow.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Auto M3U Updates */}
              <div className="flex items-start justify-between space-x-4 rounded-lg border p-4">
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="auto_m3u_updates" className="text-base font-semibold cursor-pointer">
                      Automatic M3U Updates
                    </Label>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Automatically refresh M3U playlists from configured sources at the specified interval or schedule.
                  </p>
                </div>
                <Switch
                  id="auto_m3u_updates"
                  checked={automationControls.auto_m3u_updates ?? DEFAULT_AUTOMATION_CONTROLS.auto_m3u_updates}
                  onCheckedChange={(checked) => handleStreamCheckerConfigChange('automation_controls.auto_m3u_updates', checked)}
                />
              </div>

              {/* Auto Stream Matching */}
              <div className="flex items-start justify-between space-x-4 rounded-lg border p-4">
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="auto_stream_matching" className="text-base font-semibold cursor-pointer">
                      Automatic Stream Matching
                    </Label>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Automatically match streams to channels using configured regex patterns whenever new streams are discovered.
                  </p>
                </div>
                <Switch
                  id="auto_stream_matching"
                  checked={automationControls.auto_stream_matching ?? DEFAULT_AUTOMATION_CONTROLS.auto_stream_matching}
                  onCheckedChange={(checked) => handleStreamCheckerConfigChange('automation_controls.auto_stream_matching', checked)}
                />
              </div>

              {/* Auto Quality Checking */}
              <div className="flex items-start justify-between space-x-4 rounded-lg border p-4">
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="auto_quality_checking" className="text-base font-semibold cursor-pointer">
                      Automatic Quality Checking
                    </Label>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Automatically analyze stream quality (bitrate, resolution, FPS) and reorder streams when channels receive updates. Includes 2-hour immunity to prevent excessive checking.
                  </p>
                </div>
                <Switch
                  id="auto_quality_checking"
                  checked={automationControls.auto_quality_checking ?? DEFAULT_AUTOMATION_CONTROLS.auto_quality_checking}
                  onCheckedChange={(checked) => handleStreamCheckerConfigChange('automation_controls.auto_quality_checking', checked)}
                />
              </div>

              {/* Scheduled Global Action */}
              <div className="flex items-start justify-between space-x-4 rounded-lg border p-4">
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="scheduled_global_action" className="text-base font-semibold cursor-pointer">
                      Scheduled Global Action
                    </Label>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Run a complete automation cycle (Update → Match → Check all channels) on a scheduled basis, bypassing the 2-hour immunity. Configure the schedule in the Scheduling tab.
                  </p>
                </div>
                <Switch
                  id="scheduled_global_action"
                  checked={automationControls.scheduled_global_action ?? DEFAULT_AUTOMATION_CONTROLS.scheduled_global_action}
                  onCheckedChange={(checked) => handleStreamCheckerConfigChange('automation_controls.scheduled_global_action', checked)}
                />
              </div>

              {/* Remove Non-Matching Streams */}
              <div className="flex items-start justify-between space-x-4 rounded-lg border p-4">
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="remove_non_matching_streams" className="text-base font-semibold cursor-pointer">
                      Remove Non-Matching Streams
                    </Label>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Automatically remove streams from channels if they no longer match the configured regex patterns. Useful when providers change stream names but keep the same URLs.
                  </p>
                </div>
                <Switch
                  id="remove_non_matching_streams"
                  checked={automationControls.remove_non_matching_streams ?? false}
                  onCheckedChange={(checked) => handleStreamCheckerConfigChange('automation_controls.remove_non_matching_streams', checked)}
                />
              </div>
            </CardContent>
          </Card>

          {/* Save Button */}
          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={saving} size="lg">
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Settings
            </Button>
          </div>
        </TabsContent>
        
        <TabsContent value="scheduling" className="space-y-6">
          {/* Update Interval Settings */}
          {showUpdateInterval && (
            <Card>
              <CardHeader>
                <CardTitle>Playlist Update Configuration</CardTitle>
                <CardDescription>
                  Configure how often playlists are updated using either interval or cron expression
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Tabs 
                  defaultValue={config.playlist_update_cron ? "cron" : "interval"} 
                  onValueChange={(value) => {
                    // Clear the other option when switching tabs
                    if (value === "interval") {
                      handleConfigChange('playlist_update_cron', '')
                      // Ensure interval has a default value
                      if (!config.playlist_update_interval_minutes) {
                        handleConfigChange('playlist_update_interval_minutes', 5)
                      }
                    } else {
                      // Don't clear interval, just switch to using cron
                      // The backend will prioritize cron when both are set
                    }
                  }}
                >
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="interval">Interval (Minutes)</TabsTrigger>
                    <TabsTrigger value="cron">Cron Expression</TabsTrigger>
                  </TabsList>
                  
                  <TabsContent value="interval" className="space-y-2">
                    <Label htmlFor="playlist_update_interval">Playlist Update Interval (minutes)</Label>
                    <Input
                      id="playlist_update_interval"
                      type="number"
                      min="1"
                      max="1440"
                      value={config.playlist_update_interval_minutes || 5}
                      onChange={(e) => handleConfigChange('playlist_update_interval_minutes', parseInt(e.target.value))}
                    />
                    <p className="text-sm text-muted-foreground">How often to check for playlist updates (in minutes)</p>
                  </TabsContent>
                  
                  <TabsContent value="cron" className="space-y-2">
                    <Label htmlFor="playlist_update_cron">Cron Expression</Label>
                    <Input
                      id="playlist_update_cron"
                      type="text"
                      value={config.playlist_update_cron || ''}
                      onChange={(e) => handleConfigChange('playlist_update_cron', e.target.value)}
                      placeholder="*/30 * * * *"
                    />
                    <p className="text-sm text-muted-foreground">Use cron expression for more precise scheduling</p>
                    <Alert>
                      <AlertCircle className="h-4 w-4" />
                      <AlertTitle>Cron Expression Format</AlertTitle>
                      <AlertDescription>
                        <p className="font-semibold mb-2">Format: minute hour day month weekday</p>
                        <p className="mb-1">Common examples:</p>
                        <ul className="list-disc list-inside space-y-1">
                          <li><code className="text-sm">*/5 * * * *</code> - Every 5 minutes</li>
                          <li><code className="text-sm">*/30 * * * *</code> - Every 30 minutes</li>
                          <li><code className="text-sm">0 * * * *</code> - Every hour</li>
                          <li><code className="text-sm">0 */6 * * *</code> - Every 6 hours</li>
                          <li><code className="text-sm">0 0 * * *</code> - Daily at midnight</li>
                        </ul>
                      </AlertDescription>
                    </Alert>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          )}

          {!showUpdateInterval && (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>No Playlist Update Settings</AlertTitle>
              <AlertDescription>
                Playlist update settings are not available for the selected pipeline. Please select a pipeline that supports automatic updates.
              </AlertDescription>
            </Alert>
          )}

          {/* Global Check Schedule */}
          {showScheduleSettings && (
            <Card>
              <CardHeader>
                <CardTitle>Global Check Schedule</CardTitle>
                <CardDescription>
                  Configure when the scheduled Global Action runs. This performs a complete cycle: Updates all M3U playlists, matches all streams, and checks ALL channels (bypassing the 2-hour immunity).
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="cron_expression">Cron Expression</Label>
                  <Input
                    id="cron_expression"
                    type="text"
                    value={streamCheckerConfig.global_check_schedule?.cron_expression ?? '0 3 * * *'}
                    onChange={(e) => handleStreamCheckerConfigChange('global_check_schedule.cron_expression', e.target.value)}
                    placeholder="0 3 * * *"
                  />
                  <p className="text-sm text-muted-foreground">Enter a cron expression (e.g., '0 3 * * *' for daily at 3:00 AM, '0 3 1 * *' for monthly on the 1st at 3:00 AM)</p>
                </div>
                
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>Cron Expression Format</AlertTitle>
                  <AlertDescription>
                    <p className="font-semibold mb-2">Format: minute hour day month weekday</p>
                    <p className="mb-1">Common examples:</p>
                    <ul className="list-disc list-inside space-y-1">
                      <li><code className="text-sm">0 3 * * *</code> - Every day at 3:00 AM</li>
                      <li><code className="text-sm">30 2 * * *</code> - Every day at 2:30 AM</li>
                      <li><code className="text-sm">0 3 1 * *</code> - Monthly on the 1st at 3:00 AM</li>
                      <li><code className="text-sm">0 0 * * 0</code> - Every Sunday at midnight</li>
                      <li><code className="text-sm">0 */6 * * *</code> - Every 6 hours</li>
                    </ul>
                  </AlertDescription>
                </Alert>
              </CardContent>
            </Card>
          )}

          {!showScheduleSettings && (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>No Global Check Schedule Settings</AlertTitle>
              <AlertDescription>
                Global check schedule settings are not available for the selected pipeline. Please select a pipeline that supports scheduled global checks.
              </AlertDescription>
            </Alert>
          )}

          {/* Save Button */}
          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={saving} size="lg">
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Settings
            </Button>
          </div>
        </TabsContent>
        
        <TabsContent value="queue" className="space-y-6">
          {/* Queue Settings */}
          {(usingIndividualControls ? (automationControls.auto_quality_checking || automationControls.scheduled_global_action) : (pipelineMode && pipelineMode !== 'disabled')) && (
            <Card>
              <CardHeader>
                <CardTitle>Queue Settings</CardTitle>
                <CardDescription>
                  Configure channel checking queue
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="max_queue_size">Maximum Queue Size</Label>
                  <Input
                    id="max_queue_size"
                    type="number"
                    min="10"
                    max="10000"
                    value={streamCheckerConfig.queue?.max_size ?? 1000}
                    onChange={(e) => handleStreamCheckerConfigChange('queue.max_size', parseInt(e.target.value))}
                  />
                  <p className="text-sm text-muted-foreground">Maximum number of channels in the checking queue</p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="max_channels_per_run">Max Channels Per Run</Label>
                  <Input
                    id="max_channels_per_run"
                    type="number"
                    min="1"
                    max="500"
                    value={streamCheckerConfig.queue?.max_channels_per_run ?? 50}
                    onChange={(e) => handleStreamCheckerConfigChange('queue.max_channels_per_run', parseInt(e.target.value))}
                  />
                  <p className="text-sm text-muted-foreground">Maximum channels to check in a single run</p>
                </div>

                <div className="flex items-center space-x-2 pt-4">
                  <Switch
                    id="check_on_update"
                    checked={streamCheckerConfig.queue?.check_on_update === true || streamCheckerConfig.queue?.check_on_update === undefined}
                    onCheckedChange={(checked) => handleStreamCheckerConfigChange('queue.check_on_update', checked)}
                  />
                  <Label htmlFor="check_on_update">Check Channels on M3U Update</Label>
                </div>
                <p className="text-sm text-muted-foreground">Automatically queue channels for checking when they receive M3U playlist updates.</p>
              </CardContent>
            </Card>
          )}

          {(usingIndividualControls ? (!automationControls.auto_quality_checking && !automationControls.scheduled_global_action) : (!pipelineMode || pipelineMode === 'disabled')) && (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>No Queue Settings</AlertTitle>
              <AlertDescription>
                Queue settings are not available when both automatic quality checking and scheduled global action are disabled. Enable at least one of these features in the Automation tab to configure queue settings.
              </AlertDescription>
            </Alert>
          )}

          {/* Save Button */}
          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={saving} size="lg">
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Settings
            </Button>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
