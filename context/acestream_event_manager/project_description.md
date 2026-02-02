Hello Copilot,

I am working on a project that will tackle the issue of having sources of AceStream streams that can become unstable over time. 
My setup currently involves Dispatcharr, which gathers streams into channels and puts a proxy in front of these, so that the client only sees one channel and Dispatcharr changes between streams if they get buffer.
I currently use an external tool that uses ffmpeg and orders the streams by quality before the EPG events that I select, but this doesn't help if those streams work well for 5 minutes and then become unstable. I also have a tool called AceStream Orchestrator that provides a robust AceStream Backend that can play 100s of streams at the same time.
The purpose of this tool is to gather the streams from Dispatcharr for certain channels (by matching them against the desired regex) and when a desired EPG event starts:
1. Order them by quality, bitrate and framerate.
2. Dead streams should be put on "quarantine", and be periodically checked again in case they get revived. During the event the sources (m3u accounts) should be refreshed as they may get new matching streams and delete non working ones.
3. Alive streams should be continuously monitored using ffmpeg. You should use the Null Muxer approach (-c copy -f null -), so that the process is as light as we can, since we might be continuously monitoring tens of streams at the same time. FFMpeg can, by measuring stream speed, give info about buffering. Also, the orchestrator's /streams endpoint can provide information about how the AceStream Backend is processing the streams (check the streams_endpoint.json).
4. With this information obtained and evaluated throughout the session, this tool should keep a stream order that prioritizes stabilities so that end users can enjoy a seamless streaming experience with the least amount of stream changes as possible.

The project should feature session and stats storage using databases, a modern UI based in ShadCN.

Resources at your disposition:
- Dispatcharr instance @ http://100.107.251.48:9191/ with user: anderregidor and password: 3tx8qBSB2HC&2E
- AceStream Orchestrator instance @ http://100.107.251.48:8000/
- Dispatcharr API documentation in the file dispatcharr_api.json
- Example of the output of the Orchestrator's /streams endpoint in the file streams_endpoint.json
