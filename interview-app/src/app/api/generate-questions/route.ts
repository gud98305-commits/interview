import { NextRequest, NextResponse } from "next/server";
import { getOpenAIClient, safeExtractContent } from "@/lib/openai";
import type { InterviewQuestion } from "@/lib/types";

export async function POST(req: NextRequest) {
  try {
    const { company, position, count = 5, language = "ko" } = await req.json();

    if (!company?.trim() || !position?.trim()) {
      return NextResponse.json(
        { error: "회사명과 직무를 입력해 주세요." },
        { status: 400 }
      );
    }

    const safeCompany = company.trim().slice(0, 200);
    const safePosition = position.trim().slice(0, 200);
    const safeCount = Math.max(1, Math.min(15, count));

    const langLine =
      language === "en"
        ? "Write all questions in English."
        : "질문은 한국어로 작성해 주세요.";

    const prompt = `당신은 채용 전문가입니다. 다음 조건에 맞는 면접 예상 질문을 생성해 주세요.

【지원 회사】 ${safeCompany}
【지원 직무】 ${safePosition}

${langLine}

위 맥락을 반영해, 실제 면접에서 나올 법한 예상 질문 ${safeCount}개를 만들어 주세요.
다음 JSON 배열 형식으로만 답변하세요. 다른 설명은 붙이지 마세요.
[
  { "text": "질문 내용", "category": "카테고리", "difficulty": "쉬움|보통|어려움" }
]`;

    const client = getOpenAIClient();
    const response = await client.chat.completions.create({
      model: process.env.GPT_MODEL || "gpt-4o-mini",
      messages: [{ role: "user", content: prompt }],
      temperature: 0.7,
    });

    const raw = safeExtractContent(response);
    if (!raw) {
      return NextResponse.json({ error: "AI 응답이 비어 있습니다." }, { status: 502 });
    }

    const start = raw.indexOf("[");
    const end = raw.lastIndexOf("]") + 1;
    if (start < 0 || end <= start) {
      return NextResponse.json({ error: "AI 응답 파싱 실패" }, { status: 502 });
    }

    const data = JSON.parse(raw.slice(start, end));
    if (!Array.isArray(data)) {
      return NextResponse.json({ error: "AI 응답이 배열이 아닙니다." }, { status: 502 });
    }

    const questions: InterviewQuestion[] = data
      .filter((item: Record<string, unknown>) => item?.text)
      .map((item: Record<string, unknown>, i: number) => ({
        id: `q-${Date.now()}-${i}`,
        text: String(item.text),
        category: String(item.category || "기타"),
        difficulty: String(item.difficulty || "보통"),
        language,
      }));

    return NextResponse.json({ questions });
  } catch (err) {
    console.error("질문 생성 오류:", err);
    return NextResponse.json(
      { error: "질문 생성에 실패했습니다. 잠시 후 다시 시도해 주세요." },
      { status: 500 }
    );
  }
}
