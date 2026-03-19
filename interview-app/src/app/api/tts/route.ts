import { NextRequest, NextResponse } from "next/server";
import { getOpenAIClient } from "@/lib/openai";

export async function POST(req: NextRequest) {
  try {
    const { text } = await req.json();
    if (!text?.trim()) {
      return NextResponse.json({ error: "텍스트가 필요합니다." }, { status: 400 });
    }

    const client = getOpenAIClient();
    const response = await client.audio.speech.create({
      model: process.env.TTS_MODEL || "tts-1",
      voice: (process.env.TTS_VOICE as "nova") || "nova",
      input: text.slice(0, 4096),
    });

    const arrayBuffer = await response.arrayBuffer();
    return new NextResponse(arrayBuffer, {
      headers: {
        "Content-Type": "audio/mpeg",
        "Content-Length": String(arrayBuffer.byteLength),
      },
    });
  } catch (err) {
    console.error("TTS 오류:", err);
    return NextResponse.json({ error: "TTS 생성에 실패했습니다." }, { status: 500 });
  }
}
