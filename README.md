# Fluid Voice Convo

A web interface for having fluent conversations with an LLM — low-latency voice
in, streamed intelligence, streamed speech out.

## Status: Phase 3 — Streaming intelligence

Phase 1 established the browser ↔ server WebRTC audio transport. Phase 2 added
streaming speech-to-text (ElevenLabs Scribe v2 Realtime behind a swappable
`STTProvider`). Phase 3 adds a generic, swappable intelligence layer: on each
committed transcript, the assistant's response streams token-by-token into the
UI, powered by an OpenAI-compatible streaming endpoint behind a stateful
`IntelligenceProvider` interface. Later phases add streamed text-to-speech and
barge-in handling.

### Prerequisites

- Python 3.11+ (a `uv venv --python 3.11` fetches it for you if your system
  Python is older)
- [uv](https://docs.astral.sh/uv/) — Python package/project manager used
  throughout
- Node.js 20+
- Headphones (recommended to avoid feedback while testing)
- An ElevenLabs API key with Scribe v2 Realtime access (for the STT demo)
- An OpenAI-compatible chat completions endpoint: `OPENAI_COMPATIBLE_BASE_URL`,
  `OPENAI_COMPATIBLE_API_KEY`, and `OPENAI_COMPATIBLE_MODEL` (for the Phase 3
  conversation demo)

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

### Run the conversation demo (Phase 3)

The live conversation requires an ElevenLabs API key **and** an
OpenAI-compatible endpoint.

1. Copy `.env.example` to `.env` and set `ELEVENLABS_API_KEY` and the three
   `OPENAI_COMPATIBLE_*` variables (base URL, API key, model).
2. Start both dev servers as above.
3. Open the Vite URL, click **Start**, and speak a sentence, then pause. A
   dimmed partial transcript updates live; a committed user turn appears; then
   the assistant's reply streams in token-by-token (green-accented) and
   finalizes into the turns list. Speak again and the assistant responds again,
   with conversation context preserved across turns.

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
  │  WebRTC: audio up, transcript + assistant text data channel down
  ▼
FastAPI + aiortc
  ├─ /health        — liveness
  └─ /offer         — mic audio → STT → (committed) → Intelligence → tokens
```

The browser does no AI logic: mic capture, WebRTC signaling, and transcript +
assistant display only. The server owns the peer connection, feeds audio frames
to the `STTProvider`, and on each committed transcript calls the stateful
`IntelligenceProvider`, streaming assistant tokens back over the `transcript`
data channel. Single user, single session.

### Planned phases

- **Phase 4:** streaming text-to-speech (ElevenLabs) for the full voice loop.
- **Phase 5:** barge-in / interruption handling.

Each provider sits behind a protocol so backends can be swapped without touching
the voice transport.

## License

See [LICENSE](LICENSE).
