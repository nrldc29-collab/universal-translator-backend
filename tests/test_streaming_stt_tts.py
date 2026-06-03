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
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")

import backend.streaming as streaming
from backend.conversation import ConversationBrain
from backend.memory import ConversationMemory
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
