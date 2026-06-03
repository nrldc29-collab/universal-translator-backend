"""Integration coverage for voice output on the streaming-STT path.

`websocket_streaming_stt_translation` used to translate finalized transcripts
but never synthesize speech (`audio_output_path=None`), so the streaming STT
mode produced text-only output. These tests drive the handler with fakes and
assert that a finalized transcript now yields TTS audio chunks, while a
low-confidence final correctly skips voice output.
"""
import asyncio
import json
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")

import backend.streaming as streaming
from backend.conversation import ConversationBrain
from backend.memory import ConversationMemory
from backend.sessions import session_registry
from backend.speakers import SpeakerMemory
from starlette.websockets import WebSocketDisconnect


class FakeProviderWS:
    """Stands in for the STT provider WebSocket connection."""

    def __init__(self, events):
        self._events = list(events)
        self.sent = []
        self.closed = False

    async def send(self, data):
        self.sent.append(data)

    async def close(self):
        self.closed = True

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for event in self._events:
            await asyncio.sleep(0)
            yield event


class FakeClientWS:
    """Stands in for the browser/mobile client WebSocket.

    Drives the handler with a config message followed by one audio frame, then
    blocks until the handler emits the terminal ``final`` message (which is sent
    after any TTS), at which point it raises ``WebSocketDisconnect`` to stop.
    """

    def __init__(self, config_payload):
        self.sent = []
        self._finished = asyncio.Event()
        self._steps = [
            {"text": json.dumps({"type": "config", **config_payload})},
            {"bytes": b"\x00\x01" * 64},
        ]
        self._step = 0

    async def accept(self):
        return None

    async def send_json(self, payload):
        self.sent.append(payload)
        if payload.get("type") == "final":
            self._finished.set()

    async def receive(self):
        if self._step < len(self._steps):
            message = self._steps[self._step]
            self._step += 1
            return message
        await asyncio.wait_for(self._finished.wait(), timeout=5.0)
        raise WebSocketDisconnect(code=1000)

    def messages_of_type(self, msg_type):
        return [m for m in self.sent if m.get("type") == msg_type]


def _make_pipeline(tmp_path, synth_bytes=400):
    """Build a pipeline mock whose TTS writes a small WAV file."""

    def synthesize(text, path, language=None):
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"R" * synth_bytes)
        return str(out)

    pipeline = MagicMock()
    pipeline.stt.is_streaming = True
    pipeline.stt.get_streaming_client.return_value._stream_url.return_value = (
        "ws://127.0.0.1:8002/stt/stream?language=en"
    )
    pipeline.context_layer.improve.side_effect = lambda text, *a, **k: text
    pipeline.translator.translate.side_effect = lambda text, *a, **k: "hola mundo amigo"
    pipeline.tts.synthesize.side_effect = synthesize
    return pipeline


def _run_handler(pipeline, client, provider_ws, stt_conf, tr_conf, identity="tester"):
    async def _go():
        async def fake_connect(*args, **kwargs):
            return provider_ws

        async def fake_cip(*args, **kwargs):
            return None

        with patch.object(streaming, "call_cip_brain", side_effect=fake_cip), \
             patch("websockets.connect", side_effect=fake_connect), \
             patch.object(streaming, "estimate_stt_confidence", return_value=stt_conf), \
             patch.object(streaming, "estimate_translation_confidence", return_value=tr_conf):
            await streaming.websocket_streaming_stt_translation(
                client,
                pipeline,
                ConversationBrain(),
                ConversationMemory(),
                SpeakerMemory(),
                identity,
            )

    asyncio.run(asyncio.wait_for(_go(), timeout=10.0))


def test_final_transcript_produces_tts_audio(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pipeline = _make_pipeline(tmp_path)
    provider_ws = FakeProviderWS([
        json.dumps({"type": "transcript", "is_final": True, "text": "hello world friend"}),
    ])
    client = FakeClientWS({
        "source_language": "en",
        "target_language": "es",
        "speaker_mode": "manual",
        "session_id": "s1",
    })

    _run_handler(pipeline, client, provider_ws, stt_conf=0.95, tr_conf=0.95)

    tts_starts = client.messages_of_type("tts_start")
    tts_chunks = client.messages_of_type("tts_audio_chunk")
    tts_ends = client.messages_of_type("tts_end")
    assert tts_starts, "expected a tts_start message"
    assert tts_chunks, "expected at least one tts_audio_chunk"
    assert tts_ends, "expected a tts_end message"
    assert all(c.get("audio_base64") for c in tts_chunks)
    assert pipeline.tts.synthesize.called

    finals = client.messages_of_type("final")
    assert finals, "expected a final message"
    assert finals[-1].get("audio_output_path")


def test_low_confidence_final_skips_tts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pipeline = _make_pipeline(tmp_path)
    provider_ws = FakeProviderWS([
        json.dumps({"type": "transcript", "is_final": True, "text": "hello world friend"}),
    ])
    client = FakeClientWS({
        "source_language": "en",
        "target_language": "es",
        "speaker_mode": "manual",
        "session_id": "s2",
    })

    _run_handler(pipeline, client, provider_ws, stt_conf=0.05, tr_conf=0.05)

    assert client.messages_of_type("clarify"), "expected a clarify message"
    assert not client.messages_of_type("tts_audio_chunk"), "low confidence must skip TTS"
    finals = client.messages_of_type("final")
    assert finals, "expected a final message"
    assert finals[-1].get("audio_output_path") is None


def test_partial_transcript_is_translated_live(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pipeline = _make_pipeline(tmp_path)
    # A multi-word partial (>= min words) followed by the final transcript.
    provider_ws = FakeProviderWS([
        json.dumps({"type": "transcript", "is_final": False, "text": "hello world friend nice to meet you"}),
        json.dumps({"type": "transcript", "is_final": True, "text": "hello world friend nice to meet you today"}),
    ])
    client = FakeClientWS({
        "source_language": "en",
        "target_language": "es",
        "speaker_mode": "manual",
        "session_id": "s3",
    })

    _run_handler(pipeline, client, provider_ws, stt_conf=0.95, tr_conf=0.95)

    # The partial source text is still forwarded.
    assert client.messages_of_type("partial_transcription"), "expected partial_transcription"
    # The partial is now also translated live (text-only, no partial TTS).
    partial_translations = client.messages_of_type("partial_translation")
    assert partial_translations, "expected a live partial_translation"
    assert all(p.get("text") for p in partial_translations)
    # No TTS should fire for partials specifically; TTS only on the final turn.
    assert client.messages_of_type("final"), "expected a final message"


def test_auto_detects_and_switches_source_language(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AUTO_LANGUAGE_DETECTION", "1")
    pipeline = _make_pipeline(tmp_path)
    # Configured source is English, but the speaker clearly speaks Spanish
    # (multiple Spanish hint words => detect_language_mix flags a mismatch).
    provider_ws = FakeProviderWS([
        json.dumps({
            "type": "transcript",
            "is_final": True,
            "text": "hola necesito ayuda donde gracias",
        }),
    ])
    client = FakeClientWS({
        "source_language": "en",
        "target_language": "es",
        "speaker_mode": "manual",
        "session_id": "s4",
    })

    _run_handler(pipeline, client, provider_ws, stt_conf=0.95, tr_conf=0.95)

    switches = client.messages_of_type("language_switched")
    assert switches, "expected a language_switched event"
    switch = switches[-1]
    assert switch["previous_source_language"] == "en"
    assert switch["source_language"] == "es"
    # source==target collision resolved by flipping target back to the old source.
    assert switch["target_language"] == "en"

    # The web client should be able to auto-update its source via the final hints.
    finals = client.messages_of_type("final")
    assert finals, "expected a final message"
    hints = finals[-1].get("cip_client_hints") or {}
    assert hints.get("language_auto_repaired") is True
    assert hints.get("repaired_source_language") == "es"


def test_auto_detection_disabled_keeps_source_language(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AUTO_LANGUAGE_DETECTION", "0")
    pipeline = _make_pipeline(tmp_path)
    provider_ws = FakeProviderWS([
        json.dumps({
            "type": "transcript",
            "is_final": True,
            "text": "hola necesito ayuda donde gracias",
        }),
    ])
    client = FakeClientWS({
        "source_language": "en",
        "target_language": "es",
        "speaker_mode": "manual",
        "session_id": "s5",
    })

    _run_handler(pipeline, client, provider_ws, stt_conf=0.95, tr_conf=0.95)

    assert not client.messages_of_type("language_switched"), "switch must not fire when disabled"


def _write_pcm16_wav(path, pcm_bytes, sample_rate=16000):
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return str(path)


def test_non_pcm16_chunks_are_transcoded_before_forwarding(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pipeline = _make_pipeline(tmp_path)
    # The "m4a" frame the mobile client sends; its raw bytes must NOT reach the
    # provider directly — they should be transcoded to PCM16 first.
    m4a_chunk = b"\x00\x01\x02\x03" * 32
    expected_pcm = b"\x10\x00\x20\x00\x30\x00\x40\x00" * 8

    provider_ws = FakeProviderWS([
        json.dumps({"type": "transcript", "is_final": True, "text": "hello world friend"}),
    ])
    client = FakeClientWS({
        "source_language": "en",
        "target_language": "es",
        "speaker_mode": "manual",
        "session_id": "s6",
        "audio_format": "m4a",
    })
    # FakeClientWS sends a fixed audio frame; here that frame stands in for m4a.
    client._steps[1] = {"bytes": m4a_chunk}

    wav_path = _write_pcm16_wav(tmp_path / "decoded.wav", expected_pcm)

    def fake_transcode(audio_bytes, suffix=".webm"):
        assert audio_bytes == m4a_chunk
        assert suffix == ".m4a"
        return wav_path

    async def _go():
        async def fake_connect(*args, **kwargs):
            return provider_ws

        async def fake_cip(*args, **kwargs):
            return None

        with patch.object(streaming, "call_cip_brain", side_effect=fake_cip), \
             patch.object(streaming, "transcode_bytes_to_wav", side_effect=fake_transcode), \
             patch("websockets.connect", side_effect=fake_connect), \
             patch.object(streaming, "estimate_stt_confidence", return_value=0.95), \
             patch.object(streaming, "estimate_translation_confidence", return_value=0.95):
            await streaming.websocket_streaming_stt_translation(
                client, pipeline, ConversationBrain(),
                ConversationMemory(), SpeakerMemory(), "tester",
            )

    asyncio.run(asyncio.wait_for(_go(), timeout=10.0))

    audio_frames = [m for m in provider_ws.sent if isinstance(m, (bytes, bytearray))]
    assert audio_frames, "expected audio forwarded to the provider"
    assert m4a_chunk not in audio_frames, "raw m4a must not be forwarded as PCM16"
    assert any(bytes(frame) == expected_pcm for frame in audio_frames), \
        "expected decoded PCM16 frames forwarded to the provider"

    # The client is told it is being transcoded.
    listening = client.messages_of_type("listening")
    assert listening and listening[-1].get("audio_format") == "m4a"


def test_chunk_meta_sets_audio_format_for_mobile(tmp_path, monkeypatch):
    """Mobile declares audio/m4a via chunk_meta (not in config); the handler
    should pick it up and transcode without any client-side config change."""
    monkeypatch.chdir(tmp_path)
    pipeline = _make_pipeline(tmp_path)
    m4a_chunk = b"\x05\x06\x07\x08" * 32
    expected_pcm = b"\x11\x00\x22\x00\x33\x00\x44\x00" * 8

    provider_ws = FakeProviderWS([
        json.dumps({"type": "transcript", "is_final": True, "text": "hello world friend"}),
    ])
    # Config has NO audio_format (mirrors mobile's `start`). Instead a chunk_meta
    # message announces audio/m4a right before the audio frame.
    client = FakeClientWS({
        "source_language": "en",
        "target_language": "es",
        "speaker_mode": "manual",
        "session_id": "s7",
    })
    client._steps = [
        client._steps[0],
        {"text": json.dumps({"type": "chunk_meta", "mime_type": "audio/m4a"})},
        {"bytes": m4a_chunk},
    ]

    wav_path = _write_pcm16_wav(tmp_path / "decoded2.wav", expected_pcm)

    def fake_transcode(audio_bytes, suffix=".webm"):
        assert suffix == ".m4a"
        return wav_path

    async def _go():
        async def fake_connect(*args, **kwargs):
            return provider_ws

        async def fake_cip(*args, **kwargs):
            return None

        with patch.object(streaming, "call_cip_brain", side_effect=fake_cip), \
             patch.object(streaming, "transcode_bytes_to_wav", side_effect=fake_transcode), \
             patch("websockets.connect", side_effect=fake_connect), \
             patch.object(streaming, "estimate_stt_confidence", return_value=0.95), \
             patch.object(streaming, "estimate_translation_confidence", return_value=0.95):
            await streaming.websocket_streaming_stt_translation(
                client, pipeline, ConversationBrain(),
                ConversationMemory(), SpeakerMemory(), "tester",
            )

    asyncio.run(asyncio.wait_for(_go(), timeout=10.0))

    audio_frames = [bytes(m) for m in provider_ws.sent if isinstance(m, (bytes, bytearray))]
    assert m4a_chunk not in audio_frames, "raw m4a must not be forwarded as PCM16"
    assert expected_pcm in audio_frames, "expected decoded PCM16 forwarded after chunk_meta"


def test_final_translation_is_routed_to_peer_devices(tmp_path, monkeypatch):
    """Step 3 speaker routing: a speaker's finalized translation is delivered to
    the other devices in the same session (the 'two people talking' case)."""
    monkeypatch.chdir(tmp_path)
    pipeline = _make_pipeline(tmp_path)
    provider_ws = FakeProviderWS([
        json.dumps({"type": "transcript", "is_final": True, "text": "hello world friend"}),
    ])
    client = FakeClientWS({
        "source_language": "en",
        "target_language": "es",
        "speaker_mode": "manual",
        "session_id": "routing-session",
        "device_id": "device-a",
    })

    # A second device subscribed to the same session/identity should receive the
    # speaker's translation; the speaker's own device must be excluded.
    peer_messages = []

    async def peer_collector(payload):
        peer_messages.append(payload)

    peer_token = session_registry.subscribe("routing-session", "tester", "device-b", peer_collector)
    try:
        _run_handler(pipeline, client, provider_ws, stt_conf=0.95, tr_conf=0.95)
    finally:
        session_registry.unsubscribe(peer_token)

    routed = [m for m in peer_messages if m.get("type") == "peer_message"]
    assert routed, "expected the peer device to receive a peer_message"
    msg = routed[-1]
    assert msg["translated_text"].lower() == "hola mundo amigo"
    assert msg["device_id"] == "device-a"
    assert msg["target_language"] == "es"
    # The peer should also receive the synthesized voice so it can play it.
    assert msg.get("audio_chunks"), "expected peer to receive TTS audio chunks"
    assert all(chunk.get("audio_base64") for chunk in msg["audio_chunks"])
    # The speaker's own socket must NOT receive its own peer_message.
    assert not client.messages_of_type("peer_message")
