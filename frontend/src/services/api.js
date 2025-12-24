import axios from 'axios';

// Create axios instance with default config
// Use /api path since both frontend and backend are served from the same origin
const baseURL = '/api';

export const api = axios.create({
  baseURL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// API methods
export const automationAPI = {
  getStatus: () => api.get('/automation/status'),
  start: () => api.post('/automation/start'),
  stop: () => api.post('/automation/stop'),
  runCycle: () => api.post('/automation/cycle'),
  getConfig: () => api.get('/automation/config'),
  updateConfig: (config) => api.put('/automation/config', config),
};

export const channelsAPI = {
  getChannels: () => api.get('/channels'),
  getGroups: () => api.get('/channels/groups'),
  getChannelStats: (channelId) => api.get(`/channels/${channelId}/stats`),
  getLogo: (logoId) => api.get(`/channels/logos/${logoId}`),
  getLogoCached: (logoId) => `/api/channels/logos/${logoId}/cache`,
};

export const channelSettingsAPI = {
  getAllSettings: () => api.get('/channel-settings'),
  getSettings: (channelId) => api.get(`/channel-settings/${channelId}`),
  updateSettings: (channelId, settings) => api.put(`/channel-settings/${channelId}`, settings),
};

export const groupSettingsAPI = {
  getAllSettings: () => api.get('/group-settings'),
  getSettings: (groupId) => api.get(`/group-settings/${groupId}`),
  updateSettings: (groupId, settings) => api.put(`/group-settings/${groupId}`, settings),
  bulkDisableMatching: () => api.post('/group-settings/bulk-disable-matching'),
  bulkDisableChecking: () => api.post('/group-settings/bulk-disable-checking'),
};

export const channelOrderAPI = {
  getOrder: () => api.get('/channel-order'),
  setOrder: (order) => api.put('/channel-order', { order }),
  clearOrder: () => api.delete('/channel-order'),
};

export const regexAPI = {
  getPatterns: () => api.get('/regex-patterns'),
  addPattern: (pattern) => api.post('/regex-patterns', pattern),
  deletePattern: (channelId) => api.delete(`/regex-patterns/${channelId}`),
  testPattern: (data) => api.post('/test-regex', data),
  testPatternLive: (data) => api.post('/test-regex-live', data),
  importPatterns: (patterns) => api.post('/regex-patterns/import', patterns),
  bulkAddPatterns: (data) => api.post('/regex-patterns/bulk', data),
};

export const streamAPI = {
  discoverStreams: () => api.post('/discover-streams'),
  refreshPlaylist: (accountId) => api.post('/refresh-playlist', accountId ? { account_id: accountId } : {}),
};

export const m3uAPI = {
  getAccounts: () => api.get('/m3u-accounts'),
  updateAccountPriority: (accountId, data) => api.patch(`/m3u-accounts/${accountId}/priority`, data),
  updateGlobalPriorityMode: (data) => api.put('/m3u-priority/global-mode', data),
};

export const streamCheckerAPI = {
  getStatus: () => api.get('/stream-checker/status'),
  start: () => api.post('/stream-checker/start'),
  stop: () => api.post('/stream-checker/stop'),
  getQueue: () => api.get('/stream-checker/queue'),
  addToQueue: (data) => api.post('/stream-checker/queue/add', data),
  clearQueue: () => api.post('/stream-checker/queue/clear'),
  getConfig: () => api.get('/stream-checker/config'),
  updateConfig: (config) => api.put('/stream-checker/config', config),
  getProgress: () => api.get('/stream-checker/progress'),
  checkChannel: (channelId) => api.post('/stream-checker/check-channel', { channel_id: channelId }),
  // Use longer timeout for single channel check as it can take time
  checkSingleChannel: (channelId) => api.post('/stream-checker/check-single-channel', { channel_id: channelId }, { timeout: 120000 }),
  markUpdated: (data) => api.post('/stream-checker/mark-updated', data),
  queueAllChannels: () => api.post('/stream-checker/queue-all'),
  triggerGlobalAction: () => api.post('/stream-checker/global-action'),
};

export const changelogAPI = {
  getChangelog: (days = 7) => api.get(`/changelog?days=${days}`),
};

export const deadStreamsAPI = {
  getDeadStreams: (page = 1, per_page = 20) => {
    // Ensure page and per_page are primitive numbers to avoid sending objects
    const safePage = typeof page === 'number' ? page : parseInt(page) || 1;
    const safePerPage = typeof per_page === 'number' ? per_page : parseInt(per_page) || 20;
    return api.get('/dead-streams', { params: { page: safePage, per_page: safePerPage } });
  },
  reviveStream: (streamUrl) => api.post('/dead-streams/revive', { stream_url: streamUrl }),
  clearAllDeadStreams: () => api.post('/dead-streams/clear'),
};

export const setupAPI = {
  getStatus: () => api.get('/setup-wizard'),
};

export const dispatcharrAPI = {
  getConfig: () => api.get('/dispatcharr/config'),
  updateConfig: (config) => api.put('/dispatcharr/config', config),
  testConnection: (config) => api.post('/dispatcharr/test-connection', config),
  initializeUDI: () => api.post('/dispatcharr/initialize-udi'),
};

export const schedulingAPI = {
  getConfig: () => api.get('/scheduling/config'),
  updateConfig: (config) => api.put('/scheduling/config', config),
  getEPGGrid: (forceRefresh = false) => api.get('/scheduling/epg/grid', { params: { force_refresh: forceRefresh } }),
  getChannelPrograms: (channelId) => api.get(`/scheduling/epg/channel/${channelId}`),
  getEvents: () => api.get('/scheduling/events'),
  createEvent: (eventData) => api.post('/scheduling/events', eventData),
  deleteEvent: (eventId) => api.delete(`/scheduling/events/${eventId}`),
  getAutoCreateRules: () => api.get('/scheduling/auto-create-rules'),
  createAutoCreateRule: (ruleData) => api.post('/scheduling/auto-create-rules', ruleData),
  updateAutoCreateRule: (ruleId, ruleData) => api.put(`/scheduling/auto-create-rules/${ruleId}`, ruleData),
  deleteAutoCreateRule: (ruleId) => api.delete(`/scheduling/auto-create-rules/${ruleId}`),
  testAutoCreateRule: (testData) => api.post('/scheduling/auto-create-rules/test', testData),
  exportAutoCreateRules: () => api.get('/scheduling/auto-create-rules/export'),
  importAutoCreateRules: (rulesData) => api.post('/scheduling/auto-create-rules/import', rulesData),
};

export const versionAPI = {
  getVersion: () => api.get('/version'),
};

export const profileAPI = {
  // Profile configuration
  getConfig: () => api.get('/profile-config'),
  updateConfig: (config) => api.put('/profile-config', config),
  
  // Profile management
  getProfiles: () => api.get('/profiles'),
  getProfileChannels: (profileId, includeSnapshot = false) => {
    const params = includeSnapshot ? { include_snapshot: 'true' } : {};
    return api.get(`/profiles/${profileId}/channels`, { params });
  },
  refreshProfiles: () => api.post('/profiles/refresh'),
  diagnoseProfiles: () => api.get('/profiles/diagnose'),
  
  // Snapshot management
  createSnapshot: (profileId) => api.post(`/profiles/${profileId}/snapshot`),
  getSnapshot: (profileId) => api.get(`/profiles/${profileId}/snapshot`),
  deleteSnapshot: (profileId) => api.delete(`/profiles/${profileId}/snapshot`),
  getAllSnapshots: () => api.get('/profiles/snapshots'),
  
  // Actions
  disableEmptyChannels: (profileId) => api.post(`/profiles/${profileId}/disable-empty-channels`),
};