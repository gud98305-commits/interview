import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";

const geist = Geist({
  variable: "--font-geist",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AI 스마트 면접관",
  description: "실시간 카메라·마이크 면접 연습 → GPT 피드백 · 점수 · 리포트",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className={`${geist.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col font-[family-name:var(--font-geist)]">
        {children}
      </body>
    </html>
  );
}
