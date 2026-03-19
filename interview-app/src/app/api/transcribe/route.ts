import { NextRequest, NextResponse } from "next/server";
import { getOpenAIClient } from "@/lib/openai";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const audioFile = formData.get("audio") as File | null;
    const language = (formData.get("language") as string) || "ko";

    if (!audioFile) {
      return NextResponse.json({ error: "오디오 파일이 필요합니다." }, { status: 400 });
    }

    const client = getOpenAIClient();
    const transcript = await client.audio.transcriptions.create({
      model: process.env.WHISPER_MODEL || "whisper-1",
      file: audioFile,
      language: language === "en" ? "en" : "ko",
      response_format: "verbose_json",
    });

    return NextResponse.json({
      text: transcript.text || "",
      duration: transcript.duration || 0,
    });
  } catch (err) {
    console.error("음성 인식 오류:", err);
    return NextResponse.json(
      { error: "음성 인식에 실패했습니다.", text: "", duration: 0 },
      { status: 500 }
    );
  }
}
