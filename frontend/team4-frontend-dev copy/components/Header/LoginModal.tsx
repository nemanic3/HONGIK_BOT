"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, errorMessage } from "../../lib/api";
import { useRouter } from "next/navigation";
import styles from "./LoginModal.module.css";

type Props = { onClose: () => void };

export default function LoginModal({ onClose }: Props) {
  const router = useRouter();

  // ESC 닫기 + 바디 스크롤 잠금
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const [studentId, setStudentId] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [touched, setTouched] = useState<{ id?: boolean; pw?: boolean }>({});
  const [loading, setLoading] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  // 유효성 (영문 1자 + 숫자 6자리)
  const errors = useMemo(() => {
    const e: { id?: string; pw?: string } = {};
    if (!/^[A-Za-z][0-9]{6}$/.test(studentId)) {
      e.id = "학번은 영문 1자 + 숫자 6자리로 입력해주세요.";
    }
    if (!password) e.pw = "비밀번호를 입력해주세요.";
    return e;
  }, [studentId, password]);

  const isInvalid = (k: "id" | "pw") =>
    Boolean((errors as any)[k] && (touched as any)[k]);
  const canSubmit = Boolean(studentId && password && !errors.id && !errors.pw);

  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    controller.current = new AbortController();
    return () => controller.current?.abort();
  }, []);
  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched({ id: true, pw: true });
    if (!canSubmit || loading) return;
    const signal = controller.current!.signal;
    setLoading(true); setServerError(null);
    try {
      await api().login(studentId, password, signal);
      if (signal.aborted) return;
      window.dispatchEvent(new Event("user-updated"));
      router.push("/success"); onClose();
    } catch (error) { if (!signal.aborted) setServerError(errorMessage(error)); }
    finally { if (!signal.aborted) setLoading(false); }
  }

  return (
    <>
      <div className={styles.dim} onClick={onClose} />

      <section role="dialog" aria-modal="true" aria-labelledby="loginTitle" className={styles.modal}>
        <button type="button" aria-label="닫기" className={styles.close} onClick={onClose}>×</button>

        <h1 id="loginTitle" className={styles.title}>로그인</h1>
        <p className={styles.sub}>올바른 정보를 입력해 주세요.</p>

        {serverError && <div className={styles.serverError}>{serverError}</div>}

        <form className={styles.form} onSubmit={onSubmit}>
          {/* 학번 */}
          <label className={styles.label}>
            학번
            <input
              className={`${styles.input} ${isInvalid("id") ? styles.invalid : ""}`}
              aria-invalid={isInvalid("id")}
              placeholder="학번을 입력해주세요."
              value={studentId}
              onChange={(e) =>
                setStudentId(e.target.value)
              }
              onBlur={() => setTouched((t) => ({ ...t, id: true }))}
            />
            {isInvalid("id") && <span className={styles.helper}>{errors.id}</span>}
          </label>

          {/* 비밀번호 */}
          <label className={styles.label}>
            비밀번호
            <div className={styles.pwWrap}>
              <input
                type={showPw ? "text" : "password"}
                className={`${styles.input} ${isInvalid("pw") ? styles.invalid : ""}`}
                aria-invalid={isInvalid("pw")}
                placeholder="비밀번호를 입력해주세요."
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onBlur={() => setTouched((t) => ({ ...t, pw: true }))}
              />
              <button
                type="button"
                aria-label={showPw ? "비밀번호 숨기기" : "비밀번호 보기"}
                className={styles.eye}
                onClick={() => setShowPw((v) => !v)}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 5C7 5 2.73 8.11 1 12c1.73 3.89 6 7 11 7s9.27-3.11 11-7c-1.73-3.89-6-7-11-7zm0 12a5 5 0 1 1 0-10 5 5 0 0 1 0 10z" fill="currentColor"/>
                </svg>
              </button>
            </div>
            {isInvalid("pw") && <span className={styles.helper}>{errors.pw}</span>}
          </label>

          <button
            type="submit"
            className={`${styles.primary} ${(!canSubmit || loading) ? styles.primaryDisabled : ""}`}
            disabled={!canSubmit || loading}
          >
            {loading ? "로그인 중..." : "로그인하기"}
          </button>
        </form>
      </section>
    </>
  );
}
