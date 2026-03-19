"""회사/직무 기반 맞춤형 면접 질문 생성 (에러 처리·입력 검증 강화)."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

from config import (
    API_MAX_RETRIES,
    API_TIMEOUT,
    GPT_MODEL,
    MAX_INPUT_LENGTH,
    OPENAI_API_KEY,
    sanitize_input,
)

logger = logging.getLogger(__name__)

# OpenAI 클라이언트 싱글턴
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY, timeout=API_TIMEOUT)
    return _client


@dataclass
class InterviewQuestion:
    """면접 질문 한 개."""
    text: str
    category: str  # e.g. "자기소개", "경력", "기술", "역량"
    difficulty: str  # "쉬움" | "보통" | "어려움"
    language: str = "ko"  # "ko" | "en"


def _safe_extract_response(response) -> str | None:
    """OpenAI 응답에서 안전하게 텍스트 추출."""
    try:
        if not response.choices:
            logger.warning("질문 생성 API 응답에 choices가 비어 있음")
            return None
        content = response.choices[0].message.content
        if content is None:
            logger.warning("질문 생성 API 응답 content가 None")
            return None
        return content.strip()
    except (AttributeError, IndexError) as e:
        logger.error("질문 생성 API 응답 추출 실패: %s", e)
        return None


def generate_questions(
    company_name: str,
    position: str,
    known_questions: list[str],
    count: int = 5,
    language: str = "ko",
) -> list[InterviewQuestion]:
    """
    지원 회사명·직무와 (선택) 실제 수집 질문을 바탕으로 AI 예상 질문 생성.
    입력값 검증, 에러 처리, 재시도 로직 포함.
    """
    # 입력 검증 및 정제
    company_name = sanitize_input(company_name, MAX_INPUT_LENGTH)
    position = sanitize_input(position, MAX_INPUT_LENGTH)
    if not company_name or not position:
        logger.warning("빈 회사명/직무로 질문 생성 시도")
        return []

    count = max(1, min(15, count))  # 1~15개로 제한

    client = _get_client()
    known_part = ""
    if known_questions:
        safe_questions = [q[:300] for q in known_questions[:15]]
        known_part = "\n【해당 회사에서 나온 실제 면접 질문 예시 (참고용)】\n" + "\n".join(
            f"- {q}" for q in safe_questions
        )

    language_line = "질문은 한국어로 작성해 주세요."
    if language == "en":
        language_line = "Write all questions in English."

    prompt = f"""당신은 채용 전문가입니다. 다음 조건에 맞는 면접 예상 질문을 생성해 주세요.

【지원 회사】 {company_name}
【지원 직무】 {position}
{known_part}

{language_line}

위 맥락을 반영해, 실제 면접에서 나올 법한 예상 질문 {count}개를 만들어 주세요.
다음 JSON 배열 형식으로만 답변하세요. 다른 설명은 붙이지 마세요.
[
  {{ "text": "질문 내용", "category": "카테고리", "difficulty": "쉬움|보통|어려움" }},
  ...
]"""

    raw = None
    for attempt in range(1, API_MAX_RETRIES + 1):
        try:
            logger.info("질문 생성 API 호출 시도 %d/%d", attempt, API_MAX_RETRIES)
            response = client.chat.completions.create(
                model=GPT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            raw = _safe_extract_response(response)
            if raw:
                logger.info("질문 생성 API 응답 수신 (%d자)", len(raw))
                break
            # 빈 응답이면 재시도
            if attempt < API_MAX_RETRIES:
                time.sleep(2)
        except (APITimeoutError, APIConnectionError) as e:
            logger.warning("질문 생성 API 타임아웃/연결 오류 (시도 %d): %s", attempt, e)
            if attempt < API_MAX_RETRIES:
                time.sleep(2 ** attempt)
        except RateLimitError as e:
            logger.warning("질문 생성 API 속도 제한 (시도 %d): %s", attempt, e)
            if attempt < API_MAX_RETRIES:
                time.sleep(5 * attempt)
        except Exception as e:
            logger.error("질문 생성 API 예외: %s", e)
            return []

    if not raw:
        logger.error("질문 생성 실패: API 응답 없음")
        return []

    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            raw = raw[start:end]
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("질문 JSON 파싱 실패: %s", e)
        return []

    # data가 리스트인지 확인
    if not isinstance(data, list):
        logger.warning("질문 JSON이 배열이 아님: %s", type(data).__name__)
        return []

    result: list[InterviewQuestion] = []
    for item in data:
        if isinstance(item, dict) and "text" in item:
            text = str(item["text"]).strip()
            if not text:
                continue
            result.append(
                InterviewQuestion(
                    text=text,
                    category=str(item.get("category", "기타")),
                    difficulty=str(item.get("difficulty", "보통")),
                    language=language,
                )
            )
    logger.info("질문 %d개 생성 완료", len(result))
    return result


def collect_questions_placeholder(company_name: str) -> list[str]:
    """
    해당 회사 실제 면접 질문 수집 플레이스홀더.
    실제로는 크롤링/API로 수집 가능. 여기서는 빈 리스트 반환.
    """
    return []
