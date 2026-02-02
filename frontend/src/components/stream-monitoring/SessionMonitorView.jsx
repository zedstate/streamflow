import { useState, useEffect } from 'react';
import { ArrowLeft, Square, Trash2, Activity, AlertCircle, Image as ImageIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { useToast } from '@/hooks/use-toast';
import { streamSessionsAPI } from '@/services/streamSessions';

function SessionMonitorView({ sessionId, onBack, onStop, onDelete }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedStream, setSelectedStream] = useState(null);
  const [screenshotDialogOpen, setScreenshotDialogOpen] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadSession();
    
    // Poll for updates every 2 seconds
    const interval = setInterval(() => {
      loadSession();
    }, 2000);
    
    return () => clearInterval(interval);
  }, [sessionId]);

  const loadSession = async () => {
    try {
      const response = await streamSessionsAPI.getSession(sessionId);
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

  const handleViewScreenshot = (stream) => {
    setSelectedStream(stream);
    setScreenshotDialogOpen(true);
  };

  if (loading || !session) {
    return (
      <div className="text-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
        <p className="text-muted-foreground">Loading session...</p>
      </div>
    );
  }

  const activeStreams = session.streams.filter(s => !s.is_quarantined);
  const quarantinedStreams = session.streams.filter(s => s.is_quarantined);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={onBack}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
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
          <Button variant="outline" onClick={onDelete}>
            <Trash2 className="h-4 w-4 mr-2" />
            Delete Session
          </Button>
        </div>
      </div>

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
      <Tabs defaultValue="active" className="w-full">
        <TabsList>
          <TabsTrigger value="active">
            Active Streams ({activeStreams.length})
          </TabsTrigger>
          <TabsTrigger value="quarantined">
            Quarantined ({quarantinedStreams.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="active">
          <Card>
            <CardHeader>
              <CardTitle>Active Streams</CardTitle>
              <CardDescription>
                Streams being continuously monitored with reliability scoring
              </CardDescription>
            </CardHeader>
            <CardContent>
              {activeStreams.length === 0 ? (
                <div className="text-center py-12">
                  <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">No active streams</p>
                </div>
              ) : (
                <StreamsTable
                  streams={activeStreams}
                  onViewScreenshot={handleViewScreenshot}
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
                Streams that failed quality checks and are not being monitored
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
                  onViewScreenshot={handleViewScreenshot}
                  showQuarantined
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Screenshot Dialog */}
      {selectedStream && (
        <ScreenshotDialog
          open={screenshotDialogOpen}
          onOpenChange={setScreenshotDialogOpen}
          stream={selectedStream}
        />
      )}
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
function StreamsTable({ streams, onViewScreenshot, showQuarantined = false }) {
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
                <TableHead>Screenshot</TableHead>
              </>
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {streams.map((stream, index) => (
            <TableRow key={stream.stream_id}>
              <TableCell className="font-medium">{index + 1}</TableCell>
              <TableCell className="max-w-xs truncate" title={stream.name}>
                {stream.name}
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
                  <TableCell>
                    {stream.screenshot_path ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onViewScreenshot(stream)}
                      >
                        <ImageIcon className="h-3 w-3 mr-1" />
                        View
                      </Button>
                    ) : (
                      <span className="text-xs text-muted-foreground">No screenshot</span>
                    )}
                  </TableCell>
                </>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

// Screenshot Dialog Component
function ScreenshotDialog({ open, onOpenChange, stream }) {
  if (!stream) return null;

  const screenshotUrl = streamSessionsAPI.getScreenshotUrl(stream.stream_id);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>{stream.name}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Quality:</span>{' '}
              <span className="font-medium">{stream.width}x{stream.height}</span>
            </div>
            <div>
              <span className="text-muted-foreground">FPS:</span>{' '}
              <span className="font-medium">{stream.fps?.toFixed(1) || 'N/A'}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Bitrate:</span>{' '}
              <span className="font-medium">
                {stream.bitrate ? `${(stream.bitrate / 1000).toFixed(1)} Mbps` : 'N/A'}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Reliability:</span>{' '}
              <span className="font-medium">{stream.reliability_score.toFixed(1)}%</span>
            </div>
          </div>
          
          <div className="bg-black rounded-lg overflow-hidden">
            <img
              src={screenshotUrl}
              alt="Stream screenshot"
              className="w-full h-auto"
              onError={(e) => {
                e.target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="100" height="100"%3E%3Crect fill="%23ddd" width="100" height="100"/%3E%3Ctext fill="%23999" x="50%25" y="50%25" text-anchor="middle" dominant-baseline="middle"%3ENo Image%3C/text%3E%3C/svg%3E';
              }}
            />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Helper function
function calculateAverageScore(streams) {
  if (streams.length === 0) return 0;
  const sum = streams.reduce((acc, s) => acc + (s.reliability_score || 0), 0);
  return (sum / streams.length).toFixed(1);
}

export default SessionMonitorView;
