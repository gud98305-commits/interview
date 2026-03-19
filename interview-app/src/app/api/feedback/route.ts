import { NextRequest, NextResponse } from "next/server";
import { getOpenAIClient, safeExtractContent } from "@/lib/openai";
import type { FeedbackResult } from "@/lib/types";

function clamp(v: unknown, lo = 0, hi = 100): number {
  const n = Number(v);
  if (isNaN(n)) return 50;
  return Math.max(lo, Math.min(hi, Math.round(n)));
}

export async function POST(req: NextRequest) {
  try {
    const { question, answerText, durationSeconds, fillerCounts, speechRateWpm } =
      await req.json();

    if (!question || !answerText) {
      return NextResponse.json({ error: "질문과 답변이 필요합니다." }, { status: 400 });
    }

    const fillerSummary = Object.keys(fillerCounts || {}).length
      ? `습관어 사용: ${JSON.stringify(fillerCounts)}`
      : "습관어 사용: 없음";

    const prompt = `당신은 면접 코치입니다. 다음 면접 질문과 지원자의 답변을 분석해 주세요.

【질문】
${question}

【답변(음성 인식 결과)】
${answerText}

【추가 정보】
- ${fillerSummary}
- 말하기 속도(추정): 분당 약 ${Math.round(speechRateWpm || 0)}단어 (답변 길이: ${(durationSeconds || 0).toFixed(1)}초)

다음 JSON 형식으로만 답변하세요. 다른 설명은 붙이지 마세요.
{
  "score": 0에서 100 사이 정수,
  "logic_comment": "논리성에 대한 한 줄 평가",
  "specificity_comment": "구체성(숫자, 사례, 경험)에 대한 한 줄 평가",
  "speed_comment": "말하기 속도에 대한 한 줄 평가",
  "tone_confidence_comment": "목소리 톤과 자신감에 대한 한 줄 평가",
  "filler_comment": "습관어 사용에 대한 한 줄 평가",
  "improvement_tips": ["개선 팁 1", "개선 팁 2", "개선 팁 3"]
}`;

    const client = getOpenAIClient();
    const response = await client.chat.completions.create({
      model: process.env.GPT_MODEL || "gpt-4o-mini",
      messages: [{ role: "user", content: prompt }],
      temperature: 0.3,
    });

    const raw = safeExtractContent(response);
    if (!raw) {
      const fallback: FeedbackResult = {
        score: 0,
        logicComment: "",
        specificityComment: "",
        speedComment: "",
        toneConfidenceComment: "",
        fillerComment: "",
        improvementTips: [],
        errorMessage: "AI 응답이 비어 있습니다.",
      };
      return NextResponse.json(fallback);
    }

    const start = raw.indexOf("{");
    const end = raw.lastIndexOf("}") + 1;
    let data: Record<string, unknown> = {};
    try {
      data = JSON.parse(raw.slice(start, end));
    } catch {
      const fallback: FeedbackResult = {
        score: 50,
        logicComment: "",
        specificityComment: "",
        speedComment: "",
        toneConfidenceComment: "",
        fillerComment: "",
        improvementTips: [],
        errorMessage: "AI 응답 파싱 실패",
      };
      return NextResponse.json(fallback);
    }

    const tips = Array.isArray(data.improvement_tips)
      ? data.improvement_tips.map(String)
      : typeof data.improvement_tips === "string"
        ? [data.improvement_tips]
        : [];

    const result: FeedbackResult = {
      score: clamp(data.score),
      logicComment: String(data.logic_comment || ""),
      specificityComment: String(data.specificity_comment || ""),
      speedComment: String(data.speed_comment || ""),
      toneConfidenceComment: String(data.tone_confidence_comment || ""),
      fillerComment: String(data.filler_comment || ""),
      improvementTips: tips,
    };

    return NextResponse.json(result);
  } catch (err) {
    console.error("피드백 생성 오류:", err);
    return NextResponse.json(
      {
        score: 0,
        logicComment: "",
        specificityComment: "",
        speedComment: "",
        toneConfidenceComment: "",
        fillerComment: "",
        improvementTips: [],
        errorMessage: "피드백 생성에 실패했습니다.",
      } satisfies FeedbackResult,
      { status: 500 }
    );
  }
}
