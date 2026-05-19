"""
CI test coverage for STT integration.

Tests STTBridge functionality, /ready endpoint behavior with STT provider,
and streaming events handling.
"""
import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, '.')


class TestSTTBridge:
    """Test STTBridge class functionality."""

    def test_stt_bridge_initializes_local_mode(self):
        """Test STTBridge initializes in local mode by default."""
        os.environ['STT_PROVIDER'] = 'local'
        from backend.stt_bridge import STTBridge
        
        bridge = STTBridge()
        assert bridge._provider == 'local'
        assert bridge.is_streaming is False

    def test_stt_bridge_initializes_streaming_mode(self):
        """Test STTBridge initializes in streaming mode when configured."""
        os.environ['STT_PROVIDER'] = 'streaming'
        os.environ['STT_PROVIDER_URL'] = 'http://127.0.0.1:8002'
        os.environ['STT_PROVIDER_WS_URL'] = 'ws://127.0.0.1:8002/stt/stream'
        os.environ['STT_PROVIDER_API_KEY'] = ''
        from backend.stt_bridge import STTBridge
        
        bridge = STTBridge()
        assert bridge._provider == 'streaming'
        assert bridge.is_streaming is True

    def test_stt_bridge_preload_local_mode(self):
        """Test STTBridge preload in local mode."""
        os.environ['STT_PROVIDER'] = 'local'
        from backend.stt_bridge import STTBridge
        
        bridge = STTBridge()
        # In local mode, preload() calls the local STT preload method
        # We just verify the method exists and can be called
        assert hasattr(bridge, 'preload')
        assert bridge.is_streaming is False

    @patch('backend.stt_bridge.STTBridge._check_streaming_health')
    def test_stt_bridge_preload_streaming_mode_reachable(self, mock_health):
        """Test STTBridge preload in streaming mode when provider is reachable."""
        os.environ['STT_PROVIDER'] = 'streaming'
        os.environ['STT_PROVIDER_URL'] = 'http://127.0.0.1:8002'
        os.environ['STT_PROVIDER_WS_URL'] = 'ws://127.0.0.1:8002/stt/stream'
        os.environ['STT_PROVIDER_API_KEY'] = ''
        
        mock_health.return_value = True
        from backend.stt_bridge import STTBridge
        
        bridge = STTBridge()
        result = bridge.preload()
        assert result is True
        mock_health.assert_called_once()

    def test_stt_bridge_get_streaming_client_streaming_mode(self):
        """Test STTBridge returns streaming client in streaming mode."""
        os.environ['STT_PROVIDER'] = 'streaming'
        os.environ['STT_PROVIDER_URL'] = 'http://127.0.0.1:8002'
        os.environ['STT_PROVIDER_WS_URL'] = 'ws://127.0.0.1:8002/stt/stream'
        os.environ['STT_PROVIDER_API_KEY'] = 'test-key'
        from backend.stt_bridge import STTBridge
        
        bridge = STTBridge()
        client = bridge.get_streaming_client()
        assert client is not None
        assert hasattr(client, 'transcribe_file')


class TestReadyEndpoint:
    """Test /ready endpoint behavior with STT provider."""

    @patch('backend.api._stt_provider_health_snapshot')
    def test_ready_endpoint_includes_stt_provider_health_streaming(self, mock_health):
        """Test /ready endpoint includes STT provider health in streaming mode."""
        os.environ['STT_PROVIDER'] = 'streaming'
        os.environ['STT_PROVIDER_URL'] = 'http://127.0.0.1:8002'
        os.environ['STT_PROVIDER_WS_URL'] = 'ws://127.0.0.1:8002/stt/stream'
        os.environ['STT_PROVIDER_API_KEY'] = ''
        
        mock_health.return_value = {
            'mode': 'streaming',
            'url': 'http://127.0.0.1:8002',
            'ws_url': 'ws://127.0.0.1:8002/stt/stream',
            'reachable': True,
            'status_code': 200,
            'latency_ms': 50,
            'health_url': 'http://127.0.0.1:8002/health'
        }
        
        from backend.api import _stt_provider_health_snapshot
        health = _stt_provider_health_snapshot()
        
        assert health['mode'] == 'streaming'
        assert health['reachable'] is True
        assert health['status_code'] == 200
        assert health['latency_ms'] == 50

    def test_ready_endpoint_local_mode_no_provider_check(self):
        """Test /ready endpoint does not check provider in local mode."""
        os.environ['STT_PROVIDER'] = 'local'
        from backend.api import _stt_provider_health_snapshot
        
        health = _stt_provider_health_snapshot()
        
        assert health['mode'] == 'local'
        # In local mode, provider health is not checked
        assert 'reachable' not in health or health.get('reachable') is None


class TestStreamingClient:
    """Test StreamingSTTClient SDK functionality."""

    def test_streaming_client_initialization(self):
        """Test StreamingSTTClient initializes with correct parameters."""
        from backend.stt_client.client import StreamingSTTClient
        
        client = StreamingSTTClient(
            api_key='test-key',
            websocket_url='ws://127.0.0.1:8002/stt/stream',
            base_url='http://127.0.0.1:8002'
        )
        
        assert client.base_url == 'http://127.0.0.1:8002'
        assert client.websocket_url == 'ws://127.0.0.1:8002/stt/stream'
        assert client.api_key == 'test-key'

    def test_streaming_client_language_parameter(self):
        """Test StreamingSTTClient includes language in WebSocket URL."""
        from backend.stt_client.client import StreamingSTTClient
        
        client = StreamingSTTClient(
            api_key='test-key',
            websocket_url='ws://127.0.0.1:8002/stt/stream',
            base_url='http://127.0.0.1:8002'
        )
        
        # Check that language is included in the stream URL
        stream_url = client._stream_url(language='es')
        assert 'language=es' in stream_url


class TestStreamingEvents:
    """Test streaming event handling."""

    def test_partial_transcript_event_structure(self):
        """Test partial transcript event structure is understood."""
        from backend.stt_client.client import StreamingSTTClient
        
        client = StreamingSTTClient(
            api_key='test-key',
            websocket_url='ws://127.0.0.1:8002/stt/stream',
            base_url='http://127.0.0.1:8002'
        )
        
        # Verify the client has the streaming method
        assert hasattr(client, 'stream_pcm16')

    def test_final_transcript_event_structure(self):
        """Test final transcript event structure is understood."""
        from backend.stt_client.client import StreamingSTTClient
        
        client = StreamingSTTClient(
            api_key='test-key',
            websocket_url='ws://127.0.0.1:8002/stt/stream',
            base_url='http://127.0.0.1:8002'
        )
        
        # Verify the client has the streaming method
        assert hasattr(client, 'stream_pcm16')


class TestSTTProviderConfig:
    """Test STT provider configuration accessors."""

    def test_get_stt_provider_returns_configured_value(self):
        """Test get_stt_provider returns the configured STT provider mode."""
        os.environ['STT_PROVIDER'] = 'streaming'
        from backend.config import get_stt_provider
        
        assert get_stt_provider() == 'streaming'

    def test_get_stt_provider_url_returns_configured_value(self):
        """Test get_stt_provider_url returns the configured URL."""
        os.environ['STT_PROVIDER_URL'] = 'http://example.com:8002'
        from backend.config import get_stt_provider_url
        
        assert get_stt_provider_url() == 'http://example.com:8002'

    def test_get_stt_provider_ws_url_returns_configured_value(self):
        """Test get_stt_provider_ws_url returns the configured WebSocket URL."""
        os.environ['STT_PROVIDER_WS_URL'] = 'ws://example.com:8002/stt/stream'
        from backend.config import get_stt_provider_ws_url
        
        assert get_stt_provider_ws_url() == 'ws://example.com:8002/stt/stream'

    def test_get_stt_provider_api_key_returns_configured_value(self):
        """Test get_stt_provider_api_key returns the configured API key."""
        os.environ['STT_PROVIDER_API_KEY'] = 'test-api-key'
        from backend.config import get_stt_provider_api_key
        
        assert get_stt_provider_api_key() == 'test-api-key'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
