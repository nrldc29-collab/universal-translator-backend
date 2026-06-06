import { renderHook, act } from '@testing-library/react-hooks';
import { useMobileRecording } from '../hooks/useMobileRecording';

describe('useMobileRecording', () => {
  const mockProps = {
    isConnected: true,
    sourceLanguage: 'en',
    targetLanguage: 'ht',
    wsUrl: 'http://localhost:8000',
    token: 'test-token',
    recording: null,
    setRecording: jest.fn(),
    setStatus: jest.fn(),
    setStatusType: jest.fn(),
    setResult: jest.fn(),
    isPlayingTtsRef: { current: false },
    setIsPlayingTts: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('initializes with HIGH audio quality', () => {
    const { result } = renderHook(() => useMobileRecording(mockProps));
    
    expect(result.current.audioQuality).toBe('HIGH');
    expect(result.current.isUploading).toBe(false);
    expect(result.current.uploadProgress).toBe(0);
  });

  test('provides AUDIO_QUALITIES options', () => {
    const { result } = renderHook(() => useMobileRecording(mockProps));
    
    expect(result.current.AUDIO_QUALITIES).toBeDefined();
    expect(result.current.AUDIO_QUALITIES.LOW).toBeDefined();
    expect(result.current.AUDIO_QUALITIES.MEDIUM).toBeDefined();
    expect(result.current.AUDIO_QUALITIES.HIGH).toBeDefined();
  });

  test('updates audio quality', () => {
    const { result } = renderHook(() => useMobileRecording(mockProps));

    act(() => {
      result.current.setAudioQuality('MEDIUM');
    });

    expect(result.current.audioQuality).toBe('MEDIUM');
  });

  test('does not update audio quality with invalid value', () => {
    const { result } = renderHook(() => useMobileRecording(mockProps));
    const initialQuality = result.current.audioQuality;

    act(() => {
      result.current.setAudioQuality('INVALID');
    });

    expect(result.current.audioQuality).toBe(initialQuality);
  });

  test('returns startRecording and stopRecording functions', () => {
    const { result } = renderHook(() => useMobileRecording(mockProps));
    
    expect(typeof result.current.startRecording).toBe('function');
    expect(typeof result.current.stopRecording).toBe('function');
  });

  test('returns cancelUpload function', () => {
    const { result } = renderHook(() => useMobileRecording(mockProps));
    
    expect(typeof result.current.cancelUpload).toBe('function');
  });

  test('cancelUpload resets upload state', () => {
    const { result } = renderHook(() => useMobileRecording(mockProps));
    
    // Simulate uploading state
    result.current.isUploading = true;
    result.current.uploadProgress = 50;

    act(() => {
      result.current.cancelUpload();
    });

    expect(result.current.isUploading).toBe(false);
    expect(result.current.uploadProgress).toBe(0);
  });
});
