import { api } from './api'

export const aceStreamMonitoringAPI = {
  createChannelSession: (payload) => api.post('/acestream-channel-sessions', payload),

  createGroupChannelSessions: (payload) => api.post('/acestream-channel-sessions/group/start', payload),

  getChannelSessions: (status = null) => {
    const params = status ? { status } : {}
    return api.get('/acestream-channel-sessions', { params })
  },

  getChannelSession: (sessionId) => api.get(`/acestream-channel-sessions/${sessionId}`),

  quarantineChannelSessionStream: (sessionId, streamId) =>
    api.post(`/acestream-channel-sessions/${sessionId}/streams/${streamId}/quarantine`),

  reviveChannelSessionStream: (sessionId, streamId) =>
    api.post(`/acestream-channel-sessions/${sessionId}/streams/${streamId}/revive`),

  stopChannelSession: (sessionId) => api.post(`/acestream-channel-sessions/${sessionId}/stop`),

  deleteChannelSession: (sessionId) => api.delete(`/acestream-channel-sessions/${sessionId}`),

  checkOrchestratorReady: () => api.get('/acestream-orchestrator/ready'),

  startSession: (payload) => api.post('/acestream-monitor-sessions/start', payload),

  getSessions: (includeCorrelation = true) =>
    api.get('/acestream-monitor-sessions', {
      params: { include_correlation: includeCorrelation },
    }),

  getSession: (monitorId, includeCorrelation = true) =>
    api.get(`/acestream-monitor-sessions/${monitorId}`, {
      params: { include_correlation: includeCorrelation },
    }),

  stopSession: (monitorId) => api.delete(`/acestream-monitor-sessions/${monitorId}`),

  deleteEntry: (monitorId) => api.delete(`/acestream-monitor-sessions/${monitorId}/entry`),

  parseM3U: (m3uContent) =>
    api.post('/acestream-monitor-sessions/parse-m3u', {
      m3u_content: m3uContent,
    }),

  getStartedStreams: () => api.get('/acestream-monitor-sessions/streams/started'),
}
