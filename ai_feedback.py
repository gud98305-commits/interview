"""OpenAI GPT 기반 실시간 면접 피드백 및 평가 (에러 처리·재시도·타임아웃 강화)."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

from config import API_MAX_RETRIES, API_TIMEOUT, GPT_MODEL, OPENAI_API_KEY
from speech_handler import count_filler_words, estimate_speech_rate

logger = logging.getLogger(__name__)

# OpenAI 클라이언트 싱글턴 — 매 호출마다 재생성하지 않음
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """OpenAI 클라이언트를 싱글턴으로 반환."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY, timeout=API_TIMEOUT)
    return _client


@dataclass
class FeedbackResult:
    """단일 답변에 대한 피드백 결과."""
    score: int  # 0-100
    logic_comment: str
    specificity_comment: str
    speed_comment: str
    tone_confidence_comment: str
    filler_comment: str
    improvement_tips: list[str]
    raw_feedback: str = ""
    error_message: str = ""


def _clamp_score(value: int | float | str, low: int = 0, high: int = 100) -> int:
    """점수를 0-100 범위로 클램핑."""
    try:
        return max(low, min(high, int(value)))
    except (ValueError, TypeError):
        return 50


def _safe_extract_response(response) -> str | None:
    """OpenAI 응답에서 안전하게 텍스트 추출. choices가 비었거나 content가 None이면 None."""
    try:
        if not response.choices:
            logger.warning("API 응답에 choices가 비어 있음")
            return None
        content = response.choices[0].message.content
        if content is None:
            logger.warning("API 응답 content가 None")
            return None
        return content.strip()
    except (AttributeError, IndexError) as e:
        logger.error("API 응답 추출 실패: %s", e)
        return None


def _call_openai_with_retry(
    messages: list[dict],
    model: str = GPT_MODEL,
    temperature: float = 0.3,
    max_retries: int = API_MAX_RETRIES,
) -> str | None:
    """OpenAI API 호출 + 재시도 로직. 성공 시 응답 텍스트, 실패 시 None."""
    client = _get_client()
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("OpenAI API 호출 시도 %d/%d (model=%s)", attempt, max_retries, model)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            raw = _safe_extract_response(response)
            if raw is None:
                logger.warning("빈 응답, 재시도 필요")
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return None
            logger.info("OpenAI API 응답 수신 (%d자)", len(raw))
            return raw
        except (APITimeoutError, APIConnectionError) as e:
            logger.warning("API 타임아웃/연결 오류 (시도 %d/%d): %s", attempt, max_retries, e)
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.info("%d초 후 재시도...", wait)
                time.sleep(wait)
        except RateLimitError as e:
            logger.warning("API 속도 제한 (시도 %d/%d): %s", attempt, max_retries, e)
            if attempt < max_retries:
                wait = 5 * attempt
                logger.info("%d초 후 재시도...", wait)
                time.sleep(wait)
        except Exception as e:
            logger.error("API 호출 예외: %s", e)
            return None
    logger.error("API 호출 최대 재시도 횟수 초과")
    return None


def _parse_feedback_json(raw: str) -> dict | None:
    """GPT 응답에서 JSON 추출 및 파싱."""
    if not raw:
        return None
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            raw = raw[start:end]
        data = json.loads(raw)
        if not isinstance(data, dict):
            logger.warning("피드백 JSON이 dict가 아님: %s", type(data).__name__)
            return None
        return data
    except json.JSONDecodeError as e:
        logger.warning("피드백 JSON 파싱 실패: %s", e)
        return None


def _safe_tips_list(value) -> list[str]:
    """improvement_tips를 안전하게 문자열 리스트로 변환."""
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        # GPT가 문자열 하나만 반환한 경우
        return [value] if value else []
    return []


def analyze_with_gpt(
    question: str,
    answer_text: str,
    filler_counts: dict[str, int],
    speech_rate_wpm: float,
    duration_seconds: float,
) -> FeedbackResult:
    """GPT로 답변을 분석해 논리성, 구체성, 말하기 속도, 톤/자신감, 습관어 피드백 반환."""
    filler_summary = (
        f"습관어 사용: {dict(filler_counts)}"
        if filler_counts
        else "습관어 사용: 없음"
    )
    prompt = f"""당신은 면접 코치입니다. 다음 면접 질문과 지원자의 답변을 분석해 주세요.

【질문】
{question}

【답변(음성 인식 결과)】
{answer_text}

【추가 정보】
- {filler_summary}
- 말하기 속도(추정): 분당 약 {speech_rate_wpm:.0f}단어 (답변 길이: {duration_seconds:.1f}초)

다음 JSON 형식으로만 답변하세요. 다른 설명은 붙이지 마세요.
{{
  "score": 0에서 100 사이 정수,
  "logic_comment": "논리성에 대한 한 줄 평가",
  "specificity_comment": "구체성(숫자, 사례, 경험)에 대한 한 줄 평가",
  "speed_comment": "말하기 속도에 대한 한 줄 평가",
  "tone_confidence_comment": "목소리 톤과 자신감에 대한 한 줄 평가 (텍스트만으로 추론)",
  "filler_comment": "습관어(um, uh, 어, 음 등) 사용에 대한 한 줄 평가",
  "improvement_tips": ["개선 팁 1", "개선 팁 2", "개선 팁 3"]
}}"""

    raw = _call_openai_with_retry(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    if raw is None:
        return FeedbackResult(
            score=0,
            logic_comment="",
            specificity_comment="",
            speed_comment="",
            tone_confidence_comment="",
            filler_comment="",
            improvement_tips=[],
            error_message="API 호출에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        )

    data = _parse_feedback_json(raw)
    if data is None:
        return FeedbackResult(
            score=50,
            logic_comment="",
            specificity_comment="",
            speed_comment="",
            tone_confidence_comment="",
            filler_comment="",
            improvement_tips=[],
            raw_feedback=raw,
            error_message="AI 응답 파싱에 실패했습니다.",
        )

    return FeedbackResult(
        score=_clamp_score(data.get("score", 50)),
        logic_comment=str(data.get("logic_comment", "")),
        specificity_comment=str(data.get("specificity_comment", "")),
        speed_comment=str(data.get("speed_comment", "")),
        tone_confidence_comment=str(data.get("tone_confidence_comment", "")),
        filler_comment=str(data.get("filler_comment", "")),
        improvement_tips=_safe_tips_list(data.get("improvement_tips", [])),
        raw_feedback=raw,
    )


def get_feedback(
    question: str,
    answer_text: str,
    duration_seconds: float,
) -> FeedbackResult:
    """답변 텍스트와 길이만으로 피드백 생성 (습관어·속도는 여기서 계산)."""
    word_count = len(answer_text.split()) if answer_text else 0
    rate = estimate_speech_rate(word_count, duration_seconds)
    filler_counts = count_filler_words(answer_text or "")
    return analyze_with_gpt(
        question=question,
        answer_text=answer_text or "(인식된 내용 없음)",
        filler_counts=filler_counts,
        speech_rate_wpm=rate,
        duration_seconds=duration_seconds,
    )
