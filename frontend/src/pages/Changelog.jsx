import { useState, useEffect, useMemo } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table.jsx'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion.jsx'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select.jsx'
import { useToast } from '@/hooks/use-toast.js'
import { changelogAPI } from '@/services/api.js'
import { Loader2, CheckCircle2, AlertCircle, Activity } from 'lucide-react'

function formatTimestamp(timestamp) {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function getActionLabel(action) {
  switch (action) {
    case 'playlist_update_match':
      return 'Playlist Update & Match'
    case 'global_check':
      return 'Global Check'
    case 'single_channel_check':
      return 'Single Channel Check'
    case 'batch_stream_check':
      return 'Batch Stream Check'
    case 'playlist_refresh':
      return 'Playlist Refresh'
    case 'streams_assigned':
      return 'Streams Assigned'
    case 'stream_check':
      return 'Stream Check'
    default:
      return action
  }
}

function getActionIcon(action) {
  switch (action) {
    case 'playlist_update_match':
    case 'global_check':
    case 'single_channel_check':
      return <CheckCircle2 className="h-4 w-4" />
    case 'playlist_refresh':
      return <Activity className="h-4 w-4" />
    default:
      return <AlertCircle className="h-4 w-4" />
  }
}

function getActionColor(action) {
  switch (action) {
    case 'playlist_update_match':
      return 'bg-blue-500/10 text-blue-500 border-blue-500/20'
    case 'global_check':
      return 'bg-green-500/10 text-green-500 border-green-500/20'
    case 'single_channel_check':
      return 'bg-purple-500/10 text-purple-500 border-purple-500/20'
    case 'batch_stream_check':
      return 'bg-cyan-500/10 text-cyan-500 border-cyan-500/20'
    case 'playlist_refresh':
      return 'bg-orange-500/10 text-orange-500 border-orange-500/20'
    default:
      return 'bg-gray-500/10 text-gray-500 border-gray-500/20'
  }
}

function ChannelItem({ item, groupType, groupIndex, itemIndex }) {
  const [logoError, setLogoError] = useState(false)
  const channelLabel = item.channel_name
  const channelStats = groupType === 'check' && item.stats ?
    `Avg ${item.stats.avg_resolution || 'N/A'}, ${item.stats.avg_bitrate || 'N/A'}` :
    null

  return (
    <AccordionItem key={itemIndex} value={`channel-${groupIndex}-${itemIndex}`}>
      <AccordionTrigger className="hover:no-underline py-2">
        <div className="flex items-center gap-2">
          {/* Channel Logo */}
          {item.logo_url && !logoError && (
            <img
              src={item.logo_url}
              alt={channelLabel}
              className="w-6 h-6 object-contain"
              onError={() => setLogoError(true)}
            />
          )}
          <span className="text-sm font-medium">{channelLabel}</span>
          {channelStats && (
            <span className="text-xs text-muted-foreground ml-2">: {channelStats}</span>
          )}
        </div>
      </AccordionTrigger>
      <AccordionContent>
        <div className="space-y-1 pl-4">
          {/* Stream list for update_match */}
          {groupType === 'update_match' && item.streams && (
            <ul className="list-none text-sm space-y-1">
              {item.streams.map((stream, idx) => (
                <li key={stream.id || stream.stream_id || `stream-${itemIndex}-${idx}`} className="text-muted-foreground">
                  - {stream.name || stream.stream_name || `Stream ${stream.id || stream.stream_id}`}
                </li>
              ))}
            </ul>
          )}

          {/* Stream details for check */}
          {groupType === 'check' && item.stats && item.stats.stream_details && item.stats.stream_details.length > 0 && (
            <div className="rounded-md border mt-2">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Stream Name</TableHead>
                    <TableHead>M3U Account</TableHead>
                    <TableHead>Resolution</TableHead>
                    <TableHead>Framerate</TableHead>
                    <TableHead>Bitrate</TableHead>
                    <TableHead>Codec</TableHead>
                    {item.stats.stream_details.some(s => s.score !== undefined && s.score !== null) && (
                      <TableHead>Score</TableHead>
                    )}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {[...item.stats.stream_details]
                    .sort((a, b) => {
                      // Sort by score in descending order (highest score first)
                      const scoreA = a.score !== undefined && a.score !== null ? a.score : -Infinity
                      const scoreB = b.score !== undefined && b.score !== null ? b.score : -Infinity
                      return scoreB - scoreA
                    })
                    .map((streamDetail, idx) => (
                      <TableRow key={streamDetail.stream_id || `detail-${idx}`}>
                        <TableCell className="font-medium">{streamDetail.stream_name || 'Unknown'}</TableCell>
                        <TableCell>{streamDetail.m3u_account || 'N/A'}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span>{streamDetail.resolution || 'N/A'}</span>
                            {streamDetail.hdr_format && (
                              <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20 text-xs px-2 py-0 h-5">
                                {streamDetail.hdr_format}
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>{streamDetail.fps || 'N/A'}</TableCell>
                        <TableCell>{streamDetail.bitrate || 'N/A'}</TableCell>
                        <TableCell>{streamDetail.video_codec || 'N/A'}</TableCell>
                        {item.stats.stream_details.some(s => s.score !== undefined && s.score !== null) && (
                          <TableCell>{streamDetail.score !== undefined && streamDetail.score !== null ? streamDetail.score.toFixed(2) : 'N/A'}</TableCell>
                        )}
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </AccordionContent>
    </AccordionItem>
  )
}

function ChangelogEntry({ entry }) {
  const { timestamp, action, details, subentries } = entry
  const hasSubentries = subentries && subentries.length > 0

  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={`${getActionColor(action)} border`}>
              {getActionIcon(action)}
              <span className="ml-1">{getActionLabel(action)}</span>
            </Badge>
          </div>
          <span className="text-sm text-muted-foreground">{formatTimestamp(timestamp)}</span>
        </div>

        {/* Global Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3 pt-3 border-t">
          {details.total_channels !== undefined && (
            <div>
              <p className="text-xs text-muted-foreground">Total Channels</p>
              <p className="text-lg font-semibold">{details.total_channels}</p>
            </div>
          )}
          {details.successful_checks !== undefined && (
            <div>
              <p className="text-xs text-muted-foreground">Successful</p>
              <p className="text-lg font-semibold text-green-600">{details.successful_checks}</p>
            </div>
          )}
          {details.failed_checks !== undefined && details.failed_checks > 0 && (
            <div>
              <p className="text-xs text-muted-foreground">Failed</p>
              <p className="text-lg font-semibold text-destructive">{details.failed_checks}</p>
            </div>
          )}
          {details.total_streams !== undefined && (
            <div>
              <p className="text-xs text-muted-foreground">Total Streams</p>
              <p className="text-lg font-semibold">{details.total_streams}</p>
            </div>
          )}
          {details.streams_analyzed !== undefined && (
            <div>
              <p className="text-xs text-muted-foreground">Successful Checks</p>
              <p className="text-lg font-semibold">{details.streams_analyzed}</p>
            </div>
          )}
          {details.dead_streams !== undefined && (
            <div>
              <p className="text-xs text-muted-foreground">Dead Streams</p>
              <p className="text-lg font-semibold text-destructive">{details.dead_streams}</p>
            </div>
          )}
          {details.streams_revived !== undefined && details.streams_revived > 0 && (
            <div>
              <p className="text-xs text-muted-foreground">Revived Streams</p>
              <p className="text-lg font-semibold text-green-600">{details.streams_revived}</p>
            </div>
          )}
          {details.duration && (
            <div>
              <p className="text-xs text-muted-foreground">Duration</p>
              <p className="text-lg font-semibold">{details.duration}</p>
            </div>
          )}
          {details.avg_resolution && (
            <div>
              <p className="text-xs text-muted-foreground">Avg Resolution</p>
              <p className="text-lg font-semibold">{details.avg_resolution}</p>
            </div>
          )}
          {details.avg_bitrate && (
            <div>
              <p className="text-xs text-muted-foreground">Avg Bitrate</p>
              <p className="text-lg font-semibold">{details.avg_bitrate}</p>
            </div>
          )}
          {details.channel_name && (
            <div className="col-span-2">
              <p className="text-xs text-muted-foreground">Channel</p>
              <p className="text-lg font-semibold truncate">{details.channel_name}</p>
            </div>
          )}
          {details.program_name && (
            <div className="col-span-2">
              <p className="text-xs text-muted-foreground">Program (Scheduled Check)</p>
              <p className="text-lg font-semibold truncate">{details.program_name}</p>
            </div>
          )}
          {/* Streams Assigned specific stats */}
          {details.total_assigned !== undefined && (
            <div>
              <p className="text-xs text-muted-foreground">Total Assigned</p>
              <p className="text-lg font-semibold text-green-600">{details.total_assigned}</p>
            </div>
          )}
          {details.channel_count !== undefined && (
            <div>
              <p className="text-xs text-muted-foreground">Channels Updated</p>
              <p className="text-lg font-semibold">{details.channel_count}</p>
            </div>
          )}
        </div>
      </CardHeader>

      {/* Streams Assigned Details */}
      {action === 'streams_assigned' && details.assignments && details.assignments.length > 0 && (
        <CardContent className="pt-0">
          <Accordion type="multiple" className="w-full">
            <AccordionItem value="streams-assigned-details">
              <AccordionTrigger className="hover:no-underline font-semibold">
                <div className="flex items-center gap-2">
                  {getActionIcon(action)}
                  <span>Streams Assigned to Channels ({details.assignments.length} channels)</span>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <Accordion type="multiple" className="w-full pl-4">
                  {details.assignments.map((assignment, idx) => (
                    <AccordionItem key={idx} value={`assignment-${idx}`}>
                      <AccordionTrigger className="hover:no-underline py-2">
                        <div className="flex items-center gap-2">
                          {assignment.logo_url && (
                            <img
                              src={assignment.logo_url}
                              alt={assignment.channel_name}
                              className="w-6 h-6 object-contain"
                              onError={(e) => e.target.style.display = 'none'}
                            />
                          )}
                          <span className="text-sm font-medium">{assignment.channel_name}</span>
                          <span className="text-xs text-muted-foreground ml-2">
                            ({assignment.stream_count} {assignment.stream_count === 1 ? 'stream' : 'streams'})
                          </span>
                        </div>
                      </AccordionTrigger>
                      <AccordionContent>
                        <div className="space-y-1 pl-4">
                          {assignment.streams && assignment.streams.length > 0 && (
                            <ul className="list-none text-sm space-y-1">
                              {assignment.streams.map((stream, streamIdx) => (
                                <li key={streamIdx} className="text-muted-foreground">
                                  - {stream.name || stream.stream_name || `Stream ${stream.id || stream.stream_id}`}
                                </li>
                              ))}
                              {assignment.stream_count > assignment.streams.length && (
                                <li className="text-xs text-muted-foreground italic">
                                  ... and {assignment.stream_count - assignment.streams.length} more
                                </li>
                              )}
                            </ul>
                          )}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
                {details.has_more_channels && (
                  <p className="text-xs text-muted-foreground italic mt-2 pl-4">
                    ... and more channels (showing top {details.assignments.length} by stream count)
                  </p>
                )}
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </CardContent>
      )}

      {/* Subentries */}
      {hasSubentries && (
        <CardContent className="pt-0">
          {/* Wrap all subentries under a parent accordion showing the action reason */}
          <Accordion type="multiple" className="w-full">
            <AccordionItem value="main-reason">
              <AccordionTrigger className="hover:no-underline font-semibold">
                <div className="flex items-center gap-2">
                  {getActionIcon(action)}
                  <span>{getActionLabel(action)} Details</span>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                {/* Nested accordion for groups (update_match, check) */}
                <Accordion type="multiple" className="w-full pl-4">
                  {subentries.map((group, groupIndex) => {
                    const groupType = group.group
                    const items = group.items || []
                    const groupLabel = groupType === 'update_match' ? 'Added Streams' : 'Checked Streams'
                    const totalCount = items.reduce((sum, item) => {
                      if (groupType === 'update_match') {
                        return sum + (item.streams?.length || 0)
                      } else {
                        return sum + (item.stats?.total_streams || 0)
                      }
                    }, 0)

                    return (
                      <AccordionItem key={groupIndex} value={`group-${groupIndex}`}>
                        <AccordionTrigger className="hover:no-underline">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">
                              {groupLabel}. {groupType === 'update_match' ? 'Added' : 'Checked'}: {totalCount} streams.
                            </span>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent>
                          {/* Nested accordion for channels */}
                          <Accordion type="multiple" className="w-full pl-4">
                            {items.map((item, itemIndex) => (
                              <ChannelItem
                                key={itemIndex}
                                item={item}
                                groupType={groupType}
                                groupIndex={groupIndex}
                                itemIndex={itemIndex}
                              />
                            ))}
                          </Accordion>
                        </AccordionContent>
                      </AccordionItem>
                    )
                  })}
                </Accordion>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </CardContent>
      )}
    </Card>
  )
}

export default function Changelog() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(7)
  const [actionFilter, setActionFilter] = useState('all')
  const { toast } = useToast()

  useEffect(() => {
    loadChangelog()
  }, [days])

  const loadChangelog = async () => {
    try {
      setLoading(true)
      const response = await changelogAPI.getChangelog(days)
      setEntries(response.data || [])
    } catch (err) {
      console.error('Failed to load changelog:', err)
      toast({
        title: "Error",
        description: "Failed to load changelog",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  // Filter entries based on action type (memoized to avoid re-computation on every render)
  const filteredEntries = useMemo(() => {
    return actionFilter === 'all'
      ? entries
      : entries.filter(entry => entry.action === actionFilter)
  }, [entries, actionFilter])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Changelog</h1>
          <p className="text-muted-foreground">
            View activity history and system events
          </p>
        </div>

        <div className="flex gap-3">
          <Select value={actionFilter} onValueChange={setActionFilter}>
            <SelectTrigger className="w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Actions</SelectItem>
              <SelectItem value="playlist_update_match">Playlist Update & Match</SelectItem>
              <SelectItem value="global_check">Global Check</SelectItem>
              <SelectItem value="single_channel_check">Single Channel Check</SelectItem>
              <SelectItem value="batch_stream_check">Batch Stream Check</SelectItem>
              <SelectItem value="playlist_refresh">Playlist Refresh</SelectItem>
              <SelectItem value="streams_assigned">Streams Assigned</SelectItem>
              <SelectItem value="stream_check">Stream Check</SelectItem>
            </SelectContent>
          </Select>

          <Select value={days.toString()} onValueChange={(value) => setDays(Number(value))}>
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">Last 24 hours</SelectItem>
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
              <SelectItem value="90">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {loading ? (
        <Card>
          <CardContent className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </CardContent>
        </Card>
      ) : filteredEntries.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Activity className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              {actionFilter === 'all'
                ? 'No changelog entries found for the selected period'
                : `No ${getActionLabel(actionFilter)} entries found for the selected period`}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredEntries.map((entry, index) => (
            <ChangelogEntry key={index} entry={entry} />
          ))}
        </div>
      )}
    </div>
  )
}
