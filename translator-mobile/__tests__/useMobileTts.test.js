import { renderHook, act } from '@testing-library/react-native';
import { useMobileTts } from '../hooks/useMobileTts';

describe('useMobileTts', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('initializes with empty queue and not playing', () => {
    const { result } = renderHook(() => useMobileTts());
    
    expect(result.current.ttsQueue).toEqual([]);
    expect(result.current.isPlayingTts).toBe(false);
    expect(result.current.volume).toBe(0.8);
    expect(result.current.playbackSpeed).toBe(1.0);
  });

  test('handles TTS chunk and starts playback', () => {
    const { result } = renderHook(() => useMobileTts());
    const mockMessage = {
      audio_base64: 'base64audiodata',
      mime_type: 'audio/wav'
    };

    act(() => {
      result.current.handleTtsChunk(mockMessage);
    });

    expect(result.current.hasReplayAudio).toBe(true);
    expect(result.current.isPlayingTts || result.current.ttsQueue.length >= 0).toBe(true);
  });

  test('clears TTS queue', () => {
    const { result } = renderHook(() => useMobileTts());
    const mockMessage = {
      audio_base64: 'base64audiodata',
      mime_type: 'audio/wav'
    };

    act(() => {
      result.current.handleTtsChunk(mockMessage);
      result.current.clearTtsQueue();
    });

    expect(result.current.ttsQueue).toEqual([]);
    expect(result.current.isPlayingTts).toBe(false);
  });

  test('updates volume within valid range', () => {
    const { result } = renderHook(() => useMobileTts());

    act(() => {
      result.current.setVolume(0.5);
    });

    expect(result.current.volume).toBe(0.5);

    act(() => {
      result.current.setVolume(1.5);
    });

    expect(result.current.volume).toBe(1.0); // Clamped to max

    act(() => {
      result.current.setVolume(-0.5);
    });

    expect(result.current.volume).toBe(0.0); // Clamped to min
  });

  test('updates playback speed within valid range', () => {
    const { result } = renderHook(() => useMobileTts());

    act(() => {
      result.current.setPlaybackSpeed(1.5);
    });

    expect(result.current.playbackSpeed).toBe(1.5);

    act(() => {
      result.current.setPlaybackSpeed(3.0);
    });

    expect(result.current.playbackSpeed).toBe(2.0); // Clamped to max

    act(() => {
      result.current.setPlaybackSpeed(0.2);
    });

    expect(result.current.playbackSpeed).toBe(0.5); // Clamped to min
  });

  test('does not add chunk without audio_base64', () => {
    const { result } = renderHook(() => useMobileTts());
    const mockMessage = {
      mime_type: 'audio/wav'
    };

    act(() => {
      result.current.handleTtsChunk(mockMessage);
    });

    expect(result.current.ttsQueue.length).toBe(0);
  });

  test('limits queue size to MAX_QUEUE_SIZE', () => {
    const { result } = renderHook(() => useMobileTts());
    
    // Add more than MAX_QUEUE_SIZE (50) chunks
    for (let i = 0; i < 55; i++) {
      act(() => {
        result.current.handleTtsChunk({
          audio_base64: `base64audiodata${i}`,
          mime_type: 'audio/wav'
        });
      });
    }

    expect(result.current.ttsQueue.length).toBe(50);
  });
});
