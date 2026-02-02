import { DispatcharrClient } from './DispatcharrClient';
import { OrchestratorClient } from './OrchestratorClient';
import { FFmpegMonitor } from './FFmpegMonitor';
import { ScreenshotService } from './ScreenshotService';
import { Stream, EventSession } from '@prisma/client';
import { prisma } from '../lib/prisma';
import { QualityParser } from '../utils/QualityParser';
import { Server } from 'socket.io';

export interface SessionContext {
    session: EventSession;
    refreshInterval: NodeJS.Timeout;
    monitorInterval: NodeJS.Timeout;
    monitors: Map<string, FFmpegMonitor>;
    attemptedStreams: Set<string>;
    lastScreenshotTime: Map<string, number>;
}

export class StreamManager {
    private dispatcharr: DispatcharrClient;
    private orchestrator: OrchestratorClient;
    private screenshotService: ScreenshotService;
    private sessions: Map<number, SessionContext> = new Map(); // Key: Session ID
    private io: Server;

    constructor(io: Server) {
        this.io = io;
        this.dispatcharr = new DispatcharrClient();
        this.orchestrator = new OrchestratorClient();
        this.screenshotService = ScreenshotService.getInstance();
    }

    async startSession(channelId: number, regexFilter?: string, timeoutMs: number = 30000, staggerMs: number = 200) {
        // Create session in DB

        // First, ensure Channel exists locally
        const channel = await this.dispatcharr.getChannel(channelId);
        if (channel) {
            await prisma.channel.upsert({
                where: { id: channel.id },
                update: {
                    name: channel.name,
                    channelNumber: channel.channel_number
                },
                create: {
                    id: channel.id,
                    name: channel.name,
                    channelNumber: channel.channel_number
                }
            });
        }

        // CLEANUP: Delete all existing streams for this channel to avoid stale data
        console.log(`[Session] Cleaning up stale streams for channel ${channelId}...`);

        // First, get all streams for this channel
        const streamsToDelete = await prisma.stream.findMany({
            where: { channelId: channelId },
            select: { id: true }
        });

        // Delete associated StreamHealth records first (foreign key constraint)
        if (streamsToDelete.length > 0) {
            await prisma.streamHealth.deleteMany({
                where: {
                    streamId: {
                        in: streamsToDelete.map(s => s.id)
                    }
                }
            });
        }

        // Now delete the streams
        await prisma.stream.deleteMany({
            where: { channelId: channelId }
        });

        const session = await prisma.eventSession.create({
            data: {
                regexFilter: regexFilter || '.*',
                timeoutMs,
                staggerMs,
                isActive: true,
                channel: {
                    connect: { id: channelId }
                }
            }
        });

        // Initialize Context
        const context: SessionContext = {
            session,
            refreshInterval: setInterval(() => this.refreshSessionStreams(session.id), 60000),
            monitorInterval: setInterval(() => this.evaluateSessionStreams(session.id), 1000),
            monitors: new Map(),
            attemptedStreams: new Set(),
            lastScreenshotTime: new Map()
        };

        this.sessions.set(session.id, context);

        // Fetch Metadata (Icon & Program)
        if (channel) {
            this.updateChannelMetadata(channelId, channel);
        }

        console.log(`Started session ${session.id} for channel ${channelId}`);

        // Initial fetch
        await this.refreshSessionStreams(session.id);

        return session;
    }

    private async updateChannelMetadata(channelId: number, channel: any) {
        try {
            // ICON
            if (channel.logo_id) {
                const logoUrl = await this.dispatcharr.getLogo(channel.logo_id);
                if (logoUrl) {
                    await prisma.channel.update({
                        where: { id: channelId },
                        data: { iconUrl: logoUrl }
                    }).catch(e => console.warn("Icon update failed", e));
                }
            }
            // PROGRAM
            const program = await this.dispatcharr.getCurrentProgram(channelId);
            if (program) {
                await prisma.channel.update({
                    where: { id: channelId },
                    data: {
                        currentProgramTitle: program.title,
                        currentProgramStart: program.start_time ? new Date(program.start_time) : null,
                        currentProgramEnd: program.end_time ? new Date(program.end_time) : null
                    }
                }).catch(e => console.warn("Program update failed", e));
            }
        } catch (e) {
            console.error("Metadata update error", e);
        }
    }

    async stopSession(sessionId: number) {
        const context = this.sessions.get(sessionId);
        if (!context) return;

        clearInterval(context.refreshInterval);
        clearInterval(context.monitorInterval);

        for (const monitor of context.monitors.values()) {
            monitor.stop();
        }
        context.monitors.clear();

        await prisma.eventSession.update({
            where: { id: sessionId },
            data: { isActive: false }
        });

        this.sessions.delete(sessionId);
        console.log(`Stopped session ${sessionId}`);
    }

    async getSessionStatus(sessionId?: number) {
        if (sessionId) {
            const context = this.sessions.get(sessionId);
            if (!context) return null;
            return this.buildSessionStatus(context);
        }

        // If no ID, return all active sessions
        const statuses = [];
        for (const context of this.sessions.values()) {
            statuses.push(await this.buildSessionStatus(context));
        }
        return statuses;
    }

    private async buildSessionStatus(context: SessionContext) {
        if (!context.session.channelId) return null;

        const streams = await prisma.stream.findMany({
            where: { channelId: context.session.channelId }
        });

        const streamsWithStats = streams.map(s => {
            const monitor = context.monitors.get(s.id);
            const stats = monitor ? monitor.getStats() : null;

            // append screenshot URL if it exists (we know the path convention)
            // But we can check if file exists? For now assume valid if active.
            // Or better, we can return the timestamp of the last screenshot to force refresh
            const lastScreenshot = context.lastScreenshotTime.get(s.id);

            return { ...s, stats, lastScreenshot };
        });

        // Sort: Active & High Width first
        streamsWithStats.sort((a, b) => {
            const aActive = a.stats?.isAlive ? 1 : 0;
            const bActive = b.stats?.isAlive ? 1 : 0;
            if (aActive !== bActive) return bActive - aActive;
            const aWidth = a.width ?? 0;
            const bWidth = b.width ?? 0;
            return bWidth - aWidth;
        });

        const channel = await prisma.channel.findUnique({ where: { id: context.session.channelId } });

        return {
            session: context.session,
            channel: channel,
            streams: streamsWithStats,
            monitoredStreams: context.monitors.size
        };
    }

    async refreshSessionStreams(sessionId: number) {
        const context = this.sessions.get(sessionId);
        if (!context || !context.session.channelId) return;

        try {
            const allStreams = await this.dispatcharr.getAllStreams();
            const regexRaw = context.session.regexFilter || '.*';
            const regexList = regexRaw.split('\n').filter(line => line.trim().length > 0).map(line => new RegExp(line.trim(), 'i'));

            const matchingStreams = allStreams.filter(s => regexList.some(regex => regex.test(s.name)));
            console.log(`[Session ${sessionId}] Found ${matchingStreams.length} matching streams`);

            const STAGGER_MS = context.session.staggerMs;

            for (const dStream of matchingStreams) {
                const quality = QualityParser.parse(dStream.name);

                await prisma.stream.upsert({
                    where: { id: dStream.id.toString() },
                    update: { url: dStream.url, name: dStream.name },
                    create: {
                        id: dStream.id.toString(),
                        channelId: context.session.channelId!,
                        url: dStream.url,
                        name: dStream.name,
                        m3u_account: dStream.m3u_account ? dStream.m3u_account.toString() : null,
                        width: quality.width,
                        height: quality.height,
                        fps: quality.fps,
                    }
                });

                const dbStream = await prisma.stream.findUnique({ where: { id: dStream.id.toString() } });
                if (dbStream && !dbStream.isQuarantined) {
                    if (!context.monitors.has(dbStream.id) && !context.attemptedStreams.has(dbStream.id)) {
                        this.startMonitor(context, dbStream);
                        context.attemptedStreams.add(dbStream.id);
                        await new Promise(resolve => setTimeout(resolve, STAGGER_MS));
                    }
                }
            }
        } catch (err) {
            console.error(`[Session ${sessionId}] Error refreshing streams:`, err);
        }
    }

    private startMonitor(context: SessionContext, stream: Stream) {
        const monitor = new FFmpegMonitor(stream.url);
        monitor.start();
        context.monitors.set(stream.id, monitor);
    }

    async evaluateSessionStreams(sessionId: number) {
        const context = this.sessions.get(sessionId);
        if (!context) return;

        const TIMEOUT_MS = context.session.timeoutMs;

        for (const [id, monitor] of context.monitors) {
            const stats = monitor.getStats();

            // Record health history
            await prisma.streamHealth.create({
                data: {
                    streamId: id,
                    speed: stats.speed,
                    timestamp: new Date(),
                }
            }).catch(() => { }); // catch potential race if stream deleted

            // UPDATE STREAM METADATA
            if (stats.isAlive && (stats.width > 0 || stats.bitrate > 0 || stats.fps > 0)) {
                await prisma.stream.update({
                    where: { id: id },
                    data: {
                        ...(stats.width > 0 ? { width: stats.width, height: stats.height } : {}),
                        ...(stats.fps > 0 ? { fps: stats.fps } : {}),
                        ...(stats.bitrate > 0 ? { bitrate: Math.round(stats.bitrate) } : {})
                    }
                }).catch(() => { });
            }

            // TIMEOUT / STALL CHECK
            if (stats.isAlive) {
                if (stats.speed === 0 && Date.now() - stats.lastUpdated > TIMEOUT_MS) {
                    console.warn(`[Session ${sessionId}] Stream ${id} timed out. Stopping monitor.`);
                    monitor.stop();
                    context.monitors.delete(id);
                } else {
                    // SCREENSHOT CHECK
                    // Logic: Take screenshot if last one was > 60s ago
                    const lastShot = context.lastScreenshotTime.get(id) || 0;
                    if (Date.now() - lastShot > 60000) { // 60 seconds
                        // We don't want to await this, let it run in background
                        this.screenshotService.capture(stats.url, id).then((path) => {
                            if (path) {
                                context.lastScreenshotTime.set(id, Date.now());
                            }
                        });
                        // Mark as attempted so we don't spam if it takes long
                        context.lastScreenshotTime.set(id, Date.now());
                    }
                }
            }
        }

        // REAL-TIME UPDATE for THIS session
        const status = await this.buildSessionStatus(context);
        this.io.emit('session:update', status); // Broadcast update for this session
        // Note: Client needs to filter or we send { sessionId, ... }
        // Update payload actually contains 'session' object so client can filter by ID.
    }

    stopAllMonitors() {
        // Stop EVERYTHING (shutdown)
        for (const context of this.sessions.values()) {
            for (const monitor of context.monitors.values()) {
                monitor.stop();
            }
        }
        this.sessions.clear();
    }
}
