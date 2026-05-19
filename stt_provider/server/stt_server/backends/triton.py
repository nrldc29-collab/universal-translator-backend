"""
Triton backend client for streaming transcription.

This module provides a Python client for interacting with Triton Inference Server
for streaming speech-to-text transcription using Parakeet ASR and Sortformer
diarization models. The client handles audio preprocessing, model inference,
and transcript result parsing.

Requires: pip install tritonclient[grpc]
"""
import logging
from dataclasses import dataclass
from typing import Any, List
from uuid import UUID

import numpy as np
import tritonclient.grpc as grpcclient

logger = logging.getLogger(__name__)


@dataclass
class TritonSpeakerIdentity:
    """
    Speaker identity information from diarization.
    
    Attributes:
        speaker_profile_id: UUID of the matched speaker profile
        display_name: Human-readable display name for the speaker
        confidence: Confidence score of the speaker match (0.0 to 1.0)
    """
    speaker_profile_id: UUID
    display_name: str
    confidence: float


@dataclass
class TritonTranscriptWord:
    """
    Individual word in a transcript with timing and speaker information.
    
    Attributes:
        word: The transcribed word text
        start: Start time of the word in seconds
        end: End time of the word in seconds
        speaker: Speaker label (e.g., "SPEAKER_00", "SPEAKER_01")
        confidence: Word-level confidence score (0.0 to 1.0)
        speaker_identity: Full speaker identity information if available
    """
    word: str
    start: float
    end: float
    speaker: str | None = None
    confidence: float | None = None
    speaker_identity: TritonSpeakerIdentity | None = None


@dataclass
class TritonTranscriptResult:
    """
    Complete transcript result from Triton inference.
    
    Attributes:
        text: Full transcript text
        is_final: Whether this is a final (non-interim) result
        words: List of word-level details with timing and speaker info
    """
    text: str
    is_final: bool
    words: List[TritonTranscriptWord]


class TritonStreamingClient:
    """
    Client for streaming transcription via Triton Inference Server.
    
    This client provides a Python wrapper around the Triton gRPC client for
    performing streaming speech-to-text transcription with optional speaker
    diarization. It handles audio format conversion, input preparation, and
    response parsing.
    
    Attributes:
        grpc_url: URL of the Triton gRPC server
        asr_model: Name of the ASR model in Triton
        diarization_model: Name of the diarization model in Triton
        timeout_ms: Request timeout in milliseconds (default: 5000)
        client: Underlying Triton gRPC inference client
    """
    
    def __init__(
        self,
        *,
        grpc_url: str,
        asr_model: str,
        diarization_model: str,
        timeout_ms: int = 5000,
    ) -> None:
        """
        Initialize the Triton streaming client.
        
        Args:
            grpc_url: URL of the Triton gRPC server (e.g., "localhost:8001")
            asr_model: Name of the ASR model deployed in Triton
            diarization_model: Name of the diarization model deployed in Triton
            timeout_ms: Request timeout in milliseconds (default: 5000)
        """
        self.grpc_url = grpc_url
        self.asr_model = asr_model
        self.diarization_model = diarization_model
        self.timeout_ms = timeout_ms
        self.client = grpcclient.InferenceServerClient(url=grpc_url)
        
        logger.info(
            f"Initialized Triton client for {grpc_url}",
            extra={
                "grpc_url": grpc_url,
                "asr_model": asr_model,
                "diarization_model": diarization_model,
                "timeout_ms": timeout_ms,
            },
        )

    def is_ready(self) -> bool:
        """
        Check if the Triton server and required models are ready.
        
        Returns:
            True if server and both ASR and diarization models are ready, False otherwise
        """
        try:
            server_ready = self.client.is_server_ready()
            asr_ready = self.client.is_model_ready(self.asr_model)
            diarization_ready = self.client.is_model_ready(self.diarization_model)
            
            ready = server_ready and asr_ready and diarization_ready
            
            if not ready:
                logger.warning(
                    f"Triton not ready: server={server_ready}, "
                    f"asr={asr_ready}, diarization={diarization_ready}"
                )
            
            return ready
        except Exception as e:
            logger.error(f"Error checking Triton readiness: {e}")
            return False

    def transcribe_chunk(
        self,
        audio: np.ndarray,
        *,
        sample_rate: int = 16000,
        language: str = "en",
        model_override: str | None = None,
    ) -> TritonTranscriptResult:
        """
        Transcribe an audio chunk using Triton inference.
        
        Converts audio to FP32 format, prepares Triton inputs, and performs
        inference to get transcript text and final status.
        
        Args:
            audio: Audio data as numpy array (any dtype, will be converted to float32)
            sample_rate: Sample rate of the audio in Hz (default: 16000)
            language: Language code for transcription (default: "en")
            model_override: Optional override model name instead of default ASR model
            
        Returns:
            TritonTranscriptResult containing transcribed text, final status, and word list
            
        Raises:
            Exception: If Triton inference fails
        """
        logger.debug(
            f"Transcribing audio chunk: shape={audio.shape}, "
            f"dtype={audio.dtype}, sample_rate={sample_rate}"
        )
        
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        model_name = model_override or self.asr_model
        
        if model_override:
            logger.debug(f"Using model override: {model_override}")

        audio_input = grpcclient.InferInput(
            "AUDIO",
            audio.shape,
            "FP32",
        )
        audio_input.set_data_from_numpy(audio)

        sample_rate_input = grpcclient.InferInput(
            "SAMPLE_RATE",
            [1],
            "INT32",
        )
        sample_rate_input.set_data_from_numpy(
            np.array([sample_rate], dtype=np.int32)
        )

        language_input = grpcclient.InferInput(
            "LANGUAGE",
            [1],
            "BYTES",
        )
        language_input.set_data_from_numpy(
            np.array([language.encode("utf-8")], dtype=object)
        )

        try:
            response = self.client.infer(
                model_name=model_name,
                inputs=[
                    audio_input,
                    sample_rate_input,
                    language_input,
                ],
                client_timeout=self.timeout_ms / 1000,
            )
        except Exception as e:
            logger.error(f"Triton inference failed: {e}")
            raise

        text_output = response.as_numpy("TEXT")
        is_final_output = response.as_numpy("IS_FINAL")

        text = (
            text_output[0].decode("utf-8")
            if text_output is not None and len(text_output)
            else ""
        )

        is_final = (
            bool(is_final_output[0])
            if is_final_output is not None and len(is_final_output)
            else False
        )
        
        logger.debug(
            f"Transcription result: text_length={len(text)}, is_final={is_final}"
        )

        return TritonTranscriptResult(
            text=text,
            is_final=is_final,
            words=[],
        )
