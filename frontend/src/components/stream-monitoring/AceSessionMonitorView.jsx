import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Square, Trash2, Activity, AlertCircle, Radio, ShieldAlert, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useToast } from '@/hooks/use-toast'
import { aceStreamMonitoringAPI } from '@/services/aceStreamMonitoring'

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

function AceSessionMonitorView({ sessionId, onBack, onStop, onDelete }) {
  const { toast } = useToast()
  const [loading, setLoading] = useState(true)
  const [session, setSession] = useState(null)
  const [actionStreamId, setActionStreamId] = useState(null)

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
    const timer = setInterval(() => loadSession(false), 1000)
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
      return {
        ...entry,
        status: monitor.status || 'unknown',
        management_state: entry.management_state || 'review',
        management_score: Number(entry.management_score || 0),
        management_reason: entry.management_reason || '-',
        management_since: entry.management_since,
        manual_quarantine: !!entry.manual_quarantine,
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
          <div className="min-w-0">
            <h1 className="text-3xl font-bold tracking-tight truncate">{session.channel_name || `Channel ${session.channel_id}`}</h1>
            <p className="text-muted-foreground mt-1 truncate">AceStream Channel Session Monitor</p>
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

      <div className="grid gap-4 md:grid-cols-5">
        <StatsCard title="Streams" value={formatNumber(streamRows.length)} icon={Activity} />
        <StatsCard title="Stable / Review / Quarantined" value={`${stableCount} / ${reviewCount} / ${quarantinedCount}`} icon={ShieldAlert} />
        <StatsCard title="Raw Running / Stuck / Dead" value={`${runningCount} / ${stuckCount} / ${deadCount}`} icon={Radio} />
        <StatsCard title="Played Streams" value={formatNumber(playedCount)} icon={Activity} />
        <StatsCard title="Total Samples" value={formatNumber(totalSamples)} icon={Activity} />
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
          <CardDescription>Per-stream orchestrator telemetry for this channel session</CardDescription>
        </CardHeader>
        <CardContent>
          {streamRows.length === 0 ? (
            <p className="text-muted-foreground">No stream monitors attached.</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Stream</TableHead>
                    <TableHead>Management</TableHead>
                    <TableHead>Score</TableHead>
                    <TableHead>Reason</TableHead>
                    <TableHead>Raw Status</TableHead>
                    <TableHead>Samples</TableHead>
                    <TableHead>Played</TableHead>
                    <TableHead>Engine</TableHead>
                    <TableHead>Speed Down</TableHead>
                    <TableHead>Speed Up</TableHead>
                    <TableHead>Peers</TableHead>
                    <TableHead>Movement</TableHead>
                    <TableHead>Movement Delta</TableHead>
                    <TableHead>Infohash</TableHead>
                    <TableHead>Last Collected</TableHead>
                    <TableHead>Last Error</TableHead>
                    <TableHead>Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {streamRows.map((row) => (
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
                      <TableCell>{formatNumber(row.sample_count)}</TableCell>
                      <TableCell>{row.currently_played ? 'Yes' : 'No'}</TableCell>
                      <TableCell>{row.engine_host ? `${row.engine_host}:${row.engine_port || '-'}` : '-'}</TableCell>
                      <TableCell>{formatNumber(row.speed_down)}</TableCell>
                      <TableCell>{formatNumber(row.speed_up)}</TableCell>
                      <TableCell>{formatNumber(row.peers)}</TableCell>
                      <TableCell>{row.is_moving ? `${row.direction} (moving)` : row.direction}</TableCell>
                      <TableCell>
                        pos {formatNumber(row.pos_delta)} / ts {formatNumber(row.last_ts_delta)} / dl {formatNumber(row.downloaded_delta)}
                      </TableCell>
                      <TableCell>{row.infohash || '-'}</TableCell>
                      <TableCell>{formatTime(row.last_collected_at)}</TableCell>
                      <TableCell>{row.last_error || '-'}</TableCell>
                      <TableCell>
                        {(row.management_state || '').toLowerCase() === 'quarantined' ? (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => updateManagementState(row.stream_id, 'revive')}
                            disabled={actionStreamId === row.stream_id}
                          >
                            <RotateCcw className="h-3 w-3 mr-1" />
                            Revive
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => updateManagementState(row.stream_id, 'quarantine')}
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
          )}
        </CardContent>
      </Card>

    </div>
  )
}

function StatsCard({ title, value, icon: Icon }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-xl font-bold break-words">{value}</div>
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
