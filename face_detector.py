"""MediaPipe 기반 실시간 얼굴 인식 모듈."""
from __future__ import annotations

import logging

import cv2
import mediapipe as mp
import numpy as np

logger = logging.getLogger(__name__)


class FaceDetector:
    """카메라 영상에서 얼굴을 감지하고 시선/자세 정보를 반환."""

    def __init__(self, min_detection_confidence: float = 0.7) -> None:
        self.mp_face = mp.solutions.face_detection
        self.mp_drawing = mp.solutions.drawing_utils
        self.detector = self.mp_face.FaceDetection(
            min_detection_confidence=min_detection_confidence
        )
        self._is_face_visible = False
        self._last_bbox: tuple[float, float, float, float] | None = None
        self._face_count: int = 0
        self._face_center: tuple[float, float] | None = None

    def process_frame(self, frame: np.ndarray) -> tuple[bool, np.ndarray]:
        """
        BGR 프레임을 처리해 얼굴 감지 여부와 시각화된 프레임 반환.
        Returns:
            (얼굴 감지 여부, 시각화된 프레임)
        """
        self._is_face_visible = False
        self._last_bbox = None
        self._face_count = 0
        self._face_center = None

        # 프레임 유효성 검사
        if frame is None or frame.size == 0:
            logger.warning("빈 프레임 입력")
            return False, frame if frame is not None else np.zeros((480, 640, 3), dtype=np.uint8)

        try:
            # 채널 수 확인 및 변환
            if len(frame.shape) == 2:
                # 그레이스케일 → BGR 변환
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            elif frame.shape[2] == 4:
                # BGRA → BGR 변환
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            elif frame.shape[2] != 3:
                logger.warning("지원하지 않는 채널 수: %d", frame.shape[2])
                return False, frame

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.detector.process(rgb)
        except Exception as e:
            logger.error("얼굴 인식 처리 실패: %s", e)
            return False, frame

        if results.detections:
            self._is_face_visible = True
            self._face_count = len(results.detections)

            for detection in results.detections:
                self.mp_drawing.draw_detection(frame, detection)
                if detection.location_data.relative_bounding_box:
                    box = detection.location_data.relative_bounding_box
                    h, w = frame.shape[:2]
                    self._last_bbox = (
                        box.xmin * w,
                        box.ymin * h,
                        box.width * w,
                        box.height * h,
                    )
                    # 얼굴 중심 좌표 계산 (시선 방향 추정용)
                    cx = (box.xmin + box.width / 2) * w
                    cy = (box.ymin + box.height / 2) * h
                    self._face_center = (cx, cy)

            # 얼굴 위치 안내 오버레이
            if self._face_center:
                h, w = frame.shape[:2]
                cx, cy = self._face_center
                frame_cx, frame_cy = w / 2, h / 2
                dx = cx - frame_cx
                dy = cy - frame_cy
                # 중심에서 벗어난 정도에 따라 안내
                if abs(dx) > w * 0.2:
                    direction = "왼쪽" if dx < 0 else "오른쪽"
                    cv2.putText(frame, f"<- {direction}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
                if abs(dy) > h * 0.2:
                    direction = "위" if dy < 0 else "아래"
                    cv2.putText(frame, f"^ {direction}", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        return self._is_face_visible, frame

    @property
    def is_face_visible(self) -> bool:
        return self._is_face_visible

    @property
    def face_count(self) -> int:
        return self._face_count

    @property
    def face_center(self) -> tuple[float, float] | None:
        return self._face_center

    @property
    def last_bbox(self) -> tuple[float, float, float, float] | None:
        return self._last_bbox

    def release(self) -> None:
        """리소스 해제."""
        try:
            self.detector.close()
        except Exception:
            pass
