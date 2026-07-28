from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import av
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError
from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from app.audio import TTSOutputTrack
from app.config import (
    ElevenLabsSTTSettings,
    get_elevenlabs_api_key,
    get_elevenlabs_tts_settings,
    get_openai_compatible_settings,
)
from app.intelligence import OpenAICompatibleIntelligenceProvider
from app.stt import ElevenLabsSTTProvider, TranscriptEvent
from app.tts import ElevenLabsTTSProvider, TTSProvider, chunk_text

logger = logging.getLogger(__name__)

router = APIRouter()
peer_connections: set[RTCPeerConnection] = set()


class OfferRequest(BaseModel):
    sdp: str
    type: str

    @field_validator("type")
    @classmethod
    def must_be_offer(cls, v: str) -> str:
        if v != "offer":
            raise ValueError("type must be 'offer'")
        return v


class OfferResponse(BaseModel):
    sdp: str
    type: str


class STTStarter:
    """Joins the audio-track and transcript-channel events so STT starts exactly
    once, after both arrive — in either order.

    Extracted from the `/offer` handler so the join logic is unit-testable
    without a live WebRTC connection (the events otherwise only fire after
    ICE/DTLS/SCTP establish between two real peers, which is out of CI scope).
    """

    def __init__(self, on_start: Any = None) -> None:
        self._track: MediaStreamTrack | None = None
        self._channel: Any = None
        self._started: bool = False
        self._on_start = on_start
        self.start_calls: list[tuple[MediaStreamTrack, Any]] = []

    def set_track(self, track: MediaStreamTrack) -> None:
        if self._track is not None:
            return
        self._track = track
        self._maybe_start()

    def set_channel(self, channel: Any) -> None:
        if self._channel is not None:
            return
        self._channel = channel
        self._maybe_start()

    def _maybe_start(self) -> None:
        if self._started:
            return
        if self._track is not None and self._channel is not None:
            self._started = True
            self.start_calls.append((self._track, self._channel))
            if self._on_start is not None:
                self._on_start(self._track, self._channel)


@router.post("/offer", response_model=OfferResponse)
async def offer(req: OfferRequest) -> OfferResponse:
    pc = RTCPeerConnection()
    peer_connections.add(pc)

    # The browser creates the 'transcript' data channel; the server receives it
    # via the datachannel event. (WebRTC forbids the answerer from adding new
    # m-lines, so the server cannot create the channel itself.)
    #
    # The audio track event and the datachannel event fire independently; the
    # data channel (SCTP) usually completes after the audio track is signaled.
    # STTStarter joins them: it starts the STT task exactly once, only after
    # both the audio track and the 'transcript' channel have arrived, in either
    # order.
    tts_output_track = TTSOutputTrack()
    starter = STTStarter(
        on_start=lambda track, channel: asyncio.ensure_future(
            _run_stt(track, channel, tts_output_track)
        )
    )

    @pc.on("datachannel")
    def on_datachannel(channel: Any) -> None:
        logger.info(
            "datachannel event: label=%s readyState=%s",
            channel.label,
            channel.readyState,
        )
        if channel.label == "transcript":
            starter.set_channel(channel)

    @pc.on("track")
    def on_track(track: MediaStreamTrack) -> None:
        logger.info("track event: kind=%s id=%s", track.kind, track.id)
        if track.kind == "audio":
            # Attach the outgoing TTS track to the peer connection now that an
            # audio transceiver exists (adding it before setRemoteDescription
            # fails when the offer has no matching audio m-line).
            pc.addTrack(tts_output_track)
            starter.set_track(track)

    @pc.on("connectionstatechange")
    def on_state_change() -> None:
        logger.info("connectionstatechange: %s", pc.connectionState)
        if pc.connectionState in ("failed", "closed"):
            peer_connections.discard(pc)
            asyncio.ensure_future(pc.close())

    description = RTCSessionDescription(sdp=req.sdp, type=req.type)
    await pc.setRemoteDescription(description)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return OfferResponse(sdp=pc.localDescription.sdp, type=pc.localDescription.type)


async def _run_stt(
    track: MediaStreamTrack, channel: Any, tts_output_track: TTSOutputTrack
) -> None:
    """Feed incoming audio frames to the STT provider and forward transcript
    events to the browser over the data channel.

    Errors are surfaced to the browser as an `error` event (so the UI shows
    what went wrong instead of silently hanging) AND logged server-side.
    """
    logger.info("_run_stt: starting")
    try:
        settings = ElevenLabsSTTSettings(api_key=get_elevenlabs_api_key())
        provider = ElevenLabsSTTProvider(settings=settings)
        logger.info("_run_stt: provider constructed, opening stream")

        # Resample incoming frames to 16 kHz s16 mono — the format ElevenLabs
        # Scribe v2 Realtime expects. Browser WebRTC Opus decodes at 48 kHz, so
        # without resampling we'd send mis-labeled audio and get no transcripts.
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        frame_count = 0

        async def audio_frames() -> AsyncIterator[bytes]:
            nonlocal frame_count
            while True:
                try:
                    frame = await track.recv()
                except MediaStreamError:
                    logger.info("_run_stt: track ended after %d frames", frame_count)
                    return
                if not isinstance(frame, av.AudioFrame):
                    continue
                for out_frame in resampler.resample(frame):
                    pcm = bytes(out_frame.planes[0])
                    if pcm:
                        frame_count += 1
                        if frame_count == 1:
                            logger.info(
                                "_run_stt: first audio frame (in=%dHz, out=16000Hz)",
                                frame.sample_rate,
                            )
                        yield pcm

        event_count = 0
        intelligence_settings = get_openai_compatible_settings()
        intelligence = OpenAICompatibleIntelligenceProvider(intelligence_settings)
        tts_settings = get_elevenlabs_tts_settings()
        tts = ElevenLabsTTSProvider(tts_settings)
        async for event in provider.stream(audio_frames()):
            event_count += 1
            logger.info(
                "_run_stt: event #%d kind=%s text=%r",
                event_count,
                event.kind,
                event.text,
            )
            if event.kind == "committed":
                # Send the committed user turn to the browser, then stream the
                # assistant's response: tokens to the data channel AND audio to
                # the outgoing WebRTC track via TTS. Inline await: sequential,
                # correct for v1; Phase 5 adds barge-in/cancellation.
                _send_event(channel, event)
                await _respond_with_tts(
                    intelligence, tts, tts_output_track, event.text, channel
                )
            else:
                # partial, error, etc. pass straight through.
                _send_event(channel, event)
        logger.info(
            "_run_stt: stream ended after %d events, %d frames",
            event_count,
            frame_count,
        )
    except Exception as exc:
        logger.exception("STT stream failed")
        _send_error(channel, str(exc))
    finally:
        _send_closed(channel)


def _send_json(channel: Any, payload: dict[str, str]) -> None:
    if _channel_open(channel):
        channel.send(json.dumps(payload))


def _send_event(channel: Any, event: TranscriptEvent) -> None:
    _send_json(channel, {"kind": event.kind, "text": event.text})


def _send_error(channel: Any, message: str) -> None:
    _send_json(channel, {"kind": "error", "text": message})


def _send_closed(channel: Any) -> None:
    _send_json(channel, {"kind": "closed", "text": ""})


def _channel_open(channel: Any) -> bool:
    ready = getattr(channel, "readyState", None)
    return ready == "open"


async def _respond_to_committed(
    intelligence: OpenAICompatibleIntelligenceProvider, text: str, channel: Any
) -> None:
    """On a committed user transcript, stream the assistant's response to the
    browser as assistant_token / assistant_done events. Errors are surfaced.

    Retained as a no-TTS path for callers that only want text; the live loop
    uses _respond_with_tts.
    """
    try:
        await intelligence.ingest(text)
        async for token in intelligence.stream_response():
            _send_json(channel, {"kind": "assistant_token", "text": token})
    except Exception as exc:
        logger.exception("intelligence stream failed")
        _send_error(channel, str(exc))
    finally:
        _send_json(channel, {"kind": "assistant_done", "text": ""})


async def _respond_with_tts(
    intelligence: OpenAICompatibleIntelligenceProvider,
    tts: TTSProvider,
    output_track: TTSOutputTrack,
    text: str,
    channel: Any,
) -> None:
    """On a committed transcript: stream assistant tokens to the browser AND
    feed them (boundary-chunked) into TTS, pushing audio onto the output track.
    Each token is duplicated to two queues (one per consumer) so both receive
    the full stream. Errors are surfaced; assistant_done always fires.
    """
    try:
        await intelligence.ingest(text)
        channel_queue: asyncio.Queue[str | None] = asyncio.Queue()
        tts_queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def _to_channel() -> None:
            while True:
                token = await channel_queue.get()
                if token is None:
                    return
                _send_json(channel, {"kind": "assistant_token", "text": token})

        async def _to_tts() -> None:
            async def _token_gen() -> AsyncIterator[str]:
                while True:
                    token = await tts_queue.get()
                    if token is None:
                        return
                    yield token

            async for audio in tts.stream(chunk_text(_token_gen())):
                await output_track.push(audio)
            await output_track.stop_stream()

        pump_channel = asyncio.ensure_future(_to_channel())
        pump_tts = asyncio.ensure_future(_to_tts())
        try:
            async for token in intelligence.stream_response():
                await channel_queue.put(token)
                await tts_queue.put(token)
            await channel_queue.put(None)
            await tts_queue.put(None)
            await asyncio.gather(pump_channel, pump_tts)
        finally:
            await channel_queue.put(None)
            await tts_queue.put(None)
    except Exception as exc:
        logger.exception("intelligence/tts stream failed")
        _send_error(channel, str(exc))
    finally:
        _send_json(channel, {"kind": "assistant_done", "text": ""})
