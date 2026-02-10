
import React, { useRef, useEffect, useState, useMemo } from 'react';
import { Button } from "@/components/ui/button";
import { Play, Pause, ChevronLeft, ChevronRight, SkipForward } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * TimelineControl component
 * 
 * A video-editor style timeline with a time ruler, scrubbable playhead, and potential for tracks.
 */
export function TimelineControl({ minTime, maxTime, currentTime, onTimeChange, isLive, onLiveClick }) {
    const [isPlaying, setIsPlaying] = useState(false);
    const [zoomLevel, setZoomLevel] = useState(1); // Pixels per second
    const containerRef = useRef(null);
    const playbackRef = useRef(null);
    const [isDragging, setIsDragging] = useState(false);

    // Calculate total duration
    const duration = Math.max(1, maxTime - minTime);

    // Auto-playback logic
    useEffect(() => {
        if (isPlaying) {
            playbackRef.current = setInterval(() => {
                onTimeChange(prev => {
                    const next = prev + 1;
                    if (next >= maxTime) {
                        setIsPlaying(false);
                        return maxTime;
                    }
                    return next;
                });
            }, 1000);
        } else {
            clearInterval(playbackRef.current);
        }
        return () => clearInterval(playbackRef.current);
    }, [isPlaying, maxTime, onTimeChange]);

    // Handle mouse events for scrubbing
    const handleMouseDown = (e) => {
        setIsDragging(true);
        setIsPlaying(false);
        updateTimeFromMouse(e);
    };

    const handleMouseMove = (e) => {
        if (isDragging) {
            updateTimeFromMouse(e);
        }
    };

    const handleMouseUp = () => {
        setIsDragging(false);
    };

    useEffect(() => {
        if (isDragging) {
            window.addEventListener('mousemove', handleMouseMove);
            window.addEventListener('mouseup', handleMouseUp);
        }
        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [isDragging]);

    const updateTimeFromMouse = (e) => {
        if (!containerRef.current) return;
        const rect = containerRef.current.getBoundingClientRect();
        const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
        const percentage = x / rect.width;
        const newTime = minTime + (percentage * duration);
        onTimeChange(Math.floor(newTime));
    };

    // Format time for display (HH:MM:SS)
    const formatTime = (timestamp) => {
        if (!timestamp) return '--:--:--';
        const date = new Date(timestamp * 1000);
        return date.toLocaleTimeString('en-US', { hour12: false });
    };

    // Calculate position percentage for an item
    const getPosition = (time) => {
        const relativeTime = Math.max(0, Math.min(time - minTime, duration));
        return (relativeTime / duration) * 100;
    };

    // Generate ticks for the ruler
    const ticks = useMemo(() => {
        const tickCount = 10; // Target number of ticks
        const interval = duration / tickCount;
        const generatedTicks = [];

        for (let i = 0; i <= tickCount; i++) {
            const time = minTime + (i * interval);
            generatedTicks.push({
                time,
                label: formatTime(time),
                percent: (i / tickCount) * 100
            });
        }
        return generatedTicks;
    }, [minTime, duration]);

    return (
        <Card className="border-t sticky bottom-0 z-50 bg-background/95 backdrop-blur shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)]">
            <div className="flex flex-col">
                {/* Toolbar */}
                <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
                    <div className="flex items-center gap-2">
                        <div className="flex items-center bg-background rounded-md border px-2 py-1">
                            <span className={`text-xs font-bold mr-2 ${isLive ? 'text-red-500 animate-pulse' : 'text-muted-foreground'}`}>
                                {isLive ? 'LIVE' : 'REC'}
                            </span>
                            <span className="font-mono text-sm tabular-nums text-foreground">
                                {formatTime(currentTime)}
                            </span>
                        </div>
                        {!isLive && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs gap-1 hover:text-primary hover:bg-primary/10"
                                onClick={onLiveClick}
                            >
                                <SkipForward className="h-3 w-3" />
                                Return to Live
                            </Button>
                        )}
                    </div>

                    <div className="flex items-center gap-1">
                        <Button
                            variant="secondary"
                            size="icon"
                            className="h-8 w-8 rounded-full"
                            onClick={() => setIsPlaying(!isPlaying)}
                        >
                            {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
                        </Button>
                    </div>

                    <div className="w-24"></div> {/* Spacer for balance */}
                </div>

                {/* Timeline Area */}
                <div
                    ref={containerRef}
                    className="relative h-24 w-full cursor-pointer select-none overflow-hidden bg-zinc-900/5 dark:bg-zinc-950/50"
                    onMouseDown={handleMouseDown}
                >
                    {/* Ruler */}
                    <div className="absolute top-0 left-0 right-0 h-6 border-b border-white/5 bg-background/50">
                        {ticks.map((tick, i) => (
                            <div
                                key={i}
                                className="absolute top-0 bottom-0 pointer-events-none border-l border-zinc-400/30 dark:border-zinc-600/50"
                                style={{ left: `${tick.percent}%` }}
                            >
                                <span className="absolute left-1 top-1 text-[9px] text-muted-foreground font-mono">
                                    {tick.label}
                                </span>
                            </div>
                        ))}
                    </div>

                    {/* Tracks Area (Visual placeholder for now) */}
                    <div className="absolute top-6 bottom-0 left-0 right-0 p-1 opacity-50">
                        <div className="h-full w-full bg-stripe-pattern opacity-10"></div>
                    </div>

                    {/* Playhead / Cursor */}
                    <div
                        className="absolute top-0 bottom-0 w-[1px] bg-red-500 z-10 pointer-events-none shadow-[0_0_10px_rgba(239,68,68,0.5)]"
                        style={{ left: `${getPosition(currentTime)}%` }}
                    >
                        <div className="absolute -top-[1px] -left-[4px] w-[9px] h-[9px] bg-red-500 transform rotate-45 rounded-[1px] shadow-sm"></div>
                        <div className="absolute bottom-0 -left-[2px] w-[4px] h-[4px] bg-red-500 rounded-full"></div>
                    </div>

                    {/* Hover Effect (optional - could add a ghost cursor) */}
                </div>
            </div>
        </Card>
    );
}
