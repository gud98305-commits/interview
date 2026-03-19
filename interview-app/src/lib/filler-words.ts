const FILLER_KO = /(^|\s)(어{1,3}|음{1,3}|저기|그러니까|뭐|막|어차피|아니\s?근데|약간)(?=\s|$|[,.])/gi;
const FILLER_EN = /\b(um+|uh+|er+|ah+|like|you know|actually|basically|literally)\b/gi;

export function countFillerWords(text: string): Record<string, number> {
  const counts: Record<string, number> = {};
  if (!text?.trim()) return counts;

  for (const match of text.matchAll(FILLER_KO)) {
    const word = match[2].trim().toLowerCase();
    if (word) counts[word] = (counts[word] || 0) + 1;
  }
  for (const match of text.matchAll(FILLER_EN)) {
    const word = match[1].trim().toLowerCase();
    if (word) counts[word] = (counts[word] || 0) + 1;
  }
  return counts;
}

export function estimateSpeechRate(wordCount: number, durationSeconds: number): number {
  if (durationSeconds <= 0) return 0;
  return (wordCount / durationSeconds) * 60;
}
