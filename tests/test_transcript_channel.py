import pytest
from aiortc import RTCPeerConnection


@pytest.mark.asyncio
async def test_offer_negotiates_transcript_data_channel(client):
    """The server must create a 'transcript' data channel; its presence shows up
    as an application m-line in the answer SDP. (The channel label itself is
    negotiated post-connection via DCEP, not in the SDP.)"""
    pc = RTCPeerConnection()
    # The browser creates the data channel; the server receives it.
    pc.createDataChannel("transcript")
    try:
        offer = await pc.createOffer()
        response = await client.post(
            "/offer", json={"sdp": offer.sdp, "type": offer.type}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["type"] == "answer"
        assert "m=application" in body["sdp"]
    finally:
        await pc.close()
