
import React, { useRef, useEffect, useState } from 'react';
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Play, Pause, ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";
import { Card } from "@/components/ui/card";

/**
 * TimelineControl component
 * 
 * Provides a playback interface for session history.
 * 
 * Props:
 * - minTime: start timestamp (seconds)
 * - maxTime: end timestamp (seconds)
 * - currentTime: current playback position (seconds)
 * - onTimeChange: callback when time changes (seconds)
 * - isLive: boolean, true if currently at the latest edge
 * - onLiveClick: callback to jump to live
 */
export function TimelineControl({ minTime, maxTime, currentTime, onTimeChange, isLive, onLiveClick }) {
    const [isPlaying, setIsPlaying] = useState(false);
    const playbackRef = useRef(null);

    // Auto-playback logic
    useEffect(() => {
        if (isPlaying) {
            playbackRef.current = setInterval(() => {
                onTimeChange(prev => {
                    const next = prev + 1; // 1x speed
                    if (next >= maxTime) {
                        setIsPlaying(false);
                        return maxTime;
                    }
                    return next;
                });
            }, 1000); // Update every second
        } else {
            clearInterval(playbackRef.current);
        }
        return () => clearInterval(playbackRef.current);
    }, [isPlaying, maxTime, onTimeChange]);

    const formatTime = (timestamp) => {
        if (!timestamp) return '--:--:--';
        const date = new Date(timestamp * 1000);
        return date.toLocaleTimeString();
    };

    const handleSliderChange = (value) => {
        onTimeChange(value[0]);
        setIsPlaying(false); // Pause on user interaction
    };

    return (
        <Card className="p-4 border-t sticky bottom-0 z-50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex flex-col gap-4">
                {/* Time Info & Live Badge */}
                <div className="flex justify-between items-center text-sm">
                    <div className="font-mono tabular-nums text-muted-foreground">
                        {formatTime(currentTime)}
                    </div>
                    <div className="flex items-center gap-2">
                        {isLive ? (
                            <span className="flex h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                        ) : (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 text-xs text-muted-foreground hover:text-primary"
                                onClick={onLiveClick}
                            >
                                Return to Live
                            </Button>
                        )}
                        <span className={isLive ? "font-bold text-red-500" : "text-muted-foreground"}>
                            {isLive ? "LIVE" : "HISTORY"}
                        </span>
                    </div>
                </div>

                {/* Slider */}
                <div className="relative">
                    <Slider
                        value={[currentTime]}
                        min={minTime}
                        max={maxTime}
                        step={1}
                        onValueChange={handleSliderChange}
                        className="cursor-pointer"
                    />
                </div>

                {/* Controls */}
                <div className="flex justify-center items-center gap-2">
                    <Button variant="ghost" size="icon" onClick={() => onTimeChange(Math.max(minTime, currentTime - 10))}>
                        <ChevronLeft className="h-4 w-4" />
                    </Button>

                    <Button variant="outline" size="icon" onClick={() => setIsPlaying(!isPlaying)}>
                        {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                    </Button>

                    <Button variant="ghost" size="icon" onClick={() => onTimeChange(Math.min(maxTime, currentTime + 10))}>
                        <ChevronRight className="h-4 w-4" />
                    </Button>
                </div>
            </div>
        </Card>
    );
}
