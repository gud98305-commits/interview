"""환경 변수 로드 및 앱 설정."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# 모델 설정 — 환경 변수로 오버라이드 가능
GPT_MODEL: str = os.getenv("GPT_MODEL", "gpt-4o-mini")
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "whisper-1")
TTS_MODEL: str = os.getenv("TTS_MODEL", "tts-1")
TTS_VOICE: str = os.getenv("TTS_VOICE", "nova")  # alloy, echo, fable, onyx, nova, shimmer


def _safe_int(value: str | None, default: int) -> int:
    """환경 변수를 안전하게 int로 변환. 실패 시 기본값 반환."""
    if value is None:
        return default
    try:
        parsed = int(value)
        if parsed <= 0:
            logger.warning("환경 변수 값이 0 이하: '%s' → 기본값 %d 사용", value, default)
            return default
        return parsed
    except ValueError:
        logger.warning("환경 변수를 정수로 변환 실패: '%s' → 기본값 %d 사용", value, default)
        return default


# API 호출 설정 — 잘못된 값이어도 크래시하지 않음
API_TIMEOUT: int = _safe_int(os.getenv("API_TIMEOUT"), 30)
API_MAX_RETRIES: int = _safe_int(os.getenv("API_MAX_RETRIES"), 2)

# 입력 길이 제한
MAX_INPUT_LENGTH: int = 200  # 회사명/직무 입력 최대 길이
MAX_QUESTION_LENGTH: int = 500  # 질문 텍스트 최대 길이


def mask_api_key(key: str) -> str:
    """API 키를 로그용으로 마스킹."""
    if not key or len(key) < 10:
        return "***"
    return key[:4] + "..." + key[-4:]


def validate_config() -> tuple[bool, str]:
    """OpenAI API 키 유효성 검사."""
    if not OPENAI_API_KEY or OPENAI_API_KEY == "your_openai_api_key_here":
        return False, "OPENAI_API_KEY를 .env 파일에 설정해 주세요."
    if not OPENAI_API_KEY.startswith(("sk-", "sk-proj-")):
        logger.warning("API 키 형식이 일반적이지 않습니다: %s", mask_api_key(OPENAI_API_KEY))
    logger.info("API 키 확인 완료: %s", mask_api_key(OPENAI_API_KEY))
    return True, ""


def sanitize_input(text: str, max_length: int = MAX_INPUT_LENGTH) -> str:
    """사용자 입력을 정제: 길이 제한, 제어 문자 제거, 프롬프트 인젝션 경고."""
    if not text:
        return ""
    # 제어 문자 제거 (탭·줄바꿈 포함)
    text = "".join(ch for ch in text if ch.isprintable() or ch == " ")
    # 길이 제한
    text = text.strip()[:max_length]
    # 프롬프트 인젝션 방어: 위험 패턴 감지 시 경고 + 해당 패턴 무력화
    dangerous_patterns = [
        "ignore previous", "ignore above", "disregard",
        "forget your instructions", "system prompt",
        "you are now", "new instructions", "override",
        "이전 지시를 무시", "지시를 무시", "역할을 바꿔",
    ]
    text_lower = text.lower()
    for pattern in dangerous_patterns:
        if pattern in text_lower:
            logger.warning("프롬프트 인젝션 시도 감지 및 차단: %s", text[:50])
            # 위험 패턴을 포함한 입력은 차단
            return ""
    return text
