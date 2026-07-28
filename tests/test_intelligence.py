from app.intelligence import ChatCompleter, IntelligenceProvider


def test_intelligence_provider_protocol_exists():
    assert IntelligenceProvider is not None
    assert hasattr(IntelligenceProvider, "ingest")
    assert hasattr(IntelligenceProvider, "stream_response")


def test_chat_completer_protocol_exists():
    assert ChatCompleter is not None
    assert hasattr(ChatCompleter, "stream")
