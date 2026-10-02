"use client";

import { useState, useEffect, useMemo } from "react";
import styles from "./page.module.css";
import SignUpModal from "../components/Header/SignUpModal";
import LoginModal from "../components/Header/LoginModal";

export default function Home() {
  // (있던 자막 순환 로직 유지)
  const messages = useMemo(
    () => [
      "성적표 한 장으로 졸업까지 한 눈에!",
      "OCR로 자동 분석, 부족학점 바로 확인!",
      "홍익대 전공/교양 기준에 맞춘 맞춤 진단",
    ],
    []
  );
  const [subtitleIdx, setSubtitleIdx] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setSubtitleIdx(p => (p + 1) % messages.length), 3000);
    return () => clearInterval(id);
  }, [messages.length]);

  const [open, setOpen] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);

  return (
    <main className={styles.main}>
      <img src="/background.svg" alt="배경" className={styles.background} />

      <div className={styles.centerContent}>
        <p className={styles.subtitle}>
          <span key={subtitleIdx} className={styles.fadeIn}>
            {messages[subtitleIdx]}
          </span>
        </p>

        <img src="/Frame.svg" alt="홍익졸업봇" className={styles.titleImage} />

        <div className={styles.buttonRow}>
          <button type="button" className={styles.button} onClick={() => setOpen(true)}>
            회원가입
          </button>
          <button type="button" className={styles.button} onClick={() => setLoginOpen(true)}>
            로그인
          </button>
        </div>
      </div>
      <img src="/bottom.gif" alt="졸업봇 캐릭터" className={styles.character} />

      {open && <SignUpModal onClose={() => setOpen(false)} />}
      {loginOpen && <LoginModal onClose={() => setLoginOpen(false)} />}
    </main>
  );
}
