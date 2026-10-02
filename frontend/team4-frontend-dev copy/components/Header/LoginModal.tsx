"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import styles from "./LoginModal.module.css";

type Props = { onClose: () => void };

// JWT payload 디코더 (base64url → JSON)
function decodeJwtPayload(token: string): any | null {
  try {
    const [, payload] = token.split(".");
    if (!payload) return null;
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const jsonStr = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    return JSON.parse(jsonStr);
  } catch {
    return null;
  }
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

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

  // 프로필 조회해서 로컬스토리지에 저장
  async function fetchAndStoreProfile(sid: string, accessToken: string) {
    try {
      const res = await fetch(
        `${API_BASE}/api/users/me/?student_id=${encodeURIComponent(sid)}`,
        { headers: { Authorization: `Bearer ${accessToken}` } }
      );
      const data = await res.json().catch(() => null);

      if (res.ok && data) {
        // 개별 키 + 통합 객체 둘 다 저장
        if (data.id != null) localStorage.setItem("userId", String(data.id));
        if (data.student_id) localStorage.setItem("studentId", data.student_id);
        if (data.full_name) localStorage.setItem("fullName", data.full_name);
        if (data.current_year != null)
          localStorage.setItem("currentYear", String(data.current_year));
        if (data.major) localStorage.setItem("major", data.major);

        localStorage.setItem("user", JSON.stringify(data)); // 통합 저장
      } else {
        console.warn("GET /users/me failed", res.status, data);
      }
    } catch (e) {
      console.warn("GET /users/me error", e);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched({ id: true, pw: true });
    setServerError(null);
    if (!canSubmit) return;

    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/users/login/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_id: studentId, password }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const msg =
          typeof data?.error === "string"
            ? data.error
            : "아이디나 비밀번호가 일치하지 않습니다. 다시 시도해주세요.";
        setServerError(msg);
        return;
      }

      // 토큰 저장
      if (data?.access) localStorage.setItem("accessToken", data.access);
      if (data?.refresh) localStorage.setItem("refreshToken", data.refresh);

      // access에서 user_id/exp 추출
      const payload =
        typeof data?.access === "string" ? decodeJwtPayload(data.access) : null;
      const inferredId =
        payload?.user_id ?? payload?.sub ?? payload?.uid ?? payload?.id ?? null;

      if (inferredId != null) localStorage.setItem("userId", String(inferredId));
      if (payload?.exp)
        localStorage.setItem("accessExp", String(payload.exp * 1000));

      // 학번은 바로 저장
      localStorage.setItem("studentId", studentId);

      // 내 정보 조회해서 이름/학과/학년/가입 id 저장
      if (data?.access) {
        await fetchAndStoreProfile(studentId, data.access);
      }

      /** ✅ 같은 탭에서도 즉시 반영되도록: 갱신 이벤트 발사 */
      window.dispatchEvent(new Event("user-updated"));

      onClose();
      router.push("/success");
    } catch (err) {
      console.error(err);
      setServerError("서버와 통신 중 문제가 발생했습니다.");
    } finally {
      setLoading(false);
    }
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
                setStudentId(e.target.value.replace(/\s+/g, "").toUpperCase())
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
