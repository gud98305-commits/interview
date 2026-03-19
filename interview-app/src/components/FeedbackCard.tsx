"use client";
import type { FeedbackResult } from "@/lib/types";
import { TrendingUp, Lightbulb } from "lucide-react";
import { useState } from "react";

interface Props {
  feedback: FeedbackResult;
  answerText: string;
  duration: number;
  fillerTotal: number;
}

export default function FeedbackCard({ feedback, answerText, duration, fillerTotal }: Props) {
  const [showTips, setShowTips] = useState(false);

  const scoreColor =
    feedback.score >= 70
      ? "text-green-600"
      : feedback.score >= 40
        ? "text-yellow-600"
        : "text-red-600";

  const scoreBg =
    feedback.score >= 70
      ? "bg-green-50 border-green-200"
      : feedback.score >= 40
        ? "bg-yellow-50 border-yellow-200"
        : "bg-red-50 border-red-200";

  return (
    <div className="space-y-4">
      {/* 인식된 답변 */}
      <div>
        <h4 className="text-sm font-semibold text-green-900 mb-1">📝 인식된 답변</h4>
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-900 leading-relaxed">
          {answerText}
        </div>
      </div>

      {/* 점수 + 메트릭 */}
      <div className="grid grid-cols-3 gap-3">
        <div className={`rounded-xl border p-3 text-center ${scoreBg}`}>
          <div className={`text-2xl font-bold ${scoreColor}`}>{feedback.score}</div>
          <div className="text-xs text-gray-500 mt-1">점수 / 100</div>
        </div>
        <div className="rounded-xl border border-green-200 bg-white p-3 text-center">
          <div className="text-2xl font-bold text-green-700">{duration.toFixed(1)}</div>
          <div className="text-xs text-gray-500 mt-1">답변 (초)</div>
        </div>
        <div className="rounded-xl border border-green-200 bg-white p-3 text-center">
          <div className="text-2xl font-bold text-green-700">{fillerTotal}</div>
          <div className="text-xs text-gray-500 mt-1">습관어 (회)</div>
        </div>
      </div>

      {feedback.errorMessage && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          {feedback.errorMessage}
        </div>
      )}

      {/* 상세 피드백 */}
      <div className="bg-white rounded-xl border border-green-200 divide-y divide-green-100">
        {[
          ["논리성", feedback.logicComment],
          ["구체성", feedback.specificityComment],
          ["말하기 속도", feedback.speedComment],
          ["톤/자신감", feedback.toneConfidenceComment],
          ["습관어", feedback.fillerComment],
        ].map(
          ([label, comment]) =>
            comment && (
              <div key={label} className="px-4 py-2.5 flex gap-3 text-sm">
                <span className="font-semibold text-green-800 whitespace-nowrap">{label}</span>
                <span className="text-gray-700">{comment}</span>
              </div>
            )
        )}
      </div>

      {/* 개선 팁 */}
      {feedback.improvementTips.length > 0 && (
        <div>
          <button
            onClick={() => setShowTips(!showTips)}
            className="flex items-center gap-1 text-sm font-medium text-green-700 hover:text-green-900 transition"
          >
            <Lightbulb size={16} />
            개선 팁 {showTips ? "접기" : "보기"} ({feedback.improvementTips.length}개)
            <TrendingUp size={14} />
          </button>
          {showTips && (
            <ul className="mt-2 space-y-1 text-sm text-gray-700 bg-green-50 rounded-lg p-3">
              {feedback.improvementTips.map((tip, i) => (
                <li key={i}>• {tip}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
