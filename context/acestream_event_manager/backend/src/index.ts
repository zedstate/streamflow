import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { createServer } from 'http';
import { Server } from 'socket.io';
import { StreamManager } from './services/StreamManager';
import { DispatcharrClient } from './services/DispatcharrClient';
import { prisma } from './lib/prisma';

dotenv.config();

const app = express();
const httpServer = createServer(app);
const io = new Server(httpServer, {
    cors: {
        origin: '*',
    }
});

app.use(cors());
app.use(express.json());
app.use(express.static('public')); // Serve static files (screenshots)

const streamManager = new StreamManager(io);
const dispatcharr = new DispatcharrClient();

// API Routes

// Get Channels (for selection)
app.get('/api/channels', async (req, res) => {
    try {
        const search = req.query.search as string;
        // If search is provided, treat it as a case-insensitive regex fragment
        // If no search, pass undefined to get all
        const channels = await dispatcharr.getChannels(search);
        res.json(channels);
    } catch (err) {
        res.status(500).json({ error: 'Failed to fetch channels' });
    }
});

// Start Session
app.post('/api/session/start', async (req, res) => {
    const { channelId, regex, timeoutMs, staggerMs } = req.body;
    try {
        const session = await streamManager.startSession(channelId, regex, timeoutMs, staggerMs);
        res.json({ success: true, sessionId: session.id });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Failed to start session' });
    }
});

// Stop Session
app.post('/api/session/stop', async (req, res) => {
    const { sessionId } = req.body;
    if (!sessionId) return res.status(400).json({ error: 'Session ID required' });
    try {
        await streamManager.stopSession(sessionId);
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: 'Failed to stop session' });
    }
});

// Get Session Status (All or Specific)
app.get('/api/session', async (req, res) => {
    const sessionId = req.query.id ? parseInt(req.query.id as string) : undefined;
    const status = await streamManager.getSessionStatus(sessionId);
    res.json(status);
});

// HISTORY ROUTES
app.get('/api/history', async (req, res) => {
    try {
        const sessions = await prisma.eventSession.findMany({
            orderBy: { createdAt: 'desc' },
            include: { channel: true }
        });
        res.json(sessions);
    } catch (err) {
        res.status(500).json({ error: 'Failed to fetch history' });
    }
});

app.get('/api/history/:id', async (req, res) => {
    try {
        const id = parseInt(req.params.id);
        const session = await prisma.eventSession.findUnique({
            where: { id },
            include: { channel: true }
        });
        if (!session) return res.status(404).json({ error: 'Session not found' });

        // Maybe fetch stream stats summary?
        const streams = await prisma.stream.findMany({
            where: { channelId: session.channelId! } // Use ! if we assume legacy integrity, or check null
        });

        res.json({ session, streams });
    } catch (err) {
        res.status(500).json({ error: 'Failed to fetch session detail' });
    }
});

// PRESET ROUTES
app.get('/api/presets', async (req, res) => {
    const presets = await prisma.preset.findMany();
    res.json(presets);
});

app.post('/api/presets', async (req, res) => {
    const { name, channelId, regexFilter, timeoutMs, staggerMs } = req.body;
    try {
        const preset = await prisma.preset.create({
            data: {
                name,
                channelId,
                regexFilter,
                timeoutMs: timeoutMs || 30000,
                staggerMs: staggerMs || 200
            }
        });
        res.json(preset);
    } catch (err) {
        res.status(500).json({ error: 'Failed to create preset' });
    }
});

app.delete('/api/presets/:id', async (req, res) => {
    try {
        const id = parseInt(req.params.id);
        await prisma.preset.delete({ where: { id } });
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: 'Failed to delete preset' });
    }
});

const PORT = process.env.PORT || 3001;

httpServer.listen(PORT, () => {
    console.log(`Backend running on port ${PORT}`);
});
