import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Square, Trash2, Activity, Radio, ShieldAlert, RotateCcw, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useToast } from '@/hooks/use-toast'
import { aceStreamMonitoringAPI } from '@/services/aceStreamMonitoring'

const CHANNEL_LOGO_PREFIX = 'streamflow_channel_logo_';

const ACTIVE_STATUSES = new Set(['starting', 'running', 'stuck', 'reconnecting'])

function getStatusVariant(status) {
  const value = (status || '').toLowerCase()
  if (value === 'dead') return 'destructive'
  if (value === 'stuck') return 'secondary'
  if (value === 'running' || value === 'starting' || value === 'reconnecting') return 'default'
  return 'outline'
}

function getManagementVariant(state) {
  const value = (state || '').toLowerCase()
  if (value === 'stable') return 'default'
  if (value === 'quarantined') return 'destructive'
  return 'secondary'
}

function formatTime(value) {
  if (!value) return '-'
  if (typeof value === 'number') {
    const ms = value > 1e12 ? value : value * 1000
    return new Date(ms).toLocaleString()
  }
  const parsed = Date.parse(value)
  if (Number.isNaN(parsed)) return value
  return new Date(parsed).toLocaleString()
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return Number(value).toLocaleString()
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return `${Math.round(Number(value) * 100)}%`
}

function AceSessionMonitorView({ sessionId, onBack, onStop, onDelete }) {
  const { toast } = useToast()
  const [loading, setLoading] = useState(true)
  const [session, setSession] = useState(null)
  const [actionStreamId, setActionStreamId] = useState(null)
  const [logoUrl, setLogoUrl] = useState(null)

  // Cache channel logo from localStorage
  useEffect(() => {
    if (session && session.channel_id) {
      const cachedLogo = localStorage.getItem(`${CHANNEL_LOGO_PREFIX}${session.channel_id}`);
      if (cachedLogo) {
        setLogoUrl(cachedLogo);
      }

      // If session has a logo URL, use it and cache it
      if (session.channel_logo_url) {
        setLogoUrl(session.channel_logo_url);
        localStorage.setItem(`${CHANNEL_LOGO_PREFIX}${session.channel_id}`, session.channel_logo_url);
      }
    }
  }, [session?.channel_id, session?.channel_logo_url]);

  const loadSession = async (showLoading = false) => {
    try {
      if (showLoading) setLoading(true)
      const response = await aceStreamMonitoringAPI.getChannelSession(sessionId)
      setSession(response.data)
    } catch (err) {
      console.error('Failed to load AceStream monitor session', err)
      toast({
        title: 'Error',
        description: err.response?.data?.error || 'Failed to load AceStream monitor session',
        variant: 'destructive',
      })
    } finally {
      if (showLoading) setLoading(false)
    }
  }

  useEffect(() => {
    loadSession(true)
    const timer = setInterval(() => {
      setSession(current => {
        // Stop polling once the session is no longer active (mirrors standard view behaviour)
        if (current && !current.is_active) {
          clearInterval(timer)
          return current
        }
        loadSession(false)
        return current
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [sessionId])

  const updateManagementState = async (streamId, action) => {
    if (!session || !streamId) return
    try {
      setActionStreamId(streamId)
      if (action === 'quarantine') {
        await aceStreamMonitoringAPI.quarantineChannelSessionStream(session.session_id, streamId)
        toast({ title: 'Success', description: 'Stream quarantined' })
      } else {
        await aceStreamMonitoringAPI.reviveChannelSessionStream(session.session_id, streamId)
        toast({ title: 'Success', description: 'Stream moved to review' })
      }
      await loadSession(false)
    } catch (err) {
      console.error(`Failed to ${action} Ace stream`, err)
      toast({
        title: 'Error',
        description: err.response?.data?.error || `Failed to ${action} stream`,
        variant: 'destructive',
      })
    } finally {
      setActionStreamId(null)
    }
  }

  const streamRows = useMemo(() => {
    const entries = Array.isArray(session?.entries) ? session.entries : []
    return entries.map((entry) => {
      const monitor = entry.monitor || {}
      const latest = monitor.latest_status || {}
      const movement = monitor.livepos_movement || {}
      const ffprobe = entry.ffprobe_stats || {}
      return {
        ...entry,
        status: monitor.status || 'unknown',
        management_state: entry.management_state || 'review',
        management_score: Number(entry.management_score || 0),
        management_reason: entry.management_reason || '-',
        management_plateau_ratio: Number(entry.management_plateau_ratio || 0),
        management_ffprobe_rating: entry.management_ffprobe_rating || 'unknown',
        management_ffprobe_bonus: Number(entry.management_ffprobe_bonus || 0),
        management_since: entry.management_since,
        manual_quarantine: !!entry.manual_quarantine,
        ffprobe_stats: ffprobe,
        resolution: ffprobe.resolution || '-',
        video_codec: ffprobe.video_codec || '-',
        audio_codec: ffprobe.audio_codec || '-',
        hdr_format: ffprobe.hdr_format || '-',
        fps: ffprobe.fps,
        sample_count: monitor.sample_count || 0,
        currently_played: !!monitor.currently_played,
        monitor_id: monitor.monitor_id || entry.monitor_id,
        started_at: monitor.started_at,
        last_collected_at: monitor.last_collected_at,
        speed_down: latest.speed_down,
        speed_up: latest.speed_up,
        peers: latest.peers,
        progress: latest.progress,
        direction: movement.direction || 'unknown',
        is_moving: !!movement.is_moving,
        pos_delta: movement.pos_delta,
        last_ts_delta: movement.last_ts_delta,
        downloaded_delta: movement.downloaded_delta,
        movement_events: movement.movement_events,
        infohash: monitor?.session?.resolved_infohash,
        engine_host: monitor?.engine?.host,
        engine_port: monitor?.engine?.port,
        last_error: monitor.last_error || null,
        latest_status: latest,
      }
    })
  }, [session])

  const runningCount = streamRows.filter((r) => (r.status || '').toLowerCase() === 'running').length
  const stuckCount = streamRows.filter((r) => (r.status || '').toLowerCase() === 'stuck').length
  const deadCount = streamRows.filter((r) => (r.status || '').toLowerCase() === 'dead').length
  const stableCount = streamRows.filter((r) => (r.management_state || '').toLowerCase() === 'stable').length
  const reviewCount = streamRows.filter((r) => (r.management_state || '').toLowerCase() === 'review').length
  const quarantinedCount = streamRows.filter((r) => (r.management_state || '').toLowerCase() === 'quarantined').length
  const totalSamples = streamRows.reduce((acc, row) => acc + Number(row.sample_count || 0), 0)
  const playedCount = streamRows.filter((r) => r.currently_played).length
  const isActive = streamRows.some((r) => ACTIVE_STATUSES.has((r.status || '').toLowerCase()))
  const activeRows = streamRows.filter((r) => (r.management_state || '').toLowerCase() !== 'quarantined')
  const avgScore = activeRows.length > 0
    ? Math.round(activeRows.reduce((sum, r) => sum + Number(r.management_score || 0), 0) / activeRows.length)
    : 0

  const stableStreams = streamRows
    .filter((r) => (r.management_state || '').toLowerCase() === 'stable')
    .sort((a, b) => b.management_score - a.management_score)
  const reviewStreams = streamRows
    .filter((r) => (r.management_state || '').toLowerCase() === 'review')
    .sort((a, b) => b.management_score - a.management_score)
  const quarantinedStreams = streamRows
    .filter((r) => (r.management_state || '').toLowerCase() === 'quarantined')
    .sort((a, b) => b.management_score - a.management_score)

  if (loading || !session) {
    return (
      <div className="text-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
        <p className="text-muted-foreground">Loading AceStream monitoring session...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 min-w-0">
      <div className="flex items-center justify-between min-w-0 gap-4">
        <div className="flex items-center gap-4 min-w-0">
          <Button variant="ghost" size="icon" onClick={onBack}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          {logoUrl && (
            <div className="flex-shrink-0">
              <img
                src={logoUrl}
                alt={session.channel_name}
                className="h-16 w-16 object-contain rounded-md bg-white/5 p-1"
                onError={(e) => { e.target.style.display = 'none'; }}
              />
            </div>
          )}
          <div className="min-w-0">
            <h1 className="text-3xl font-bold tracking-tight truncate">{session.channel_name || `Channel ${session.channel_id}`}</h1>
            <p className="text-muted-foreground mt-1 truncate">
              AceStream Monitor - {isActive ? 'Active' : 'Inactive'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="outline">AceStream</Badge>
          <Badge variant={isActive ? 'default' : 'secondary'}>{isActive ? 'Active' : 'Inactive'}</Badge>
          {isActive && (
            <Button variant="outline" onClick={onStop}>
              <Square className="h-4 w-4 mr-2" />
              Stop Monitoring
            </Button>
          )}
          <Button variant="destructive" onClick={onDelete}>
            <Trash2 className="h-4 w-4 mr-2" />
            Delete Entry
          </Button>
        </div>
      </div>

      {/* EPG Event Information */}
      {(session.epg_event_title || session.epg_event_description) && (
        <Card className="bg-gradient-to-r from-primary/5 to-primary/10 border-primary/20">
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="space-y-1 flex-1">
                <CardTitle className="text-xl">{session.epg_event_title || 'Current Program'}</CardTitle>
                {session.epg_event_description && (
                  <CardDescription className="text-base mt-2">
                    {session.epg_event_description}
                  </CardDescription>
                )}
              </div>
            </div>
          </CardHeader>
          {(session.epg_event_start || session.epg_event_end) && (
            <CardContent>
              <div className="flex gap-6 text-sm">
                {session.epg_event_start && (
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">Start:</span>
                    <span className="font-medium">{new Date(session.epg_event_start).toLocaleString()}</span>
                  </div>
                )}
                {session.epg_event_end && (
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">End:</span>
                    <span className="font-medium">{new Date(session.epg_event_end).toLocaleString()}</span>
                  </div>
                )}
              </div>
            </CardContent>
          )}
        </Card>
      )}

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4 lg:grid-cols-5">
        <StatsCard title="Total Streams" value={formatNumber(streamRows.length)} icon={Activity} />
        <StatsCard title="Active Streams" value={runningCount} icon={Activity} variant="success" />
        <StatsCard title="Quarantined" value={quarantinedCount} icon={ShieldAlert} variant="warning" />
        <StatsCard title="Avg Score" value={`${avgScore}%`} icon={Activity} />
        <StatsCard title="Played Streams" value={formatNumber(playedCount)} icon={Activity} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Session Lifecycle</CardTitle>
          <CardDescription>Channel-level AceStream session metadata</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            <InfoItem label="Session ID" value={session.session_id} />
            <InfoItem label="Channel" value={session.channel_name || '-'} />
            <InfoItem label="Created" value={formatTime(session.created_at)} />
            <InfoItem label="Monitor Count" value={formatNumber(session.monitor_count)} />
            <InfoItem label="Total Streams" value={formatNumber(session.stream_count)} />
            <InfoItem label="Total Samples" value={formatNumber(session.sample_count)} />
            <InfoItem label="Channel ID" value={formatNumber(session.channel_id)} />
            <InfoItem label="Played Streams" value={formatNumber(session.played_count)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Monitored Streams</CardTitle>
          <CardDescription>Management structure aligned with Standard Monitoring sessions</CardDescription>
        </CardHeader>
        <CardContent>
          {streamRows.length === 0 ? (
            <p className="text-muted-foreground">No stream monitors attached.</p>
          ) : (
            <Tabs defaultValue="stable" className="w-full">
              <TabsList>
                <TabsTrigger value="stable">Stable ({stableStreams.length})</TabsTrigger>
                <TabsTrigger value="review">Under Review ({reviewStreams.length})</TabsTrigger>
                <TabsTrigger value="quarantined">Quarantined ({quarantinedStreams.length})</TabsTrigger>
              </TabsList>

              <TabsContent value="stable" className="pt-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Stable Streams</CardTitle>
                    <CardDescription>Streams with consistent behavior and passing management score.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {stableStreams.length === 0 ? (
                      <p className="text-muted-foreground">No stable streams</p>
                    ) : (
                      <AceStreamsTable rows={stableStreams} actionStreamId={actionStreamId} onAction={updateManagementState} />
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="review" className="pt-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Under Review</CardTitle>
                    <CardDescription>
                      Streams in warm-up or with degraded continuity. last_ts plateaus reduce score.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {reviewStreams.length === 0 ? (
                      <p className="text-muted-foreground">No streams under review</p>
                    ) : (
                      <AceStreamsTable rows={reviewStreams} actionStreamId={actionStreamId} onAction={updateManagementState} />
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="quarantined" className="pt-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Quarantined Streams</CardTitle>
                    <CardDescription>
                      Dead or stuck streams remain monitored for recovery and can be manually revived.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {quarantinedStreams.length === 0 ? (
                      <p className="text-muted-foreground">No quarantined streams</p>
                    ) : (
                      <AceStreamsTable rows={quarantinedStreams} actionStreamId={actionStreamId} onAction={updateManagementState} />
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          )}
        </CardContent>
      </Card>

    </div>
  )
}

function AceStreamsTable({ rows, actionStreamId, onAction }) {
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Stream</TableHead>
            <TableHead>State</TableHead>
            <TableHead>Score</TableHead>
            <TableHead>Reason</TableHead>
            <TableHead>Raw Status</TableHead>
            <TableHead>Plateau</TableHead>
            <TableHead>FFProbe</TableHead>
            <TableHead>Samples</TableHead>
            <TableHead>Played</TableHead>
            <TableHead>Speed Down</TableHead>
            <TableHead>Peers</TableHead>
            <TableHead>Last Collected</TableHead>
            <TableHead>Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.monitor_id}>
              <TableCell className="font-medium">{row.stream_name || row.content_id}</TableCell>
              <TableCell>
                <Badge variant={getManagementVariant(row.management_state)}>{row.management_state}</Badge>
              </TableCell>
              <TableCell>{Math.round(row.management_score)}</TableCell>
              <TableCell>{row.management_reason || '-'}</TableCell>
              <TableCell>
                <Badge variant={getStatusVariant(row.status)}>{row.status}</Badge>
              </TableCell>
              <TableCell>{formatPercent(row.management_plateau_ratio)}</TableCell>
              <TableCell>
                <div className="text-xs leading-5">
                  <div>{row.resolution}</div>
                  <div>{row.video_codec}/{row.audio_codec}</div>
                  <div>{row.hdr_format !== '-' ? row.hdr_format : 'SDR'}</div>
                  <div>
                    {row.management_ffprobe_rating} ({row.management_ffprobe_bonus > 0 ? '+' : ''}
                    {Math.round(row.management_ffprobe_bonus)})
                  </div>
                </div>
              </TableCell>
              <TableCell>{formatNumber(row.sample_count)}</TableCell>
              <TableCell>{row.currently_played ? 'Yes' : 'No'}</TableCell>
              <TableCell>{formatNumber(row.speed_down)}</TableCell>
              <TableCell>{formatNumber(row.peers)}</TableCell>
              <TableCell>{formatTime(row.last_collected_at)}</TableCell>
              <TableCell>
                {(row.management_state || '').toLowerCase() === 'quarantined' ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onAction(row.stream_id, 'revive')}
                    disabled={actionStreamId === row.stream_id}
                  >
                    <RotateCcw className="h-3 w-3 mr-1" />
                    Revive
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onAction(row.stream_id, 'quarantine')}
                    disabled={actionStreamId === row.stream_id}
                  >
                    <ShieldAlert className="h-3 w-3 mr-1" />
                    Quarantine
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function StatsCard({ title, value, icon: Icon, variant = 'default' }) {
  const variantColors = {
    default: 'text-foreground',
    success: 'text-green-600 dark:text-green-400',
    warning: 'text-yellow-600 dark:text-yellow-400',
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold break-words ${variantColors[variant]}`}>
          {value}
        </div>
      </CardContent>
    </Card>
  )
}

function InfoItem({ label, value }) {
  return (
    <div>
      <div className="text-muted-foreground">{label}</div>
      <div className="font-medium break-words">{value}</div>
    </div>
  )
}

export default AceSessionMonitorView
