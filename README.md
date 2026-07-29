# Fluid Voice Convo

A web interface for having fluent conversations with an LLM — low-latency voice
in, streamed intelligence, streamed speech out.

## Status: Phase 4 — Full voice loop

Phase 1 established the browser ↔ server WebRTC audio transport. Phase 2 added
streaming speech-to-text (ElevenLabs Scribe v2 Realtime behind a swappable
`STTProvider`). Phase 3 added a generic, swappable intelligence layer
(`IntelligenceProvider` over an OpenAI-compatible streaming endpoint). Phase 4
completes the voice loop with streaming text-to-speech (ElevenLabs behind a
swappable `TTSProvider`): on each committed transcript, the assistant's reply
streams token-by-token into the UI **and** is spoken aloud in the browser as it
generates. Phase 5 will add barge-in handling.

### Prerequisites

- Python 3.11+ (a `uv venv --python 3.11` fetches it for you if your system
  Python is older)
- [uv](https://docs.astral.sh/uv/) — Python package/project manager used
  throughout
- Node.js 20+
- Headphones (recommended to avoid feedback while testing)
- An ElevenLabs API key with Scribe v2 Realtime access (for the STT demo)
- An ElevenLabs voice ID (`ELEVENLABS_TTS_VOICE_ID`) for TTS (for the Phase 4
  voice-loop demo; `ELEVENLABS_TTS_MODEL_ID` is optional, defaults to
  `eleven_multilingual_v2`)
- An OpenAI-compatible chat completions endpoint: `OPENAI_COMPATIBLE_BASE_URL`,
  `OPENAI_COMPATIBLE_API_KEY`, and `OPENAI_COMPATIBLE_MODEL` (for the
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

### Tailscale

By default Vite binds to `localhost`, so the frontend is only reachable from
the same machine. To expose it to other devices on your tailnet, leave Vite on
localhost and proxy it through Tailscale Serve, which terminates TLS and gives
you a secure-context HTTPS URL (required for `getUserMedia` / microphone
access from a non-localhost address).

#### Prerequisite: enable Serve in the tailnet ACL

`tailscale serve --https` needs permission to provision TLS certificates. If
you get "Serve is not enabled on your tailnet," the tailnet admin must add a
`nodeAttrs` grant in the Tailscale admin console (Access Controls):

```json
"nodeAttrs": [
  {
    "target": ["autogroup:member"],
    "attr":   ["funnel"]
  }
]
```

The `funnel` attribute enables HTTPS cert provisioning for both tailnet-only
Serve and public Funnel — there is no separate serve-only attribute.

#### Expose the frontend over HTTPS

```bash
# Terminal 2 — Vite frontend (still on localhost)
cd web && npm install && npm run dev

# Terminal 3 — expose it over HTTPS via Tailscale
# (you may need sudo depending on how Tailscale was installed)
sudo tailscale serve --bg --https 8080 http://localhost:5173
```

Tailscale prints a URL like `https://<machine>.<tailnet>.ts.net:8080`.
You can then access the web UI at `https://yourhost.tailexyz1.ts.net:8080`.
Open that from any device on the tailnet. The browser sees a trusted HTTPS
context, so microphone access works without warnings.

To stop the proxy:

```bash
sudo tailscale serve --https=5173 off
```

#### Allow the Tailscale hostname in Vite

Add the Tailscale MagicDNS hostname to `server.allowedHosts` in
`web/vite.config.ts` so Vite accepts requests proxied through the
Tailscale hostname. In the `server` section, set:

```js
allowedHosts: ["yourhost.tailexyz1.ts.net"],
```

Then restart the Vite dev server so the updated config is applied.

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

### Run the full voice-loop demo (Phase 4)

The live voice loop requires an ElevenLabs API key, an ElevenLabs voice ID,
and an OpenAI-compatible endpoint.

1. Copy `.env.example` to `.env` and set `ELEVENLABS_API_KEY`,
   `ELEVENLABS_TTS_VOICE_ID`, and the three `OPENAI_COMPATIBLE_*` variables
   (base URL, API key, model).
2. Start both dev servers as above.
3. Open the Vite URL, click **Start**, and speak a sentence, then pause. A
   dimmed partial transcript updates live; a committed user turn appears; the
   assistant's reply streams in token-by-token (green-accented) in the UI **and**
   is spoken aloud in the browser as it generates. Speak again and the loop
   repeats, with conversation context preserved across turns.

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

These run in CI on pushes to `main`/`first-cut` and on pull requests (see
`.github/workflows/ci.yml`).

## Architecture

```text
Browser (vanilla TypeScript + Vite)
  │  WebRTC: mic audio up, TTS audio down; transcript + assistant text data channel
  ▼
FastAPI + aiortc
  ├─ /health        — liveness
  └─ /offer         — mic → STT → (committed) → Intelligence → tokens → TTS → audio
```

The browser does no AI logic: mic capture, WebRTC signaling, transcript +
assistant display, and TTS audio playback only. The server owns the peer
connection, feeds audio frames to the `STTProvider`, and on each committed
transcript calls the stateful `IntelligenceProvider`, teeing assistant tokens to
the `transcript` data channel (text) and to the `TTSProvider` (audio pushed onto
an outgoing WebRTC track). Single user, single session.

### Planned phases

- **Phase 5:** barge-in / interruption handling.

Each provider sits behind a protocol so backends can be swapped without touching
the voice transport.

## License

See [LICENSE](LICENSE).
