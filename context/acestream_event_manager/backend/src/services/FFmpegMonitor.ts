import { spawn, ChildProcess } from 'child_process';

export interface StreamStats {
    url: string;
    speed: number;
    bitrate: number; // kbps
    fps: number;
    width: number;
    height: number;
    time: number; // seconds
    lastUpdated: number;
    isAlive: boolean;
}

export class FFmpegMonitor {
    private process: ChildProcess | null = null;
    private stats: StreamStats;
    private url: string;

    constructor(url: string) {
        this.url = url;
        this.stats = {
            url,
            speed: 0,
            bitrate: 0,
            fps: 0,
            width: 0,
            height: 0,
            time: 0,
            lastUpdated: Date.now(),
            isAlive: false,
        };
    }

    start() {
        if (this.process) return;

        this.process = spawn('ffmpeg', [
            '-i', this.url,
            '-c', 'copy',
            '-f', 'null',
            '-'
        ]);

        this.stats.isAlive = true;

        this.process.stderr?.on('data', (data) => {
            const output = data.toString();
            // Log error if it looks critical
            if (output.includes('Error') || output.includes('Failed')) {
                console.error(`FFmpeg stderr for ${this.url}: ${output}`);
            }
            this.parseStats(output);
            this.parseMetadata(output);
        });

        this.process.on('close', (code) => {
            console.log(`FFmpeg exited with code ${code} for ${this.url}`);
            this.stats.isAlive = false;
            this.process = null;
        });

        this.process.on('error', (err) => {
            console.error(`FFmpeg spawn error for ${this.url}:`, err);
            this.stats.isAlive = false;
        });
    }

    stop() {
        if (this.process) {
            this.process.kill();
            this.process = null;
            this.stats.isAlive = false;
        }
    }

    getStats(): StreamStats {
        return this.stats;
    }

    private parseMetadata(output: string) {
        // Look for Video stream info: "Stream #0:0: Video: h264... 1920x1080 ..."
        if (output.includes('Video:')) {
            const resMatch = output.match(/(\d{3,5})x(\d{3,5})/);
            if (resMatch) {
                this.stats.width = parseInt(resMatch[1]);
                this.stats.height = parseInt(resMatch[2]);
            }

            // FPS in metadata line might be "25 fps"
            const fpsMatch = output.match(/(\d+(\.\d+)?) fps/);
            if (fpsMatch) {
                this.stats.fps = parseFloat(fpsMatch[1]);
            }
        }
    }

    private parseStats(output: string) {
        // speed (e.g., "speed=1.02x")
        const speedMatch = output.match(/speed=\s*(\d+(\.\d+)?)x?/);
        let currentSpeed = 0;
        if (speedMatch) {
            currentSpeed = parseFloat(speedMatch[1]);
            this.stats.speed = currentSpeed;
        }

        // bitrate (e.g. "bitrate= 406.1kbits/s")
        // User regex: bitrate=\s*([0-9.]+(?:\.[0-9]+)?)\s*([kmg]?)bits/s
        const bitrateMatch = output.match(/bitrate=\s*([0-9.]+(?:\.[0-9]+)?)\s*([kmg]?)bits\/s/i);
        if (bitrateMatch) {
            let val = parseFloat(bitrateMatch[1]);
            const unit = bitrateMatch[2].toLowerCase();
            if (unit === 'm') val *= 1000;
            else if (unit === 'g') val *= 1000000;
            // if 'k' or empty, assume kbps (standard ffmpeg output is kbits/s usually)
            // actually ffmpeg usually says "kbits/s". Regex group 2 is 'k'.

            this.stats.bitrate = val;
        }

        // fps (status line) e.g. "fps= 30"
        const fpsMatch = output.match(/fps=\s*(\d+(\.\d+)?)/);
        let ffmpegFps = 0;
        if (fpsMatch) {
            ffmpegFps = parseFloat(fpsMatch[1]);
        }

        // Calculate actual FPS based on user logic: actual_fps = ffmpeg_fps / ffmpeg_speed
        if (ffmpegFps > 0 && currentSpeed > 0) {
            this.stats.fps = ffmpegFps / currentSpeed;
        } else if (ffmpegFps > 0) {
            // Fallback if speed is missing (start of stream)
            // this.stats.fps = ffmpegFps; 
            // Logic says if speed > 0.
        }

        // time
        const timeMatch = output.match(/time=(\d{2}):(\d{2}):(\d{2}\.\d{2})/);
        if (timeMatch) {
            const h = parseFloat(timeMatch[1]);
            const m = parseFloat(timeMatch[2]);
            const s = parseFloat(timeMatch[3]);
            this.stats.time = h * 3600 + m * 60 + s;
        }

        this.stats.lastUpdated = Date.now();
    }
}
