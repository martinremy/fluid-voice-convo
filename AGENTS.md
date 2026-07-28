# Fluid Voice Convo

A web interface for having fluent conversations with an LLM — low-latency voice
in, streamed intelligence, streamed speech out. Open source.

## Status

Phases 1–4 (WebRTC transport, streaming STT, intelligence, TTS) are implemented
on the `first-cut` branch — the full voice loop works. Phase 5 (barge-in /
interruption) is deferred to a separate PR. See `README.md` for the user-facing
dev workflow; this file is for coding agents.

## Running dev notes

Brainstorming, architecture notes, open questions, and in-progress thinking go
in [running-dev-notes/](running-dev-notes/) at the **repo root**.

- **Naming convention:** `YYYYMMDD-short-topic.md`. Date-prefixed filenames sort
  chronologically and make the evolution of thinking easy to trace.
- **Diagrams:** commit both source (`.mmd`, `.excalidraw`, etc.) *and* a rendered
  image (`.svg`, `.png`). Renders serve readers who don't want to run tooling;
  source is for whoever needs to update the diagram.
- **Before starting new work**, skim recent dev-notes to avoid re-treading ground.

## Architecture (load-bearing)

```text
Browser (vanilla TS + Vite) ──WebRTC──► FastAPI + aiortc
                                         ├─ STTProvider   → ElevenLabs Scribe v2 Realtime
                                         ├─ IntelligenceProvider → OpenAI-compatible streaming endpoint
                                         └─ TTSProvider   → ElevenLabs streaming TTS
```

- The **browser does no AI logic** — only mic capture, WebRTC signaling, and
  rendering. All inference runs on the server via cloud APIs.
- Each provider sits behind a `Protocol` so backends can be swapped without
  touching the WebRTC transport. Keep that seam intact.
- The browser creates the `transcript` data channel; the server receives it via
  `on("datachannel")` and sends `{"kind": "partial"|"committed"|"error",
  "text": ...}` JSON. WebRTC forbids the answerer from adding m-lines, so the
  server cannot create the channel itself.
- `app/webrtc.py`'s `STTStarter` joins the audio-track and datachannel events
  (they fire independently, in either order) and starts STT exactly once.

## Commands (always via `uv run`)

```bash
uv venv --python 3.11 && uv pip install -e ".[dev]"   # one-time setup
uv run uvicorn app.main:app --reload                   # backend
cd web && npm install && npm run dev                   # frontend (separate shell)
uv run ruff check app tests && uv run mypy app && uv run pytest -v   # verify
```

`uv run` is required because pyenv shims intercept bare commands. CI
(`.github/workflows/ci.yml`) runs the same ruff + mypy + pytest + frontend
build — keep it green.

## Hard constraints

- **Python 3.11+**, `from __future__ import annotations` in every module.
- **No secrets in the browser.** API keys live in `.env` (gitignored),
  loaded via `load_dotenv()` in `app/main.py`. `.env.example` documents them.
- **Tests are hermetic** — no real network calls, no API keys in CI. Provider
  implementations are tested through an injectable seam (`RealtimeConnection`
  / the `_connection=` kwarg); the live SDK adapter is unit-tested on its pure
  logic only and verified by the manual demo.
- **Single user, single session** for v1. No multi-tenancy, no concurrency
  across sessions. Don't add worker processes.
- **No heavy inference on the server** — it orchestrates and holds state only.
- Browser WebRTC audio is **48 kHz Opus**; resample to 16 kHz s16 mono before
  sending to ElevenLabs (`av.AudioResampler`).

## Debugging discipline (read this before fixing runtime bugs)

- **Diagnostics before fixes.** Observe the real failure before changing code.
  A green suite is not verification if no test exercises the failing path.
- **Verify the diagnostics themselves.** `logger.setLevel(INFO)` with no
  handler prints nothing — run the logging path and confirm the line appears
  before asking anyone to check logs. `app/main.py` attaches a `StreamHandler`
  to the `app` logger for this reason; don't remove it.
- **Reproduce locally** with a real aiortc peer when possible (see the test
  harness pattern in `tests/test_offer_handshake.py`). Only ask a human to run
  the live mic demo once the server-side flow is confirmed.
- **Never claim verification you didn't do.** A test that asserts on a test-only
  observation instead of the real side effect is not coverage.
