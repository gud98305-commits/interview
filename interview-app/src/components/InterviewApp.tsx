"use client";
import { useState, useCallback, useRef } from "react";
import type { InterviewQuestion, AnswerRecord, FeedbackResult } from "@/lib/types";
import { countFillerWords, estimateSpeechRate } from "@/lib/filler-words";
import CameraPanel from "./CameraPanel";
import AudioRecorder from "./AudioRecorder";
import FeedbackCard from "./FeedbackCard";
import {
  ChevronLeft, ChevronRight, SkipForward, Volume2,
  Sparkles, RotateCcw, Save, FileDown, Loader2,
} from "lucide-react";

type Tab = "practice" | "report" | "generate" | "custom";

export default function InterviewApp() {
  // ── state ──
  const [tab, setTab] = useState<Tab>("practice");
  const [company, setCompany] = useState("");
  const [position, setPosition] = useState("");
  const [language, setLanguage] = useState<"ko" | "en">("ko");
  const [questions, setQuestions] = useState<InterviewQuestion[]>([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [records, setRecords] = useState<Map<string, AnswerRecord>>(new Map());
  const [isProcessing, setIsProcessing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [latestFeedback, setLatestFeedback] = useState<{ questionId: string; fb: FeedbackResult; text: string; dur: number; fillers: number } | null>(null);
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // ── 질문 생성 ──
  const generateQuestions = useCallback(async (comp: string, pos: string, count = 5) => {
    if (!comp.trim() || !pos.trim()) return;
    setIsGenerating(true);
    try {
      const res = await fetch("/api/generate-questions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company: comp, position: pos, count, language }),
      });
      const data = await res.json();
      if (data.questions?.length) {
        setQuestions(data.questions);
        setCurrentIdx(0);
        setRecords(new Map());
        setLatestFeedback(null);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsGenerating(false);
    }
  }, [language]);

  // ── TTS ──
  const playTTS = useCallback(async (text: string) => {
    setTtsPlaying(true);
    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error();
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      if (audioRef.current) {
        audioRef.current.src = url;
        audioRef.current.play();
        audioRef.current.onended = () => { setTtsPlaying(false); URL.revokeObjectURL(url); };
      }
    } catch { setTtsPlaying(false); }
  }, []);

  // ── 녹음 완료 → 음성 인식 → 피드백 ──
  const handleRecordingComplete = useCallback(async (blob: Blob, dur: number) => {
    if (!questions[currentIdx]) return;
    const q = questions[currentIdx];
    setIsProcessing(true);
    setLatestFeedback(null);

    try {
      // 1) Whisper 음성 인식
      const formData = new FormData();
      formData.append("audio", blob, "audio.webm");
      formData.append("language", q.language);
      const sttRes = await fetch("/api/transcribe", { method: "POST", body: formData });
      const sttData = await sttRes.json();
      const text = sttData.text || "(음성 인식 실패)";
      const duration = sttData.duration || dur;

      // 2) 습관어 분석
      const fillers = countFillerWords(text);
      const wordCount = text.split(/\s+/).filter(Boolean).length;
      const speechRate = estimateSpeechRate(wordCount, duration);

      // 3) GPT 피드백
      const fbRes = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q.text,
          answerText: text,
          durationSeconds: duration,
          fillerCounts: fillers,
          speechRateWpm: speechRate,
        }),
      });
      const feedback: FeedbackResult = await fbRes.json();

      // 4) 저장
      const record: AnswerRecord = {
        questionId: q.id,
        questionText: q.text,
        answerText: text,
        durationSeconds: duration,
        feedback,
        fillerCounts: fillers,
        answeredAt: new Date().toISOString(),
      };
      setRecords((prev) => new Map(prev).set(q.id, record));
      setLatestFeedback({
        questionId: q.id,
        fb: feedback,
        text,
        dur: duration,
        fillers: Object.values(fillers).reduce((a, b) => a + b, 0),
      });
    } catch (e) {
      console.error("처리 오류:", e);
    } finally {
      setIsProcessing(false);
    }
  }, [questions, currentIdx]);

  // ── 네비게이션 ──
  const goTo = (idx: number) => {
    setCurrentIdx(Math.max(0, Math.min(questions.length - 1, idx)));
    setLatestFeedback(null);
  };

  const currentQ = questions[currentIdx];
  const currentRecord = currentQ ? records.get(currentQ.id) : undefined;

  // ── 리포트 마크다운 ──
  const reportMarkdown = () => {
    const recs = Array.from(records.values());
    if (!recs.length) return "";
    const avg = recs.reduce((s, r) => s + r.feedback.score, 0) / recs.length;
    let md = `# 면접 연습 리포트\n\n`;
    md += `- **회사/직무**: ${company} / ${position}\n`;
    md += `- **총 질문 수**: ${recs.length}\n`;
    md += `- **평균 점수**: ${avg.toFixed(1)} / 100\n\n---\n\n`;
    recs.forEach((r, i) => {
      md += `## Q${i + 1}. ${r.questionText}\n\n`;
      md += `**답변**: ${r.answerText}\n\n`;
      md += `**점수**: ${r.feedback.score} / 100 | **시간**: ${r.durationSeconds.toFixed(1)}초\n\n`;
      md += `| 항목 | 피드백 |\n|------|--------|\n`;
      md += `| 논리성 | ${r.feedback.logicComment} |\n`;
      md += `| 구체성 | ${r.feedback.specificityComment} |\n`;
      md += `| 말하기 속도 | ${r.feedback.speedComment} |\n`;
      md += `| 톤/자신감 | ${r.feedback.toneConfidenceComment} |\n`;
      md += `| 습관어 | ${r.feedback.fillerComment} |\n\n`;
      if (r.feedback.improvementTips.length) {
        md += `**개선 팁**:\n`;
        r.feedback.improvementTips.forEach((t) => (md += `- ${t}\n`));
        md += "\n";
      }
      md += "---\n\n";
    });
    return md;
  };

  // ── 커스텀 질문 상태 ──
  const [customText, setCustomText] = useState("");
  const [customCategory, setCustomCategory] = useState("기타");
  const [customDifficulty, setCustomDifficulty] = useState("보통");

  // ── 질문만 생성 상태 ──
  const [genCompany, setGenCompany] = useState("");
  const [genPosition, setGenPosition] = useState("");
  const [genCount, setGenCount] = useState(5);
  const [genQuestions, setGenQuestions] = useState<InterviewQuestion[]>([]);
  const [genLoading, setGenLoading] = useState(false);

  return (
    <div className="min-h-screen bg-gradient-to-b from-green-50 via-emerald-50 to-green-50">
      <audio ref={audioRef} className="hidden" />

      {/* 헤더 */}
      <header className="border-b-2 border-green-200 bg-white/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <h1 className="text-2xl font-bold text-green-900">🎤 AI 스마트 면접관</h1>
          <p className="text-sm text-green-700">실시간 카메라·마이크 면접 연습 → GPT 피드백 · 점수 · 리포트</p>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-4 flex gap-4">
        {/* ── 사이드바 ── */}
        <aside className="w-72 shrink-0 space-y-4">
          <div className="bg-white/90 rounded-2xl border border-green-200 p-4 shadow-sm space-y-3">
            <h3 className="font-bold text-green-900">🎯 맞춤형 질문</h3>
            <input
              placeholder="회사명 (예: 카카오)"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              maxLength={200}
              className="w-full px-3 py-2 border border-green-200 rounded-lg text-sm focus:ring-2 focus:ring-green-400 outline-none"
            />
            <input
              placeholder="직무 (예: 백엔드 개발자)"
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              maxLength={200}
              className="w-full px-3 py-2 border border-green-200 rounded-lg text-sm focus:ring-2 focus:ring-green-400 outline-none"
            />
            <div className="flex gap-2">
              {(["ko", "en"] as const).map((l) => (
                <button
                  key={l}
                  onClick={() => setLanguage(l)}
                  className={`flex-1 py-1.5 rounded-lg text-sm font-medium transition ${language === l ? "bg-green-500 text-white" : "bg-green-50 text-green-700 hover:bg-green-100"}`}
                >
                  {l === "ko" ? "한국어" : "English"}
                </button>
              ))}
            </div>
            <button
              onClick={() => generateQuestions(company, position)}
              disabled={isGenerating || !company.trim() || !position.trim()}
              className="w-full py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium text-sm transition disabled:opacity-50 flex items-center justify-center gap-1"
            >
              {isGenerating ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              {isGenerating ? "생성 중..." : "예상 질문 생성"}
            </button>
          </div>

          {/* 질문 목록 */}
          {questions.length > 0 && (
            <div className="bg-white/90 rounded-2xl border border-green-200 p-4 shadow-sm">
              <h3 className="font-bold text-green-900 mb-2">📋 질문 목록</h3>
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {questions.map((q, i) => {
                  const answered = records.has(q.id);
                  const isCurrent = i === currentIdx;
                  return (
                    <button
                      key={q.id}
                      onClick={() => { goTo(i); setTab("practice"); }}
                      className={`w-full text-left px-3 py-2 rounded-lg text-xs transition ${
                        isCurrent
                          ? "bg-green-100 text-green-800 border-l-3 border-green-500 font-semibold"
                          : answered
                            ? "text-green-600 hover:bg-green-50"
                            : "text-gray-600 hover:bg-gray-50"
                      }`}
                    >
                      <span className="font-bold">Q{i + 1}.</span>{" "}
                      {q.text.length > 40 ? q.text.slice(0, 40) + "…" : q.text}
                      {answered && " ✓"}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* 세션 관리 */}
          <div className="bg-white/90 rounded-2xl border border-green-200 p-4 shadow-sm space-y-2">
            <h3 className="font-bold text-green-900">💾 세션 관리</h3>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  const data = JSON.stringify({ company, position, questions, records: Array.from(records.entries()), savedAt: new Date().toISOString() });
                  localStorage.setItem("interview-session", data);
                  alert("세션이 저장되었습니다.");
                }}
                className="flex-1 py-1.5 bg-green-100 text-green-700 rounded-lg text-xs font-medium hover:bg-green-200 flex items-center justify-center gap-1"
              >
                <Save size={14} /> 저장
              </button>
              <button
                onClick={() => {
                  setQuestions([]);
                  setRecords(new Map());
                  setCurrentIdx(0);
                  setLatestFeedback(null);
                }}
                className="flex-1 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-xs font-medium hover:bg-gray-200 flex items-center justify-center gap-1"
              >
                <RotateCcw size={14} /> 초기화
              </button>
            </div>
          </div>
        </aside>

        {/* ── 메인 ── */}
        <main className="flex-1 min-w-0">
          {/* 탭 */}
          <div className="flex gap-2 mb-4">
            {([
              ["practice", "📹 연습하기"],
              ["report", "📊 리포트"],
              ["generate", "❓ 질문 생성"],
              ["custom", "✍️ 질문 작성"],
            ] as [Tab, string][]).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                  tab === key
                    ? "bg-green-100 text-green-800"
                    : "text-gray-500 hover:bg-gray-100"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* ═══ 연습하기 탭 ═══ */}
          {tab === "practice" && (
            <div className="grid grid-cols-2 gap-4">
              <CameraPanel />

              <div className="bg-white/90 rounded-2xl border border-green-200 p-4 shadow-sm space-y-4">
                <h3 className="text-lg font-bold text-green-900">🎙️ 답변 연습</h3>

                {!questions.length ? (
                  <p className="text-sm text-gray-500 py-8 text-center">
                    👈 사이드바에서 회사명·직무를 입력하고 질문을 생성해 주세요.
                  </p>
                ) : (
                  <>
                    {/* 네비게이션 */}
                    <div className="flex items-center gap-2">
                      <button onClick={() => goTo(currentIdx - 1)} disabled={currentIdx === 0}
                        className="p-2 rounded-lg hover:bg-green-50 disabled:opacity-30 transition">
                        <ChevronLeft size={18} />
                      </button>
                      <span className="flex-1 text-center text-sm font-semibold text-green-800">
                        Q{currentIdx + 1} / {questions.length}
                      </span>
                      <button onClick={() => goTo(currentIdx + 1)} disabled={currentIdx >= questions.length - 1}
                        className="p-2 rounded-lg hover:bg-green-50 disabled:opacity-30 transition">
                        <ChevronRight size={18} />
                      </button>
                      <button
                        onClick={() => {
                          const next = questions.findIndex((q, i) => i > currentIdx && !records.has(q.id));
                          if (next >= 0) goTo(next);
                        }}
                        className="p-2 rounded-lg hover:bg-green-50 transition text-gray-500"
                        title="건너뛰기"
                      >
                        <SkipForward size={18} />
                      </button>
                    </div>

                    {/* 질문 표시 */}
                    {currentQ && (
                      <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl p-4 border-l-4 border-green-500">
                        <p className="font-semibold text-green-900">
                          Q{currentIdx + 1}. {currentQ.text}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          {currentQ.language === "ko" ? "한국어" : "English"} · {currentQ.category} · {currentQ.difficulty}
                          {currentRecord && " · ✓ 답변 완료"}
                        </p>
                        <button
                          onClick={() => playTTS(currentQ.text)}
                          disabled={ttsPlaying}
                          className="mt-2 flex items-center gap-1 text-xs text-green-600 hover:text-green-800 transition"
                        >
                          <Volume2 size={14} />
                          {ttsPlaying ? "재생 중..." : "질문 듣기"}
                        </button>
                      </div>
                    )}

                    {/* 이전 답변 표시 */}
                    {currentRecord && !latestFeedback && (
                      <div className="bg-green-50 rounded-lg p-3 text-sm text-green-800">
                        <strong>이전 답변 (점수: {currentRecord.feedback.score})</strong>
                        <p className="mt-1 text-gray-600">{currentRecord.answerText.slice(0, 100)}...</p>
                        <p className="mt-1 text-xs text-gray-500">다시 녹음하면 이전 답변을 대체합니다.</p>
                      </div>
                    )}

                    {/* 녹음 버튼 */}
                    <AudioRecorder
                      onRecordingComplete={handleRecordingComplete}
                      disabled={isProcessing}
                    />

                    {/* 최신 피드백 */}
                    {latestFeedback && latestFeedback.questionId === currentQ?.id && (
                      <FeedbackCard
                        feedback={latestFeedback.fb}
                        answerText={latestFeedback.text}
                        duration={latestFeedback.dur}
                        fillerTotal={latestFeedback.fillers}
                      />
                    )}
                  </>
                )}
              </div>
            </div>
          )}

          {/* ═══ 리포트 탭 ═══ */}
          {tab === "report" && (
            <div className="bg-white/90 rounded-2xl border border-green-200 p-6 shadow-sm">
              <h3 className="text-lg font-bold text-green-900 mb-4">📊 세션 리포트</h3>
              {records.size === 0 ? (
                <p className="text-sm text-gray-500 py-8 text-center">
                  연습하기 탭에서 질문에 답변하면 리포트가 생성됩니다.
                </p>
              ) : (
                <>
                  {/* 요약 메트릭 */}
                  {(() => {
                    const recs = Array.from(records.values());
                    const avg = recs.reduce((s, r) => s + r.feedback.score, 0) / recs.length;
                    const totalFillers = recs.reduce((s, r) => s + Object.values(r.fillerCounts).reduce((a, b) => a + b, 0), 0);
                    const totalDur = recs.reduce((s, r) => s + r.durationSeconds, 0);
                    return (
                      <div className="grid grid-cols-4 gap-3 mb-6">
                        <div className="bg-green-50 rounded-xl p-4 text-center border border-green-200">
                          <div className="text-3xl font-bold text-green-700">{avg.toFixed(1)}</div>
                          <div className="text-xs text-gray-500 mt-1">평균 점수</div>
                        </div>
                        <div className="bg-white rounded-xl p-4 text-center border border-green-200">
                          <div className="text-3xl font-bold text-green-700">{recs.length}</div>
                          <div className="text-xs text-gray-500 mt-1">답변 수</div>
                        </div>
                        <div className="bg-white rounded-xl p-4 text-center border border-green-200">
                          <div className="text-3xl font-bold text-green-700">{totalFillers}</div>
                          <div className="text-xs text-gray-500 mt-1">습관어 총계</div>
                        </div>
                        <div className="bg-white rounded-xl p-4 text-center border border-green-200">
                          <div className="text-3xl font-bold text-green-700">{totalDur.toFixed(0)}s</div>
                          <div className="text-xs text-gray-500 mt-1">총 답변 시간</div>
                        </div>
                      </div>
                    );
                  })()}

                  <button
                    onClick={() => {
                      const md = reportMarkdown();
                      const blob = new Blob([md], { type: "text/markdown" });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `interview-report-${Date.now()}.md`;
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                    className="mb-4 flex items-center gap-1 px-4 py-2 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600 transition"
                  >
                    <FileDown size={16} /> 리포트 다운로드
                  </button>

                  {/* 개별 기록 */}
                  <div className="space-y-4">
                    {Array.from(records.values()).map((r, i) => (
                      <div key={r.questionId} className="border border-green-200 rounded-xl p-4">
                        <h4 className="font-semibold text-green-900 mb-2">Q{i + 1}. {r.questionText}</h4>
                        <FeedbackCard
                          feedback={r.feedback}
                          answerText={r.answerText}
                          duration={r.durationSeconds}
                          fillerTotal={Object.values(r.fillerCounts).reduce((a, b) => a + b, 0)}
                        />
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {/* ═══ 질문만 생성 탭 ═══ */}
          {tab === "generate" && (
            <div className="bg-white/90 rounded-2xl border border-green-200 p-6 shadow-sm">
              <h3 className="text-lg font-bold text-green-900 mb-4">❓ 예상 질문만 생성</h3>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <input placeholder="회사명" value={genCompany} onChange={(e) => setGenCompany(e.target.value)} maxLength={200}
                  className="px-3 py-2 border border-green-200 rounded-lg text-sm focus:ring-2 focus:ring-green-400 outline-none" />
                <input placeholder="직무" value={genPosition} onChange={(e) => setGenPosition(e.target.value)} maxLength={200}
                  className="px-3 py-2 border border-green-200 rounded-lg text-sm focus:ring-2 focus:ring-green-400 outline-none" />
              </div>
              <div className="flex gap-3 items-center mb-4">
                <label className="text-sm text-gray-600">질문 개수:</label>
                <input type="number" min={1} max={15} value={genCount} onChange={(e) => setGenCount(Number(e.target.value))}
                  className="w-20 px-2 py-1 border border-green-200 rounded-lg text-sm" />
                <button
                  onClick={async () => {
                    setGenLoading(true);
                    try {
                      const res = await fetch("/api/generate-questions", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ company: genCompany, position: genPosition, count: genCount, language }),
                      });
                      const data = await res.json();
                      setGenQuestions(data.questions || []);
                    } catch { /* */ } finally { setGenLoading(false); }
                  }}
                  disabled={genLoading || !genCompany.trim() || !genPosition.trim()}
                  className="px-4 py-2 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600 disabled:opacity-50 flex items-center gap-1"
                >
                  {genLoading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                  생성
                </button>
              </div>
              {genQuestions.length > 0 && (
                <div className="space-y-2">
                  {genQuestions.map((q, i) => (
                    <div key={q.id} className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl p-3 border-l-4 border-green-500">
                      <p className="text-sm font-semibold text-green-900">{i + 1}. [{q.category}] {q.text}</p>
                      <p className="text-xs text-gray-500 mt-1">난이도: {q.difficulty}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ═══ 질문 작성 탭 ═══ */}
          {tab === "custom" && (
            <div className="bg-white/90 rounded-2xl border border-green-200 p-6 shadow-sm">
              <h3 className="text-lg font-bold text-green-900 mb-4">✍️ 내 질문 작성</h3>
              <textarea
                value={customText}
                onChange={(e) => setCustomText(e.target.value)}
                placeholder="질문 내용을 입력하세요..."
                maxLength={500}
                rows={4}
                className="w-full px-3 py-2 border border-green-200 rounded-lg text-sm focus:ring-2 focus:ring-green-400 outline-none resize-none mb-3"
              />
              <div className="flex gap-3 items-center mb-4">
                <select value={customCategory} onChange={(e) => setCustomCategory(e.target.value)}
                  className="px-3 py-2 border border-green-200 rounded-lg text-sm">
                  {["자기소개", "경력", "기술", "역량", "기타"].map((c) => <option key={c}>{c}</option>)}
                </select>
                <select value={customDifficulty} onChange={(e) => setCustomDifficulty(e.target.value)}
                  className="px-3 py-2 border border-green-200 rounded-lg text-sm">
                  {["쉬움", "보통", "어려움"].map((d) => <option key={d}>{d}</option>)}
                </select>
                <button
                  onClick={() => {
                    if (!customText.trim()) return;
                    const q: InterviewQuestion = {
                      id: `custom-${Date.now()}`,
                      text: customText.trim(),
                      category: customCategory,
                      difficulty: customDifficulty,
                      language,
                    };
                    setQuestions((prev) => [...prev, q]);
                    setCustomText("");
                  }}
                  className="px-4 py-2 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600"
                >
                  ➕ 추가
                </button>
              </div>
              {questions.filter((q) => q.id.startsWith("custom-")).length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs text-gray-500">추가된 질문:</p>
                  {questions.filter((q) => q.id.startsWith("custom-")).map((q, i) => (
                    <div key={q.id} className="text-sm text-green-800 bg-green-50 rounded-lg px-3 py-2">
                      {i + 1}. {q.text}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
