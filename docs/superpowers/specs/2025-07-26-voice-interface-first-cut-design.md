# Fluid Voice Interface — First-Cut Design

**Date:** 2025-07-26
**Branch:** `first-cut`
**Status:** Approved — ready for implementation planning

## Purpose

Build a low-latency, natural voice conversation interface over a web browser. The
user speaks; the system transcribes, thinks, and speaks back — with every stage
streaming so response feels immediate. The intelligence layer is **generic and
swappable**: v1 uses an OpenAI-compatible streaming endpoint, but the architecture
is designed so a stateful agent system (e.g. Hermes) can drop in later without
touching the voice transport.

## Topology

```
Browser (vanilla TypeScript + Vite)
  │  WebRTC (Opus audio, bidirectional)
  ▼
Raspberry Pi: FastAPI + aiortc
  │
  ├─ SessionManager       (owns message history, turn state, cancellation)
  ├─ STTProvider          → ElevenLabs Scribe v2 Realtime (WebSocket streaming)
  ├─ IntelligenceProvider → OpenAI-compatible streaming client (stateful wrapper)
  └─ TTSProvider          → ElevenLabs streaming TTS (WebSocket streaming)
```

All heavy inference runs in cloud APIs. The Pi orchestrates and holds state but
runs no models itself.

## Division of Labor

- **Browser** — microphone capture, audio playback, live transcript display. No
  AI logic, no model calls. Vanilla TypeScript + Vite; no framework.
- **Pi (FastAPI)** — WebRTC termination, session state, provider plumbing,
  streaming pipeline orchestration. No heavy inference.
- **STTProvider** — streaming speech-to-text, emits partial + committed transcripts.
- **IntelligenceProvider** — holds conversation history, produces streamed assistant
  tokens. Stateless *transport* (OpenAI-compatible), stateful *interface*.
- **TTSProvider** — streamed text-to-speech, emits audio frames as they're ready.

## Provider Contracts

All providers are async and cancellable. Cancellation is built into the interface
from day one (via `asyncio` task cancellation) even though barge-in *logic* is
deferred to Phase 5 — this avoids a later interface change.

### STTProvider

```python
@dataclass
class TranscriptEvent:
    kind: Literal["partial", "committed"]
    text: str

class STTProvider(Protocol):
    async def stream(
        self, audio_frames: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptEvent]: ...
```

- v1 implementation: ElevenLabs Scribe v2 Realtime over WebSocket.
- Consumes PCM audio frames from the WebRTC mic track; emits partial transcripts
  for live display and committed transcripts to feed the intelligence layer.
- Uses VAD commit strategy (recommended for microphone input by the API docs).
- Behind the interface so Deepgram / faster-whisper / local Whisper can drop in later.

### IntelligenceProvider (stateful, option C)

```python
class IntelligenceProvider(Protocol):
    async def ingest(self, user_text: str) -> None: ...
    async def stream_response(self) -> AsyncIterator[str]: ...
```

- `ingest()` appends a user message to the provider's in-memory history.
- `stream_response()` appends an assistant placeholder, streams tokens (yielding
  each delta), and finalizes the assistant message in history when the stream ends.
- v1 implementation holds message history in memory and internally calls an
  OpenAI-compatible `/v1/chat/completions` endpoint with `stream: true`, sending
  the full message array each turn. The provider is a **stateful wrapper over a
  stateless transport**.
- The interface is Hermes-shaped (stateful, decision-capable) so a future
  stateful agent backend can implement the same protocol without breaking the
  voice layer. No tool-calling / decisions / memory in v1 — straight streamed chat
  completions.

### TTSProvider

```python
class TTSProvider(Protocol):
    async def stream(
        self, text_chunks: AsyncIterator[str]
    ) -> AsyncIterator[bytes]: ...
```

- v1 implementation: ElevenLabs streaming TTS over WebSocket.
- Consumes text chunks (tokens) from the intelligence layer; emits audio frames
  suitable for the WebRTC outgoing track.
- Behind the interface so other TTS systems can drop in later.

## Streaming Pipeline

The core principle: **everything overlaps; never wait for a stage to fully
complete before starting the next.**

1. Browser captures mic audio and streams it to the Pi over WebRTC.
2. Pi feeds audio frames into `STTProvider.stream()`.
3. On each **committed** transcript, the session manager calls
   `IntelligenceProvider.ingest(text)` then `stream_response()`.
4. Assistant tokens flow immediately into `TTSProvider.stream()`.
5. TTS audio frames flow back to the browser over WebRTC and play immediately.
6. Partial transcripts stream to the browser for live display (not fed to the
   intelligence layer — only committed turns are).

Token→TTS chunking is **sentence/clause-boundary aware** so TTS gets natural
boundaries and doesn't produce robotic mid-word breaks. The intelligence stream is
buffered just enough to emit on `.`, `,`, `!`, `?`, or a flush threshold.

## Session & State

- **Single user, single session** for v1. No multi-tenancy, no concurrency across
  sessions.
- The **SessionManager** (on the Pi) owns:
  - the active WebRTC peer connection,
  - the running asyncio tasks for STT / intelligence / TTS,
  - cancellation handles for barge-in (Phase 5),
  - a reference to the `IntelligenceProvider` (which itself owns message history).
- Conversation history lives in the `IntelligenceProvider`, not the session
  manager — the session manager owns *turn* state, the provider owns *message
  history*. This keeps the swappable boundary clean.

## Interruption (Phase 5 — deferred, but enabled now)

No barge-in *logic* in v1. But because every provider stream is an
`AsyncIterator` driven by asyncio tasks, cancellation is nearly free: the session
manager can cancel the in-flight intelligence + TTS tasks and restart STT when the
user speaks again. The interfaces require no change in Phase 5; only orchestration
logic is added.

Detection of barge-in (VAD on the mic stream while TTS plays) is an open
implementation detail for Phase 5, not a v1 design decision.

## Implementation Phases

Each phase is independently demoable.

1. **FastAPI + WebRTC loopback** — browser ↔ Pi audio round-trips with no AI.
   Establishes the transport, the project skeleton (Python package + Vite frontend),
   and the dev workflow.
2. **Streaming STT** — wire `STTProvider` (Scribe v2 Realtime); show live partial
   + committed transcript in the browser. No intelligence, no TTS yet.
3. **Intelligence layer** — wire `IntelligenceProvider` (OpenAI-compatible
   streaming); display streamed assistant text in the browser. No TTS yet.
4. **TTS** — wire `TTSProvider` (ElevenLabs streaming); full voice loop:
   speech → transcript → assistant text → spoken audio.
5. **Interruption** — barge-in: cancel in-flight intelligence + TTS on user
   speech, restart the loop. Interfaces already support it; this is orchestration.

## Non-Goals (v1)

- Multi-session / multi-user.
- Tool-calling, decisions, RAG, memory, or agent-style branching. (The interface
  leaves room for these as a richer provider implementation later.)
- Discord voice, SIP, native mobile transports. (The intelligence-layer interface
  is transport-agnostic so these can be added later.)
- Speaker diarization.
- Conversation persistence / database.

## Configuration & Secrets

- ElevenLabs API key, OpenAI-compatible endpoint URL + key, and model names are
  read from environment variables (`.env` locally). Never exposed to the browser.
- The browser gets no API keys; all provider calls happen on the Pi.

## Open Questions Deferred to Implementation

- Exact sentence/chunk flush thresholds for token→TTS handoff (tune in Phase 4).
- WebRTC ICE configuration for the Pi (STUN/TURN) — local-network first; add STUN
  if remote-browser testing is needed.
- Barge-in VAD tuning (Phase 5).
