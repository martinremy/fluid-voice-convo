# Fluid Voice Convo

A web interface for having fluent conversations with an LLM — low-latency voice
in, streamed intelligence, streamed speech out.

## Status: Phase 1 — WebRTC audio loopback

Phase 1 establishes the browser ↔ server audio transport. Speak into the mic and
hear yourself back, proving the round-trip path that later phases fill with
streaming speech-to-text, a generic intelligence layer, and streaming
text-to-speech.

### Prerequisites

- Python 3.11+
- Node.js 20+
- Headphones (to avoid feedback during the loopback demo)

### Run the dev servers

Two terminals, both from the repo root:

```bash
# Terminal 1 — FastAPI + WebRTC server
uv venv --python 3.11 && uv pip install -e ".[dev]"
uvicorn app.main:app --reload
```

```bash
# Terminal 2 — Vite frontend
cd web && npm install && npm run dev
```

Open the URL Vite prints (e.g. `http://localhost:5173`), put on headphones,
click **Start loopback**, and speak.

### Tests, lint, and type-check

```bash
ruff check app tests
mypy app
pytest -v
```

These run in CI on every push and pull request (see `.github/workflows/ci.yml`).

## Architecture

```
Browser (vanilla TypeScript + Vite)
  │  WebRTC (Opus audio, bidirectional)
  ▼
FastAPI + aiortc
  ├─ /health        — liveness
  └─ /offer         — WebRTC signaling; loops incoming audio back to the peer
```

The browser does no AI logic: mic capture, WebRTC signaling, and audio playback
only. The server owns the peer connection and relays frames. Single user,
single session.

### Planned phases

- **Phase 2:** streaming speech-to-text (ElevenLabs Scribe v2 Realtime) with a
  live transcript in the browser.
- **Phase 3:** a generic, swappable intelligence layer (stateful provider
  interface over an OpenAI-compatible streaming endpoint).
- **Phase 4:** streaming text-to-speech (ElevenLabs) for the full voice loop.
- **Phase 5:** barge-in / interruption handling.

Each provider sits behind a protocol so backends can be swapped without touching
the voice transport.

## License

See [LICENSE](LICENSE).
