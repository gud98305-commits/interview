"use client";
import { useState, useRef, useCallback, useEffect } from "react";

interface UseCameraReturn {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  isActive: boolean;
  faceDetected: boolean;
  faceCount: number;
  startCamera: () => Promise<void>;
  stopCamera: () => void;
  error: string | null;
}

export function useCamera(): UseCameraReturn {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animFrameRef = useRef<number>(0);
  const detectorRef = useRef<unknown>(null);

  const [isActive, setIsActive] = useState(false);
  const [faceDetected, setFaceDetected] = useState(false);
  const [faceCount, setFaceCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const initFaceDetector = useCallback(async () => {
    try {
      const vision = await import("@mediapipe/tasks-vision");
      const { FaceDetector, FilesetResolver } = vision;
      const wasmFileset = await FilesetResolver.forVisionTasks(
        "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm"
      );
      detectorRef.current = await FaceDetector.createFromOptions(wasmFileset, {
        baseOptions: {
          modelAssetPath:
            "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
          delegate: "GPU",
        },
        runningMode: "VIDEO",
        minDetectionConfidence: 0.7,
      });
    } catch (e) {
      console.warn("MediaPipe 초기화 실패:", e);
    }
  }, []);

  const detectFaces = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const detector = detectorRef.current as { detectForVideo?: (v: HTMLVideoElement, t: number) => { detections: Array<{ boundingBox?: { originX: number; originY: number; width: number; height: number } }> } } | null;

    if (!video || !canvas || !detector?.detectForVideo || video.readyState < 2) {
      animFrameRef.current = requestAnimationFrame(detectFaces);
      return;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);

    try {
      const result = detector.detectForVideo(video, performance.now());
      const detections = result.detections || [];
      setFaceDetected(detections.length > 0);
      setFaceCount(detections.length);

      // 얼굴 바운딩 박스 그리기
      ctx.strokeStyle = detections.length > 0 ? "#22c55e" : "#ef4444";
      ctx.lineWidth = 3;
      for (const det of detections) {
        if (det.boundingBox) {
          const { originX, originY, width, height } = det.boundingBox;
          ctx.strokeRect(originX, originY, width, height);
        }
      }

      // 얼굴 위치 안내
      if (detections.length === 1 && detections[0].boundingBox) {
        const box = detections[0].boundingBox;
        const cx = box.originX + box.width / 2;
        const cy = box.originY + box.height / 2;
        const frameCx = canvas.width / 2;
        const frameCy = canvas.height / 2;

        ctx.font = "20px sans-serif";
        ctx.fillStyle = "#f97316";
        if (Math.abs(cx - frameCx) > canvas.width * 0.25) {
          ctx.fillText(cx < frameCx ? "← 왼쪽으로 치우침" : "오른쪽으로 치우침 →", 10, 30);
        }
        if (Math.abs(cy - frameCy) > canvas.height * 0.25) {
          ctx.fillText(cy < frameCy ? "↑ 위로 치우침" : "↓ 아래로 치우침", 10, 55);
        }
      }
    } catch {
      // 프레임 스킵
    }

    animFrameRef.current = requestAnimationFrame(detectFaces);
  }, []);

  const startCamera = useCallback(async () => {
    try {
      setError(null);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: 640, height: 480 },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      await initFaceDetector();
      setIsActive(true);
      animFrameRef.current = requestAnimationFrame(detectFaces);
    } catch {
      setError("카메라를 사용할 수 없습니다. 브라우저에서 카메라를 허용해 주세요.");
    }
  }, [initFaceDetector, detectFaces]);

  const stopCamera = useCallback(() => {
    cancelAnimationFrame(animFrameRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setIsActive(false);
    setFaceDetected(false);
    setFaceCount(0);
  }, []);

  useEffect(() => {
    return () => {
      cancelAnimationFrame(animFrameRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return { videoRef, canvasRef, isActive, faceDetected, faceCount, startCamera, stopCamera, error };
}
