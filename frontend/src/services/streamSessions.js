/**
 * API service for Stream Monitoring Sessions
 */
import { api } from './api';

export const streamSessionsAPI = {
  /**
   * Get all stream monitoring sessions
   * @param {string} status - Optional filter by status ('active' or undefined for all)
   * @returns {Promise} Array of sessions
   */
  getSessions: (status = null) => {
    const params = status ? { status } : {};
    return api.get('/stream-sessions', { params });
  },

  /**
   * Get a specific session with details
   * @param {string} sessionId - Session ID
   * @returns {Promise} Session details including streams
   */
  getSession: (sessionId) => {
    return api.get(`/stream-sessions/${sessionId}`);
  },

  /**
   * Create a new stream monitoring session
   * @param {object} sessionData - Session configuration
   * @returns {Promise} Created session info
   */
  createSession: (sessionData) => {
    return api.post('/stream-sessions', sessionData);
  },

  /**
   * Start monitoring for a session
   * @param {string} sessionId - Session ID
   * @returns {Promise}
   */
  startSession: (sessionId) => {
    return api.post(`/stream-sessions/${sessionId}/start`);
  },

  /**
   * Stop monitoring for a session
   * @param {string} sessionId - Session ID
   * @returns {Promise}
   */
  stopSession: (sessionId) => {
    return api.post(`/stream-sessions/${sessionId}/stop`);
  },

  /**
   * Delete a session
   * @param {string} sessionId - Session ID
   * @returns {Promise}
   */
  deleteSession: (sessionId) => {
    return api.delete(`/stream-sessions/${sessionId}`);
  },

  /**
   * Get metrics history for a stream
   * @param {string} sessionId - Session ID
   * @param {number} streamId - Stream ID
   * @returns {Promise} Metrics data
   */
  getStreamMetrics: (sessionId, streamId) => {
    return api.get(`/stream-sessions/${sessionId}/streams/${streamId}/metrics`);
  },

  /**
   * Get screenshot URL for a stream
   * @param {number} streamId - Stream ID
   * @returns {string} Screenshot URL
   */
  getScreenshotUrl: (streamId) => {
    return `/data/screenshots/${streamId}.jpg?t=${Date.now()}`;
  },
};
