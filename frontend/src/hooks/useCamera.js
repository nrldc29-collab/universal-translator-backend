import { useRef, useState } from 'react';
import { authHeaders, responseErrorMessage } from '../utils';

export default function useCamera({ apiUrl, authToken, targetLanguage, setStatus, onResult }) {
  const [cameraActive, setCameraActive] = useState(false);
  const [ocrText, setOcrText] = useState('');
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  async function startCamera() {
    try {
      if (streamRef.current) return;
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      streamRef.current = stream;
      const el = videoRef.current || document.createElement('video');
      el.setAttribute('playsinline', '');
      el.muted = true;
      el.srcObject = stream;
      await el.play();
      videoRef.current = el;
      setCameraActive(true);
      setStatus('Camera ready');
    } catch (e) {
      setStatus('Camera permission denied');
    }
  }

  async function stopCamera() {
    try { streamRef.current?.getTracks()?.forEach((t) => t.stop()); } catch {}
    streamRef.current = null;
    setCameraActive(false);
  }

  async function captureAndTranslateFrame() {
    if (!videoRef.current) { setStatus('Open camera first'); return; }
    try {
      const video = videoRef.current;
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 360;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise((res) => canvas.toBlob(res, 'image/png'));
      const form = new FormData();
      form.append('image', blob, 'frame.png');
      form.append('source_language', 'auto');
      form.append('target_language', targetLanguage);
      form.append('synthesize_audio', 'false');
      setStatus('OCR translating...');
      const resp = await fetch(`${apiUrl}/translate/image`, { method: 'POST', headers: authHeaders(authToken), body: form });
      if (!resp.ok) throw new Error(await responseErrorMessage(resp, 'OCR failed'));
      const data = await resp.json();
      setOcrText(data.ocr_text || '');
      onResult({ source_text: data.ocr_text || '', translated_text: data.translated_text || '' });
      setStatus('Image translated');
    } catch (e) {
      setStatus(e.message || 'OCR failed');
    }
  }

  return { cameraActive, ocrText, videoRef, startCamera, stopCamera, captureAndTranslateFrame };
}
