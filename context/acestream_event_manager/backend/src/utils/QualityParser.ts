export interface StreamQuality {
    width: number;
    height: number;
    fps: number;
    bitrate: number; // Inferred or 0
    priority: number; // Higher is better
}

export class QualityParser {
    static parse(name: string): StreamQuality {
        let width = 0;
        let height = 0;
        let fps = 0;
        let priority = 0;

        const lowerName = name.toLowerCase();

        // Resolution inference
        if (lowerName.includes('4k') || lowerName.includes('2160p')) {
            height = 2160;
            width = 3840;
            priority += 4000;
        } else if (lowerName.includes('1080p')) {
            height = 1080;
            width = 1920;
            priority += 1080;
        } else if (lowerName.includes('720p')) {
            height = 720;
            width = 1280;
            priority += 720;
        } else if (lowerName.includes('576p')) {
            height = 576;
            priority += 576;
        } else if (lowerName.includes('480p') || lowerName.includes('sd')) {
            height = 480;
            priority += 480;
        }

        // FPS inference
        if (lowerName.includes('50fps') || lowerName.includes('60fps')) {
            fps = 50; // Treat 50/60 similar for priority
            priority += 100;
        } else if (lowerName.includes('25fps') || lowerName.includes('30fps')) {
            fps = 25;
        }

        // Bitrate is hard to guess from name, defaulting to 0
        return { width, height, fps, bitrate: 0, priority };
    }
}
