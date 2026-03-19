"""
AI 기반 스마트 면접관 - 스트림릿 앱 (v2.1).
- 카메라 실시간 얼굴 인식 (MediaPipe) + 위치 안내
- 마이크로 실제 면접 연습 (Whisper API + Google STT)
- GPT 실시간 피드백 (말하기 속도, 논리성, 구체성, 습관어, 톤/자신감)
- 점수 및 상세 리포트
- 맞춤형 질문 생성 (회사/직무)
- OpenAI TTS로 질문 음성 읽기
- 질문 네비게이션 (이전/다음/건너뛰기)
- 세션 저장/불러오기 (전체 복원)
- 전체 초기화
"""
from __future__ import annotations

import base64
import html
import io
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from openai import OpenAI

from ai_feedback import FeedbackResult, get_feedback
from config import (
    MAX_INPUT_LENGTH,
    MAX_QUESTION_LENGTH,
    OPENAI_API_KEY,
    TTS_MODEL,
    TTS_VOICE,
    sanitize_input,
    validate_config,
)
from face_detector import FaceDetector
from question_generator import (
    InterviewQuestion,
    collect_questions_placeholder,
    generate_questions,
)
from report_generator import AnswerRecord, SessionReport
from speech_handler import count_filler_words, wav_bytes_to_text

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="AI 스마트 면접관",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 세션 저장 디렉토리
SESSION_DIR = Path(__file__).resolve().parent / "sessions"


def _esc(text: str) -> str:
    """HTML 이스케이프 — XSS 방어."""
    return html.escape(str(text)) if text else ""


# 커스텀 UI 스타일 — 연한 초록 톤
st.markdown("""
<style>
    .stApp { background: linear-gradient(180deg, #f0fdf4 0%, #ecfdf5 50%, #f0fdf4 100%); }
    .main-header { padding: 1.5rem 0 1rem 0; border-bottom: 2px solid #bbf7d0; margin-bottom: 1.5rem; }
    .main-header h1 { font-size: 1.85rem; color: #14532d; font-weight: 700; }
    .main-header .caption { color: #166534; font-size: 0.95rem; margin-top: 0.25rem; opacity: 0.9; }
    .metric-card { background: rgba(255,255,255,0.9); border-radius: 12px; padding: 1.25rem;
        box-shadow: 0 1px 3px rgba(34,197,94,0.08); border: 1px solid #bbf7d0; text-align: center; margin-bottom: 0.5rem; }
    .metric-card .value { font-size: 1.75rem; font-weight: 700; color: #14532d; }
    .metric-card .label { font-size: 0.8rem; color: #166534; text-transform: uppercase; letter-spacing: 0.05em; }
    .question-box { background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); border-radius: 12px;
        padding: 1.25rem; border-left: 4px solid #22c55e; margin: 1rem 0; }
    .feedback-section { background: rgba(255,255,255,0.95); border-radius: 12px; padding: 1.25rem;
        box-shadow: 0 1px 3px rgba(34,197,94,0.06); border: 1px solid #bbf7d0; margin: 1rem 0; }
    .feedback-section h4 { color: #14532d; font-size: 0.95rem; margin-bottom: 0.5rem; }
    .feedback-item { padding: 0.5rem 0; border-bottom: 1px solid #dcfce7; font-size: 0.9rem; }
    .feedback-item:last-child { border-bottom: none; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #f0fdf4 0%, #ecfdf5 100%); }
    [data-testid="stSidebar"] .stMarkdown { font-weight: 600; color: #14532d; }
    .sidebar-question { padding: 0.5rem 0.75rem; margin: 0.25rem 0; border-radius: 8px; font-size: 0.85rem; }
    .sidebar-question.current { background: #dcfce7; color: #166534; border-left: 3px solid #22c55e; }
    .sidebar-question.done { color: #15803d; opacity: 0.85; }
    .sidebar-question.skipped { color: #9ca3af; opacity: 0.6; font-style: italic; }
    .stTabs [data-baseweb="tab-list"] { gap: 0.5rem; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px; padding: 0.5rem 1rem; font-weight: 500; }
    .stTabs [aria-selected="true"] { background: #dcfce7; color: #166534; }
    .stButton > button { border-radius: 8px; font-weight: 500; transition: all 0.2s ease;
        background: linear-gradient(180deg, #22c55e 0%, #16a34a 100%) !important;
        color: white !important; border: none !important; }
    .stButton > button:hover { transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(34,197,94,0.35);
        background: linear-gradient(180deg, #16a34a 0%, #15803d 100%) !important; }
    .answer-text { background: #ecfdf5; border-radius: 8px; padding: 1rem; border: 1px solid #bbf7d0;
        font-size: 0.95rem; line-height: 1.6; color: #14532d; }
    [data-testid="stAlert"] { border-left: 4px solid #22c55e; }
</style>
""", unsafe_allow_html=True)

# ── 세션 상태 초기화 ──
_defaults = {
    "questions": [],
    "current_index": 0,
    "records": [],           # list[AnswerRecord]
    "record_map": {},        # {question_idx: AnswerRecord} — 중복 방지용
    "session_report": None,
    "stable_session_id": "",  # 탭 렌더링에도 유지되는 고정 ID
    "company_name": "",
    "position": "",
    "session_started_at": None,
    "generation_language": "ko",
    "use_whisper": True,
    "use_tts": True,
    "face_detector": None,
    "answered_indices": set(),
    "skipped_indices": set(),
    "last_generate_click": 0.0,  # 디바운스용 타임스탬프
}
for key, default in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default


def _get_face_detector() -> FaceDetector:
    """FaceDetector를 세션 상태에 캐시."""
    if st.session_state.face_detector is None:
        st.session_state.face_detector = FaceDetector()
    return st.session_state.face_detector


def _reset_session() -> None:
    """전체 세션 초기화."""
    st.session_state.questions = []
    st.session_state.current_index = 0
    st.session_state.records = []
    st.session_state.record_map = {}
    st.session_state.session_report = None
    st.session_state.stable_session_id = ""
    st.session_state.session_started_at = None
    st.session_state.answered_indices = set()
    st.session_state.skipped_indices = set()


# ── TTS ──
def _tts_audio_bytes(text: str, voice: str = TTS_VOICE) -> bytes | None:
    """OpenAI TTS API로 텍스트를 음성으로 변환. 실패 시 None."""
    if not OPENAI_API_KEY or not text:
        return None
    try:
        client = OpenAI(api_key=OPENAI_API_KEY, timeout=15)
        response = client.audio.speech.create(
            model=TTS_MODEL,
            voice=voice,
            input=text[:4096],  # TTS 최대 입력 길이
        )
        return response.content
    except Exception as e:
        logger.warning("TTS 생성 실패: %s", e)
        return None


def _play_tts(text: str) -> None:
    """TTS 오디오를 Streamlit에서 재생."""
    audio_bytes = _tts_audio_bytes(text)
    if audio_bytes:
        b64 = base64.b64encode(audio_bytes).decode()
        st.markdown(
            f'<audio autoplay controls style="width:100%;height:40px">'
            f'<source src="data:audio/mp3;base64,{b64}" type="audio/mp3">'
            f'</audio>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("(TTS 음성 생성 실패)")


# ── 세션 저장/불러오기 ──
def _save_session(records: list[AnswerRecord], company: str, position: str) -> Path | None:
    """세션 기록을 JSON 파일로 저장 (피드백 전체 포함)."""
    if not records:
        return None
    try:
        SESSION_DIR.mkdir(exist_ok=True)
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = SESSION_DIR / f"session_{session_id}.json"
        data = {
            "company": company,
            "position": position,
            "saved_at": datetime.now().isoformat(),
            "records": [
                {
                    "question": r.question,
                    "answer_text": r.answer_text,
                    "duration_seconds": r.duration_seconds,
                    "score": r.feedback.score,
                    "logic_comment": r.feedback.logic_comment,
                    "specificity_comment": r.feedback.specificity_comment,
                    "speed_comment": r.feedback.speed_comment,
                    "tone_confidence_comment": r.feedback.tone_confidence_comment,
                    "filler_comment": r.feedback.filler_comment,
                    "improvement_tips": r.feedback.improvement_tips,
                    "filler_counts": r.filler_counts,
                }
                for r in records
            ],
        }
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("세션 저장: %s", filepath)
        return filepath
    except Exception as e:
        logger.error("세션 저장 실패: %s", e)
        return None


def _load_session(filepath: Path) -> bool:
    """저장된 세션 파일을 복원. 성공 시 True."""
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
        restored_records = []
        restored_questions = []
        for i, rec_data in enumerate(data.get("records", [])):
            fb = FeedbackResult(
                score=rec_data.get("score", 0),
                logic_comment=rec_data.get("logic_comment", ""),
                specificity_comment=rec_data.get("specificity_comment", ""),
                speed_comment=rec_data.get("speed_comment", ""),
                tone_confidence_comment=rec_data.get("tone_confidence_comment", ""),
                filler_comment=rec_data.get("filler_comment", ""),
                improvement_tips=rec_data.get("improvement_tips", []),
            )
            rec = AnswerRecord(
                question=rec_data.get("question", ""),
                answer_text=rec_data.get("answer_text", ""),
                duration_seconds=rec_data.get("duration_seconds", 0),
                feedback=fb,
                filler_counts=rec_data.get("filler_counts", {}),
            )
            restored_records.append(rec)
            restored_questions.append(
                InterviewQuestion(
                    text=rec_data.get("question", ""),
                    category="복원",
                    difficulty="보통",
                )
            )

        st.session_state.records = restored_records
        st.session_state.questions = restored_questions
        st.session_state.record_map = {i: r for i, r in enumerate(restored_records)}
        st.session_state.answered_indices = set(range(len(restored_records)))
        st.session_state.skipped_indices = set()
        st.session_state.current_index = len(restored_records)
        st.session_state.company_name = data.get("company", "")
        st.session_state.position = data.get("position", "")
        st.session_state.session_started_at = datetime.now()
        logger.info("세션 복원 완료: %d개 기록", len(restored_records))
        return True
    except Exception as e:
        logger.error("세션 복원 실패: %s", e)
        return False


def _list_saved_sessions() -> list[Path]:
    """저장된 세션 파일 목록."""
    if not SESSION_DIR.exists():
        return []
    return sorted(SESSION_DIR.glob("session_*.json"), reverse=True)


# ── 카메라 ──
def run_face_camera_placeholder() -> None:
    """카메라 영역: 스냅샷 또는 플레이스홀더."""
    with st.container():
        st.markdown("#### 📷 얼굴 인식")
        st.caption("면접관 시선 유지 연습 — 카메라를 켜고 정면을 보세요.")
        cam_img = st.camera_input("캠 촬영 (캡처)", label_visibility="collapsed")
    if cam_img is not None:
        bytes_data = cam_img.getvalue()
        nparr = cv2.imdecode(
            np.frombuffer(bytes_data, np.uint8),
            cv2.IMREAD_COLOR,
        )
        if nparr is not None:
            detector = _get_face_detector()
            visible, out_frame = detector.process_frame(nparr)
            st.image(
                cv2.cvtColor(out_frame, cv2.COLOR_BGR2RGB),
                channels="RGB",
                use_container_width=True,
            )
            if visible:
                face_count = detector.face_count
                msg = "얼굴이 감지되었습니다. 시선을 유지하세요."
                if face_count > 1:
                    msg = f"얼굴 {face_count}개 감지. 한 명만 화면에 위치해 주세요."
                st.success(msg)
            else:
                st.warning("얼굴이 감지되지 않았습니다. 카메라를 정면으로 맞춰 주세요.")


# ── 사이드바 ──
def render_sidebar() -> None:
    """사이드바: 회사/직무 입력 및 질문 생성."""
    with st.sidebar:
        st.markdown("### 🎯 맞춤형 질문")
        company = st.text_input(
            "지원 회사명",
            value=st.session_state.company_name,
            placeholder="예: 카카오, 네이버",
            max_chars=MAX_INPUT_LENGTH,
        )
        position = st.text_input(
            "지원 직무",
            value=st.session_state.position,
            placeholder="예: 백엔드 개발자",
            max_chars=MAX_INPUT_LENGTH,
        )
        st.session_state.company_name = sanitize_input(company) if company else ""
        st.session_state.position = sanitize_input(position) if position else ""

        st.markdown("#### 🌐 질문 언어")
        lang_label_to_value = {"한국어": "ko", "English": "en"}
        selected_label = st.radio(
            "생성/작성 질문 언어",
            options=list(lang_label_to_value.keys()),
            index=list(lang_label_to_value.values()).index(st.session_state.generation_language),
            horizontal=True,
            label_visibility="collapsed",
        )
        st.session_state.generation_language = lang_label_to_value[selected_label]

        st.markdown("#### 🔧 설정")
        st.session_state.use_whisper = st.checkbox(
            "Whisper API (고정밀 음성 인식)",
            value=st.session_state.use_whisper,
        )
        st.session_state.use_tts = st.checkbox(
            "TTS 질문 읽기 (면접관 음성)",
            value=st.session_state.use_tts,
        )

        # 디바운스: 2초 이내 재클릭 무시
        import time as _time
        if st.button("✨ 예상 질문 생성", use_container_width=True):
            now = _time.time()
            if now - st.session_state.last_generate_click < 2.0:
                st.warning("잠시 후 다시 시도해 주세요.")
            elif not st.session_state.company_name or not st.session_state.position:
                st.error("회사명과 직무를 입력해 주세요.")
            else:
                st.session_state.last_generate_click = now
                with st.spinner("AI가 예상 질문을 생성하는 중..."):
                    known = collect_questions_placeholder(st.session_state.company_name)
                    qs = generate_questions(
                        st.session_state.company_name,
                        st.session_state.position,
                        known,
                        count=5,
                        language=st.session_state.generation_language,
                    )
                    if qs:
                        _reset_session()
                        st.session_state.questions = qs
                        st.session_state.company_name = sanitize_input(company) if company else ""
                        st.session_state.position = sanitize_input(position) if position else ""
                        st.session_state.stable_session_id = str(uuid.uuid4())[:8]
                        st.success(f"질문 {len(qs)}개 생성 완료.")
                    else:
                        st.error("질문 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.")

        st.divider()
        st.markdown("### 📋 질문 목록")
        for i, q in enumerate(st.session_state.questions):
            idx = st.session_state.current_index
            short = (_esc(q.text[:45]) + "…") if len(q.text) > 45 else _esc(q.text)
            if i in st.session_state.answered_indices:
                status = "done"
            elif i in st.session_state.skipped_indices:
                status = "skipped"
            elif i == idx:
                status = "current"
            else:
                status = ""
            lang_badge = "KR" if getattr(q, "language", "ko") == "ko" else "EN"
            st.markdown(
                f'<div class="sidebar-question {status}">'
                f'<strong>Q{i+1}.</strong> <span style="opacity:0.75">[{_esc(lang_badge)}]</span> {short}'
                "</div>",
                unsafe_allow_html=True,
            )

        # 세션 관리
        st.divider()
        st.markdown("### 💾 세션 관리")

        col_save, col_reset = st.columns(2)
        with col_save:
            if st.button("💾 저장", use_container_width=True):
                path = _save_session(
                    st.session_state.records,
                    st.session_state.company_name,
                    st.session_state.position,
                )
                if path:
                    st.success(f"저장 완료: {path.name}")
                else:
                    st.warning("저장할 답변 기록이 없습니다.")
        with col_reset:
            if st.button("🔄 초기화", use_container_width=True):
                _reset_session()
                st.rerun()

        saved = _list_saved_sessions()
        if saved:
            options = ["선택하세요..."] + [p.name for p in saved]
            choice = st.selectbox("저장된 세션", options=options)
            if choice != "선택하세요...":
                try:
                    data = json.loads((SESSION_DIR / choice).read_text(encoding="utf-8"))
                    n_records = len(data.get("records", []))
                    st.caption(
                        f"{_esc(data.get('company', ''))} / {_esc(data.get('position', ''))} "
                        f"— {n_records}개 답변 ({data.get('saved_at', '')[:16]})",
                    )
                except Exception:
                    pass
                if st.button("📂 이 세션 불러오기", use_container_width=True):
                    filepath = SESSION_DIR / choice
                    if _load_session(filepath):
                        st.success("세션을 복원했습니다.")
                        st.rerun()
                    else:
                        st.error("세션 복원에 실패했습니다.")


def _navigate_question(direction: int) -> None:
    """질문 인덱스를 direction만큼 이동 (범위 제한)."""
    total = len(st.session_state.questions)
    if total == 0:
        return
    new_idx = st.session_state.current_index + direction
    st.session_state.current_index = max(0, min(total - 1, new_idx))


def main() -> None:
    """메인 화면."""
    ok, err = validate_config()
    if not ok:
        st.error(err)
        st.info(".env 파일을 만들고 OPENAI_API_KEY=your_key 형태로 저장해 주세요. .env.example을 참고하세요.")
        return

    st.markdown(
        '<div class="main-header">'
        '<h1>🎤 AI 스마트 면접관</h1>'
        '<p class="caption">실시간 카메라·마이크로 면접 연습 → GPT 피드백 · 점수 · 상세 리포트</p>'
        "</div>",
        unsafe_allow_html=True,
    )
    render_sidebar()

    tab1, tab2, tab3, tab4 = st.tabs(["📹 연습하기", "📊 세션 리포트", "❓ 질문만 생성", "✍️ 질문 작성"])

    with tab1:
        col_cam, col_practice = st.columns([1, 1])
        with col_cam:
            run_face_camera_placeholder()
        with col_practice:
            st.markdown("#### 🎙️ 마이크로 답변 연습")
            questions: list[InterviewQuestion] = st.session_state.questions
            if not questions:
                st.info("👈 왼쪽 사이드바에서 **회사명·직무**를 입력한 뒤 **예상 질문 생성**을 눌러 주세요.")
            else:
                idx = st.session_state.current_index
                total = len(questions)

                # 범위 보정
                if idx >= total:
                    idx = total - 1
                    st.session_state.current_index = idx

                all_done = len(st.session_state.answered_indices | st.session_state.skipped_indices) >= total
                if all_done:
                    st.success("모든 질문에 답변하셨습니다. **세션 리포트** 탭에서 결과를 확인하세요.")
                    if st.button("🔄 처음부터 다시 연습"):
                        st.session_state.current_index = 0
                        st.session_state.answered_indices = set()
                        st.session_state.skipped_indices = set()
                        st.session_state.records = []
                        st.session_state.record_map = {}
                        st.rerun()
                else:
                    q = questions[idx]
                    if st.session_state.session_started_at is None:
                        st.session_state.session_started_at = datetime.now()
                    if not st.session_state.stable_session_id:
                        st.session_state.stable_session_id = str(uuid.uuid4())[:8]

                    # 네비게이션
                    nav1, nav2, nav3, nav4 = st.columns([1, 1, 1, 1])
                    with nav1:
                        st.button("⬅ 이전", disabled=(idx == 0),
                                  on_click=_navigate_question, args=(-1,), use_container_width=True)
                    with nav2:
                        st.button("다음 ➡", disabled=(idx >= total - 1),
                                  on_click=_navigate_question, args=(1,), use_container_width=True)
                    with nav3:
                        if st.button("⏭ 건너뛰기", use_container_width=True):
                            st.session_state.skipped_indices.add(idx)
                            # 다음 미답변 질문 찾기
                            done = st.session_state.answered_indices | st.session_state.skipped_indices
                            next_idx = None
                            for ni in range(idx + 1, total):
                                if ni not in done:
                                    next_idx = ni
                                    break
                            if next_idx is not None:
                                st.session_state.current_index = next_idx
                            st.rerun()
                    with nav4:
                        st.markdown(
                            f"<div style='text-align:center;padding:0.5rem;color:#166534;font-weight:600'>"
                            f"Q{idx+1} / {total}</div>",
                            unsafe_allow_html=True,
                        )

                    lang_badge = "한국어" if getattr(q, "language", "ko") == "ko" else "English"
                    already_answered = idx in st.session_state.answered_indices
                    status_badge = " (답변 완료)" if already_answered else ""

                    st.markdown(
                        f'<div class="question-box">'
                        f'<strong>Q{idx+1}.</strong> {_esc(q.text)}<br>'
                        f'<small style="color:#64748b">언어: {_esc(lang_badge)} · 카테고리: {_esc(q.category)} · 난이도: {_esc(q.difficulty)}{_esc(status_badge)}</small>'
                        "</div>",
                        unsafe_allow_html=True,
                    )

                    # TTS로 질문 읽기
                    if st.session_state.use_tts:
                        if st.button("🔊 질문 듣기", key=f"tts_{idx}"):
                            with st.spinner("음성 생성 중..."):
                                _play_tts(q.text)

                    # 이전 답변 표시
                    if already_answered and idx in st.session_state.record_map:
                        prev_rec = st.session_state.record_map[idx]
                        st.markdown("##### 📝 이전 답변")
                        st.markdown(f'<div class="answer-text">{_esc(prev_rec.answer_text)}</div>', unsafe_allow_html=True)
                        st.metric("점수", f"{prev_rec.feedback.score} / 100")
                        st.info("이미 답변한 질문입니다. 다시 녹음하면 이전 답변을 대체합니다.")

                    # 마이크 녹음
                    try:
                        from streamlit_mic_recorder import mic_recorder
                        audio = mic_recorder(
                            start_prompt="🎤 녹음 시작",
                            stop_prompt="⏹ 녹음 종료",
                            key=f"rec_{idx}",
                        )
                    except ImportError:
                        st.warning("`pip install streamlit-mic-recorder`를 실행해 주세요.")
                        audio = None
                    except Exception as e:
                        logger.error("마이크 레코더 오류: %s", e)
                        st.warning(f"마이크 오류: {_esc(str(e))}")
                        audio = None

                    if audio and audio.get("bytes"):
                        with st.spinner("음성 인식 및 AI 피드백 분석 중..."):
                            lang = getattr(q, "language", "ko")
                            text, duration = wav_bytes_to_text(
                                audio["bytes"],
                                use_whisper=st.session_state.use_whisper,
                                language=lang,
                            )

                            # 폴백: webm→wav 변환
                            if not text and duration <= 0:
                                try:
                                    from pydub import AudioSegment
                                    seg = AudioSegment.from_file(io.BytesIO(audio["bytes"]), format="webm")
                                    seg = seg.set_frame_rate(16000).set_channels(1)
                                    buf = io.BytesIO()
                                    seg.export(buf, format="wav")
                                    text, duration = wav_bytes_to_text(
                                        buf.getvalue(),
                                        use_whisper=st.session_state.use_whisper,
                                        language=lang,
                                    )
                                except Exception as e:
                                    logger.warning("webm→wav 변환 실패: %s", e)

                            if not text:
                                text = "(음성 인식 실패 - 다시 녹음해 주세요)"
                            if duration <= 0:
                                duration = 1.0

                            logger.info("음성 인식 완료: %d자, %.1f초", len(text), duration)
                            feedback = get_feedback(q.text, text, duration)
                            fillers = count_filler_words(text)

                            if feedback.error_message:
                                st.error(f"피드백 오류: {_esc(feedback.error_message)}")

                            rec = AnswerRecord(
                                question=q.text,
                                answer_text=text,
                                duration_seconds=duration,
                                feedback=feedback,
                                filler_counts=fillers,
                            )

                            # 중복 답변 처리: 같은 질문 재답변 시 대체
                            if idx in st.session_state.record_map:
                                old_rec = st.session_state.record_map[idx]
                                if old_rec in st.session_state.records:
                                    st.session_state.records.remove(old_rec)
                            st.session_state.records.append(rec)
                            st.session_state.record_map[idx] = rec
                            st.session_state.answered_indices.add(idx)
                            st.session_state.skipped_indices.discard(idx)

                            # 피드백 표시
                            st.markdown("##### 📝 인식된 답변")
                            st.markdown(f'<div class="answer-text">{_esc(text)}</div>', unsafe_allow_html=True)

                            st.markdown("##### 📈 즉시 피드백")
                            m1, m2, m3 = st.columns(3)
                            with m1:
                                st.metric("점수", f"{feedback.score} / 100")
                            with m2:
                                st.metric("답변 길이", f"{duration:.1f}초")
                            with m3:
                                st.metric("습관어", f"{sum(fillers.values())}회")

                            with st.container():
                                st.markdown(
                                    '<div class="feedback-section">'
                                    f'<div class="feedback-item"><strong>논리성</strong> — {_esc(feedback.logic_comment)}</div>'
                                    f'<div class="feedback-item"><strong>구체성</strong> — {_esc(feedback.specificity_comment)}</div>'
                                    f'<div class="feedback-item"><strong>말하기 속도</strong> — {_esc(feedback.speed_comment)}</div>'
                                    f'<div class="feedback-item"><strong>톤/자신감</strong> — {_esc(feedback.tone_confidence_comment)}</div>'
                                    f'<div class="feedback-item"><strong>습관어</strong> — {_esc(feedback.filler_comment)}</div>'
                                    "</div>",
                                    unsafe_allow_html=True,
                                )
                            if feedback.improvement_tips:
                                with st.expander("💡 개선 팁"):
                                    for t in feedback.improvement_tips:
                                        st.write(f"• {_esc(str(t))}")

                            # 다음 미답변 질문으로 자동 이동
                            done = st.session_state.answered_indices | st.session_state.skipped_indices
                            next_idx = None
                            for ni in range(idx + 1, total):
                                if ni not in done:
                                    next_idx = ni
                                    break
                            if next_idx is not None:
                                st.session_state.current_index = next_idx
                            st.rerun()

    with tab2:
        st.markdown("#### 📊 세션 상세 리포트")
        records = st.session_state.records
        if not records:
            st.info("📹 **연습하기** 탭에서 질문에 답변하면 여기에 리포트가 쌓입니다.")
        else:
            company = st.session_state.company_name or "미입력"
            position = st.session_state.position or "미입력"
            started = st.session_state.session_started_at or datetime.now()
            ended = datetime.now()

            # 안정적인 session_id 사용
            sid = st.session_state.stable_session_id or str(uuid.uuid4())[:8]
            if not st.session_state.stable_session_id:
                st.session_state.stable_session_id = sid

            report = SessionReport(
                session_id=sid,
                company_name=company,
                position=position,
                started_at=started,
                ended_at=ended,
                records=records,
            )
            st.session_state.session_report = report

            r1, r2, r3, r4 = st.columns(4)
            with r1:
                st.metric("평균 점수", f"{report.average_score:.1f} / 100")
            with r2:
                st.metric("총 질문 수", f"{report.total_questions}개")
            with r3:
                st.metric("습관어 총 사용", f"{report.total_filler_count}회")
            with r4:
                st.metric("총 답변 시간", f"{report.total_duration:.0f}초")

            st.download_button(
                "📥 리포트 마크다운 다운로드",
                report.to_markdown(),
                file_name=f"interview_report_{report.session_id}.md",
                mime="text/markdown",
            )
            st.divider()
            st.markdown(report.to_markdown())

    with tab3:
        st.markdown("#### ❓ 회사/직무별 예상 질문만 생성")
        st.caption("지원 예정인 회사·직무를 입력하면 AI가 예상 질문만 생성합니다.")
        c1, c2 = st.columns(2)
        with c1:
            comp = st.text_input("회사명", key="q_company", placeholder="예: 삼성전자", max_chars=MAX_INPUT_LENGTH)
        with c2:
            pos = st.text_input("직무", key="q_position", placeholder="예: 소프트웨어 엔지니어", max_chars=MAX_INPUT_LENGTH)
        num = st.number_input("질문 개수", min_value=1, max_value=15, value=5)
        if st.button("✨ 질문 생성", key="tab3_gen"):
            safe_comp = sanitize_input(comp) if comp else ""
            safe_pos = sanitize_input(pos) if pos else ""
            if safe_comp and safe_pos:
                with st.spinner("AI가 예상 질문을 생성하는 중..."):
                    known = collect_questions_placeholder(safe_comp)
                    qs = generate_questions(
                        safe_comp, safe_pos, known,
                        count=num,
                        language=st.session_state.generation_language,
                    )
                if qs:
                    for i, q in enumerate(qs, 1):
                        lang_badge = "KR" if getattr(q, "language", "ko") == "ko" else "EN"
                        st.markdown(
                            f'<div class="question-box" style="margin:0.5rem 0">'
                            f'<strong>{i}.</strong> <span style="opacity:0.75">[{_esc(lang_badge)}]</span> [{_esc(q.category)}] {_esc(q.text)}<br>'
                            f'<small style="color:#64748b">난이도: {_esc(q.difficulty)}</small></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.error("질문 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.")
            else:
                st.error("회사명과 직무를 입력해 주세요.")

    with tab4:
        st.markdown("#### ✍️ 내 질문 작성")
        st.caption("질문을 직접 추가하고, 질문마다 한국어/영어를 선택할 수 있습니다.")

        col_left, col_right = st.columns([2, 1])
        with col_left:
            new_text = st.text_area(
                "질문 내용",
                placeholder="예: 최근에 해결한 어려운 문제를 설명해 주세요.",
                height=120,
                max_chars=MAX_QUESTION_LENGTH,
            )
        with col_right:
            lang_value_to_label = {"ko": "한국어", "en": "English"}
            lang_label_to_value = {v: k for k, v in lang_value_to_label.items()}
            default_label = lang_value_to_label.get(st.session_state.generation_language, "한국어")
            chosen_label = st.radio(
                "언어",
                options=list(lang_label_to_value.keys()),
                index=list(lang_label_to_value.keys()).index(default_label),
            )
            new_language = lang_label_to_value[chosen_label]
            new_category = st.selectbox("카테고리", options=["자기소개", "경력", "기술", "역량", "기타"], index=4)
            new_difficulty = st.selectbox("난이도", options=["쉬움", "보통", "어려움"], index=1)

        add_col, reset_col = st.columns([1, 1])
        with add_col:
            if st.button("➕ 질문 추가", use_container_width=True):
                cleaned = new_text.strip() if new_text else ""
                if not cleaned:
                    st.error("질문 내용을 입력해 주세요.")
                elif len(cleaned) > MAX_QUESTION_LENGTH:
                    st.error(f"질문은 {MAX_QUESTION_LENGTH}자 이내로 입력해 주세요.")
                else:
                    st.session_state.questions.append(
                        InterviewQuestion(
                            text=cleaned,
                            category=new_category,
                            difficulty=new_difficulty,
                            language=new_language,
                        )
                    )
                    st.success("질문을 추가했습니다.")
                    st.rerun()
        with reset_col:
            if st.button("🧹 비우기", use_container_width=True):
                st.rerun()


if __name__ == "__main__":
    main()
