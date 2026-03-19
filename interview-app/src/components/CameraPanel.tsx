"use client";
import { useCamera } from "@/hooks/useCamera";
import { Camera, CameraOff, AlertTriangle, CheckCircle } from "lucide-react";

export default function CameraPanel() {
  const { videoRef, canvasRef, isActive, faceDetected, faceCount, startCamera, stopCamera, error } =
    useCamera();

  return (
    <div className="bg-white/90 rounded-2xl border border-green-200 p-4 shadow-sm">
      <h3 className="text-lg font-bold text-green-900 mb-2 flex items-center gap-2">
        <Camera size={20} /> 얼굴 인식
      </h3>
      <p className="text-sm text-green-700 mb-3">면접관 시선 유지 연습 — 정면을 보세요.</p>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="relative aspect-[4/3] bg-green-50 rounded-xl overflow-hidden mb-3">
        <video ref={videoRef} className="absolute inset-0 w-full h-full object-cover" style={{ display: isActive ? "block" : "none" }} playsInline muted />
        <canvas ref={canvasRef} className="absolute inset-0 w-full h-full object-cover" style={{ display: isActive ? "block" : "none" }} />
        {!isActive && (
          <div className="absolute inset-0 flex items-center justify-center text-green-400">
            <CameraOff size={48} />
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 mb-3">
        <button
          onClick={isActive ? stopCamera : startCamera}
          className={`flex-1 py-2 px-4 rounded-lg font-medium text-sm transition-all ${
            isActive
              ? "bg-red-500 hover:bg-red-600 text-white"
              : "bg-green-500 hover:bg-green-600 text-white"
          }`}
        >
          {isActive ? "카메라 끄기" : "카메라 켜기"}
        </button>
      </div>

      {isActive && (
        <div className={`flex items-center gap-2 text-sm rounded-lg p-2 ${
          faceDetected ? "bg-green-50 text-green-700" : "bg-orange-50 text-orange-700"
        }`}>
          {faceDetected ? (
            <>
              <CheckCircle size={16} />
              {faceCount > 1
                ? `얼굴 ${faceCount}개 감지 — 한 명만 화면에 위치해 주세요.`
                : "얼굴 감지됨. 시선을 유지하세요."}
            </>
          ) : (
            <>
              <AlertTriangle size={16} />
              얼굴이 감지되지 않습니다. 정면을 봐 주세요.
            </>
          )}
        </div>
      )}
    </div>
  );
}
