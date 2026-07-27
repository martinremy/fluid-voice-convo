from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription

if TYPE_CHECKING:
    from av.frame import Frame
    from av.packet import Packet
from fastapi import APIRouter
from pydantic import BaseModel, field_validator

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


class LoopbackAudioTrack(MediaStreamTrack):
    """Relays frames from an incoming audio track back to the peer."""

    def __init__(self, incoming: MediaStreamTrack) -> None:
        super().__init__()
        self.incoming = incoming

    async def recv(self) -> Frame | Packet:
        return await self.incoming.recv()


@router.post("/offer", response_model=OfferResponse)
async def offer(req: OfferRequest) -> OfferResponse:
    pc = RTCPeerConnection()
    peer_connections.add(pc)

    @pc.on("track")
    def on_track(track: MediaStreamTrack) -> None:
        if track.kind == "audio":
            pc.addTrack(LoopbackAudioTrack(track))

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
