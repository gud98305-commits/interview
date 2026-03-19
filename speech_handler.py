"""마이크 음성 입력 및 음성 인식 모듈 (Whisper API + Google STT 이중 지원)."""
from __future__ import annotations

import io
import logging
import re
from collections import defaultdict

import speech_recognition as sr
from openai import OpenAI

from config import API_TIMEOUT, OPENAI_API_KEY, WHISPER_MODEL

logger = logging.getLogger(__name__)

# ── 습관어 패턴 ──
# 한국어: 단독 사용되는 습관어만 잡기 위해 앞뒤가 공백/문장 시작·끝인 경우만 매칭
# "어떤", "음악", "프로그래밍" 등의 오탐 방지
FILLER_PATTERNS_KO = re.compile(
    r"(?:^|(?<=\s))"  # 앞이 문장 시작 또는 공백
    r"(어{1,3}|음{1,3}|저기|그러니까|뭐|막|어차피|아니\s?근데|약간)"
    r"(?=\s|$|[,.])",  # 뒤가 공백, 문장끝, 쉼표, 마침표
    re.IGNORECASE,
)
# 영어: \b 단어 경계 사용
FILLER_PATTERNS_EN = re.compile(
    r"\b(um+|uh+|er+|ah+|like|you know|actually|basically|literally)\b",
    re.IGNORECASE,
)


def count_filler_words(text: str) -> dict[str, int]:
    """발화 텍스트에서 습관어 등장 횟수 집계 (한국어/영어 분리 감지)."""
    counts: dict[str, int] = defaultdict(int)
    if not text or not text.strip():
        return dict(counts)
    for m in FILLER_PATTERNS_KO.finditer(text):
        word = m.group(1).strip()
        if word:
            counts[word] += 1
    for m in FILLER_PATTERNS_EN.finditer(text):
        word = m.group(1).lower().strip()
        if word:
            counts[word] += 1
    return dict(counts)


def estimate_speech_rate(word_count: int, duration_seconds: float) -> float:
    """단어 수와 구간 길이로 분당 단어 수(대략 말하기 속도) 추정."""
    if duration_seconds <= 0:
        return 0.0
    return (word_count / duration_seconds) * 60.0


def _detect_audio_format(audio_bytes: bytes) -> str:
    """오디오 바이트의 실제 포맷을 헤더로 감지."""
    if audio_bytes[:4] == b"RIFF":
        return "wav"
    if audio_bytes[:4] == b"fLaC":
        return "flac"
    if audio_bytes[:4] == b"OggS":
        return "ogg"
    if audio_bytes[:4] == b"\x1aE\xdf\xa3":  # EBML header (webm/mkv)
        return "webm"
    if audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb":
        return "mp3"
    # 기본값
    return "wav"


def _transcribe_with_whisper(audio_bytes: bytes, language: str = "ko") -> str | None:
    """OpenAI Whisper API로 음성을 텍스트로 변환. 실패 시 None 반환."""
    if not OPENAI_API_KEY:
        return None
    try:
        client = OpenAI(api_key=OPENAI_API_KEY, timeout=API_TIMEOUT)
        fmt = _detect_audio_format(audio_bytes)
        buf = io.BytesIO(audio_bytes)
        buf.name = f"audio.{fmt}"
        transcript = client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=buf,
            language=language,
            response_format="text",
        )
        result = transcript.strip() if isinstance(transcript, str) else str(transcript).strip()
        if result:
            logger.info("Whisper 인식 성공 (%s, %s): %d자", fmt, language, len(result))
            return result
        return None
    except Exception as e:
        logger.warning("Whisper API 실패, Google STT로 폴백: %s", e)
        return None


def _transcribe_with_google(audio: sr.AudioData, language: str = "ko-KR") -> str:
    """Google Speech Recognition으로 음성을 텍스트로 변환."""
    recognizer = sr.Recognizer()
    try:
        text = recognizer.recognize_google(audio, language=language)
        logger.info("Google STT 인식 성공 (%s): %d자", language, len(text))
        return text
    except sr.UnknownValueError:
        logger.debug("Google STT: 음성 인식 실패 (%s)", language)
        if language == "ko-KR":
            return _transcribe_with_google(audio, "en-US")
        return ""
    except sr.RequestError as e:
        logger.warning("Google STT 요청 실패 (%s): %s", language, e)
        if language == "ko-KR":
            return _transcribe_with_google(audio, "en-US")
        return ""


def wav_bytes_to_text(
    wav_bytes: bytes,
    use_whisper: bool = True,
    language: str = "ko",
) -> tuple[str, float]:
    """
    오디오 바이트(streamlit-mic-recorder 등)를 텍스트로 변환.
    use_whisper=True이면 Whisper API를 우선 시도하고, 실패 시 Google STT로 폴백.
    Returns: (인식된 텍스트, 추정 길이 초)
    """
    if not wav_bytes:
        return "", 0.0

    # 오디오 길이 추정 (Google STT용)
    recognizer = sr.Recognizer()
    duration = 0.0
    audio = None
    try:
        buf = io.BytesIO(wav_bytes)
        with sr.AudioFile(buf) as source:
            audio = recognizer.record(source)
        duration = len(audio.get_raw_data()) / (audio.sample_rate * audio.sample_width)
    except Exception as e:
        logger.warning("WAV 파싱 실패: %s", e)
        # WAV 파싱 실패해도 Whisper는 시도 가능
        if use_whisper:
            lang_code = "ko" if language == "ko" else "en"
            whisper_text = _transcribe_with_whisper(wav_bytes, language=lang_code)
            if whisper_text:
                # duration을 바이트 크기로 대략 추정 (16kHz 16bit mono 기준)
                duration = max(1.0, len(wav_bytes) / 32000)
                return whisper_text, duration
        return "", 0.0

    # 1차: Whisper API 시도
    if use_whisper:
        lang_code = "ko" if language == "ko" else "en"
        whisper_text = _transcribe_with_whisper(wav_bytes, language=lang_code)
        if whisper_text:
            return whisper_text, duration

    # 2차: Google STT 폴백
    if audio:
        lang_code = "ko-KR" if language == "ko" else "en-US"
        text = _transcribe_with_google(audio, lang_code)
        return text.strip(), duration

    return "", duration
