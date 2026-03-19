"use client";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { useEffect, useCallback } from "react";
import { Mic, Square, Loader2 } from "lucide-react";

interface Props {
  onRecordingComplete: (blob: Blob, duration: number) => void;
  disabled?: boolean;
}

export default function AudioRecorder({ onRecordingComplete, disabled }: Props) {
  const { isRecording, startRecording, stopRecording, audioBlob, duration, error } =
    useAudioRecorder();

  const handleComplete = useCallback(() => {
    if (audioBlob && duration > 0) {
      onRecordingComplete(audioBlob, duration);
    }
  }, [audioBlob, duration, onRecordingComplete]);

  useEffect(() => {
    handleComplete();
  }, [handleComplete]);

  return (
    <div className="space-y-2">
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <button
        onClick={isRecording ? stopRecording : startRecording}
        disabled={disabled}
        className={`w-full py-3 px-6 rounded-xl font-semibold text-base transition-all flex items-center justify-center gap-2 ${
          isRecording
            ? "bg-red-500 hover:bg-red-600 text-white animate-pulse"
            : "bg-green-500 hover:bg-green-600 text-white"
        } disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        {isRecording ? (
          <>
            <Square size={18} /> 녹음 종료
          </>
        ) : disabled ? (
          <>
            <Loader2 size={18} className="animate-spin" /> 분석 중...
          </>
        ) : (
          <>
            <Mic size={18} /> 녹음 시작
          </>
        )}
      </button>

      {isRecording && (
        <p className="text-center text-sm text-red-600 font-medium">
          🔴 녹음 중... 답변이 끝나면 종료 버튼을 누르세요.
        </p>
      )}
    </div>
  );
}
