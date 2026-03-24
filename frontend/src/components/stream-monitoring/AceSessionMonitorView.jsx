import * as React from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Square, Trash2, Activity, Radio, ShieldAlert, RotateCcw, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useToast } from '@/hooks/use-toast'
import { aceStreamMonitoringAPI } from '@/services/aceStreamMonitoring'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts'
import { TimelineControl } from './TimelineControl'

const CHANNEL_LOGO_PREFIX = 'streamflow_channel_logo_';
// Maximum number of per-stream metric snapshots retained client-side (1 hour at 1-second poll rate)
const MAX_METRICS_HISTORY = 3600

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
  const [cursorTime, setCursorTime] = useState(null)
  const [isLive, setIsLive] = useState(true)
  const [zoomLevel, setZoomLevel] = useState(60)
  const [showTimeline, setShowTimeline] = useState(true)
  const [expandedStreamId, setExpandedStreamId] = useState(null)

  // Client-side metrics history: { [stream_id]: [{timestamp, speed_down, peers, management_score, management_state, management_reason}] }
  const metricsHistoryRef = useRef({})
  const isLiveRef = useRef(true)

  useEffect(() => {
    isLiveRef.current = isLive
  }, [isLive])

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
      const data = response.data

      // Accumulate per-stream metrics history client-side
      const now = Math.floor(Date.now() / 1000)
      const entries = Array.isArray(data?.entries) ? data.entries : []
      entries.forEach((entry) => {
        const streamId = entry.stream_id
        if (!streamId) return
        const monitor = entry.monitor || {}
        const latest = monitor.latest_status || {}
        const livepos = latest.livepos || {}
        const snapshot = {
          timestamp: now,
          speed_down: latest.speed_down != null ? Number(latest.speed_down) : null,
          peers: latest.peers != null ? Number(latest.peers) : null,
          last_ts: livepos.last_ts != null ? Number(livepos.last_ts) : null,
          management_score: Number(entry.management_score || 0),
          management_state: entry.management_state || 'review',
          management_reason: entry.management_reason || null,
        }
        const history = metricsHistoryRef.current[streamId] || []
        // Avoid duplicate timestamps
        if (history.length === 0 || history[history.length - 1].timestamp < now) {
          metricsHistoryRef.current[streamId] = [...history, snapshot].slice(-MAX_METRICS_HISTORY)
        }
      })

      setSession(data)
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

  // Build streams in the format TimelineControl expects (using accumulated client-side history)
  const streamsForTimeline = useMemo(() => {
    return streamRows.map((row) => {
      const history = metricsHistoryRef.current[row.stream_id] || []
      return {
        stream_id: row.stream_id,
        name: row.stream_name || row.content_id,
        status: row.management_state || 'review',
        status_reason: row.management_reason || null,
        metrics_history: history.map((h) => ({
          timestamp: h.timestamp,
          status: h.management_state || 'review',
          status_reason: h.management_reason || null,
        })),
      }
    })
  }, [streamRows])

  const minTime = useMemo(() => {
    if (!session) return 0
    let min = session.created_at ? Math.floor(new Date(session.created_at).getTime() / 1000) : Math.floor(Date.now() / 1000)
    Object.values(metricsHistoryRef.current).forEach((history) => {
      if (history.length > 0 && history[0].timestamp < min) min = history[0].timestamp
    })
    return min
  }, [session, streamRows])

  const maxTime = useMemo(() => {
    if (!session) return Math.floor(Date.now() / 1000)
    if (session.is_active) return Math.floor(Date.now() / 1000)
    let max = session.created_at ? Math.floor(new Date(session.created_at).getTime() / 1000) : 0
    Object.values(metricsHistoryRef.current).forEach((history) => {
      if (history.length > 0) {
        const last = history[history.length - 1]
        if (last.timestamp > max) max = last.timestamp
      }
    })
    return max
  }, [session, streamRows])

  const handleTimeChange = (newTime) => {
    setCursorTime(typeof newTime === 'function' ? newTime(cursorTime || maxTime) : newTime)
    setIsLive(false)
  }

  const handleLiveClick = () => {
    setIsLive(true)
    setCursorTime(null)
  }

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
                      <AceStreamsTable rows={stableStreams} actionStreamId={actionStreamId} onAction={updateManagementState} metricsHistoryRef={metricsHistoryRef} expandedStreamId={expandedStreamId} onToggleExpand={(id) => setExpandedStreamId(prev => prev === id ? null : id)} cursorTime={cursorTime} isLive={isLive} zoomLevel={zoomLevel} />
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
                      <AceStreamsTable rows={reviewStreams} actionStreamId={actionStreamId} onAction={updateManagementState} metricsHistoryRef={metricsHistoryRef} expandedStreamId={expandedStreamId} onToggleExpand={(id) => setExpandedStreamId(prev => prev === id ? null : id)} cursorTime={cursorTime} isLive={isLive} zoomLevel={zoomLevel} />
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
                      <AceStreamsTable rows={quarantinedStreams} actionStreamId={actionStreamId} onAction={updateManagementState} metricsHistoryRef={metricsHistoryRef} expandedStreamId={expandedStreamId} onToggleExpand={(id) => setExpandedStreamId(prev => prev === id ? null : id)} cursorTime={cursorTime} isLive={isLive} zoomLevel={zoomLevel} />
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          )}
        </CardContent>
      </Card>

      {/* Floating Timeline Button (shown when timeline is hidden) */}
      {!showTimeline && (
        <div className="fixed bottom-6 right-6 z-[60] animate-in fade-in slide-in-from-bottom-4 duration-500">
          <Button
            onClick={() => setShowTimeline(true)}
            className="group relative overflow-hidden bg-zinc-950 hover:bg-zinc-900 text-white border border-white/10 rounded-full h-12 px-6 shadow-[0_8px_30px_rgb(0,0,0,0.4)] flex items-center gap-2 transition-all hover:scale-105 active:scale-95"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-primary/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
            <div className="relative flex items-center gap-2">
              <span className="text-sm font-semibold tracking-wide">Show Timeline</span>
              <ChevronUp className="h-4 w-4 text-primary" />
            </div>
          </Button>
        </div>
      )}

      {/* Timeline Control */}
      {session && streamsForTimeline.length > 0 && (
        <TimelineControl
          className={!showTimeline ? 'hidden' : ''}
          minTime={minTime}
          maxTime={maxTime}
          currentTime={cursorTime || maxTime}
          onTimeChange={handleTimeChange}
          isLive={isLive}
          onLiveClick={handleLiveClick}
          events={[]}
          streams={streamsForTimeline}
          zoomLevel={zoomLevel}
          onZoomChange={setZoomLevel}
          adPeriods={[]}
          showTimeline={showTimeline}
          onToggleTimeline={() => setShowTimeline(!showTimeline)}
        />
      )}

    </div>
  )
}

// Thresholds for speed_down and peers color coding
const SPEED_DOWN_GOOD = 1000   // kB/s - green above this
const SPEED_DOWN_OK = 200      // kB/s - yellow above this, red below
const PEERS_GOOD = 5           // green at or above this
const PEERS_OK = 2             // yellow at or above this, red below

function getSpeedColor(kbps) {
  return 'text-green-600 dark:text-green-400'
}

function getPeersColor(peers) {
  if (peers >= PEERS_GOOD) return 'text-green-600 dark:text-green-400'
  if (peers >= PEERS_OK) return 'text-yellow-600 dark:text-yellow-400'
  return 'text-red-600 dark:text-red-400'
}

function AceStreamsTable({ rows, actionStreamId, onAction, metricsHistoryRef, expandedStreamId, onToggleExpand, cursorTime, isLive, zoomLevel }) {
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8"></TableHead>
            <TableHead>Stream</TableHead>
            <TableHead>State</TableHead>
            <TableHead>Score</TableHead>
            <TableHead>Raw Status</TableHead>
            <TableHead>FFProbe</TableHead>
            <TableHead>Speed Down</TableHead>
            <TableHead>Peers</TableHead>
            <TableHead>Last Collected</TableHead>
            <TableHead>Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const isExpanded = expandedStreamId === row.stream_id
            const speedValue = row.speed_down != null ? Number(row.speed_down) : null
            return (
              <React.Fragment key={row.monitor_id || row.stream_id}>
                <TableRow
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => onToggleExpand(row.stream_id)}
                >
                  <TableCell className="text-muted-foreground">
                    {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </TableCell>
                  <TableCell className="font-medium max-w-xs">
                    <div className="flex items-center gap-2">
                      <span className="truncate" title={row.stream_name || row.content_id}>
                        {row.stream_name || row.content_id}
                      </span>
                      {row.currently_played && (
                        <div className="flex items-center justify-center bg-green-100 dark:bg-green-900/30 p-1 rounded-full" title="Currently Played">
                          <Radio className="h-3 w-3 text-green-600 dark:text-green-400" />
                        </div>
                      )}
                    </div>
                    {row.management_reason && row.management_reason !== '-' && (
                      <div className="text-xs text-muted-foreground mt-1 truncate" title={row.management_reason}>
                        {row.management_reason}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={getManagementVariant(row.management_state)}>{row.management_state}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2 min-w-[100px]">
                      <Progress value={row.management_score} className="w-16 h-2" />
                      <span className={`text-sm font-medium ${row.management_score >= 70 ? 'text-green-600 dark:text-green-400' : row.management_score >= 40 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400'}`}>
                        {Math.round(row.management_score)}%
                      </span>
                    </div>
                    {row.management_plateau_ratio > 0 && (
                      <div className="text-xs text-orange-500 mt-1">
                        Plateau: {formatPercent(row.management_plateau_ratio)}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={getStatusVariant(row.status)}>{row.status}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="text-xs leading-5">
                      {row.resolution !== '-' && <div className="font-medium">{row.resolution}</div>}
                      {(row.video_codec !== '-' || row.audio_codec !== '-') && (
                        <div className="text-muted-foreground">{row.video_codec}/{row.audio_codec}</div>
                      )}
                      {row.hdr_format && row.hdr_format !== '-' ? (
                        <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20 text-[10px] px-1 h-4 mt-0.5">
                          {row.hdr_format}
                        </Badge>
                      ) : null}
                      {row.management_ffprobe_rating && row.management_ffprobe_rating !== 'unknown' && (
                        <div className="text-muted-foreground">
                          {row.management_ffprobe_rating}
                          {row.management_ffprobe_bonus !== 0 && (
                            <span className={row.management_ffprobe_bonus > 0 ? 'text-green-500 ml-1' : 'text-red-500 ml-1'}>
                              ({row.management_ffprobe_bonus > 0 ? '+' : ''}{Math.round(row.management_ffprobe_bonus)})
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    {speedValue != null ? (
                      <span className={`font-mono font-medium ${getSpeedColor(speedValue)}`}>
                        {speedValue >= SPEED_DOWN_GOOD ? `${(speedValue / 1024).toFixed(1)} MB/s` : `${speedValue} kB/s`}
                      </span>
                    ) : '-'}
                  </TableCell>
                  <TableCell>
                    {row.peers != null ? (
                      <span className={`font-medium ${getPeersColor(Number(row.peers))}`}>
                        {formatNumber(row.peers)}
                      </span>
                    ) : '-'}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">{formatTime(row.last_collected_at)}</TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
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
                        className="text-orange-600 hover:text-orange-700 hover:bg-orange-50 dark:hover:bg-orange-950"
                      >
                        <ShieldAlert className="h-3 w-3 mr-1" />
                        Quarantine
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
                {isExpanded && (
                  <TableRow>
                    <TableCell colSpan={10} className="bg-muted/30 p-3">
                      <AceSpeedChart
                        streamId={row.stream_id}
                        metricsHistoryRef={metricsHistoryRef}
                        cursorTime={cursorTime}
                        isLive={isLive}
                        zoomLevel={zoomLevel}
                      />
                    </TableCell>
                  </TableRow>
                )}
              </React.Fragment>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

// Speed chart for a single AceStream stream using client-side accumulated history
function AceSpeedChart({ streamId, metricsHistoryRef, cursorTime, isLive, zoomLevel }) {
  const [, forceUpdate] = useState(0)

  // Re-render when metrics are updated (every few seconds)
  useEffect(() => {
    const interval = setInterval(() => forceUpdate((n) => n + 1), 3000)
    return () => clearInterval(interval)
  }, [])

  const allMetrics = metricsHistoryRef.current[streamId] || []

  const referenceTime = useMemo(() => {
    if (isLive) {
      const last = allMetrics[allMetrics.length - 1]
      return last ? last.timestamp : Math.floor(Date.now() / 1000)
    }
    if (cursorTime) return cursorTime
    const last = allMetrics[allMetrics.length - 1]
    return last ? last.timestamp : Math.floor(Date.now() / 1000)
  }, [allMetrics, cursorTime, isLive])

  const endTimestamp = Math.ceil(referenceTime)
  const startTime = referenceTime - zoomLevel

  const chartData = useMemo(() => {
    return allMetrics
      .filter((m) => m.timestamp >= startTime && m.timestamp <= endTimestamp)
      .map((m, index, arr) => {
        const date = new Date(m.timestamp * 1000)
        const h = date.getHours().toString().padStart(2, '0')
        const min = date.getMinutes().toString().padStart(2, '0')
        const s = date.getSeconds().toString().padStart(2, '0')
        // Calculate last_ts delta relative to previous sample (only when timestamps are ordered)
        const prev = arr[index - 1]
        const last_ts_delta = (
          index > 0 &&
          prev &&
          prev.last_ts != null &&
          m.last_ts != null &&
          prev.timestamp < m.timestamp
        )
          ? m.last_ts - prev.last_ts
          : null
        return {
          time: `${h}:${min}:${s}`,
          timestamp: m.timestamp,
          speed_down: m.speed_down != null ? Number(m.speed_down) : 0,
          peers: m.peers != null ? Number(m.peers) : 0,
          last_ts: m.last_ts != null ? Number(m.last_ts) : null,
          last_ts_delta: last_ts_delta,
        }
      })
  }, [allMetrics, startTime, endTimestamp])

  const formatTimeTick = (ts) => {
    const d = new Date(ts * 1000)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  if (allMetrics.length === 0) {
    return (
      <div className="h-24 flex items-center justify-center text-muted-foreground text-sm">
        No metrics recorded yet — data accumulates while the session is active
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div className="h-24 flex flex-col items-center justify-center text-muted-foreground text-sm">
        <span>No data in this time range</span>
        <span className="text-xs opacity-70">
          ({formatTimeTick(startTime)} – {formatTimeTick(endTimestamp)})
        </span>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <div className="text-xs text-muted-foreground font-medium px-2">Speed Down (kB/s)</div>
          <ResponsiveContainer width="100%" height={80}>
            <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="timestamp"
                tickFormatter={formatTimeTick}
                tick={{ fontSize: 10 }}
                domain={[startTime, endTimestamp]}
                type="number"
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 10 }} width={40} domain={[0, 'auto']} />
              <RechartsTooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--background))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
                labelFormatter={(value) => formatTimeTick(value)}
                formatter={(value) => [`${value.toFixed(0)} kB/s`, 'Speed Down']}
              />
              <Line type="monotone" dataKey="speed_down" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} animationDuration={300} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-1">
          <div className="text-xs text-muted-foreground font-medium px-2">Peers</div>
          <ResponsiveContainer width="100%" height={80}>
            <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="timestamp"
                tickFormatter={formatTimeTick}
                tick={{ fontSize: 10 }}
                domain={[startTime, endTimestamp]}
                type="number"
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 10 }} width={30} domain={[0, 'auto']} />
              <RechartsTooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--background))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
                labelFormatter={(value) => formatTimeTick(value)}
                formatter={(value) => [`${value}`, 'Peers']}
              />
              <Line type="monotone" dataKey="peers" stroke="hsl(142 76% 36%)" strokeWidth={2} dot={false} animationDuration={300} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-1">
          <div className="text-xs text-orange-500 font-medium px-2">last_ts (stream position)</div>
          <ResponsiveContainer width="100%" height={80}>
            <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="timestamp"
                tickFormatter={formatTimeTick}
                tick={{ fontSize: 10 }}
                domain={[startTime, endTimestamp]}
                type="number"
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 10 }} width={50} domain={['auto', 'auto']} />
              <RechartsTooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--background))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
                labelFormatter={(value) => formatTimeTick(value)}
                formatter={(value) => [value != null ? value.toFixed(2) : '-', 'last_ts']}
              />
              <Line type="monotone" dataKey="last_ts" stroke="hsl(25 95% 53%)" strokeWidth={2} dot={false} animationDuration={300} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-1">
          <div className="text-xs text-orange-500 font-medium px-2">last_ts delta (advancement rate)</div>
          <ResponsiveContainer width="100%" height={80}>
            <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="timestamp"
                tickFormatter={formatTimeTick}
                tick={{ fontSize: 10 }}
                domain={[startTime, endTimestamp]}
                type="number"
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 10 }} width={50} domain={['auto', 'auto']} />
              <RechartsTooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--background))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
                labelFormatter={(value) => formatTimeTick(value)}
                formatter={(value) => [value != null ? `${value.toFixed(3)}s` : '-', 'Δlast_ts']}
              />
              <Line type="monotone" dataKey="last_ts_delta" stroke="hsl(0 84% 60%)" strokeWidth={2} dot={false} animationDuration={300} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
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
