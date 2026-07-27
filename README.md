# Fluid Voice Convo

A web interface for having fluent conversations with an LLM — low-latency voice
in, streamed intelligence, streamed speech out.

## Status: Phase 2 — Streaming speech-to-text

Phase 1 established the browser ↔ server WebRTC audio transport. Phase 2 adds
streaming speech-to-text: the browser's mic audio is transcribed live and
partial/committed transcripts appear in the UI, powered by ElevenLabs Scribe v2
Realtime behind a swappable `STTProvider` interface. Later phases add a generic
intelligence layer and streamed text-to-speech.

### Prerequisites

- Python 3.11+ (a `uv venv --python 3.11` fetches it for you if your system
  Python is older)
- [uv](https://docs.astral.sh/uv/) — Python package/project manager used
  throughout
- Node.js 20+
- Headphones (recommended to avoid feedback while testing)
- An ElevenLabs API key with Scribe v2 Realtime access (for the STT demo)

### Run the dev servers

Two terminals, both from the repo root:

```bash
# Terminal 1 — FastAPI + WebRTC server
uv venv --python 3.11 && uv pip install -e ".[dev]"
uv run uvicorn app.main:app --reload
```

```bash
# Terminal 2 — Vite frontend
cd web && npm install && npm run dev
```

Open the URL Vite prints (e.g. `http://localhost:5173`), click **Start**, and
speak — partial transcripts appear dimmed and update live; committed turns
append as new lines when you pause.

### Run the STT demo (Phase 2)

The live transcript requires an ElevenLabs API key.

1. Copy `.env.example` to `.env` and set `ELEVENLABS_API_KEY`.
2. Start both dev servers as above.
3. Open the Vite URL, click **Start**, and speak — partial transcripts appear
   dimmed and update live; committed turns append as new lines when you pause.

> **Tip:** Run every Python command through `uv run ...` (e.g.
> `uv run pytest`) so it resolves to the project's `.venv` regardless of
> whether you activated it or use pyenv. Alternatively, `source .venv/bin/activate`
> once per shell and use bare `uvicorn` / `ruff` / `pytest`.

### Tests, lint, and type-check

```bash
uv run ruff check app tests
uv run mypy app
uv run pytest -v
```

These run in CI on every push and pull request (see `.github/workflows/ci.yml`).

## Architecture

```
Browser (vanilla TypeScript + Vite)
  │  WebRTC: audio up, transcript data channel down
  ▼
FastAPI + aiortc
  ├─ /health        — liveness
  └─ /offer         — WebRTC signaling; mic audio → STT → transcript events
```

The browser does no AI logic: mic capture, WebRTC signaling, and transcript
display only. The server owns the peer connection, feeds audio frames to the
`STTProvider`, and relays transcript events back over a `transcript` data
channel. Single user, single session.

### Planned phases

- **Phase 3:** a generic, swappable intelligence layer (stateful provider
  interface over an OpenAI-compatible streaming endpoint).
- **Phase 4:** streaming text-to-speech (ElevenLabs) for the full voice loop.
- **Phase 5:** barge-in / interruption handling.

Each provider sits behind a protocol so backends can be swapped without touching
the voice transport.

## License

See [LICENSE](LICENSE).
