async def test_offer_rejects_missing_fields(client):
    response = await client.post("/offer", json={})
    assert response.status_code == 422


async def test_offer_rejects_non_offer_type(client):
    response = await client.post(
        "/offer", json={"sdp": "v=0\r\n", "type": "answer"}
    )
    assert response.status_code == 422
