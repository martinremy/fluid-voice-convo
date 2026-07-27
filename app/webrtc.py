from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError
from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from app.config import ElevenLabsSTTSettings, get_elevenlabs_api_key
from app.stt import ElevenLabsSTTProvider, TranscriptEvent

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
    # So we collect whichever arrives first and start STT only once both are
    # present, avoiding a race where on("track") fires before the channel
    # exists.
    state: dict[str, Any] = {"audio_track": None, "channel": None, "started": False}

    def maybe_start_stt() -> None:
        if state["started"]:
            return
        track = state["audio_track"]
        channel = state["channel"]
        if track is not None and channel is not None:
            state["started"] = True
            asyncio.ensure_future(_run_stt(track, channel))

    @pc.on("datachannel")
    def on_datachannel(channel: Any) -> None:
        if channel.label == "transcript":
            state["channel"] = channel
            maybe_start_stt()

    @pc.on("track")
    def on_track(track: MediaStreamTrack) -> None:
        if track.kind == "audio":
            state["audio_track"] = track
            maybe_start_stt()

    @pc.on("connectionstatechange")
    def on_state_change() -> None:
        if pc.connectionState in ("failed", "closed"):
            peer_connections.discard(pc)
            asyncio.ensure_future(pc.close())

    description = RTCSessionDescription(sdp=req.sdp, type=req.type)
    await pc.setRemoteDescription(description)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return OfferResponse(sdp=pc.localDescription.sdp, type=pc.localDescription.type)


async def _run_stt(track: MediaStreamTrack, channel: Any) -> None:
    """Feed incoming audio frames to the STT provider and forward transcript
    events to the browser over the data channel."""
    settings = ElevenLabsSTTSettings(api_key=get_elevenlabs_api_key())
    provider = ElevenLabsSTTProvider(settings=settings)

    async def audio_frames() -> AsyncIterator[bytes]:
        while True:
            try:
                frame = await track.recv()
            except MediaStreamError:
                return
            pcm = _frame_to_pcm(frame)
            if pcm:
                yield pcm

    try:
        async for event in provider.stream(audio_frames()):
            _send_event(channel, event)
    except Exception:
        logger.exception("STT stream failed")
    finally:
        _send_closed(channel)


def _send_event(channel: Any, event: TranscriptEvent) -> None:
    if _channel_open(channel):
        channel.send(json.dumps({"kind": event.kind, "text": event.text}))


def _send_closed(channel: Any) -> None:
    if _channel_open(channel):
        channel.send(json.dumps({"kind": "closed", "text": ""}))


def _channel_open(channel: Any) -> bool:
    ready = getattr(channel, "readyState", None)
    return ready == "open"


def _frame_to_pcm(frame: Any) -> bytes:
    """Convert an aiortc AudioFrame to 16 kHz mono s16 PCM bytes."""
    try:
        return bytes(frame.planes[0])
    except Exception:
        return b""
