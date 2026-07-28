# 2025-07-26 — Phases 1–4: WebRTC transport, streaming STT, intelligence, TTS

## Scope

Built the first four phases of the fluid voice conversation interface on the
`first-cut` branch, taking the project from an empty repo to a working
end-to-end voice loop: speak → transcript → assistant reply (text + spoken).

- **Phase 1** — FastAPI + aiortc WebRTC transport; browser mic capture and a
  loopback demo to prove the audio round-trip.
- **Phase 2** — streaming speech-to-text (ElevenLabs Scribe v2 Realtime) behind
  a swappable `STTProvider` protocol; live transcript in the browser.
- **Phase 3** — a generic, swappable intelligence layer (`IntelligenceProvider`,
  stateful "option C" over an OpenAI-compatible streaming endpoint); assistant
  tokens stream into the browser.
- **Phase 4** — streaming text-to-speech (ElevenLabs `convert_realtime`) behind
  a `TTSProvider` protocol; assistant replies are spoken aloud, completing the
  voice loop.

## Architecture as built

```text
Browser (vanilla TS + Vite)
  │  WebRTC: mic audio up, TTS audio down; transcript + assistant text data channel
  ▼
FastAPI + aiortc
  ├─ /health        — liveness
  └─ /offer         — mic → STT → (committed) → Intelligence → tokens → TTS → audio
```

Each provider (`STTProvider`, `IntelligenceProvider`, `TTSProvider`) sits behind
a `Protocol` so backends can be swapped without touching the WebRTC transport.
The intelligence provider is **stateful over a stateless transport**: it holds
message history in memory and re-sends the full array on each turn (keeps the
interface Hermes-shaped for a future stateful agent backend). Single user,
single session for v1.

## Key decisions

- **Provider protocols + injectable seams.** Every provider has an injectable
  seam (`RealtimeConnection` for STT, `ChatCompleter` for intelligence,
  `_tts_callable` for TTS) so CI is hermetic — no real network, no API keys.
  The live SDK adapters are unit-tested on pure logic only and verified by the
  manual demo.
- **Stateful intelligence (option C).** Chosen over a stateless provider so the
  interface stays swappable for a future Hermes-style stateful agent without
  breaking the voice layer.
- **Browser creates the `transcript` data channel.** WebRTC forbids the
  answerer from adding m-lines, so the server can't create the channel — it
  receives it via `on("datachannel")`.
- **`STTStarter` joins the audio-track and datachannel events.** They fire
  independently in either order; the join starts STT exactly once both arrive.
- **TTSOutputTrack lives for the whole connection.** It emits silence between
  TTS bursts so aiortc's `RTCRtpSender` keeps pulling. A per-turn
  `stop_stream()` kills the sender after the first `MediaStreamError` and turns
  2+ go silent — see "Bugs that bit us" below.
- **Resample 48 kHz → 16 kHz for ElevenLabs.** Browser WebRTC Opus decodes at
  48 kHz; ElevenLabs wants 16 kHz. Outgoing TTS is `pcm_16000`, resampled to
  48 kHz for the WebRTC track.

## Bugs that bit us (and the lessons)

Several runtime bugs surfaced only during manual demoing because the hermetic
tests can't exercise live WebRTC event ordering or real SDK behavior. Each is
now guarded by a regression test on the testable parts.

1. **`python-dotenv` declared but never called.** `.env` was never loaded, so
   `ELEVENLABS_API_KEY` was unset at runtime and STT failed with a swallowed
   `RuntimeError`. Fix: `load_dotenv()` in `app/main.py`. Lesson: **a green
   suite is not verification if no test exercises the failing runtime path.**
2. **`STTStarter` recorded `start_calls` but never dispatched.** The join logic
   was extracted for testability, but the test asserted on the observation list
   instead of the real side effect — so it passed against broken code. Lesson:
   **a test that asserts on a test-only observation is a lie in green.**
3. **ElevenLabs CLOSE event has no argument.** The SDK emits `RealtimeEvents.CLOSE`
   with a bare `_emit(CLOSE)`; my `_enqueue(self, msg)` required `msg` and
   crashed, hanging the stream. Fix: `msg: object | None = None`.
4. **App INFO logs were silently dropped.** `logger.setLevel(INFO)` with no
   handler prints nothing; three rounds of "check the logs" were theater. Fix:
   attach a `StreamHandler` to the `app` logger in `app/main.py`. Lesson:
   **verify the diagnostics themselves before asking anyone to check logs.**
5. **48 kHz audio mislabeled as 16 kHz.** Browser Opus decodes at 48 kHz; raw
   bytes sent to ElevenLabs as `sample_rate: 16000` were garbled → no
   transcripts. Fix: `av.AudioResampler` 48k→16k.
6. **Tee deadlock in `_respond_with_tts`.** A single queue consumed by three
   readers with items put once deadlocked. Fix: duplicate each token to two
   queues (one per consumer).
7. **`pc.addTrack` before `setRemoteDescription`** broke SDP direction
   negotiation. Fix: add the outgoing track in `on("track")` when the audio
   transceiver exists.
8. **`TTSOutputTrack` ended per turn.** `stop_stream()` → `MediaStreamError` →
   aiortc's `RTCRtpSender` permanently stops pulling → turns 2+ silent. Fix:
   the track lives for the connection and emits silence between bursts.
9. **ElevenLabs `convert_realtime` `voice_settings` sentinel.** The SDK defaults
   `voice_settings` to an `Ellipsis` sentinel that is truthy, so its internal
   `voice_settings.dict() if voice_settings else None` crashes. Fix: pass
   `voice_settings=None` explicitly.

These drove the debugging-discipline rules now in `~/.pi/agent/AGENTS.md` and
the repo `AGENTS.md`: **diagnostics before fixes, verify the diagnostics
themselves, never claim verification you didn't do.**

## Open questions / deferred

- **Phase 5 (barge-in / interruption) is deferred to a separate PR.** The
  interfaces are already cancellable (async iterators + asyncio tasks), so the
  work is orchestration: on user speech while the assistant is responding,
  cancel the in-flight intelligence + TTS, flush the `TTSOutputTrack` buffer,
  and restart STT. Captured in the PR as "Not done."
- **`uv.lock` is untracked.** Committing it would give reproducible Python
    installs (matching `web/package-lock.json`); decision still pending.
- **`CORSMiddleware` uses `allow_origins=["*"]`.** Fine for local dev; tighten
  before any real deployment.
- **Multi-session / multi-user.** Out of scope for v1; the single-session
  `STTStarter` and per-connection track would need reworking.

## How to run

See `README.md`. Short version: `uv run uvicorn app.main:app --reload` + `cd web
&& npm run dev`; set `ELEVENLABS_API_KEY`, `ELEVENLABS_TTS_VOICE_ID`, and the
three `OPENAI_COMPATIBLE_*` vars in `.env`.

## Source materials

- Design spec: `docs/superpowers/specs/2025-07-26-voice-interface-first-cut-design.md`
  (gitignored working artifact).
- Per-phase implementation plans: `docs/superpowers/plans/2025-07-26-voice-interface-phase{1..4}-*.md`
  (gitignored).
- Original Hermes-centric outline was the starting point; the intelligence layer
  was generalized to a swappable protocol per the brainstorming session.
