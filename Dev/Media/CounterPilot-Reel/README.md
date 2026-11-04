# CounterPilot Reel: recording package

Approved format: 3:45, vertical, the creator's voiceover over real screen recordings. Narration and shot directions are maintained in `scenes.json`. This package changes no application behavior.

Generated files live in `artifacts/counterpilot-reel/`. Start with `START_HERE.md` there. The package includes a read-aloud script, the complete timed recording guide, provisional subtitle timing, silent footage and a silent picture cut when capture succeeds. The creator's recorded narration is still needed; subtitle timing must follow the recorded voice before publishing.

Event source checked November 3, 2026: https://dev.meta.ai/events/global-hackathon. Verified: event title, worldwide virtual format, ten-day build period, $1,000,000 total prize pool and Build for Your World theme. No deadline, winner/finalist status or endorsement claim belongs in this video.

The app sequence uses the configured live Meta adapter and the actual local catalog, not intercepted responses. API errors stop capture. Capture runs in a separate browser context with an empty Garage and fresh chat; it does not change the user's saved browser data. Raw recordings and timing metadata remain available for editing. Source files and API credentials are never filmed.

To reproduce, start the local app with network access for Meta. Set `COUNTERPILOT_CHAT_URL`, `COUNTERPILOT_PLAYWRIGHT` and `PLAYWRIGHT_BROWSERS_PATH` for the installed local tools. Run `capture.cjs` with Node, then `package.py` with Python and Pillow. Set `COUNTERPILOT_FFMPEG` to the encoder executable for MP4 export. The browser cache and temporary encoder used for this session are inside ignored `artifacts/`.
