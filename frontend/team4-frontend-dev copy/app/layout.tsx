// app/layout.tsx
import type { Metadata } from "next";
import "./global.css";

export const metadata: Metadata = {
  title: "홍익졸업봇",
  description: "성적표 한 장으로 졸업까지 한 눈에!",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      {/* 최소 여백만 리셋 */}
      <body style={{ margin: 0 }}>{children}</body>
    </html>
  );
}
