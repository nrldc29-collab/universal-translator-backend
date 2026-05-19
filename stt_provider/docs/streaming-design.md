# Streaming design: from chunked re-transcription to true incremental decoding

## Where we are today

`StreamingTranscriptionSession` in `stt_server/streaming.py` is driven by `webrtcvad`:

1. Every incoming PCM-16LE frame is split into 10/20/30 ms VAD frames.
2. Frames classified as speech are appended to a growing `speech_buffer`. Silent frames
   are tolerated and counted until `max_silence_frames`.
3. Every ~35 speech frames (`partial_every_frames`), the **entire** buffer is written to
   a temp WAV file and passed to `faster_whisper.WhisperModel.transcribe(...)` to produce
   a `transcript.partial` event.
4. After ~20 consecutive silent frames, the same thing happens once more to produce a
   `transcript.final`, and the buffer is reset.

This is simple and correct, but it has two structural problems:

- **Quadratic CPU.** A 30-second utterance produces ~15 partials, each of which decodes
  the full audio from the start. The decoder does roughly `O(N²)` total work where `N`
  is the utterance length in frames.
- **Latency grows with utterance length.** The longer someone talks, the slower partials
  arrive, because each partial re-decodes everything that came before.

A "true streaming" service should keep per-partial work approximately constant in the
length of audio already committed.

## Target behaviour

We want each partial to do work proportional to the size of the *uncommitted* tail of
audio, not the total. Concretely:

- A stable "committed prefix" of the utterance that we never re-decode.
- A small "rolling tail" of the most recent N seconds that we re-decode on each partial
  to refine the live hypothesis.
- Final events that commit any remaining tail and reset.

## Approach A: rolling window with confirmation (recommended near-term)

This works on top of stock `faster-whisper` without modifying CTranslate2, and gives most
of the latency win.

**State per session**

```
committed_text: str               # text we have already emitted and won't change
committed_audio_seconds: float    # how much audio that text covers (anchor)
tail_buffer: bytearray            # audio after committed_audio_seconds
last_partial_text: str
```

**On each batch of speech frames**

1. Append the new frames to `tail_buffer`.
2. If `len(tail_buffer)` exceeds the partial cadence (e.g. ≥ 800 ms of new speech):
   - Decode `tail_buffer` alone (not the whole utterance).
   - Let `hypothesis` be the decoded text.
   - Compare `hypothesis` against `last_partial_text`. Use the longest stable prefix
     that survived across two consecutive decodes — call that the *confirmation set*.
   - Emit `transcript.partial` with `committed_text + " " + hypothesis`.
   - When the confirmation prefix exceeds e.g. 2 seconds of audio (estimated from word
     timestamps that `faster-whisper` already returns), promote it: append it to
     `committed_text`, advance `committed_audio_seconds`, and trim `tail_buffer` to the
     audio that wasn't yet confirmed.

3. On VAD-detected end-of-utterance, decode the remaining `tail_buffer`, emit
   `transcript.final` with the full `committed_text + tail_text`, and reset state.

**Why this works**

- The tail buffer stays bounded (a few seconds), so per-partial decode time is roughly
  constant.
- Word-level timestamps from `faster-whisper` (it returns them when you pass
  `word_timestamps=True`) give us a reliable way to slice audio at word boundaries when
  we promote text from "tentative" to "committed".
- Confirming across two consecutive decodes avoids flicker — the partial text only
  changes within the unconfirmed tail.

**Where it falls down**

- The promotion heuristic is the whole game. Too eager and you commit wrong words; too
  conservative and the tail grows and latency creeps back up.
- Whisper is a sequence-to-sequence model with no causal guarantees: a word in the
  middle of the tail can change because of context that appears later. Confirmation
  across rolling decodes is the practical workaround, but it's not free.

## Approach B: switch to a streaming-native engine

If we want truly incremental decoding without the heuristics above, the encoder itself
needs to be designed for it. Options:

- **whisper-streaming / WhisperLive** — community wrappers around Whisper that implement
  variants of the approach above with chunk-based decoding, voice activity detection,
  and a "LocalAgreement" confirmation policy. Drop-in conceptually; would need to be
  vendored or invoked as a subprocess.

- **NVIDIA NeMo streaming Conformer / FastConformer-TDT** — purpose-built for streaming
  ASR. Lower latency than Whisper, but it's a heavier dependency stack (PyTorch + NeMo),
  GPU strongly recommended, and accuracy at our model sizes is comparable to medium
  Whisper rather than large.

- **Vosk / Kaldi** — true streaming, CPU-friendly, but materially worse WER than
  Whisper on most non-English audio.

- **Cloud APIs (Deepgram, AssemblyAI, Google STT v2 streaming)** — the easy answer if
  self-hosting isn't a hard requirement.

For "self-hosted, GPU optional, Whisper-quality", approach A is the right next step.
Approach B's NeMo path is the right move if we eventually need sub-300 ms latency.

## Sketch of an incremental implementation

A minimal incremental `StreamingTranscriptionSession.receive_audio` would look like this:

```python
PARTIAL_INTERVAL_BYTES = bytes_per_second * 0.8     # decode every ~800 ms of new tail
CONFIRM_AFTER_SECONDS = 2.0                          # promote prefix older than 2 s

async def receive_audio(self, pcm16_audio: bytes) -> AsyncIterator[TranscriptEvent]:
    frames = self.vad.split_frames(pcm16_audio)
    for frame in frames:
        is_speech = self.vad.is_speech(frame)
        if is_speech:
            self.tail_buffer.extend(frame)
            self.speech_frames += 1
            self.silence_frames = 0
        elif self.tail_buffer:
            self.tail_buffer.extend(frame)
            self.silence_frames += 1

        if len(self.tail_buffer) >= self.next_partial_at_bytes:
            words = await self._decode_tail_with_word_timestamps()
            confirmed_words, tentative_words = self._confirm(words)

            if confirmed_words:
                self._promote(confirmed_words)        # advances committed_text + trims tail

            partial_text = (self.committed_text + " " +
                            " ".join(w.word for w in tentative_words)).strip()
            if partial_text != self.last_partial_text:
                self.last_partial_text = partial_text
                yield TranscriptEvent("transcript.partial", partial_text)

            self.next_partial_at_bytes = len(self.tail_buffer) + PARTIAL_INTERVAL_BYTES

        if self._should_emit_final():
            words = await self._decode_tail_with_word_timestamps()
            self._promote(words)                       # commit everything left
            final_text = self.committed_text
            self._reset()
            if final_text:
                yield TranscriptEvent("transcript.final", final_text)
```

The two methods worth getting right:

- `_decode_tail_with_word_timestamps` — writes only `tail_buffer` to a temp WAV and calls
  `model.transcribe(..., word_timestamps=True, condition_on_previous_text=False,
   initial_prompt=self.committed_text[-200:])`. Passing the recent committed text as the
  initial prompt biases Whisper toward consistent terminology without forcing it to
  re-decode the prefix.
- `_confirm` — keeps `self.previous_tentative_words` from the prior decode, and treats a
  word as confirmed once it has appeared at the same approximate timestamp in two
  consecutive decodes. The exact rule is the tunable knob.

## Other latency wins worth tracking

- **Drop the temp-WAV round trip.** `faster-whisper` accepts a NumPy float32 array
  directly; today we write to a temp WAV file on every partial. Converting once in
  memory removes a chunk of per-partial overhead.
- **`vad_filter=False` and `beam_size=1`** are already set — good. Keep them for
  partials. The final pass could optionally be re-run with `beam_size=5` on just the
  tail for a small accuracy bump.
- **Per-session model handle.** `get_whisper_model()` is `lru_cache`d to a single global
  instance, which is correct for CPU. On GPU, consider a small pool to absorb bursts.
- **Concurrency.** `asyncio.to_thread` is fine for CPU `int8`, but on GPU the decode
  thread will serialize on the CUDA stream. A bounded `asyncio.Semaphore` around decodes
  would prevent unbounded queueing under load.

## Migration plan

1. Land the rolling-tail decoder behind a feature flag (`STT_STREAMING_MODE=incremental`)
   so the current chunked behaviour stays default while we tune the promotion rule.
2. Add a smoke test that pipes a known WAV through `StreamingTranscriptionSession` and
   asserts that the final text equals the offline `transcribe_pcm16_file` result.
3. Add a latency benchmark that records `time-to-first-partial` and
   `time-to-stable-partial` over a fixture corpus.
4. Flip the flag on once the benchmark beats today's median partial latency by ≥ 2× and
   the smoke test still passes.

## Open questions

- Do we want to expose the committed/tentative split to clients (e.g. mark which prefix
  of a partial is stable)? The current event schema can't carry that.
- Should the final event include per-word timestamps? Almost free once we decode with
  `word_timestamps=True` for partials anyway.
- For non-English audio, how aggressive can the promotion rule be without regressing WER?
  Probably needs language-specific tuning.
