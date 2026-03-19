export interface InterviewQuestion {
  id: string;
  text: string;
  category: string;
  difficulty: string;
  language: "ko" | "en";
}

export interface FeedbackResult {
  score: number;
  logicComment: string;
  specificityComment: string;
  speedComment: string;
  toneConfidenceComment: string;
  fillerComment: string;
  improvementTips: string[];
  errorMessage?: string;
}

export interface AnswerRecord {
  questionId: string;
  questionText: string;
  answerText: string;
  durationSeconds: number;
  feedback: FeedbackResult;
  fillerCounts: Record<string, number>;
  answeredAt: string;
}

export interface SessionData {
  sessionId: string;
  company: string;
  position: string;
  language: "ko" | "en";
  questions: InterviewQuestion[];
  records: AnswerRecord[];
  startedAt: string;
}
