"""면접 연습 점수 및 상세 리포트 생성."""
from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import datetime

from ai_feedback import FeedbackResult


def _esc(text: str) -> str:
    """마크다운/HTML 안전 이스케이프."""
    return html.escape(str(text)) if text else ""


@dataclass
class AnswerRecord:
    """한 질문에 대한 답변 기록."""
    question: str
    answer_text: str
    duration_seconds: float
    feedback: FeedbackResult
    filler_counts: dict[str, int]


@dataclass
class SessionReport:
    """한 연습 세션 전체 리포트."""
    session_id: str
    company_name: str
    position: str
    started_at: datetime
    ended_at: datetime
    records: list[AnswerRecord] = field(default_factory=list)

    @property
    def total_questions(self) -> int:
        return len(self.records)

    @property
    def average_score(self) -> float:
        if not self.records:
            return 0.0
        return sum(r.feedback.score for r in self.records) / len(self.records)

    @property
    def total_filler_count(self) -> int:
        return sum(
            sum(r.filler_counts.values()) for r in self.records
        )

    @property
    def total_duration(self) -> float:
        return sum(r.duration_seconds for r in self.records)

    @property
    def score_trend(self) -> list[int]:
        """각 질문별 점수 리스트 (추세 분석용)."""
        return [r.feedback.score for r in self.records]

    @property
    def best_record(self) -> AnswerRecord | None:
        """최고 점수 답변."""
        if not self.records:
            return None
        return max(self.records, key=lambda r: r.feedback.score)

    @property
    def worst_record(self) -> AnswerRecord | None:
        """최저 점수 답변."""
        if not self.records:
            return None
        return min(self.records, key=lambda r: r.feedback.score)

    def to_markdown(self) -> str:
        """상세 리포트를 마크다운 문자열로 반환."""
        lines = [
            "# 면접 연습 상세 리포트",
            "",
            f"- **세션 ID**: {_esc(self.session_id)}",
            f"- **지원 회사/직무**: {_esc(self.company_name)} / {_esc(self.position)}",
            f"- **연습 일시**: {self.started_at.strftime('%Y-%m-%d %H:%M')} ~ {self.ended_at.strftime('%H:%M')}",
            f"- **총 질문 수**: {self.total_questions}",
            f"- **평균 점수**: {self.average_score:.1f} / 100",
            f"- **총 답변 시간**: {self.total_duration:.0f}초",
            f"- **습관어 총 사용**: {self.total_filler_count}회",
            "",
        ]

        # 점수 추세
        trend = self.score_trend
        if len(trend) >= 2:
            diff = trend[-1] - trend[0]
            direction = "상승" if diff > 0 else ("하락" if diff < 0 else "유지")
            lines.append(f"- **점수 추세**: {direction} ({trend[0]}점 → {trend[-1]}점)")
            lines.append("")

        # 최고/최저 점수 요약
        best = self.best_record
        worst = self.worst_record
        if best and worst and self.total_questions > 1:
            lines.append(f"- **최고 점수**: {best.feedback.score}점 — {_esc(best.question[:40])}")
            lines.append(f"- **최저 점수**: {worst.feedback.score}점 — {_esc(worst.question[:40])}")
            lines.append("")

        lines.extend(["---", ""])

        for i, rec in enumerate(self.records, 1):
            lines.extend([
                f"## Q{i}. {_esc(rec.question)}",
                "",
                "**답변**: " + (_esc(rec.answer_text) or "(음성 인식 없음)"),
                "",
                f"**점수**: {rec.feedback.score} / 100 | **답변 시간**: {rec.duration_seconds:.1f}초",
                "",
                "| 항목 | 피드백 |",
                "|------|--------|",
                f"| 논리성 | {_esc(rec.feedback.logic_comment)} |",
                f"| 구체성 | {_esc(rec.feedback.specificity_comment)} |",
                f"| 말하기 속도 | {_esc(rec.feedback.speed_comment)} |",
                f"| 톤/자신감 | {_esc(rec.feedback.tone_confidence_comment)} |",
                f"| 습관어 | {_esc(rec.feedback.filler_comment)} |",
                "",
            ])
            if rec.filler_counts:
                filler_str = ", ".join(f"{_esc(k)}: {v}회" for k, v in rec.filler_counts.items())
                lines.append(f"**습관어 상세**: {filler_str}")
                lines.append("")
            if rec.feedback.improvement_tips:
                lines.append("**개선 팁**:")
                for tip in rec.feedback.improvement_tips:
                    lines.append(f"- {_esc(str(tip))}")
                lines.append("")
            lines.append("---")
            lines.append("")
        return "\n".join(lines)

    def to_summary_dict(self) -> dict[str, str | int | float]:
        """요약 정보만 딕셔너리로."""
        return {
            "session_id": self.session_id,
            "company_name": self.company_name,
            "position": self.position,
            "total_questions": self.total_questions,
            "average_score": round(self.average_score, 1),
            "total_filler_count": self.total_filler_count,
            "total_duration": round(self.total_duration, 1),
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
        }
