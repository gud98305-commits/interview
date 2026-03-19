import OpenAI from "openai";

let client: OpenAI | null = null;

export function getOpenAIClient(): OpenAI {
  if (!client) {
    client = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY,
      timeout: 30000,
      maxRetries: 2,
    });
  }
  return client;
}

export function safeExtractContent(
  response: OpenAI.Chat.Completions.ChatCompletion
): string | null {
  if (!response.choices?.length) return null;
  return response.choices[0].message?.content?.trim() ?? null;
}
