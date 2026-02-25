# Stream Monitoring

## Overview

Stream Monitoring is a live health tracking system that runs independently of the main automation pipeline. It maintains a session for each active stream and continuously evaluates quality over time, storing history for review.

---

## Sessions

A **stream session** starts when StreamFlow begins monitoring a stream and ends when the stream is stopped, replaced, or fails. Each session tracks:

- Start/end time and total duration
- Quality samples (bitrate, FPS, resolution) taken at regular intervals
- Error events (decode errors, dropped frames, stalls)
- Reliability score — computed from error rate and uptime consistency
- Screenshots captured at configurable intervals

Session data is persisted and accessible from the **Stream Monitoring** page in the UI.

---

## Reliability scoring

Each session produces a **reliability score** (0–100) based on:

- Ratio of error frames to total frames
- Number of stall events
- Uptime consistency (dropped connections vs. total session time)

Higher = more reliable. Used to inform stream replacement decisions.

---

## Timeline

The monitoring page includes an interactive timeline — similar to a video editor's timeline — showing the complete history of stream sessions for a channel. You can scrub through it to inspect quality metrics at any point in time.

Metrics displayed on the timeline:

- Bitrate
- FPS
- Resolution changes
- Error events
- Screenshots at sample points

---

## Screenshots

StreamFlow can capture screenshots from a running stream at configured intervals using ffmpeg. Screenshots are stored locally and linked to their corresponding session and timestamp.

---

## FFmpeg-based monitoring

Live monitoring uses `ffmpeg_stream_monitor.py`, which spawns a persistent ffmpeg process per stream and parses stderr output in real time to extract quality metrics without requiring a separate ffprobe call or additional stream connection.
