# Product Overview

## What this is
YouTube Agent is a topic-to-content engine. You give it a single topic and it
produces a complete, ready-to-publish content package:

- A narration **script** written for smooth text-to-speech delivery.
- **Audio** narration (MP3) using natural neural voices.
- Cross-platform **metadata**: catchy titles, SEO descriptions, tags, and
  hashtags for YouTube, Instagram, and LinkedIn.
- **Thumbnails** in three formats: YouTube 16:9, Instagram/Reel 9:16, and
  square 1:1.

Everything for one run is written into a single, timestamped project folder
under `output/`.

## Who it's for
A solo creator or small team running a YouTube channel plus companion Instagram
and LinkedIn presence, who wants to go from idea to publishable assets fast.

## Core principles
- **Local-first & free**: text/creative work runs on local Ollama models; TTS
  uses free neural voices via edge-tts. No paid API keys required to run.
- **Scalable & pluggable**: every capability (LLM, TTS, thumbnails) sits behind
  an interface so providers can be swapped without touching the pipeline.
- **Partial success over total failure**: if one stage fails (e.g. thumbnails),
  the run still produces the script and whatever else succeeded, recording the
  problem as a warning.
- **Organized output**: each run is self-contained and easy to hand off.

## Primary user actions
1. `POST /generate` (or `python cli.py "<topic>"`) to produce a full package.
2. `GET /voices` to explore available narration voices.
3. `GET /health` to confirm Ollama is reachable and see active models.
