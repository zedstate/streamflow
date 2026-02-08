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

  const [selectedSessions, setSelectedSessions] = useState(new Set());

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

      // Remove from selection if deleted
      if (selectedSessions.has(sessionToDelete)) {
        const newSelected = new Set(selectedSessions);
        newSelected.delete(sessionToDelete);
        setSelectedSessions(newSelected);
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
      if (sessionData.group_id) {
        // Group Monitoring
        const response = await streamSessionsAPI.createGroupSession(sessionData);
        toast({
          title: 'Success',
          description: response.data.message || `Started sessions for group`
        });

        // Show any errors if partial success
        if (response.data.errors && response.data.errors.length > 0) {
          toast({
            title: 'Warning',
            description: `Some sessions failed to start: ${response.data.errors[0]}`,
            variant: 'warning'
          });
        }
      } else {
        // Single Channel Monitoring
        const response = await streamSessionsAPI.createSession(sessionData);
        toast({
          title: 'Success',
          description: 'Session created successfully'
        });

        // Optionally auto-start the session
        if (sessionData.autoStart) {
          await handleStartSession(response.data.session_id);
        }
      }

      setCreateDialogOpen(false);
      loadSessions();
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

  // Batch Operations
  const toggleSelection = (sessionId) => {
    const newSelected = new Set(selectedSessions);
    if (newSelected.has(sessionId)) {
      newSelected.delete(sessionId);
    } else {
      newSelected.add(sessionId);
    }
    setSelectedSessions(newSelected);
  };

  const toggleSelectAll = (filteredSessions) => {
    if (selectedSessions.size === filteredSessions.length && filteredSessions.length > 0) {
      // Deselect all
      setSelectedSessions(new Set());
    } else {
      // Select all visible
      const newSelected = new Set();
      filteredSessions.forEach(s => newSelected.add(s.session_id));
      setSelectedSessions(newSelected);
    }
  };

  const handleBatchStop = async () => {
    if (selectedSessions.size === 0) return;

    try {
      const sessionIds = Array.from(selectedSessions);
      await streamSessionsAPI.batchStopSessions(sessionIds);
      toast({
        title: 'Batch Operation',
        description: `Stopped ${selectedSessions.size} sessions`
      });
      loadSessions();
      setSelectedSessions(new Set());
    } catch (err) {
      console.error('Batch stop failed:', err);
      toast({
        title: 'Error',
        description: 'Failed to stop selected sessions',
        variant: 'destructive'
      });
    }
  };

  const handleBatchDelete = async () => {
    if (selectedSessions.size === 0) return;

    if (!window.confirm(`Are you sure you want to delete ${selectedSessions.size} sessions? This cannot be undone.`)) {
      return;
    }

    try {
      const sessionIds = Array.from(selectedSessions);
      await streamSessionsAPI.batchDeleteSessions(sessionIds);
      toast({
        title: 'Batch Operation',
        description: `Deleted ${selectedSessions.size} sessions`
      });
      loadSessions();
      setSelectedSessions(new Set());
    } catch (err) {
      console.error('Batch delete failed:', err);
      toast({
        title: 'Error',
        description: 'Failed to delete selected sessions',
        variant: 'destructive'
      });
    }
  };

  return (
    <>
      {/* If viewing a specific session, show the monitor view */}
      {selectedSessionId ? (
        <SessionMonitorView
          sessionId={selectedSessionId}
          onBack={handleBackToList}
          onStop={() => handleStopSession(selectedSessionId)}
        />
      ) : (
        <div className="space-y-6 relative pb-20">
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
            <div className="flex justify-between items-center mb-4">
              <TabsList>
                <TabsTrigger value="active">
                  Active Sessions ({activeSessions.length})
                </TabsTrigger>
                <TabsTrigger value="all">
                  All Sessions ({sessions.length})
                </TabsTrigger>
              </TabsList>

              {/* Select All Button */}
              {((sessions.length > 0)) && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    // Logic depends on active tab, but for simplicity we can just clear if any selected,
                    // or maybe disabled this button. 
                    // Better approach: Let individual tabs render select all logic or handle it generically?
                    // Let's keep it simple: Select All is contextual?
                    // Actually, simpler implementation: Just clear selection if any.
                    if (selectedSessions.size > 0) {
                      setSelectedSessions(new Set());
                    }
                  }}
                  disabled={selectedSessions.size === 0}
                >
                  {selectedSessions.size > 0 ? `Deselect All (${selectedSessions.size})` : 'Select Items'}
                </Button>
              )}
            </div>

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
                <>
                  <div className="flex justify-end mb-2">
                    <Button variant="ghost" size="sm" onClick={() => toggleSelectAll(activeSessions)}>
                      {selectedSessions.size === activeSessions.length && activeSessions.length > 0 ? 'Deselect All' : 'Select All Active'}
                    </Button>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {activeSessions.map((session) => (
                      <SessionCard
                        key={session.session_id}
                        session={session}
                        onView={handleViewSession}
                        onStop={handleStopSession}
                        onDelete={handleDeleteSession}
                        selected={selectedSessions.has(session.session_id)}
                        onToggleSelection={toggleSelection}
                      />
                    ))}
                  </div>
                </>
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
                <>
                  <div className="flex justify-end mb-2">
                    <Button variant="ghost" size="sm" onClick={() => toggleSelectAll(sessions)}>
                      {selectedSessions.size === sessions.length && sessions.length > 0 ? 'Deselect All' : 'Select All'}
                    </Button>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {sessions.map((session) => (
                      <SessionCard
                        key={session.session_id}
                        session={session}
                        onView={handleViewSession}
                        onStart={handleStartSession}
                        onStop={handleStopSession}
                        onDelete={handleDeleteSession}
                        selected={selectedSessions.has(session.session_id)}
                        onToggleSelection={toggleSelection}
                      />
                    ))}
                  </div>
                </>
              )}
            </TabsContent>
          </Tabs>

          {/* Floating Batch Action Bar */}
          {selectedSessions.size > 0 && (
            <div className="fixed bottom-6 left-1/2 transform -translate-x-1/2 bg-popover border shadow-xl rounded-full px-6 py-3 flex items-center gap-4 z-50 animate-in slide-in-from-bottom-5">
              <span className="font-medium text-sm">{selectedSessions.size} selected</span>
              <div className="h-4 w-px bg-border" />
              <Button size="sm" variant="secondary" onClick={handleBatchStop}>
                <Square className="h-3 w-3 mr-2" />
                Stop Selected
              </Button>
              <Button size="sm" variant="destructive" onClick={handleBatchDelete}>
                <Trash2 className="h-3 w-3 mr-2" />
                Delete Selected
              </Button>
              <Button size="icon" variant="ghost" className="h-6 w-6 rounded-full ml-2" onClick={() => setSelectedSessions(new Set())}>
                <span className="sr-only">Close</span>
                ×
              </Button>
            </div>
          )}

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
function SessionCard({ session, onView, onStart, onStop, onDelete, selected, onToggleSelection }) {
  const formatDate = (timestamp) => {
    return new Date(timestamp * 1000).toLocaleString();
  };

  return (
    <Card
      className={`hover:shadow-lg transition-shadow cursor-pointer relative group ${selected ? 'ring-2 ring-primary border-primary' : ''}`}
      onClick={() => onView(session.session_id)}
    >
      <div
        className="absolute top-3 right-3 z-10"
        onClick={(e) => {
          e.stopPropagation();
          onToggleSelection(session.session_id);
        }}
      >
        <div className={`h-5 w-5 rounded border flex items-center justify-center transition-colors ${selected ? 'bg-primary border-primary text-primary-foreground' : 'bg-background/80 border-input hover:bg-accent'}`}>
          {selected && <div className="h-2.5 w-2.5 rounded-sm bg-current" />}
        </div>
      </div>

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
          <div className="flex-1 min-w-0 pr-6"> {/* Padding for checkbox */}
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
          {/* Stats */}
          <div className="grid grid-cols-3 gap-2 text-sm text-center">
            <div className="bg-green-50 dark:bg-green-900/20 p-2 rounded-md">
              <p className="text-xs text-green-700 dark:text-green-400 font-medium">Stable</p>
              <p className="font-bold text-green-800 dark:text-green-300">{session.stable_count || 0}</p>
            </div>
            <div className="bg-blue-50 dark:bg-blue-900/20 p-2 rounded-md">
              <p className="text-xs text-blue-700 dark:text-blue-400 font-medium">Review</p>
              <p className="font-bold text-blue-800 dark:text-blue-300">{session.review_count || 0}</p>
            </div>
            <div className="bg-amber-50 dark:bg-amber-900/20 p-2 rounded-md">
              <p className="text-xs text-amber-700 dark:text-amber-400 font-medium">Quarantined</p>
              <p className="font-bold text-amber-800 dark:text-amber-300">{session.quarantined_count || 0}</p>
            </div>
          </div>



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
