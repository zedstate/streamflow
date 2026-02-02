import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle } from 'lucide-react';
import { channelsAPI } from '@/services/api';
import { useToast } from '@/hooks/use-toast';

function CreateSessionDialog({ open, onOpenChange, onCreateSession }) {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    channel_id: '',
    regex_filter: '.*',
    pre_event_minutes: 30,
    stagger_ms: 200,
    timeout_ms: 30000,
    autoStart: true
  });
  const { toast } = useToast();

  useEffect(() => {
    if (open) {
      loadChannels();
    }
  }, [open]);

  const loadChannels = async () => {
    try {
      setLoading(true);
      const response = await channelsAPI.getChannels();
      setChannels(response.data || []);
    } catch (err) {
      console.error('Failed to load channels:', err);
      toast({
        title: 'Error',
        description: 'Failed to load channels',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    if (!formData.channel_id) {
      toast({
        title: 'Validation Error',
        description: 'Please select a channel',
        variant: 'destructive'
      });
      return;
    }

    onCreateSession(formData);
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Create Monitoring Session</DialogTitle>
          <DialogDescription>
            Create a new stream monitoring session for live event quality tracking
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Channel Selection */}
          <div className="space-y-2">
            <Label htmlFor="channel">Channel *</Label>
            <Select
              value={formData.channel_id ? formData.channel_id.toString() : ''}
              onValueChange={(value) => handleChange('channel_id', parseInt(value))}
            >
              <SelectTrigger id="channel">
                <SelectValue placeholder="Select a channel" />
              </SelectTrigger>
              <SelectContent>
                {channels.map((channel) => (
                  <SelectItem key={channel.id} value={channel.id.toString()}>
                    {channel.name} (#{channel.channel_number})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              The channel to monitor streams for
            </p>
          </div>

          {/* Regex Filter */}
          <div className="space-y-2">
            <Label htmlFor="regex">Stream Filter (Regex)</Label>
            <Input
              id="regex"
              value={formData.regex_filter}
              onChange={(e) => handleChange('regex_filter', e.target.value)}
              placeholder=".*"
              className="font-mono"
            />
            <p className="text-xs text-muted-foreground">
              Regular expression to filter which streams to monitor. Use .* for all streams.
            </p>
          </div>

          {/* Pre-event Minutes */}
          <div className="space-y-2">
            <Label htmlFor="pre_event">Pre-Event Start (Minutes)</Label>
            <Input
              id="pre_event"
              type="number"
              min="5"
              max="120"
              value={formData.pre_event_minutes}
              onChange={(e) => handleChange('pre_event_minutes', parseInt(e.target.value))}
            />
            <p className="text-xs text-muted-foreground">
              How many minutes before an event to start monitoring (5-120)
            </p>
          </div>

          {/* Advanced Settings */}
          <div className="border rounded-lg p-4 space-y-3">
            <h4 className="text-sm font-medium">Advanced Settings</h4>
            
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="stagger" className="text-xs">Stagger Delay (ms)</Label>
                <Input
                  id="stagger"
                  type="number"
                  min="0"
                  max="5000"
                  value={formData.stagger_ms}
                  onChange={(e) => handleChange('stagger_ms', parseInt(e.target.value))}
                  className="text-sm"
                />
                <p className="text-xs text-muted-foreground">
                  Delay between starting stream monitors
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="timeout" className="text-xs">Timeout (ms)</Label>
                <Input
                  id="timeout"
                  type="number"
                  min="5000"
                  max="120000"
                  value={formData.timeout_ms}
                  onChange={(e) => handleChange('timeout_ms', parseInt(e.target.value))}
                  className="text-sm"
                />
                <p className="text-xs text-muted-foreground">
                  Stream timeout before quarantine
                </p>
              </div>
            </div>
          </div>

          {/* Auto-start Toggle */}
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="space-y-0.5">
              <Label htmlFor="autostart" className="text-sm font-medium">
                Auto-start Monitoring
              </Label>
              <p className="text-xs text-muted-foreground">
                Begin monitoring immediately after creation
              </p>
            </div>
            <Switch
              id="autostart"
              checked={formData.autoStart}
              onCheckedChange={(checked) => handleChange('autoStart', checked)}
            />
          </div>

          {/* Info Alert */}
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="text-xs">
              Sessions continuously monitor stream quality, capture screenshots, and calculate
              reliability scores using a Capped Sliding Window algorithm to minimize unnecessary
              stream changes in Dispatcharr.
            </AlertDescription>
          </Alert>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading || !formData.channel_id}>
              Create Session
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default CreateSessionDialog;
