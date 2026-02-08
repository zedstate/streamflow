import { useState, useEffect } from 'react';
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
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';

// Constants
const FALLBACK_IMAGE_SVG = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 225"%3E%3Crect fill="%23111" width="400" height="225"/%3E%3Ctext fill="%23666" x="50%25" y="50%25" text-anchor="middle" dominant-baseline="middle" font-family="sans-serif"%3ENo Image%3C/text%3E%3C/svg%3E';
const CHANNEL_LOGO_PREFIX = 'streamflow_channel_logo_';

function SessionMonitorView({ sessionId, onBack, onStop }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [aliveScreenshots, setAliveScreenshots] = useState([]);
  const [logoUrl, setLogoUrl] = useState(null);
  const [playingStreamIds, setPlayingStreamIds] = useState(new Set());
  const { toast } = useToast();

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

    // Poll for updates every 2 seconds
    const interval = setInterval(() => {
      loadSession();
      loadAliveScreenshots();
      loadPlayingStreams();
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
      setLoading(false);
    } catch (err) {
      console.error('Failed to load session:', err);
      toast({
        title: 'Error',
        description: 'Failed to load session details',
        variant: 'destructive'
      });
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

  if (loading || !session) {
    return (
      <div className="text-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
        <p className="text-muted-foreground">Loading session...</p>
      </div>
    );
  }

  /* New logic: filter by status string */
  const stableStreams = session.streams.filter(s => s.status === 'stable');
  const reviewStreams = session.streams.filter(s => s.status === 'review');
  const quarantinedStreams = session.streams.filter(s => s.status === 'quarantined' || s.is_quarantined); // fallback for mixed data

  // Provide a combined list for specific "All Active" logic if needed, but tabs are better
  const activeStreams = [...stableStreams, ...reviewStreams];

  return (
    <div className="space-y-6">
      {/* Header with Channel Logo and EPG Info */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
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
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{session.channel_name}</h1>
            <p className="text-muted-foreground mt-1">
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
        <Card>
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

              <TabsContent value="screenshots">
                {aliveScreenshots.length > 0 ? (
                  <div className="overflow-x-auto scrollbar-thin scrollbar-thumb-gray-400 scrollbar-track-gray-200 dark:scrollbar-thumb-gray-600 dark:scrollbar-track-gray-800">
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
                  isReview
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
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
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
function StreamsTable({ streams, sessionId, onQuarantine, onRevive, playingStreamIds = new Set(), showQuarantined = false, isReview = false }) {
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
            <TableHead>Bitrate</TableHead>
            {!showQuarantined && (
              <>
                <TableHead>Reliability</TableHead>
                {isReview && <TableHead>Time into Stable</TableHead>}
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
                  </div>
                </TableCell>
                <TableCell>{formatQuality(stream)}</TableCell>
                <TableCell>{stream.fps ? `${stream.fps.toFixed(1)} fps` : 'N/A'}</TableCell>
                <TableCell>{formatBitrate(stream.bitrate)}</TableCell>
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
                          size="sm"
                          variant="outline"
                          onClick={() => onQuarantine(stream.stream_id)}
                          className="text-orange-600 hover:text-orange-700 hover:bg-orange-50 dark:hover:bg-orange-950"
                        >
                          <Ban className="h-3 w-3 mr-1" />
                          Quarantine
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
                  <TableCell colSpan={8} className="bg-muted/30 p-2">
                    <SpeedMetricsChart sessionId={sessionId} streamId={stream.stream_id} />
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
function SpeedMetricsChart({ sessionId, streamId }) {
  const [metrics, setMetrics] = useState([]);
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
      const metricsData = response.data?.metrics || [];

      // Transform metrics data for the chart
      const chartData = metricsData.map((metric) => {
        // Timestamp is in Unix seconds, convert to milliseconds for JavaScript Date
        const date = new Date(metric.timestamp * 1000);
        // Format as HH:MM:SS for better granularity
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        const seconds = date.getSeconds().toString().padStart(2, '0');
        return {
          time: `${hours}:${minutes}:${seconds}`,
          speed: metric.speed || 0,
          timestamp: metric.timestamp, // Keep original for reference
        };
      }).slice(-20); // Keep last 20 data points

      setMetrics(chartData);
      setLoading(false);
    } catch (err) {
      console.error('Failed to load metrics:', err);
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="h-24 flex items-center justify-center text-muted-foreground text-sm">
        Loading metrics...
      </div>
    );
  }

  if (metrics.length === 0) {
    return (
      <div className="h-24 flex items-center justify-center text-muted-foreground text-sm">
        No metrics data available
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="text-xs text-muted-foreground font-medium px-2">FFmpeg Speed</div>
      <ResponsiveContainer width="100%" height={80}>
        <LineChart data={metrics} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 10 }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 10 }}
            width={30}
            domain={[0, 'auto']}
          />
          <RechartsTooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--background))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '6px',
              fontSize: '12px'
            }}
            formatter={(value) => [`${value.toFixed(2)}x`, 'Speed']}
          />
          <Line
            type="monotone"
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
