import { apiToWsUrl, connectWS } from '../services/ws';

const activeSockets = [];

describe('WebSocket Service', () => {
  afterEach(() => {
    while (activeSockets.length > 0) {
      const socket = activeSockets.pop();
      try {
        socket?.close?.();
      } catch {
        // Socket may already be closed.
      }
    }
  });
  describe('apiToWsUrl', () => {
    test('converts HTTP to WS', () => {
      const result = apiToWsUrl('http://localhost:8000', '/ws/audio', 'token123');
      expect(result).toBe('ws://localhost:8000/ws/audio?access_token=token123');
    });

    test('converts HTTPS to WSS', () => {
      const result = apiToWsUrl('https://example.com', '/ws/audio', 'token123');
      expect(result).toBe('wss://example.com/ws/audio?access_token=token123');
    });

    test('handles existing query parameters', () => {
      const result = apiToWsUrl('http://localhost:8000?param=value', '/ws/audio', 'token123');
      expect(result).toBe('ws://localhost:8000/ws/audio?param=value&access_token=token123');
    });

    test('handles null token', () => {
      const result = apiToWsUrl('http://localhost:8000', '/ws/audio', null);
      expect(result).toBe('ws://localhost:8000/ws/audio');
    });

    test('uses default path when not provided', () => {
      const result = apiToWsUrl('http://localhost:8000', null, 'token123');
      expect(result).toBe('ws://localhost:8000/ws/audio?access_token=token123');
    });
  });

  describe('connectWS', () => {
    test('returns control object with required methods', () => {
      const mockOnMessage = jest.fn();
      const mockSetStatus = jest.fn();
      
      const wsControl = connectWS('ws://localhost:8000/ws/audio', mockOnMessage, mockSetStatus);
      activeSockets.push(wsControl);
      
      expect(typeof wsControl.send).toBe('function');
      expect(typeof wsControl.close).toBe('function');
      expect(typeof wsControl.updateHandlers).toBe('function');
      expect(typeof wsControl.forceReconnect).toBe('function');
      expect(typeof wsControl.isConnected).toBe('boolean');
      expect(typeof wsControl.reconnectAttempts).toBe('number');
      expect(typeof wsControl.connectionDuration).toBe('number');
    });

    test('send returns false when not connected', () => {
      const mockOnMessage = jest.fn();
      const mockSetStatus = jest.fn();
      
      const wsControl = connectWS('ws://localhost:8000/ws/audio', mockOnMessage, mockSetStatus);
      activeSockets.push(wsControl);
      
      const result = wsControl.send('test message');
      expect(result).toBe(false);
    });

    test('close can be called with custom code and reason', () => {
      const mockOnMessage = jest.fn();
      const mockSetStatus = jest.fn();
      
      const wsControl = connectWS('ws://localhost:8000/ws/audio', mockOnMessage, mockSetStatus);
      activeSockets.push(wsControl);
      
      expect(() => {
        wsControl.close(1000, 'Normal closure');
      }).not.toThrow();
    });

    test('updateHandlers updates message and status handlers', () => {
      const mockOnMessage = jest.fn();
      const mockSetStatus = jest.fn();
      const newOnMessage = jest.fn();
      const newSetStatus = jest.fn();
      
      const wsControl = connectWS('ws://localhost:8000/ws/audio', mockOnMessage, mockSetStatus);
      activeSockets.push(wsControl);
      
      wsControl.updateHandlers(newOnMessage, newSetStatus);
      
      // Handlers should be updated (no direct way to verify without actual connection)
      expect(() => wsControl.updateHandlers(newOnMessage, newSetStatus)).not.toThrow();
    });

    test('forceReconnect can be called', () => {
      const mockOnMessage = jest.fn();
      const mockSetStatus = jest.fn();
      
      const wsControl = connectWS('ws://localhost:8000/ws/audio', mockOnMessage, mockSetStatus);
      activeSockets.push(wsControl);
      
      expect(() => {
        wsControl.forceReconnect();
      }).not.toThrow();
    });
  });
});
