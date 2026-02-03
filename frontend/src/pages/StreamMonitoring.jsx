import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play, Square, Trash2, Plus, Activity, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { useToast } from '@/hooks/use-toast';
import { streamSessionsAPI } from '@/services/streamSessions';
import CreateSessionDialog from '@/components/stream-monitoring/CreateSessionDialog';
import SessionMonitorView from '@/components/stream-monitoring/SessionMonitorView';

function StreamMonitoring() {
  const [sessions, setSessions] = useState([]);
  const [activeSessions, setActiveSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState(null);
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const { toast } = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    loadSessions();
    
    // Poll for updates every 5 seconds for active sessions
    const interval = setInterval(() => {
      if (selectedSessionId) {
        // Refresh will happen in SessionMonitorView
      } else {
        loadSessions(false); // Don't show loading on interval refresh
      }
    }, 5000);
    
    return () => clearInterval(interval);
  }, [selectedSessionId]);

  const loadSessions = async (showLoading = true) => {
    try {
      if (showLoading) {
        setLoading(true);
      }
      const [allResponse, activeResponse] = await Promise.all([
        streamSessionsAPI.getSessions(),
        streamSessionsAPI.getSessions('active')
      ]);
      
      setSessions(allResponse.data);
      setActiveSessions(activeResponse.data);
    } catch (err) {
      console.error('Failed to load sessions:', err);
      toast({
        title: 'Error',
        description: 'Failed to load monitoring sessions',
        variant: 'destructive'
      });
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  };

  const handleStartSession = async (sessionId) => {
    try {
      await streamSessionsAPI.startSession(sessionId);
      toast({
        title: 'Success',
        description: 'Session started successfully'
      });
      loadSessions();
    } catch (err) {
      console.error('Failed to start session:', err);
      toast({
        title: 'Error',
        description: 'Failed to start session',
        variant: 'destructive'
      });
    }
  };

  const handleStopSession = async (sessionId) => {
    try {
      await streamSessionsAPI.stopSession(sessionId);
      toast({
        title: 'Success',
        description: 'Session stopped successfully'
      });
      loadSessions();
    } catch (err) {
      console.error('Failed to stop session:', err);
      toast({
        title: 'Error',
        description: 'Failed to stop session',
        variant: 'destructive'
      });
    }
  };

  const handleDeleteSession = async (sessionId) => {
    setSessionToDelete(sessionId);
    setDeleteDialogOpen(true);
  };

  const confirmDeleteSession = async () => {
    if (!sessionToDelete) return;
    
    try {
      await streamSessionsAPI.deleteSession(sessionToDelete);
      toast({
        title: 'Success',
        description: 'Session deleted successfully'
      });
      
      if (selectedSessionId === sessionToDelete) {
        setSelectedSessionId(null);
      }
      
      loadSessions();
    } catch (err) {
      console.error('Failed to delete session:', err);
      toast({
        title: 'Error',
        description: 'Failed to delete session',
        variant: 'destructive'
      });
    } finally {
      setDeleteDialogOpen(false);
      setSessionToDelete(null);
    }
  };

  const handleCreateSession = async (sessionData) => {
    try {
      const response = await streamSessionsAPI.createSession(sessionData);
      toast({
        title: 'Success',
        description: 'Session created successfully'
      });
      setCreateDialogOpen(false);
      loadSessions();
      
      // Optionally auto-start the session
      if (sessionData.autoStart) {
        await handleStartSession(response.data.session_id);
      }
    } catch (err) {
      console.error('Failed to create session:', err);
      toast({
        title: 'Error',
        description: err.response?.data?.error || 'Failed to create session',
        variant: 'destructive'
      });
    }
  };

  const handleViewSession = (sessionId) => {
    setSelectedSessionId(sessionId);
  };

  const handleBackToList = () => {
    setSelectedSessionId(null);
    loadSessions();
  };

  return (
    <>
      {/* If viewing a specific session, show the monitor view */}
      {selectedSessionId ? (
        <SessionMonitorView
          sessionId={selectedSessionId}
          onBack={handleBackToList}
          onStop={() => handleStopSession(selectedSessionId)}
          onDelete={() => handleDeleteSession(selectedSessionId)}
        />
      ) : (
        <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Stream Monitoring</h1>
          <p className="text-muted-foreground mt-2">
            Advanced event-based stream quality monitoring with live reliability scoring
          </p>
        </div>
        <Button onClick={() => setCreateDialogOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          New Session
        </Button>
      </div>

      {/* Info Alert */}
      <Alert>
        <Activity className="h-4 w-4" />
        <AlertDescription>
          Stream monitoring sessions provide continuous quality assessment for live events.
          Streams are tested, scored by reliability, and monitored with screenshots to ensure
          optimal stream selection in Dispatcharr.
        </AlertDescription>
      </Alert>

      {/* Tabs */}
      <Tabs defaultValue="active" className="w-full">
        <TabsList>
          <TabsTrigger value="active">
            Active Sessions ({activeSessions.length})
          </TabsTrigger>
          <TabsTrigger value="all">
            All Sessions ({sessions.length})
          </TabsTrigger>
        </TabsList>

        {/* Active Sessions Tab */}
        <TabsContent value="active" className="space-y-4">
          {loading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
              <p className="text-muted-foreground">Loading sessions...</p>
            </div>
          ) : activeSessions.length === 0 ? (
            <Card>
              <CardContent className="pt-6">
                <div className="text-center py-12">
                  <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-medium mb-2">No Active Sessions</h3>
                  <p className="text-muted-foreground mb-4">
                    Create a new monitoring session to start tracking stream quality
                  </p>
                  <Button onClick={() => setCreateDialogOpen(true)}>
                    <Plus className="h-4 w-4 mr-2" />
                    Create Session
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {activeSessions.map((session) => (
                <SessionCard
                  key={session.session_id}
                  session={session}
                  onView={handleViewSession}
                  onStop={handleStopSession}
                  onDelete={handleDeleteSession}
                />
              ))}
            </div>
          )}
        </TabsContent>

        {/* All Sessions Tab */}
        <TabsContent value="all" className="space-y-4">
          {loading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
              <p className="text-muted-foreground">Loading sessions...</p>
            </div>
          ) : sessions.length === 0 ? (
            <Card>
              <CardContent className="pt-6">
                <div className="text-center py-12">
                  <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-medium mb-2">No Sessions</h3>
                  <p className="text-muted-foreground mb-4">
                    Get started by creating your first monitoring session
                  </p>
                  <Button onClick={() => setCreateDialogOpen(true)}>
                    <Plus className="h-4 w-4 mr-2" />
                    Create Session
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {sessions.map((session) => (
                <SessionCard
                  key={session.session_id}
                  session={session}
                  onView={handleViewSession}
                  onStart={handleStartSession}
                  onStop={handleStopSession}
                  onDelete={handleDeleteSession}
                />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Create Session Dialog */}
      <CreateSessionDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onCreateSession={handleCreateSession}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Session</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this session? This will remove all associated data including metrics and screenshots. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteSession}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
        </div>
      )}
    </>
  );
}

// Session Card Component
function SessionCard({ session, onView, onStart, onStop, onDelete }) {
  const formatDate = (timestamp) => {
    return new Date(timestamp * 1000).toLocaleString();
  };

  return (
    <Card className="hover:shadow-lg transition-shadow cursor-pointer" onClick={() => onView(session.session_id)}>
      <CardHeader>
        <div className="flex justify-between items-start gap-3">
          {/* Channel Logo */}
          {session.channel_logo_url && (
            <div className="flex-shrink-0">
              <img 
                src={session.channel_logo_url} 
                alt={session.channel_name}
                className="h-12 w-12 object-contain rounded-md bg-white/5 p-1"
                onError={(e) => { e.target.style.display = 'none'; }}
              />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <CardTitle className="text-lg">{session.channel_name}</CardTitle>
            {session.epg_event_title && (
              <p className="text-sm font-medium text-primary mt-1 truncate" title={session.epg_event_title}>
                {session.epg_event_title}
              </p>
            )}
            <CardDescription className="mt-1">
              Created {formatDate(session.created_at)}
            </CardDescription>
          </div>
          <Badge variant={session.is_active ? 'default' : 'secondary'} className="flex-shrink-0">
            {session.is_active ? 'Active' : 'Inactive'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {/* Stats */}
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <p className="text-muted-foreground">Total Streams</p>
              <p className="font-medium">{session.stream_count}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Active</p>
              <p className="font-medium">{session.active_streams}</p>
            </div>
          </div>

          {/* Regex Filter */}
          {session.regex_filter && session.regex_filter !== '.*' && (
            <div className="text-sm">
              <p className="text-muted-foreground">Filter</p>
              <p className="font-mono text-xs truncate">{session.regex_filter}</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-2" onClick={(e) => e.stopPropagation()}>
            {session.is_active ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => onStop(session.session_id)}
                className="flex-1"
              >
                <Square className="h-3 w-3 mr-1" />
                Stop
              </Button>
            ) : (
              <Button
                size="sm"
                variant="outline"
                onClick={() => onStart(session.session_id)}
                className="flex-1"
              >
                <Play className="h-3 w-3 mr-1" />
                Start
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={() => onDelete(session.session_id)}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default StreamMonitoring;
