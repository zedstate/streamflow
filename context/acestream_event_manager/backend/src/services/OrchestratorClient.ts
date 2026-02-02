import axios from 'axios';
import dotenv from 'dotenv';

dotenv.config();

const BASE_URL = process.env.ORCHESTRATOR_URL;

export interface OrchestratorStreamData {
    id: string; // infohash | playback_session
    key: string; // infohash
    status: string;
    peers: number;
    speed_down: number;
    livepos?: {
        buffer_pieces: string;
    };
}

export class OrchestratorClient {
    async getStreams(): Promise<OrchestratorStreamData[]> {
        try {
            const response = await axios.get(`${BASE_URL}/streams`);
            return response.data;
        } catch (error) {
            console.error('Failed to fetch orchestrator streams', error);
            return [];
        }
    }
}
