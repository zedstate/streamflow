import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Switch } from '@/components/ui/switch.jsx'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select.jsx'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Progress } from '@/components/ui/progress.jsx'
import { useToast } from '@/hooks/use-toast.js'
import { setupAPI, automationAPI, channelsAPI, regexAPI, dispatcharrAPI, streamCheckerAPI, m3uAPI, profileAPI } from '@/services/api.js'
import { CheckCircle2, Circle, AlertCircle, Edit, Trash2, Plus, Upload } from 'lucide-react'

const STEPS = [
  {
    id: 0,
    label: 'Check Dispatcharr Connection',
    description: 'Verify connection to Dispatcharr API and load channels',
  },
  {
    id: 1,
    label: 'Configure Channel Patterns',
    description: 'Set up regex patterns for automatic stream assignment to channels',
  },
  {
    id: 2,
    label: 'Configure Automation Settings',
    description: 'Set up automation intervals and preferences',
  },
  {
    id: 3,
    label: 'Setup Complete',
    description: 'Your automated stream manager is ready to use',
  },
]

export default function SetupWizard({ onComplete, setupStatus: initialSetupStatus }) {
  const [activeStep, setActiveStep] = useState(0)
  const [setupStatus, setSetupStatus] = useState(initialSetupStatus)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [importDialogOpen, setImportDialogOpen] = useState(false)
  const { toast } = useToast()

  // Dispatcharr configuration state
  const [dispatcharrConfig, setDispatcharrConfig] = useState({
    base_url: '',
    username: '',
    password: '',
    has_password: false
  })
  const [connectionTestResult, setConnectionTestResult] = useState(null)
  const [testingConnection, setTestingConnection] = useState(false)
  const [udiInitialized, setUdiInitialized] = useState(false)
  const [initializingUdi, setInitializingUdi] = useState(false)

  // Channel configuration state
  const [channels, setChannels] = useState([])
  const [patterns, setPatterns] = useState({})
  const [openPatternDialog, setOpenPatternDialog] = useState(false)
  const [editingChannel, setEditingChannel] = useState(null)
  const [patternFormData, setPatternFormData] = useState({
    channel_id: '',
    name: '',
    regex: [''],
    enabled: true
  })

  // Automation config state
  const [config, setConfig] = useState({
    playlist_update_interval_minutes: 5,
    global_check_interval_hours: 24,
    enabled_m3u_accounts: [],
    autostart_automation: true,
    enabled_features: {
      auto_playlist_update: true,
      auto_stream_discovery: true,
      auto_quality_reordering: true,
      changelog_tracking: true
    }
  })

  // Stream checker config
  const [streamCheckerConfig, setStreamCheckerConfig] = useState({
    automation_controls: {
      auto_m3u_updates: true,
      auto_stream_matching: true,
      auto_quality_checking: true,
      scheduled_global_action: false,
      remove_non_matching_streams: false
    },
    global_check_schedule: {
      enabled: true,
      cron_expression: '0 3 * * *',
      frequency: 'daily',
      hour: 3,
      minute: 0
    },
    queue: {
      check_on_update: true
    },
    concurrent_streams: {
      enabled: true,
      global_limit: 10,
      stagger_delay: 1.0
    }
  })

  const [m3uAccounts, setM3uAccounts] = useState([])
  const [profiles, setProfiles] = useState([])
  const [profileConfig, setProfileConfig] = useState(null)

  useEffect(() => {
    if (initialSetupStatus) {
      setSetupStatus(initialSetupStatus)
      determineActiveStep(initialSetupStatus)
    }
    loadDispatcharrConfig()
  }, [initialSetupStatus])

  // Load channels and patterns when entering step 1
  // Only depends on activeStep to avoid unnecessary reloads
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (activeStep === 1 && channels.length === 0) {
      loadChannelsAndPatterns()
    }
  }, [activeStep])

  const determineActiveStep = (status) => {
    if (status.setup_complete) {
      setActiveStep(3)
    } else if (status.dispatcharr_connection && status.has_channels) {
      if (status.has_patterns) {
        setActiveStep(2)
      } else {
        setActiveStep(1)
      }
    } else {
      setActiveStep(0)
    }
  }

  const loadDispatcharrConfig = async () => {
    try {
      const response = await dispatcharrAPI.getConfig()
      setDispatcharrConfig(response.data)
    } catch (err) {
      console.error('Failed to load Dispatcharr config:', err)
    }
  }

  const refreshSetupStatus = async () => {
    try {
      setLoading(true)
      const response = await setupAPI.getStatus()
      setSetupStatus(response.data)
      determineActiveStep(response.data)
    } catch (err) {
      console.error('Failed to refresh setup status:', err)
      setError('Failed to refresh setup status')
    } finally {
      setLoading(false)
    }
  }

  const handleTestConnection = async () => {
    try {
      setTestingConnection(true)
      setConnectionTestResult(null)
      setError('')
      
      const response = await dispatcharrAPI.testConnection(dispatcharrConfig)
      setConnectionTestResult({
        success: true,
        message: 'Connection successful!',
        ...response.data
      })
      
      toast({
        title: "Success",
        description: "Successfully connected to Dispatcharr. Click 'Save Configuration' to complete setup."
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

  const handleSaveDispatcharrConfig = async () => {
    try {
      setLoading(true)
      setInitializingUdi(true)
      setUdiInitialized(false)
      
      // Save configuration (backend will initialize UDI automatically)
      await dispatcharrAPI.updateConfig(dispatcharrConfig)
      
      toast({
        title: "Success",
        description: "Dispatcharr configuration saved. Loading channel data..."
      })
      
      // Poll status until channels are loaded (max 10 seconds)
      let attempts = 0
      const maxAttempts = 10
      let dataLoaded = false
      
      while (attempts < maxAttempts && !dataLoaded) {
        await new Promise(resolve => setTimeout(resolve, 1000))
        const response = await setupAPI.getStatus()
        setSetupStatus(response.data)
        determineActiveStep(response.data)
        
        if (response.data.has_channels && response.data.dispatcharr_connection) {
          dataLoaded = true
          setUdiInitialized(true)
          toast({
            title: "Data Loaded",
            description: "Channel data loaded successfully from Dispatcharr"
          })
        }
        
        attempts++
      }
      
      if (!dataLoaded) {
        toast({
          title: "Warning",
          description: "Configuration saved but channel data may still be loading. Please refresh if needed.",
          variant: "default"
        })
      }
      
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to save Dispatcharr configuration",
        variant: "destructive"
      })
    } finally {
      setInitializingUdi(false)
      setLoading(false)
    }
  }

  const loadChannelsAndPatterns = async () => {
    try {
      setLoading(true)
      const [channelsResponse, patternsResponse, m3uResponse, profilesResponse, profileConfigResponse] = await Promise.all([
        channelsAPI.getChannels(),
        regexAPI.getPatterns(),
        m3uAPI.getAccounts().catch(err => {
          console.warn('Failed to load M3U accounts:', err)
          return { data: { accounts: [] } }
        }),
        profileAPI.getProfiles().catch(err => {
          console.warn('Failed to load profiles:', err)
          return { data: [] }
        }),
        profileAPI.getConfig().catch(err => {
          console.warn('Failed to load profile config:', err)
          return { data: null }
        })
      ])
      
      setChannels(channelsResponse.data)
      // Extract just the patterns object, not the whole config structure
      const patternsData = patternsResponse.data?.patterns || {}
      setPatterns(patternsData)
      // API returns { accounts: [], global_priority_mode: '' }
      setM3uAccounts(m3uResponse.data.accounts || [])
      setProfiles(profilesResponse.data || [])
      setProfileConfig(profileConfigResponse.data)
    } catch (err) {
      console.error('Failed to load channels and patterns:', err)
      toast({
        title: "Error",
        description: "Failed to load channel data",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleAddPattern = () => {
    setEditingChannel(null)
    setPatternFormData({
      channel_id: '',
      name: '',
      regex: [''],
      enabled: true
    })
    setOpenPatternDialog(true)
  }

  const handleEditPattern = (channelId) => {
    const pattern = patterns[channelId]
    if (pattern) {
      setEditingChannel(channelId)
      setPatternFormData({
        channel_id: channelId,
        name: pattern.name || '',
        regex: pattern.regex || [''],
        enabled: pattern.enabled !== false
      })
      setOpenPatternDialog(true)
    }
  }

  const handleDeletePattern = async (channelId) => {
    try {
      await regexAPI.deletePattern(channelId)
      toast({
        title: "Success",
        description: "Pattern deleted successfully"
      })
      await loadChannelsAndPatterns()
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to delete pattern",
        variant: "destructive"
      })
    }
  }

  const handleSavePattern = async () => {
    try {
      // Filter out empty regex strings
      const cleanedRegex = patternFormData.regex.filter(r => r.trim() !== '')
      
      if (!patternFormData.channel_id || cleanedRegex.length === 0) {
        toast({
          title: "Validation Error",
          description: "Please select a channel and provide at least one regex pattern",
          variant: "destructive"
        })
        return
      }

      const patternData = {
        ...patternFormData,
        regex: cleanedRegex
      }

      await regexAPI.addPattern(patternData)
      toast({
        title: "Success",
        description: "Pattern saved successfully"
      })
      
      setOpenPatternDialog(false)
      await loadChannelsAndPatterns()
      await refreshSetupStatus()
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to save pattern",
        variant: "destructive"
      })
    }
  }

  const handleImportJSON = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return

    try {
      const text = await file.text()
      const data = JSON.parse(text)
      
      // Validate and import the patterns
      await regexAPI.importPatterns(data)
      
      toast({
        title: "Success",
        description: "Patterns imported successfully"
      })
      
      setImportDialogOpen(false)
      await loadChannelsAndPatterns()
      await refreshSetupStatus()
    } catch (err) {
      toast({
        title: "Error",
        description: err.response?.data?.error || "Failed to import patterns. Please check the JSON format.",
        variant: "destructive"
      })
    }
  }

  const handleSaveAutomationConfig = async () => {
    try {
      setLoading(true)
      
      // Save all configurations
      const savePromises = [
        automationAPI.updateConfig(config),
        streamCheckerAPI.updateConfig(streamCheckerConfig)
      ]
      
      // Save profile configuration if it exists
      if (profileConfig) {
        savePromises.push(profileAPI.updateConfig(profileConfig))
      }
      
      await Promise.all(savePromises)
      
      toast({
        title: "Success",
        description: "Automation configuration saved"
      })
      
      await refreshSetupStatus()
      
      const statusResponse = await setupAPI.getStatus()
      if (statusResponse.data.setup_complete) {
        setActiveStep(3)
      }
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to save automation configuration",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleComplete = async () => {
    try {
      setLoading(true)
      const response = await setupAPI.getStatus()
      
      if (response.data.setup_complete) {
        onComplete()
      } else {
        toast({
          title: "Setup Incomplete",
          description: "Please ensure all steps are properly configured",
          variant: "destructive"
        })
        determineActiveStep(response.data)
      }
    } catch (err) {
      console.error('Failed to verify setup completion:', err)
      toast({
        title: "Error",
        description: "Failed to verify setup completion",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const renderStepIcon = (stepId) => {
    if (stepId < activeStep) {
      return <CheckCircle2 className="h-6 w-6 text-green-500" />
    } else if (stepId === activeStep) {
      return <Circle className="h-6 w-6 text-primary fill-primary" />
    } else {
      return <Circle className="h-6 w-6 text-muted-foreground" />
    }
  }

  const renderStepContent = () => {
    switch (activeStep) {
      case 0:
        return (
          <div className="space-y-6">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="base_url">Dispatcharr Base URL</Label>
                <Input
                  id="base_url"
                  placeholder="http://localhost:8000"
                  value={dispatcharrConfig.base_url}
                  onChange={(e) => setDispatcharrConfig({ ...dispatcharrConfig, base_url: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  placeholder="admin"
                  value={dispatcharrConfig.username}
                  onChange={(e) => setDispatcharrConfig({ ...dispatcharrConfig, username: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder={dispatcharrConfig.has_password ? "••••••••" : "Enter password"}
                  value={dispatcharrConfig.password}
                  onChange={(e) => setDispatcharrConfig({ ...dispatcharrConfig, password: e.target.value })}
                />
                {dispatcharrConfig.has_password && (
                  <p className="text-xs text-muted-foreground">Leave blank to keep existing password</p>
                )}
              </div>
            </div>

            {connectionTestResult && (
              <Alert variant={connectionTestResult.success ? "default" : "destructive"}>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{connectionTestResult.message}</AlertDescription>
              </Alert>
            )}

            {initializingUdi && (
              <Alert>
                <div className="flex items-center gap-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                  <AlertDescription>Loading channel data from Dispatcharr...</AlertDescription>
                </div>
              </Alert>
            )}

            <div className="flex gap-2">
              <Button onClick={handleTestConnection} disabled={testingConnection || initializingUdi || loading}>
                {testingConnection ? 'Testing...' : 'Test Connection'}
              </Button>
              <Button onClick={handleSaveDispatcharrConfig} variant="default" disabled={loading || testingConnection || initializingUdi}>
                {initializingUdi ? 'Saving & Loading Data...' : 'Save & Load Data'}
              </Button>
            </div>

            {udiInitialized && (
              <Alert>
                <CheckCircle2 className="h-4 w-4" />
                <AlertDescription>
                  Connection verified and channel data loaded! Ready to proceed to next step.
                </AlertDescription>
              </Alert>
            )}
          </div>
        )

      case 1:
        return (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <p className="text-sm text-muted-foreground">
                Configure regex patterns to automatically assign streams to channels
              </p>
              <div className="flex gap-2">
                <Button 
                  onClick={() => document.getElementById('import-json-file').click()} 
                  size="sm"
                  variant="outline"
                >
                  <Upload className="h-4 w-4 mr-2" />
                  Import JSON
                </Button>
                <input
                  id="import-json-file"
                  type="file"
                  accept="application/json"
                  onChange={handleImportJSON}
                  className="hidden"
                />
                <Button onClick={() => {
                  loadChannelsAndPatterns()
                  handleAddPattern()
                }} size="sm">
                  <Plus className="h-4 w-4 mr-2" />
                  Add Pattern
                </Button>
              </div>
            </div>

            {loading ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              </div>
            ) : (
              <>
                {Object.keys(patterns).length === 0 ? (
                  <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      No patterns configured yet. Click "Add Pattern" to create your first pattern.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <div className="border rounded-lg">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Channel</TableHead>
                          <TableHead>Patterns</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {Object.entries(patterns).map(([channelId, pattern]) => (
                          <TableRow key={channelId}>
                            <TableCell className="font-medium">{pattern.name}</TableCell>
                            <TableCell className="max-w-xs truncate">
                              {pattern.regex?.join(', ') || 'No patterns'}
                            </TableCell>
                            <TableCell>
                              <Badge variant={pattern.enabled ? "default" : "secondary"}>
                                {pattern.enabled ? 'Enabled' : 'Disabled'}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex justify-end gap-2">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleEditPattern(channelId)}
                                >
                                  <Edit className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleDeletePattern(channelId)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </>
            )}

            <Dialog open={openPatternDialog} onOpenChange={setOpenPatternDialog}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{editingChannel ? 'Edit Pattern' : 'Add Pattern'}</DialogTitle>
                  <DialogDescription>
                    Configure regex patterns for automatic stream assignment
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="channel">Channel</Label>
                    <Select
                      value={patternFormData.channel_id}
                      onValueChange={(value) => {
                        const channel = channels.find(c => c.id === value)
                        setPatternFormData({
                          ...patternFormData,
                          channel_id: value,
                          name: channel?.name || ''
                        })
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select a channel" />
                      </SelectTrigger>
                      <SelectContent>
                        {channels.map(channel => (
                          <SelectItem key={channel.id} value={channel.id}>
                            {channel.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Regex Patterns</Label>
                    {patternFormData.regex.map((regex, index) => (
                      <div key={index} className="flex gap-2">
                        <Input
                          value={regex}
                          onChange={(e) => {
                            const newRegex = [...patternFormData.regex]
                            newRegex[index] = e.target.value
                            setPatternFormData({ ...patternFormData, regex: newRegex })
                          }}
                          placeholder="e.g., ESPN.*HD"
                        />
                        {patternFormData.regex.length > 1 && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              const newRegex = patternFormData.regex.filter((_, i) => i !== index)
                              setPatternFormData({ ...patternFormData, regex: newRegex })
                            }}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    ))}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setPatternFormData({
                          ...patternFormData,
                          regex: [...patternFormData.regex, '']
                        })
                      }}
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      Add Pattern
                    </Button>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Switch
                      id="enabled"
                      checked={patternFormData.enabled}
                      onCheckedChange={(checked) => setPatternFormData({ ...patternFormData, enabled: checked })}
                    />
                    <Label htmlFor="enabled">Enabled</Label>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setOpenPatternDialog(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleSavePattern}>
                    Save Pattern
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        )

      case 2:
        return (
          <div className="space-y-6">
            <div className="space-y-4">
              <div className="space-y-4">
                <Label className="text-base font-semibold">Automation Features</Label>
                <p className="text-sm text-muted-foreground">
                  Configure which automation features to enable
                </p>

                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div className="space-y-0.5">
                    <Label htmlFor="auto_m3u_updates" className="text-sm font-medium">
                      Automatic M3U Updates
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      Automatically refresh M3U playlists from configured sources
                    </p>
                  </div>
                  <Switch
                    id="auto_m3u_updates"
                    checked={streamCheckerConfig.automation_controls?.auto_m3u_updates ?? true}
                    onCheckedChange={(checked) => setStreamCheckerConfig({
                      ...streamCheckerConfig,
                      automation_controls: {
                        ...streamCheckerConfig.automation_controls,
                        auto_m3u_updates: checked
                      }
                    })}
                  />
                </div>

                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div className="space-y-0.5">
                    <Label htmlFor="auto_stream_matching" className="text-sm font-medium">
                      Automatic Stream Matching
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      Automatically match streams to channels using regex patterns
                    </p>
                  </div>
                  <Switch
                    id="auto_stream_matching"
                    checked={streamCheckerConfig.automation_controls?.auto_stream_matching ?? true}
                    onCheckedChange={(checked) => setStreamCheckerConfig({
                      ...streamCheckerConfig,
                      automation_controls: {
                        ...streamCheckerConfig.automation_controls,
                        auto_stream_matching: checked
                      }
                    })}
                  />
                </div>

                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div className="space-y-0.5">
                    <Label htmlFor="auto_quality_checking" className="text-sm font-medium">
                      Automatic Quality Checking
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      Automatically analyze and reorder streams by quality
                    </p>
                  </div>
                  <Switch
                    id="auto_quality_checking"
                    checked={streamCheckerConfig.automation_controls?.auto_quality_checking ?? true}
                    onCheckedChange={(checked) => setStreamCheckerConfig({
                      ...streamCheckerConfig,
                      automation_controls: {
                        ...streamCheckerConfig.automation_controls,
                        auto_quality_checking: checked
                      }
                    })}
                  />
                </div>

                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div className="space-y-0.5">
                    <Label htmlFor="scheduled_global_action" className="text-sm font-medium">
                      Scheduled Global Action
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      Run complete automation cycle on a schedule
                    </p>
                  </div>
                  <Switch
                    id="scheduled_global_action"
                    checked={streamCheckerConfig.automation_controls?.scheduled_global_action ?? true}
                    onCheckedChange={(checked) => setStreamCheckerConfig({
                      ...streamCheckerConfig,
                      automation_controls: {
                        ...streamCheckerConfig.automation_controls,
                        scheduled_global_action: checked
                      }
                    })}
                  />
                </div>

                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div className="space-y-0.5">
                    <Label htmlFor="remove_non_matching_streams" className="text-sm font-medium">
                      Remove Non-Matching Streams
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      Remove streams that no longer match regex patterns
                    </p>
                  </div>
                  <Switch
                    id="remove_non_matching_streams"
                    checked={streamCheckerConfig.automation_controls?.remove_non_matching_streams ?? false}
                    onCheckedChange={(checked) => setStreamCheckerConfig({
                      ...streamCheckerConfig,
                      automation_controls: {
                        ...streamCheckerConfig.automation_controls,
                        remove_non_matching_streams: checked
                      }
                    })}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="playlist_interval">Playlist Update Interval (minutes)</Label>
                <Input
                  id="playlist_interval"
                  type="number"
                  min="1"
                  value={config.playlist_update_interval_minutes}
                  onChange={(e) => setConfig({ ...config, playlist_update_interval_minutes: parseInt(e.target.value) })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="concurrent_limit">Concurrent Stream Limit</Label>
                <Input
                  id="concurrent_limit"
                  type="number"
                  min="1"
                  value={streamCheckerConfig.concurrent_streams.global_limit}
                  onChange={(e) => setStreamCheckerConfig({
                    ...streamCheckerConfig,
                    concurrent_streams: {
                      ...streamCheckerConfig.concurrent_streams,
                      global_limit: parseInt(e.target.value)
                    }
                  })}
                />
              </div>

              <div className="flex items-center justify-between">
                <Label htmlFor="autostart">Autostart Automation</Label>
                <Switch
                  id="autostart"
                  checked={config.autostart_automation}
                  onCheckedChange={(checked) => setConfig({ ...config, autostart_automation: checked })}
                />
              </div>

              {/* M3U Account Configuration */}
              {m3uAccounts && m3uAccounts.length > 0 && (
                <div className="space-y-2 border-t pt-4 mt-4">
                  <Label>M3U Account Settings</Label>
                  <p className="text-xs text-muted-foreground mb-2">
                    Enable or disable M3U accounts for stream discovery
                  </p>
                  <div className="space-y-2">
                    {m3uAccounts.map((account) => (
                      <div key={account.id} className="flex items-center justify-between">
                        <span className="text-sm">{account.name || account.username || `Account ${account.id}`}</span>
                        <Switch
                          checked={config.enabled_m3u_accounts?.includes(account.id) || false}
                          onCheckedChange={(checked) => {
                            const currentAccounts = config.enabled_m3u_accounts || []
                            const newAccounts = checked
                              ? [...currentAccounts, account.id]
                              : currentAccounts.filter(id => id !== account.id)
                            setConfig({ ...config, enabled_m3u_accounts: newAccounts })
                          }}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Profile Configuration */}
              {profiles && profiles.length > 0 && (
                <div className="space-y-2 border-t pt-4 mt-4">
                  <Label htmlFor="selected_profile">Channel Profile</Label>
                  <p className="text-xs text-muted-foreground mb-2">
                    Select which channel profile to use (optional)
                  </p>
                  <Select
                    value={profileConfig?.selected_profile_id?.toString() || 'none'}
                    onValueChange={(value) => {
                      if (value === 'none') {
                        setProfileConfig({ ...profileConfig, selected_profile_id: null, selected_profile_name: null, use_profile: false })
                      } else {
                        const profile = profiles.find(p => p.id?.toString() === value)
                        setProfileConfig({
                          ...profileConfig,
                          selected_profile_id: parseInt(value),
                          selected_profile_name: profile?.name || 'Unknown',
                          use_profile: true
                        })
                      }
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Use all channels (no profile)" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Use all channels (no profile)</SelectItem>
                      {profiles.map((profile) => (
                        <SelectItem key={profile.id} value={profile.id?.toString()}>
                          {profile.name || `Profile ${profile.id}`}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          </div>
        )

      case 3:
        return (
          <div className="space-y-6">
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>
                Setup completed successfully! Your StreamFlow system is ready to use.
              </AlertDescription>
            </Alert>

            <div className="space-y-2">
              <h3 className="font-semibold">Setup Summary:</h3>
              <ul className="space-y-1 text-sm text-muted-foreground">
                <li>✓ Dispatcharr connection configured</li>
                <li>✓ Channels loaded</li>
                <li>✓ Regex patterns configured</li>
                <li>✓ Automation settings saved</li>
              </ul>
            </div>

            <Button onClick={handleComplete} disabled={loading}>
              {loading ? 'Loading...' : 'Continue to Dashboard'}
            </Button>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-background p-4">
      <Card className="w-full max-w-4xl">
        <CardHeader>
          <CardTitle className="text-2xl">Welcome to StreamFlow</CardTitle>
          <CardDescription>
            Let's get your stream management system configured
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Step indicator */}
          <div className="mb-8">
            <div className="flex items-center justify-between">
              {STEPS.map((step, index) => (
                <div key={step.id} className="flex flex-col items-center flex-1">
                  <div className="flex items-center w-full">
                    {index > 0 && (
                      <div className={`flex-1 h-0.5 ${step.id <= activeStep ? 'bg-primary' : 'bg-muted'}`} />
                    )}
                    <div className="flex flex-col items-center px-2">
                      {renderStepIcon(step.id)}
                      <span className={`text-xs mt-2 text-center ${step.id === activeStep ? 'font-semibold' : 'text-muted-foreground'}`}>
                        {step.label}
                      </span>
                    </div>
                    {index < STEPS.length - 1 && (
                      <div className={`flex-1 h-0.5 ${step.id < activeStep ? 'bg-primary' : 'bg-muted'}`} />
                    )}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4">
              <Progress value={(activeStep / (STEPS.length - 1)) * 100} className="h-2" />
            </div>
          </div>

          {/* Step content */}
          <div className="mb-6">
            <h3 className="text-lg font-semibold mb-2">{STEPS[activeStep].label}</h3>
            <p className="text-sm text-muted-foreground mb-6">{STEPS[activeStep].description}</p>
            {renderStepContent()}
          </div>

          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Navigation buttons */}
          <div className="flex justify-between mt-6">
            <Button
              variant="outline"
              onClick={() => setActiveStep(prev => Math.max(0, prev - 1))}
              disabled={activeStep === 0 || loading}
            >
              Back
            </Button>
            {activeStep < 3 && (
              <Button
                onClick={async () => {
                  if (activeStep === 0) {
                    // On step 0, check if UDI is initialized before proceeding
                    if (!udiInitialized) {
                      toast({
                        title: "Not Ready",
                        description: "Please test the connection and wait for channel data to load before proceeding.",
                        variant: "destructive"
                      })
                      return
                    }
                    // Load channels and patterns before moving to step 1
                    await loadChannelsAndPatterns()
                    setActiveStep(prev => Math.min(3, prev + 1))
                  } else if (activeStep === 2) {
                    // Save automation config before moving to next step
                    await handleSaveAutomationConfig()
                  } else {
                    setActiveStep(prev => Math.min(3, prev + 1))
                  }
                }}
                disabled={loading || (activeStep === 0 && !udiInitialized)}
              >
                {activeStep === 2 ? (loading ? 'Saving...' : 'Save & Continue') : 'Next'}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
