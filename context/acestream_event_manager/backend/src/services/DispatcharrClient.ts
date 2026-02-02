import axios, { AxiosInstance } from 'axios';
import dotenv from 'dotenv';
import { Stream } from '@prisma/client';

dotenv.config();

const BASE_URL = process.env.DISPATCHARR_URL;
const USERNAME = process.env.DISPATCHARR_USER;
const PASSWORD = process.env.DISPATCHARR_PASS;

export interface DispatcharrChannel {
    id: number;
    name: string;
    channel_number: number;
    logo_id?: number | null;
    streams: number[];
}

export interface DispatcharrStream {
    id: number;
    name: string;
    url: string;
    m3u_account?: number;
}

export class DispatcharrClient {
    private token: string | null = null;
    private client: AxiosInstance;

    constructor() {
        this.client = axios.create({
            baseURL: BASE_URL
        });

        // Response interceptor for 401 handling
        this.client.interceptors.response.use(
            (response) => response,
            async (error) => {
                const originalRequest = error.config;
                // Check if 401 and not already retried
                if (error.response?.status === 401 && !originalRequest._retry) {
                    originalRequest._retry = true;
                    try {
                        await this.login();
                        // Update header
                        originalRequest.headers.Authorization = `Bearer ${this.token}`;
                        return this.client(originalRequest);
                    } catch (loginError) {
                        return Promise.reject(loginError);
                    }
                }
                return Promise.reject(error);
            }
        );
    }

    private async login() {
        try {
            console.log('Logging in to Dispatcharr (JWT)...');
            // Use the token endpoint for API access
            const response = await axios.post(`${BASE_URL}/api/accounts/token/`, {
                username: USERNAME,
                password: PASSWORD,
            });
            this.token = response.data.access;
            console.log('Dispatcharr login successful');
        } catch (error) {
            console.error('Failed to login to Dispatcharr', error);
            throw error;
        }
    }

    private async getHeaders() {
        if (!this.token) {
            await this.login();
        }
        return {
            Authorization: `Bearer ${this.token}`,
        };
    }

    async getChannels(regex?: string): Promise<DispatcharrChannel[]> {
        try {
            const headers = await this.getHeaders();
            const response = await this.client.get(`/api/channels/channels/?page_size=1000`, { headers });

            // Handle direct array response vs paginated object
            let channels: DispatcharrChannel[] = [];
            if (Array.isArray(response.data)) {
                channels = response.data;
            } else if (response.data.results && Array.isArray(response.data.results)) {
                channels = response.data.results;
            } else {
                console.warn('Unexpected channel response format:', Object.keys(response.data));
            }

            if (regex) {
                const re = new RegExp(regex, 'i');
                return channels.filter(c => re.test(c.name));
            }
            return channels;
        } catch (error: any) {
            console.error('Failed to fetch channels:', error.response?.status, error.message);
            throw error;
        }
    }

    async getChannel(id: number): Promise<DispatcharrChannel | null> {
        try {
            const channels = await this.getChannels();
            const channel = channels.find(c => c.id === id);
            return channel || null;
        } catch (error) {
            console.error(`Failed to get channel ${id}:`, error);
            throw error;
        }
    }

    async getLogo(logoId: number): Promise<string | null> {
        try {
            const headers = await this.getHeaders();
            const response = await this.client.get(`/api/channels/logos/${logoId}/`, { headers });
            // Cache URL is usually the one we want
            return response.data.cache_url || response.data.url || null;
        } catch (error) {
            console.error(`Failed to get logo ${logoId}:`, error);
            return null;
        }
    }

    async getCurrentProgram(channelId: number): Promise<any | null> {
        try {
            const headers = await this.getHeaders();
            // The endpoint takes channel_ids array in body
            const response = await this.client.post(`/api/epg/current-programs/`, {
                channel_ids: [channelId]
            }, { headers });

            const programs = response.data; // It's a map or list?
            // "Get currently playing programs for specified channels"
            // Let's assume response allows us to find it.
            // Based on manual check we will see format.
            // If response is array of objects with channel_id.

            // For now, return raw data or first item if list
            if (Array.isArray(programs) && programs.length > 0) {
                return programs[0];
            }
            return null;
        } catch (error) {
            console.error(`Failed to get current program for ${channelId}:`, error);
            return null;
        }
    }

    async getAllStreams(): Promise<DispatcharrStream[]> {
        try {
            const headers = await this.getHeaders();
            const response = await this.client.get(`/api/channels/streams/?page_size=1000`, { headers });

            if (Array.isArray(response.data)) {
                return response.data;
            } else if (response.data.results) {
                return response.data.results;
            }
            return [];
        } catch (error: any) {
            console.error('Failed to fetch streams:', error.response?.status, error.message);
            throw error;
        }
    }
}
