"use client";
import { useState, useRef, useCallback } from "react";

interface UseAudioRecorderReturn {
  isRecording: boolean;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  audioBlob: Blob | null;
  duration: number;
  error: string | null;
}

export function useAudioRecorder(): UseAudioRecorderReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const startTime = useRef(0);

  const startRecording = useCallback(async () => {
    try {
      setError(null);
      setAudioBlob(null);
      chunks.current = [];

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, sampleRate: 16000 },
      });

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorder.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };

      recorder.onstop = () => {
        const blob = new Blob(chunks.current, { type: mimeType });
        setAudioBlob(blob);
        setDuration((Date.now() - startTime.current) / 1000);
        stream.getTracks().forEach((t) => t.stop());
      };

      startTime.current = Date.now();
      recorder.start(250);
      setIsRecording(true);
    } catch (err) {
      setError(
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "마이크 권한이 필요합니다. 브라우저에서 마이크를 허용해 주세요."
          : "마이크를 사용할 수 없습니다."
      );
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorder.current?.state === "recording") {
      mediaRecorder.current.stop();
      setIsRecording(false);
    }
  }, []);

  return { isRecording, startRecording, stopRecording, audioBlob, duration, error };
}
