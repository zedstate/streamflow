import { useState, useEffect, useMemo, useRef } from 'react';
import * as React from 'react';
import { ArrowLeft, Square, Activity, AlertCircle, Image as ImageIcon, Calendar, Clock, Ban, Play, Volume2, VolumeX, Radio } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { useToast } from '@/hooks/use-toast';
import { streamSessionsAPI } from '@/services/streamSessions';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, ReferenceArea } from 'recharts';
import { TimelineControl } from './TimelineControl';

// Constants
const FALLBACK_IMAGE_SVG = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 225"%3E%3Crect fill="%23111" width="400" height="225"/%3E%3Ctext fill="%23666" x="50%25" y="50%25" text-anchor="middle" dominant-baseline="middle" font-family="sans-serif"%3ENo Image%3C/text%3E%3C/svg%3E';
const CHANNEL_LOGO_PREFIX = 'streamflow_channel_logo_';

function SessionMonitorView({ sessionId, onBack, onStop }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [aliveScreenshots, setAliveScreenshots] = useState([]);
  const [logoUrl, setLogoUrl] = useState(null);
  const [playingStreamIds, setPlayingStreamIds] = useState(new Set());
  const [cursorTime, setCursorTime] = useState(null); // Current timestamp of the timeline
  const [isLive, setIsLive] = useState(true); // Whether we are following the latest updates
  const [zoomLevel, setZoomLevel] = useState(60); // Window size in seconds (default 1 minute)
  const { toast } = useToast();

  // Helper to find the metric closest to the cursor time
  const getSnapshotAtTime = (stream, time) => {
    if (!stream.metrics_history || stream.metrics_history.length === 0) return stream;

    // If live, return current state
    if (isLive) return stream;

    // Find closest metric
    // Assuming metrics are sorted by timestamp (they should be appended in order)
    // We can do a simple search or binary search. For < 1000 items, simple reverse search is fine.

    // If time is past the last metric, use the last one (but maybe show as unknown if too far?)
    const lastMetric = stream.metrics_history[stream.metrics_history.length - 1];
    if (time >= lastMetric.timestamp) return stream;

    let closest = null;
    let minDiff = Infinity;

    for (const metric of stream.metrics_history) {
      const diff = Math.abs(metric.timestamp - time);
      if (diff <= minDiff) {
        minDiff = diff;
        closest = metric;
      }
    }

    if (closest) {
      return {
        ...stream,
        speed: closest.speed,
        bitrate: closest.bitrate,
        fps: closest.fps,
        reliability_score: closest.reliability_score !== undefined ? closest.reliability_score : stream.reliability_score,
        status: closest.status || stream.status, // Fallback if status wasn't recorded in old history
        status_reason: closest.status_reason || stream.status_reason,
        is_quarantined: (closest.status || stream.status) === 'quarantined',
        is_alive: closest.is_alive,
        rank: closest.rank,
        display_logo_status: closest.display_logo_status || stream.display_logo_status
      };
    }

    return stream;
  };

  // Use a ref to track isLive state for the interval callback
  const isLiveRef = useRef(isLive);

  // Update ref when state changes
  useEffect(() => {
    isLiveRef.current = isLive;
  }, [isLive]);

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

  useEffect(() => {
    loadSession();
    loadAliveScreenshots();
    loadPlayingStreams();

    // Poll for updates every 2 seconds if active
    const interval = setInterval(() => {
      // Use setSession functional update to check if session is active before polling
      setSession(currentSession => {
        if (currentSession && !currentSession.is_active) {
          clearInterval(interval);
          return currentSession;
        }
        // These calls are async, we can't easily wait for them here, 
        // but loadSession itself will skip if it sees inactive (actually it should be stopped by interval clear)
        loadAliveScreenshots();
        loadPlayingStreams();
        loadSession();
        return currentSession;
      });
    }, 2000);

    return () => clearInterval(interval);
  }, [sessionId]);

  const loadPlayingStreams = async () => {
    try {
      const response = await streamSessionsAPI.getPlayingStreams();
      setPlayingStreamIds(new Set(response.data.playing_stream_ids));
    } catch (err) {
      console.error('Failed to load playing streams:', err);
    }
  };

  const loadSession = async () => {
    try {
      const response = await streamSessionsAPI.getSession(sessionId);
      // Always update to ensure stream stats are refreshed
      // The component uses React.memo and other optimizations to prevent unnecessary re-renders
      setSession(response.data);

      // Handle inactive sessions
      if (!response.data.is_active) {
        setIsLive(false);
        // Find latest timestamp to set as cursor
        let maxTime = response.data.created_at || 0;
        if (response.data.streams) {
          response.data.streams.forEach(s => {
            if (s.metrics_history && s.metrics_history.length > 0) {
              const last = s.metrics_history[s.metrics_history.length - 1];
              if (last.timestamp > maxTime) maxTime = last.timestamp;
            }
          });
        }
        // Only update cursor if we haven't set it yet or if we were live
        if (isLiveRef.current || cursorTime === null) {
          setCursorTime(maxTime);
        }
      } else {
        // Update cursor if live, utilizing the ref to avoid stale closures in interval
        if (isLiveRef.current) {
          setCursorTime(Math.floor(Date.now() / 1000));
        }
      }

      setLoading(false);
    } catch (err) {
      console.error('Failed to load session:', err);
      // Suppress toast if we already have session data (session exists and we are just refreshing)
      if (!session) {
        toast({
          title: 'Error',
          description: 'Failed to load session details',
          variant: 'destructive'
        });
      }
      setLoading(false);
    }
  };

  const handleTimeChange = (newTime) => {
    setCursorTime(newTime);
    setIsLive(false);
  };

  const handleLiveClick = () => {
    setIsLive(true);
    if (session) {
      setCursorTime(Math.floor(Date.now() / 1000));
    }
  };

  const loadAliveScreenshots = async () => {
    try {
      const response = await streamSessionsAPI.getAliveScreenshots(sessionId);
      // Only update if screenshots array changed
      setAliveScreenshots(prevScreenshots => {
        const newScreenshots = response.data.screenshots || [];

        // Quick length check first
        if (prevScreenshots.length !== newScreenshots.length) {
          return newScreenshots;
        }

        // Check if screenshot URLs or stream IDs changed
        const hasChanged = newScreenshots.some((newShot, idx) => {
          const prevShot = prevScreenshots[idx];
          return !prevShot ||
            prevShot.stream_id !== newShot.stream_id ||
            prevShot.screenshot_url !== newShot.screenshot_url;
        });

        return hasChanged ? newScreenshots : prevScreenshots;
      });
    } catch (err) {
      console.error('Failed to load screenshots:', err);
    }
  };

  const handleViewScreenshot = (stream) => {
    setSelectedStream(stream);
    setScreenshotDialogOpen(true);
  };

  const handleQuarantineStream = async (streamId) => {
    try {
      await streamSessionsAPI.quarantineStream(sessionId, streamId);
      toast({
        title: 'Success',
        description: 'Stream quarantined successfully'
      });
      // Reload session to reflect changes
      loadSession();
    } catch (err) {
      console.error('Failed to quarantine stream:', err);
      toast({
        title: 'Error',
        description: 'Failed to quarantine stream',
        variant: 'destructive'
      });
    }
  };

  const handleReviveStream = async (streamId) => {
    try {
      await streamSessionsAPI.reviveStream(sessionId, streamId);
      toast({
        title: 'Success',
        description: 'Stream revived successfully (moved to Under Review)'
      });
      loadSession();
    } catch (err) {
      console.error('Failed to revive stream:', err);
      toast({
        title: 'Error',
        description: 'Failed to revive stream',
        variant: 'destructive'
      });
    }
  };

  /* Filter streams based on cursor time */
  const currentStreams = useMemo(() => {
    if (!session || !session.streams) return [];

    // If we have no cursor time yet, use current time
    const time = cursorTime || Math.floor(Date.now() / 1000);

    return session.streams.map(stream => getSnapshotAtTime(stream, time));
  }, [session, cursorTime, isLive]);

  const sortStreams = (a, b) => {
    // If both have rank, use it (ascending: 1 is best)
    if (a.rank !== undefined && a.rank !== null && b.rank !== undefined && b.rank !== null) {
      return a.rank - b.rank;
    }
    // Fallback to reliability score (descending)
    return b.reliability_score - a.reliability_score;
  };

  const stableStreams = currentStreams.filter(s => s.status === 'stable').sort(sortStreams);
  const reviewStreams = currentStreams.filter(s => s.status === 'review').sort(sortStreams);
  const quarantinedStreams = currentStreams.filter(s => s.status === 'quarantined' || s.is_quarantined);
  const activeStreams = [...stableStreams, ...reviewStreams];

  /* Extract significant events for timeline markers */
  const timelineEvents = useMemo(() => {
    if (!session || !session.streams) return [];

    const events = [];
    const streams = session.streams;

    // 1. Stream Status Changes (Quarantine, Promotion)
    streams.forEach(stream => {
      if (!stream.metrics_history || stream.metrics_history.length < 2) return;

      // Iterate history to find status changes
      for (let i = 1; i < stream.metrics_history.length; i++) {
        const prev = stream.metrics_history[i - 1];
        const curr = stream.metrics_history[i];

        // Status change detect
        if (prev.status !== curr.status) {
          // Stable -> Quarantined (Yellow)
          if (curr.status === 'quarantined') {
            events.push({
              time: curr.timestamp,
              type: 'Quarantine',
              description: `${stream.name} quarantined (${curr.reliability_score.toFixed(1)}%)`,
              color: 'yellow'
            });
          }
          // Review -> Stable (Blue)
          else if (prev.status === 'review' && curr.status === 'stable') {
            events.push({
              time: curr.timestamp,
              type: 'Promotion',
              description: `${stream.name} promoted to Stable`,
              color: 'blue'
            });
          }
        }
      }
    });

    // 2. Primary Stream Changes (Green)
    // We need to find when the rank 1 stream changes
    // This requires aggregating all streams at each timestamp, which is expensive.
    // Optimization: Collect all timestamps where any stream has rank 1.
    const rankOneChanges = [];
    const timestamps = new Set();
    streams.forEach(s => {
      s.metrics_history?.forEach(m => timestamps.add(m.timestamp));
    });

    const sortedTimestamps = Array.from(timestamps).sort((a, b) => a - b);
    let lastTopStreamId = null;

    // Sample every few seconds to avoid excessive processing if history is huge
    // But for accuracy in timeline, we should try to be precise.
    // Let's filter to timestamps where a rank change might have occurred (approx)

    // Simpler approach: Iterate through all metrics of all streams, filtering for rank=1
    const rankOneMetrics = [];
    streams.forEach(s => {
      s.metrics_history?.forEach(m => {
        if (m.rank === 1) {
          rankOneMetrics.push({ ...m, stream_id: s.stream_id, stream_name: s.name });
        }
      });
    });

    rankOneMetrics.sort((a, b) => a.timestamp - b.timestamp);

    rankOneMetrics.forEach(metric => {
      if (lastTopStreamId !== metric.stream_id) {
        if (lastTopStreamId !== null) {
          events.push({
            time: metric.timestamp,
            type: 'Order Change',
            description: `Primary Stream changed to ${metric.stream_name}`,
            color: 'green'
          });
        }
        lastTopStreamId = metric.stream_id;
      }
    });

    return events;
  }, [session]);

  const minTime = useMemo(() => {
    // Find earliest metric or session start
    if (!session) return 0;
    let min = session.created_at || 0;
    if (session.streams) {
      session.streams.forEach(s => {
        if (s.metrics_history && s.metrics_history.length > 0) {
          if (s.metrics_history[0].timestamp < min) min = s.metrics_history[0].timestamp;
        }
      });
    }
    return min;
  }, [session]);

  const maxTime = useMemo(() => {
    if (!session) return Math.floor(Date.now() / 1000);
    // If active, use current time
    if (session.is_active) return Math.floor(Date.now() / 1000);

    // If inactive, find max timestamp in metrics
    let max = session.created_at || 0;
    if (session.streams) {
      session.streams.forEach(s => {
        if (s.metrics_history && s.metrics_history.length > 0) {
          const last = s.metrics_history[s.metrics_history.length - 1];
          if (last.timestamp > max) max = last.timestamp;
        }
      });
    }
    return max;
  }, [session]);


  if (loading || !session) {
    return (
      <div className="text-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
        <p className="text-muted-foreground">Loading session...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 min-w-0">
      {/* Header with Channel Logo and EPG Info */}
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
            <h1 className="text-3xl font-bold tracking-tight truncate">{session.channel_name}</h1>
            <p className="text-muted-foreground mt-1 truncate">
              Session Monitor - {session.is_active ? 'Active' : 'Inactive'}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {session.is_active && (
            <Button variant="outline" onClick={onStop}>
              <Square className="h-4 w-4 mr-2" />
              Stop Monitoring
            </Button>
          )}
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

      {/* Live Stream Preview */}
      {activeStreams.length > 0 && (
        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>Live Stream Preview</CardTitle>
            <CardDescription>View screenshots and live streams from active streams</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="screenshots" className="w-full">
              <TabsList className="mb-4">
                <TabsTrigger value="screenshots">Screenshots</TabsTrigger>
                <TabsTrigger value="live">Live Streams</TabsTrigger>
              </TabsList>

              <TabsContent value="screenshots" className="mt-0 outline-none">
                {aliveScreenshots.length > 0 ? (
                  <div className="w-full relative overflow-hidden">
                    <div className="overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-gray-400 scrollbar-track-gray-200 dark:scrollbar-thumb-gray-600 dark:scrollbar-track-gray-800" style={{ maxWidth: 'calc(100vw - 400px)' }}>
                      <div className="flex gap-4 pb-4">
                        {aliveScreenshots.map((screenshot) => (
                          <div key={screenshot.stream_id} className="flex-none w-80">
                            <Card>
                              <CardContent className="p-4">
                                <div className="aspect-video bg-black rounded-md overflow-hidden mb-3">
                                  <img
                                    src={screenshot.screenshot_url}
                                    alt={screenshot.stream_name}
                                    className="w-full h-full object-contain"
                                    onError={(e) => {
                                      e.target.src = FALLBACK_IMAGE_SVG;
                                    }}
                                  />
                                </div>
                                <div className="space-y-1">
                                  <p className="font-medium text-sm truncate" title={screenshot.stream_name}>
                                    {screenshot.stream_name}
                                  </p>
                                  <p className="text-xs text-muted-foreground">
                                    Stream ID: {screenshot.stream_id}
                                  </p>
                                </div>
                              </CardContent>
                            </Card>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <ImageIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                    <p className="text-muted-foreground">No screenshots available yet</p>
                  </div>
                )}
              </TabsContent>

              <TabsContent value="live">
                <LiveStreamsGrid streams={activeStreams} sessionId={sessionId} />
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <StatsCard
          title="Total Streams"
          value={session.streams.length}
          icon={Activity}
        />
        <StatsCard
          title="Active Streams"
          value={activeStreams.length}
          icon={Activity}
          variant="success"
        />
        <StatsCard
          title="Quarantined"
          value={quarantinedStreams.length}
          icon={AlertCircle}
          variant="warning"
        />
        <StatsCard
          title="Avg Reliability"
          value={calculateAverageScore(activeStreams)}
          suffix="%"
          icon={Activity}
        />
      </div>

      {/* Streams Tables */}
      <Tabs defaultValue="stable" className="w-full">
        <TabsList>
          <TabsTrigger value="stable">
            Stable ({stableStreams.length})
          </TabsTrigger>
          <TabsTrigger value="review">
            Under Review ({reviewStreams.length})
          </TabsTrigger>
          <TabsTrigger value="quarantined">
            Quarantined ({quarantinedStreams.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="stable">
          <Card>
            <CardHeader>
              <CardTitle>Stable Streams</CardTitle>
              <CardDescription>
                Streams that have passed review and are considered reliable.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {stableStreams.length === 0 ? (
                <div className="text-center py-12">
                  <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">No stable streams</p>
                </div>
              ) : (
                <StreamsTable
                  streams={stableStreams}
                  sessionId={sessionId}
                  onQuarantine={handleQuarantineStream}
                  playingStreamIds={playingStreamIds}
                  cursorTime={cursorTime}

                  isLive={isLive}
                  zoomLevel={zoomLevel}
                  adPeriods={session?.ad_periods || []}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="review">
          <Card>
            <CardHeader>
              <CardTitle>Under Review</CardTitle>
              <CardDescription>
                New or revived streams being monitored for reliability before becoming stable.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {reviewStreams.length === 0 ? (
                <div className="text-center py-12">
                  <Activity className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">No streams under review</p>
                </div>
              ) : (
                <StreamsTable
                  streams={reviewStreams}
                  sessionId={sessionId}
                  onQuarantine={handleQuarantineStream}
                  playingStreamIds={playingStreamIds}
                  cursorTime={cursorTime}
                  isLive={isLive}
                  zoomLevel={zoomLevel}
                  isReview
                  adPeriods={session?.ad_periods || []}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="quarantined">
          <Card>
            <CardHeader>
              <CardTitle>Quarantined Streams</CardTitle>
              <CardDescription>
                Streams that failed quality checks or are dead. They will be retried automatically after a cooldown.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {quarantinedStreams.length === 0 ? (
                <div className="text-center py-12">
                  <Activity className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">No quarantined streams</p>
                </div>
              ) : (
                <StreamsTable
                  streams={quarantinedStreams}
                  sessionId={sessionId}
                  showQuarantined
                  onRevive={handleReviveStream}
                  adPeriods={session?.ad_periods || []}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Timeline Control */}
      {
        session && (
          <TimelineControl
            minTime={minTime}
            maxTime={maxTime}
            currentTime={cursorTime || maxTime}
            onTimeChange={handleTimeChange}
            isLive={isLive}
            onLiveClick={handleLiveClick}
            events={timelineEvents}
            streams={session.streams || []}
            zoomLevel={zoomLevel}
            onZoomChange={setZoomLevel}
          />
        )
      }
    </div >
  );
}

// Stats Card Component
function StatsCard({ title, value, suffix = '', icon: Icon, variant = 'default' }) {
  const variantColors = {
    default: 'text-foreground',
    success: 'text-green-600 dark:text-green-400',
    warning: 'text-yellow-600 dark:text-yellow-400',
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${variantColors[variant]}`}>
          {value}{suffix}
        </div>
      </CardContent>
    </Card>
  );
}

// Streams Table Component
function StreamsTable({ streams, sessionId, onQuarantine, onRevive, playingStreamIds = new Set(), showQuarantined = false, isReview = false, cursorTime, isLive, zoomLevel, adPeriods = [] }) {
  const formatQuality = (stream) => {
    if (!stream.width || !stream.height) return 'Unknown';
    return `${stream.width}x${stream.height}`;
  };

  const formatBitrate = (bitrate) => {
    if (!bitrate) return 'N/A';
    if (bitrate >= 1000) {
      return `${(bitrate / 1000).toFixed(1)} Mbps`;
    }
    return `${bitrate} kbps`;
  };

  const formatTimeRemaining = (seconds) => {
    if (seconds === undefined || seconds === null) return '-';
    if (seconds <= 0) return 'Stable soon';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">#</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Quality</TableHead>
            <TableHead>FPS</TableHead>
            <TableHead>Speed</TableHead>
            <TableHead>Bitrate</TableHead>
            <TableHead>Logo Verify</TableHead>
            {!showQuarantined ? (
              <>
                <TableHead>Reliability</TableHead>
                {isReview && <TableHead>Time into Stable</TableHead>}
                <TableHead>Actions</TableHead>
              </>
            ) : (
              <>
                <TableHead>Score</TableHead>
                <TableHead>Actions</TableHead>
              </>
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {streams.map((stream, index) => (
            <React.Fragment key={stream.stream_id}>
              <TableRow>
                <TableCell className="font-medium">{index + 1}</TableCell>
                <TableCell className="max-w-xs">
                  <div className="flex items-center gap-2">
                    <span className="truncate" title={stream.name}>
                      {stream.name}
                    </span>
                    {playingStreamIds.has(stream.stream_id) && (
                      <div className="flex items-center justify-center bg-green-100 dark:bg-green-900/30 p-1 rounded-full" title="Broadcasting">
                        <Radio className="h-3 w-3 text-green-600 dark:text-green-400" />
                      </div>
                    )}
                    {stream.status === 'quarantined' && (
                      <Badge variant="destructive" className="text-[10px] px-1 py-0 h-4 uppercase font-bold">
                        Dead
                      </Badge>
                    )}
                    {(stream.status === 'review' || stream.status === 'quarantined') && stream.status_reason === 'looping' && (
                      <Badge variant="outline" className="bg-yellow-500/10 text-yellow-600 border-yellow-500/20 text-[10px] px-1 py-0 h-4 uppercase font-bold">
                        Looping {stream.loop_duration ? `(${stream.loop_duration.toFixed(1)}s)` : ''}
                      </Badge>
                    )}
                    {stream.status === 'quarantined' && stream.status_reason === 'logo-mismatch' && (
                      <Badge variant="outline" className="bg-red-500/10 text-red-600 border-red-500/20 text-[10px] px-2 h-5 uppercase font-bold">
                        Logo Mismatch
                      </Badge>
                    )}
                  </div>
                  {stream.status === 'quarantined' && stream.status_reason === 'logo-mismatch' && stream.screenshot_url && (
                    <div className="mt-2 text-xs text-muted-foreground">
                      <p className="mb-1">Last seen:</p>
                      <div className="w-24 aspect-video bg-black rounded overflow-hidden">
                        <img
                          src={stream.screenshot_url}
                          alt="Logo mismatch screenshot"
                          className="w-full h-full object-contain cursor-pointer transition-transform hover:scale-105"
                          onClick={() => window.open(stream.screenshot_url, '_blank')}
                        />
                      </div>
                    </div>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <span>{formatQuality(stream)}</span>
                    {stream.hdr_format && (
                      <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20 text-xs px-2 py-0 h-5">
                        {stream.hdr_format}
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell>{stream.fps ? `${stream.fps.toFixed(0)} fps` : 'N/A'}</TableCell>
                <TableCell>
                  <span className={`font-mono ${(stream.speed || stream.current_speed || 0) < 0.9 ? 'text-orange-500' : 'text-green-500'}`}>
                    {(stream.speed || stream.current_speed || 0).toFixed(2)}x
                  </span>
                </TableCell>
                <TableCell>{formatBitrate(stream.bitrate)}</TableCell>
                <TableCell>
                  <div className="flex flex-col gap-1">
                    <Badge
                      variant="outline"
                      className={`text-[10px] px-2 h-5 uppercase font-bold flex items-center justify-center leading-none ${stream.display_logo_status === 'SUCCESS' ? 'bg-green-500/10 text-green-600 border-green-500/20' :
                        stream.display_logo_status === 'FAILED' ? 'bg-red-500/10 text-red-600 border-red-500/20' :
                          'bg-gray-500/10 text-gray-600 border-gray-500/20'
                        }`}
                    >
                      <span className="mt-[0.5px]">{stream.display_logo_status || 'PENDING'}</span>
                    </Badge>
                    {stream.consecutive_logo_misses > 0 && (
                      <span className="text-[10px] text-red-500 font-medium">
                        Misses: {stream.consecutive_logo_misses}
                      </span>
                    )}
                  </div>
                </TableCell>
                {!showQuarantined && (
                  <>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Progress
                          value={stream.reliability_score}
                          className="w-20 h-2"
                        />
                        <span className="text-sm font-medium">
                          {stream.reliability_score.toFixed(1)}
                        </span>
                      </div>
                    </TableCell>
                    {isReview && (
                      <TableCell>
                        <div className="flex items-center gap-2 text-blue-600 dark:text-blue-400 font-medium">
                          <Clock className="h-4 w-4" />
                          {formatTimeRemaining(stream.review_time_remaining)}
                        </div>
                      </TableCell>
                    )}
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          size="icon"
                          variant="outline"
                          onClick={() => onQuarantine(stream.stream_id)}
                          className="h-8 w-8 text-orange-600 hover:text-orange-700 hover:bg-orange-50 dark:hover:bg-orange-950"
                          title="Quarantine"
                        >
                          <Ban className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </>
                )}
                {showQuarantined && onRevive && (
                  <>
                    <TableCell>
                      <span className="text-sm text-muted-foreground">
                        Score: {stream.reliability_score.toFixed(1)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onRevive(stream.stream_id)}
                      >
                        <Activity className="h-3 w-3 mr-1" />
                        Revive
                      </Button>
                    </TableCell>
                  </>
                )}
              </TableRow>
              {!showQuarantined && (
                <TableRow>
                  <TableCell colSpan={10} className="bg-muted/30 p-2">
                    <SpeedMetricsChart sessionId={sessionId} streamId={stream.stream_id} cursorTime={cursorTime} isLive={isLive} zoomLevel={zoomLevel} adPeriods={adPeriods} />
                  </TableCell>
                </TableRow>
              )}
            </React.Fragment>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

// Speed Metrics Chart Component
function SpeedMetricsChart({ sessionId, streamId, cursorTime, isLive, zoomLevel, adPeriods }) {
  const [allMetrics, setAllMetrics] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMetrics();

    // Refresh metrics every 5 seconds
    const interval = setInterval(loadMetrics, 5000);
    return () => clearInterval(interval);
  }, [sessionId, streamId]);

  const loadMetrics = async () => {
    try {
      const response = await streamSessionsAPI.getStreamMetrics(sessionId, streamId);
      setAllMetrics(response.data?.metrics || []);
      setLoading(false);
    } catch (err) {
      console.error('Failed to load metrics:', err);
      setLoading(false);
    }
  };

  // Determine the reference time (end of the visible window)
  const referenceTime = useMemo(() => {
    if (isLive) {
      const lastMetric = allMetrics[allMetrics.length - 1];
      return lastMetric ? lastMetric.timestamp : Math.floor(Date.now() / 1000);
    } else {
      // In history mode, use cursor time or fallback to latest metric
      if (cursorTime) return cursorTime;
      const lastMetric = allMetrics[allMetrics.length - 1];
      return lastMetric ? lastMetric.timestamp : Math.floor(Date.now() / 1000);
    }
  }, [allMetrics, cursorTime, isLive]);

  const endTimestamp = Math.ceil(referenceTime);
  const startTime = referenceTime - zoomLevel;

  const chartData = useMemo(() => {
    if (!allMetrics.length) return [];

    return allMetrics.filter(m =>
      m.timestamp >= startTime && m.timestamp <= endTimestamp
    ).map((metric) => {
      // Timestamp is in Unix seconds, convert to milliseconds for JavaScript Date
      const date = new Date(metric.timestamp * 1000);
      // Format as HH:MM:SS for better granularity
      const hours = date.getHours().toString().padStart(2, '0');
      const minutes = date.getMinutes().toString().padStart(2, '0');
      const seconds = date.getSeconds().toString().padStart(2, '0');
      // Map quarantined streams to negative zones
      let displaySpeed = metric.speed || 0;
      if (metric.status === 'quarantined') {
        if (metric.status_reason === 'logo-mismatch') displaySpeed = -1.0;
        else if (metric.status_reason === 'looping') displaySpeed = -2.0;
        else displaySpeed = -3.0; // Default dead
      }

      return {
        time: `${hours}:${minutes}:${seconds}`,
        speed: displaySpeed,
        timestamp: metric.timestamp, // Keep original for reference
      };
    });
  }, [allMetrics, startTime, endTimestamp]);

  const formatTime = (ts) => {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  if (loading) {
    return (
      <div className="h-24 flex items-center justify-center text-muted-foreground text-sm">
        Loading metrics...
      </div>
    );
  }

  // If we have no metrics AT ALL for this stream (never recorded)
  if (allMetrics.length === 0) {
    return (
      <div className="h-24 flex items-center justify-center text-muted-foreground text-sm">
        No metrics recorded
      </div>
    );
  }

  // If we have metrics but none in the current view (Gap in data)
  if (chartData.length === 0) {
    return (
      <div className="h-24 flex flex-col items-center justify-center text-muted-foreground text-sm">
        <span>No data in this time range</span>
        <span className="text-xs opacity-70">
          ({formatTime(startTime)} - {formatTime(endTimestamp)})
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="text-xs text-muted-foreground font-medium px-2">FFmpeg Speed</div>
      <ResponsiveContainer width="100%" height={80}>
        <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis
            dataKey="timestamp"
            tickFormatter={formatTime}
            tick={{ fontSize: 10 }}
            domain={[startTime, endTimestamp]}
            type="number"
            interval="preserveStartEnd"
          />
          <YAxis
            tickFormatter={(value) => {
              if (value === -1) return "Logo";
              if (value === -2) return "Loop";
              if (value === -3) return "Dead";
              if (value < 0) return "";
              return value;
            }}
            tick={{ fontSize: 10 }}
            width={35}
            domain={[-3.5, 'auto']}
            ticks={[-3, -2, -1, 0, 1, 2, 3]}
          />
          <RechartsTooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--background))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '6px',
              fontSize: '12px'
            }}
            labelFormatter={(value) => formatTime(value)}
            formatter={(value) => {
              if (value === -1.0) return ["Logo Mismatch", "Quarantine Reason"];
              if (value === -2.0) return ["Looping", "Quarantine Reason"];
              if (value <= -3.0) return ["Dead", "Quarantine Reason"];
              return [`${value.toFixed(2)}x`, 'Speed'];
            }}
          />
          {adPeriods && adPeriods.map((period, idx) => (
            <ReferenceArea
              key={idx}
              x1={period.start}
              x2={period.end || endTimestamp}
              fill="#f97316"
              opacity={0.15}
            />
          ))}
          <Line
            type="stepAfter"
            dataKey="speed"
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            dot={false}
            animationDuration={300}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// Screenshot Dialog Component  
// LiveStreamsGrid Component with mpegts.js support
function LiveStreamsGrid({ streams, sessionId }) {
  const [mpegtsLib, setMpegtsLib] = React.useState(null);
  const [loading, setLoading] = React.useState(true);

  useEffect(() => {
    // Import mpegts.js once for all stream players
    const loadMpegts = async () => {
      try {
        const mpegts = await import('mpegts.js');
        if (!mpegts.default.isSupported()) {
          console.error('Browser does not support MPEG-TS playback');
        }
        setMpegtsLib(mpegts.default);
        setLoading(false);
      } catch (err) {
        console.error('Failed to load mpegts.js:', err);
        setLoading(false);
      }
    };

    loadMpegts();
  }, []);

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
        <p className="text-muted-foreground">Loading stream player...</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {streams.map((stream) => (
        <LiveStreamPlayer key={stream.stream_id} stream={stream} mpegtsLib={mpegtsLib} />
      ))}
    </div>
  );
}

// Live Stream Player Component using mpegts.js
function LiveStreamPlayer({ stream, mpegtsLib }) {
  const videoRef = React.useRef(null);
  const playerRef = React.useRef(null);
  const [streamUrl, setStreamUrl] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [isMuted, setIsMuted] = React.useState(true);
  const [retryKey, setRetryKey] = React.useState(0);
  const { toast } = useToast();

  // Helper function to clean up player instance
  const cleanupPlayer = React.useCallback(() => {
    if (playerRef.current) {
      try {
        playerRef.current.destroy();
      } catch (err) {
        console.error('Error destroying player:', err);
      }
      playerRef.current = null;
    }
  }, []);

  useEffect(() => {
    // Load stream URL
    const loadStreamUrl = async () => {
      try {
        const response = await streamSessionsAPI.getStreamViewerUrl(stream.stream_id);
        if (response.data.success) {
          setStreamUrl(response.data.stream_url);
          setLoading(false);
        } else {
          setError(response.data.error || 'Failed to get stream URL');
          setLoading(false);
        }
      } catch (err) {
        console.error('Failed to get stream URL:', err);
        setError('Failed to load stream');
        setLoading(false);
      }
    };

    loadStreamUrl();
  }, [stream.stream_id]);

  useEffect(() => {
    // Initialize mpegts.js player when stream URL is available
    if (!streamUrl || !videoRef.current || !mpegtsLib) return;

    const initPlayer = async () => {
      try {
        // Clean up any existing player before creating a new one
        cleanupPlayer();

        if (!mpegtsLib.isSupported()) {
          setError('Your browser does not support MPEG-TS playback');
          return;
        }

        // Create player
        const player = mpegtsLib.createPlayer({
          type: 'mpegts',
          url: streamUrl,
          isLive: true,
        }, {
          enableWorker: true,
          lazyLoadMaxDuration: 3 * 60,
          seekType: 'range',
        });

        player.attachMediaElement(videoRef.current);
        player.load();

        // Auto-play the stream
        player.play().catch(err => {
          console.warn('Autoplay blocked by browser - user interaction required. Click the video or unmute button to start playback:', err);
        });

        // Handle errors with retry capability
        player.on(mpegtsLib.Events.ERROR, (errorType, errorDetail, errorInfo) => {
          console.error('mpegts.js error:', errorType, errorDetail, errorInfo);
          setError('Stream playback error');

          // Clean up the failed player
          cleanupPlayer();
        });

        playerRef.current = player;
      } catch (err) {
        console.error('Failed to initialize mpegts.js:', err);
        setError('Failed to initialize player');
      }
    };

    initPlayer();

    // Cleanup on unmount or when dependencies change
    return cleanupPlayer;
  }, [streamUrl, mpegtsLib, retryKey]);

  const handleRetry = () => {
    setError(null);
    setRetryKey(prev => prev + 1);
  };

  const formatQuality = () => {
    if (!stream.width || !stream.height) return 'Unknown';
    return `${stream.width}x${stream.height}`;
  };

  const formatBitrate = () => {
    if (!stream.bitrate) return 'N/A';
    if (stream.bitrate >= 1000) {
      return `${(stream.bitrate / 1000).toFixed(1)} Mbps`;
    }
    return `${stream.bitrate} kbps`;
  };

  const handleToggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  return (
    <Card>
      <CardContent className="p-4">
        <div className="aspect-video bg-black rounded-md overflow-hidden mb-3 relative">
          {loading ? (
            <div className="w-full h-full flex items-center justify-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            </div>
          ) : error ? (
            <div className="w-full h-full flex flex-col items-center justify-center text-destructive">
              <div className="text-center p-4">
                <AlertCircle className="h-12 w-12 mx-auto mb-2" />
                <p className="text-sm mb-3">{error}</p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleRetry}
                  className="text-sm"
                >
                  Retry
                </Button>
              </div>
            </div>
          ) : (
            <>
              <video
                ref={videoRef}
                muted={isMuted}
                playsInline
                className="w-full h-full object-contain [&::-webkit-media-controls]:hidden [&::-webkit-media-controls-enclosure]:hidden"
              />
              <Button
                size="sm"
                variant="secondary"
                className="absolute top-2 right-2 opacity-80 hover:opacity-100"
                onClick={handleToggleMute}
              >
                {isMuted ? (
                  <VolumeX className="h-4 w-4" />
                ) : (
                  <Volume2 className="h-4 w-4" />
                )}
              </Button>
            </>
          )}
        </div>
        <div className="space-y-2">
          <p className="font-medium text-sm truncate" title={stream.name}>
            {stream.name}
          </p>
          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            <div>
              <span className="font-medium">Quality:</span> {formatQuality()}
            </div>
            <div>
              <span className="font-medium">FPS:</span> {stream.fps ? `${stream.fps.toFixed(1)}` : 'N/A'}
            </div>
            <div>
              <span className="font-medium">Bitrate:</span> {formatBitrate()}
            </div>
            <div>
              <span className="font-medium">Score:</span> {stream.reliability_score.toFixed(1)}%
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Helper function
function calculateAverageScore(streams) {
  if (streams.length === 0) return 0;
  const sum = streams.reduce((acc, s) => acc + (s.reliability_score || 0), 0);
  return (sum / streams.length).toFixed(1);
}

export default SessionMonitorView;
