import { spawn } from 'child_process';
import fs from 'fs-extra';
import path from 'path';

export class ScreenshotService {
    private static instance: ScreenshotService;
    private publicDir: string;
    private screenshotDir: string;

    private constructor() {
        this.publicDir = path.join(process.cwd(), 'public');
        this.screenshotDir = path.join(this.publicDir, 'screenshots');
        this.ensureDirectories();
    }

    public static getInstance(): ScreenshotService {
        if (!ScreenshotService.instance) {
            ScreenshotService.instance = new ScreenshotService();
        }
        return ScreenshotService.instance;
    }

    private async ensureDirectories() {
        await fs.ensureDir(this.screenshotDir);
    }

    public async capture(url: string, streamId: string): Promise<string | null> {
        const timestamp = Date.now();
        const filename = `${streamId}.jpg`; // Overwrite same file to save space? Or unique? 
        // Let's stick to one file per stream for now to keep it simple for the frontend (cache busting via query param)
        const outputPath = path.join(this.screenshotDir, filename);

        return new Promise((resolve) => {
            const ffmpeg = spawn('ffmpeg', [
                '-y',                  // Overwrite output files without asking
                '-i', url,             // Input URL
                '-ss', '00:00:01',     // Seek 1 second in (to avoid black frames at start)
                '-vframes', '1',       // Output 1 video frame
                '-q:v', '5',           // JPEG quality (2-31, lower is better)
                '-f', 'image2',        // Force image2 format
                outputPath
            ]);

            // Set a timeout to kill the process if it hangs
            const timeout = setTimeout(() => {
                ffmpeg.kill('SIGKILL');
                console.warn(`[Screenshot] Timeout for stream ${streamId}`);
                resolve(null);
            }, 10000); // 10s timeout

            ffmpeg.on('close', (code) => {
                clearTimeout(timeout);
                if (code === 0) {
                    // Return relative path for frontend
                    resolve(`/screenshots/${filename}`);
                } else {
                    console.warn(`[Screenshot] FFmpeg exited with code ${code} for stream ${streamId}`);
                    resolve(null);
                }
            });

            ffmpeg.on('error', (err) => {
                clearTimeout(timeout);
                console.error(`[Screenshot] Spawn error for stream ${streamId}:`, err);
                resolve(null);
            });
        });
    }

    public getScreenshotPath(streamId: string): string {
        return `/screenshots/${streamId}.jpg`;
    }
}
