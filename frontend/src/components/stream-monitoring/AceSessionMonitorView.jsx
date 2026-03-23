import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Square, Trash2, Activity, AlertCircle, Radio } from 'lucide-react'
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

function formatTime(value) {
  if (!value) return '-'
  const parsed = Date.parse(value)
  if (Number.isNaN(parsed)) return value
  return new Date(parsed).toLocaleString()
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return Number(value).toLocaleString()
}

function AceSessionMonitorView({ monitorId, onBack, onStop, onDelete }) {
  const { toast } = useToast()
  const [loading, setLoading] = useState(true)
  const [session, setSession] = useState(null)

  const loadSession = async (showLoading = false) => {
    try {
      if (showLoading) setLoading(true)
      const response = await aceStreamMonitoringAPI.getSession(monitorId, true)
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
  }, [monitorId])

  const latestStatusRows = useMemo(() => {
    if (!session?.latest_status || typeof session.latest_status !== 'object') return []
    return Object.entries(session.latest_status)
  }, [session])

  const recentRows = Array.isArray(session?.recent_status) ? session.recent_status : []
  const isActive = ACTIVE_STATUSES.has((session?.status || '').toLowerCase())

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
            <h1 className="text-3xl font-bold tracking-tight truncate">{session.stream_name || session.content_id}</h1>
            <p className="text-muted-foreground mt-1 truncate">AceStream Session Monitor</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="outline">AceStream</Badge>
          <Badge variant={getStatusVariant(session.status)}>{session.status || 'unknown'}</Badge>
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

      <div className="grid gap-4 md:grid-cols-4">
        <StatsCard title="Samples" value={formatNumber(session.sample_count)} icon={Activity} />
        <StatsCard title="Reconnect Attempts" value={formatNumber(session.reconnect_attempts)} icon={Radio} />
        <StatsCard title="Last Error" value={session.last_error || '-'} icon={AlertCircle} />
        <StatsCard title="Currently Played" value={session.currently_played ? 'Yes' : 'No'} icon={Activity} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Lifecycle</CardTitle>
          <CardDescription>AceStream monitor lifecycle and engine/session binding</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            <InfoItem label="Monitor ID" value={session.monitor_id} />
            <InfoItem label="Content ID" value={session.content_id} />
            <InfoItem label="Stream Name" value={session.stream_name || '-'} />
            <InfoItem label="Started" value={formatTime(session.started_at)} />
            <InfoItem label="Last Collected" value={formatTime(session.last_collected_at)} />
            <InfoItem label="Ended" value={formatTime(session.ended_at)} />
            <InfoItem label="Dead Reason" value={session.dead_reason || '-'} />
            <InfoItem label="Interval (s)" value={formatNumber(session.interval_s)} />
            <InfoItem label="Run Seconds" value={formatNumber(session.run_seconds)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Movement</CardTitle>
          <CardDescription>Live position movement analysis</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-sm">
            <InfoItem label="Is Moving" value={session.livepos_movement?.is_moving ? 'Yes' : 'No'} />
            <InfoItem label="Direction" value={session.livepos_movement?.direction || 'unknown'} />
            <InfoItem label="Sample Points" value={formatNumber(session.livepos_movement?.sample_points)} />
            <InfoItem label="Movement Events" value={formatNumber(session.livepos_movement?.movement_events)} />
            <InfoItem label="Current Pos" value={formatNumber(session.livepos_movement?.current_pos)} />
            <InfoItem label="Current Last TS" value={formatNumber(session.livepos_movement?.current_last_ts)} />
            <InfoItem label="Pos Delta" value={formatNumber(session.livepos_movement?.pos_delta)} />
            <InfoItem label="Last TS Delta" value={formatNumber(session.livepos_movement?.last_ts_delta)} />
            <InfoItem label="Downloaded Delta" value={formatNumber(session.livepos_movement?.downloaded_delta)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Latest Telemetry</CardTitle>
          <CardDescription>Most recent sample from latest_status</CardDescription>
        </CardHeader>
        <CardContent>
          {latestStatusRows.length === 0 ? (
            <p className="text-muted-foreground">No latest telemetry available.</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Field</TableHead>
                    <TableHead>Value</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {latestStatusRows.map(([key, value]) => (
                    <TableRow key={key}>
                      <TableCell className="font-medium">{key}</TableCell>
                      <TableCell>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Telemetry</CardTitle>
          <CardDescription>Short recent history from recent_status</CardDescription>
        </CardHeader>
        <CardContent>
          {recentRows.length === 0 ? (
            <p className="text-muted-foreground">No recent telemetry available.</p>
          ) : (
            <pre className="text-xs bg-muted rounded-md p-3 overflow-auto">{JSON.stringify(recentRows, null, 2)}</pre>
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
