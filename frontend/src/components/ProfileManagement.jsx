import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Switch } from '@/components/ui/switch.jsx'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog.jsx'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert.jsx'
import { Loader2, Plus, Edit2, Trash2, AlertCircle, ArrowUp, ArrowDown } from 'lucide-react'
import { useToast } from '@/hooks/use-toast.js'
import { automationAPI, m3uAPI } from '@/services/api.js'
import { Checkbox } from '@/components/ui/checkbox.jsx'

export default function ProfileManagement() {
  const [profiles, setProfiles] = useState([])
  const [m3uAccounts, setM3uAccounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingProfile, setEditingProfile] = useState(null)
  const [profileForm, setProfileForm] = useState({
    name: '',
    description: '',
    active: true,
    m3u_update: { enabled: false, playlists: [] },
    m3u_priority: []
  })
  const [saving, setSaving] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    console.log("ProfileManagement DEBUG: Component Mounted")
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      const [profilesResponse, accountsResponse] = await Promise.all([
        automationAPI.getProfiles(),
        m3uAPI.getAccounts().catch(() => ({ data: { accounts: [] } }))
      ])

      setProfiles(profilesResponse.data || [])
      setM3uAccounts(accountsResponse.data?.accounts || accountsResponse.data || [])
    } catch (err) {
      console.error('Failed to load data:', err)
      toast({
        title: "Error",
        description: "Failed to load profiles or accounts",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleOpenDialog = (profile = null) => {
    if (profile) {
      setEditingProfile(profile)
      setProfileForm({
        name: profile.name,
        description: profile.description || '',
        active: profile.active !== false,
        m3u_update: {
          enabled: profile.m3u_update?.enabled || false,
          playlists: profile.m3u_update?.playlists || []
        },
        m3u_priority: profile.m3u_priority || []
      })
    } else {
      setEditingProfile(null)
      setProfileForm({
        name: '',
        description: '',
        active: true,
        m3u_update: { enabled: false, playlists: [] },
        m3u_priority: []
      })
    }
    setDialogOpen(true)
  }

  const handleSaveProfile = async () => {
    if (!profileForm.name.trim()) return

    try {
      setSaving(true)
      if (editingProfile) {
        await automationAPI.updateProfile(editingProfile.id, profileForm)
        toast({ title: "Success", description: "Profile updated successfully" })
      } else {
        await automationAPI.createProfile(profileForm)
        toast({ title: "Success", description: "Profile created successfully" })
      }
      setDialogOpen(false)
      loadData()
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to save profile",
        variant: "destructive"
      })
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteProfile = async (profileId) => {
    if (!confirm('Are you sure you want to delete this profile?')) return

    try {
      await automationAPI.deleteProfile(profileId)
      toast({ title: "Success", description: "Profile deleted successfully" })
      loadData()
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to delete profile",
        variant: "destructive"
      })
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle>Automation Profiles</CardTitle>
              <CardDescription>Create and manage profiles to apply automation rules to channels</CardDescription>
            </div>
            <Button onClick={() => handleOpenDialog()}>
              <Plus className="h-4 w-4 mr-2" />
              New Profile
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {profiles.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground border-2 border-dashed rounded-lg">
              No profiles found. Create one to get started.
            </div>
          ) : (
            <div className="space-y-4">
              {profiles.map(profile => (
                <div key={profile.id} className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors">
                  <div>
                    <div className="font-medium flex items-center gap-2">
                      {profile.name}
                      {!profile.active && <span className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded">Inactive</span>}
                    </div>
                    {profile.description && <div className="text-sm text-muted-foreground">{profile.description}</div>}
                  </div>
                  <div className="flex gap-2">
                    <Button variant="ghost" size="sm" onClick={() => handleOpenDialog(profile)}>
                      <Edit2 className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleDeleteProfile(profile.id)} className="text-destructive hover:text-destructive">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingProfile ? 'Edit Profile' : 'New Profile'}</DialogTitle>
            <DialogDescription>
              define the automation rules and settings for this profile.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={profileForm.name}
                onChange={e => setProfileForm(prev => ({ ...prev, name: e.target.value }))}
                placeholder="e.g. Sports Channels"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={profileForm.description}
                onChange={e => setProfileForm(prev => ({ ...prev, description: e.target.value }))}
                placeholder="Optional description"
              />
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                id="active"
                checked={profileForm.active}
                onCheckedChange={checked => setProfileForm(prev => ({ ...prev, active: checked }))}
              />
              <Label htmlFor="active">Active</Label>
            </div>

            <div className="border-t pt-4 mt-4 border-2 border-red-500">
              <div className="flex items-center justify-between mb-2">
                <Label className="text-base font-semibold">M3U Playlist Updates (DEBUG)</Label>
                <Switch
                  id="m3u-enabled"
                  checked={profileForm.m3u_update.enabled}
                  onCheckedChange={checked => setProfileForm(prev => ({
                    ...prev,
                    m3u_update: { ...prev.m3u_update, enabled: checked }
                  }))}
                />
              </div>
              <p className="text-sm text-muted-foreground mb-3">
                Automatically update playlists for channels assigned to this profile.
              </p>

              {profileForm.m3u_update.enabled && (
                <div className="space-y-3 pl-2 border-l-2 border-muted ml-1">
                  <Label className="text-sm font-medium">Select Playlists to Update</Label>
                  <div className="grid grid-cols-1 gap-2 max-h-[200px] overflow-y-auto">
                    {m3uAccounts.map(account => (
                      <div key={account.id} className="flex items-center space-x-2">
                        <Checkbox
                          id={`playlist-${account.id}`}
                          checked={profileForm.m3u_update.playlists.includes(account.id)}
                          onCheckedChange={(checked) => {
                            setProfileForm(prev => {
                              const currentPlaylists = prev.m3u_update.playlists || []
                              let newPlaylists
                              if (checked) {
                                newPlaylists = [...currentPlaylists, account.id]
                              } else {
                                newPlaylists = currentPlaylists.filter(id => id !== account.id)
                              }
                              return {
                                ...prev,
                                m3u_update: { ...prev.m3u_update, playlists: newPlaylists }
                              }
                            })
                          }}
                        />
                        <Label htmlFor={`playlist-${account.id}`} className="font-normal cursor-pointer">
                          {account.name}
                        </Label>
                      </div>
                    ))}
                    {m3uAccounts.length === 0 && (
                      <div className="text-sm text-muted-foreground italic">No M3U accounts found</div>
                    )}
                  </div>
                </div>

              )}

              <div className="border-t pt-4 mt-4">
                <Label className="text-base font-semibold mb-2 block">M3U Priority</Label>
                <p className="text-sm text-muted-foreground mb-3">
                  Order playlists to define which streams are preferred during checks. Top is highest priority.
                </p>

                <div className="space-y-2 border rounded-md p-2 max-h-[250px] overflow-y-auto">
                  {(() => {
                    // Get all accounts, merge with saved priority to ensure we have all
                    // If priority list is empty, use default order of accounts
                    const priorityIds = profileForm.m3u_priority && profileForm.m3u_priority.length > 0
                      ? profileForm.m3u_priority
                      : m3uAccounts.map(a => a.id)

                    // Make sure we include any new accounts that might not be in the saved priority
                    const allIds = [...new Set([...priorityIds, ...m3uAccounts.map(a => a.id)])]

                    // Filter out any IDs that no longer exist
                    const validIds = allIds.filter(id => m3uAccounts.some(a => a.id === id))

                    return validIds.map((accountId, index) => {
                      const account = m3uAccounts.find(a => a.id === accountId)
                      if (!account) return null

                      return (
                        <div key={accountId} className="flex items-center justify-between p-2 bg-secondary/20 rounded border">
                          <span className="font-medium text-sm">{index + 1}. {account.name}</span>
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6"
                              disabled={index === 0}
                              onClick={() => {
                                const newOrder = [...validIds]
                                const temp = newOrder[index]
                                newOrder[index] = newOrder[index - 1]
                                newOrder[index - 1] = temp
                                setProfileForm(prev => ({ ...prev, m3u_priority: newOrder }))
                              }}
                            >
                              <ArrowUp className="h-3 w-3" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6"
                              disabled={index === validIds.length - 1}
                              onClick={() => {
                                const newOrder = [...validIds]
                                const temp = newOrder[index]
                                newOrder[index] = newOrder[index + 1]
                                newOrder[index + 1] = temp
                                setProfileForm(prev => ({ ...prev, m3u_priority: newOrder }))
                              }}
                            >
                              <ArrowDown className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                      )
                    })
                  })()}
                  {m3uAccounts.length === 0 && (
                    <div className="text-sm text-muted-foreground italic text-center py-4">No M3U accounts found</div>
                  )}
                </div>
              </div>

            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSaveProfile} disabled={saving || !profileForm.name.trim()}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </DialogContent >
      </Dialog >
    </div >
  )
}
