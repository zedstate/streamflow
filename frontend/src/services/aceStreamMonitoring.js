import { api } from './api'

export const aceStreamMonitoringAPI = {
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
