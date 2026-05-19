# Sortformer Streaming Diarization Deployment Notes

## Phase 2B Step 3: Add Sortformer Streaming Diarization

Target model:

- `diar_streaming_sortformer_4spk-v2`

Deployment approach:

- Deploy Sortformer alongside Parakeet in the Triton model repository.
- Keep ASR and diarization behind the same internal Triton gRPC service.
- Attach speaker labels at the word level after each end-of-utterance event.
- Surface speakers in transcript events as `spk_0`, `spk_1`, `spk_2`, and `spk_3`.

Gateway event requirements:

Each final transcript event should support speaker labels:

```json
{
  "type": "transcript.final",
  "text": "hello, thanks for calling",
  "start": 0.12,
  "end": 1.84,
  "words": [
    {
      "word": "hello",
      "start": 0.12,
      "end": 0.44,
      "speaker": "spk_0"
    }
  ]
}
```

Model repository target layout:

```
/models
  /parakeet-tdt-streaming
    /1
    config.pbtxt
  /diar_streaming_sortformer_4spk-v2
    /1
    config.pbtxt
```

Acceptance checks:

- Triton loads both Parakeet and Sortformer successfully.
- Gateway receives ASR output from Parakeet.
- Gateway receives speaker segmentation from Sortformer.
- Final transcript events include word-level speaker tags.
- Speaker labels remain stable as spk_0 through spk_3 during a session.
