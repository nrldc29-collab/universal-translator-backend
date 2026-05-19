"""
Tests for Triton model selection.

This module tests the model selection logic for the Triton streaming client.
Tests verify that the default ASR model is used when no override is provided,
and that tenant-selected domain models are used when model_override is present.

Run tests:
    pytest tests/test_triton_model_selection.py

Purpose:
This ensures that Triton uses the default ASR model when no override is provided
and routes to the tenant-selected domain model when model_override is present.
Domain models are part of the guide's Phase 4 differentiation path for improving
in-domain accuracy.
"""
import logging

import numpy as np

from stt_server.backends.triton import TritonStreamingClient

logger = logging.getLogger(__name__)


class FakeResponse:
    """
    Fake Triton inference response for testing.
    
    Simulates the as_numpy method of Triton inference responses.
    """
    def as_numpy(self, name):
        """
        Simulate Triton response as_numpy method.
        
        Args:
            name: The output tensor name to retrieve.
            
        Returns:
            A numpy array with mock data for TEXT and IS_FINAL outputs,
            None for other outputs.
        """
        if name == "TEXT":
            return np.array([b"hello world"], dtype=object)

        if name == "IS_FINAL":
            return np.array([True])

        return None


class FakeTritonGrpcClient:
    """
    Fake Triton gRPC client for testing model selection.
    
    Tracks the model name used in inference requests.
    """
    def __init__(self):
        """
        Initialize the fake gRPC client.
        
        Sets up tracking for the last model name used.
        """
        self.last_model_name = None

    def infer(self, *, model_name, inputs, client_timeout):
        """
        Simulate Triton inference call.
        
        Args:
            model_name: The model name to use for inference.
            inputs: The input tensors for inference.
            client_timeout: The client timeout for the request.
            
        Returns:
            A FakeResponse with mock inference results.
        """
        self.last_model_name = model_name
        return FakeResponse()


def test_transcribe_chunk_uses_default_asr_model_without_override():
    """
    Test that transcribe_chunk uses default ASR model without override.
    
    Verifies that when no model_override is provided, the client uses the
    default ASR model (parakeet-general) for transcription.
    """
    logger.info("Testing transcribe chunk uses default ASR model without override")
    
    client = TritonStreamingClient(
        grpc_url="triton.test:8001",
        asr_model="parakeet-general",
        diarization_model="diar_streaming_sortformer_4spk-v2",
    )

    fake_grpc = FakeTritonGrpcClient()
    client.client = fake_grpc

    result = client.transcribe_chunk(
        np.zeros(16000, dtype=np.float32),
        sample_rate=16000,
        language="en",
    )

    assert fake_grpc.last_model_name == "parakeet-general"
    assert result.text == "hello world"
    assert result.is_final is True
    
    logger.info("Default ASR model test passed")


def test_transcribe_chunk_uses_tenant_model_override():
    """
    Test that transcribe_chunk uses tenant model override.
    
    Verifies that when model_override is provided, the client uses the
    specified tenant-selected domain model (parakeet-medical) for transcription.
    """
    logger.info("Testing transcribe chunk uses tenant model override")
    
    client = TritonStreamingClient(
        grpc_url="triton.test:8001",
        asr_model="parakeet-general",
        diarization_model="diar_streaming_sortformer_4spk-v2",
    )

    fake_grpc = FakeTritonGrpcClient()
    client.client = fake_grpc

    result = client.transcribe_chunk(
        np.zeros(16000, dtype=np.float32),
        sample_rate=16000,
        language="en",
        model_override="parakeet-medical",
    )

    assert fake_grpc.last_model_name == "parakeet-medical"
    assert result.text == "hello world"
    assert result.is_final is True
    
    logger.info("Tenant model override test passed")
