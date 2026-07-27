from aiortc import RTCPeerConnection
from aiortc.mediastreams import AudioStreamTrack


async def test_offer_returns_valid_answer(client):
    """A real aiortc peer acting as the browser gets a valid answer back.

    A peer connection with no media tracks still completes the SDP handshake;
    its offer has no m= line, so we only assert the protocol header and type.
    """
    pc = RTCPeerConnection()
    try:
        offer = await pc.createOffer()
        response = await client.post(
            "/offer", json={"sdp": offer.sdp, "type": offer.type}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["type"] == "answer"
        assert "v=0" in body["sdp"]
    finally:
        await pc.close()


async def test_offer_accepts_audio_offer(client):
    """An offer that includes an audio track yields an answer with an audio m-line."""
    pc = RTCPeerConnection()
    track = AudioStreamTrack()
    pc.addTrack(track)
    try:
        offer = await pc.createOffer()
        response = await client.post(
            "/offer", json={"sdp": offer.sdp, "type": offer.type}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["type"] == "answer"
        assert "m=audio" in body["sdp"]
    finally:
        await pc.close()
