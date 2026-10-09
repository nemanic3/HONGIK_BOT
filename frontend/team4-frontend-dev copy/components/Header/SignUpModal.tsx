"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, errorMessage } from "../../lib/api";
import { profileSelection } from "../../lib/contracts";
import styles from "./SignUpModal.module.css";

type Props = { onClose: () => void };

type Errors = {
  name?: string;
  studentId?: string;
  grade?: string;
  college?: string;
  department?: string;
  password?: string;
  admissionYear?: string;
  track?: string;
};



export default function SignUpModal({ onClose }: Props) {
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

  const controller = useRef<AbortController | null>(null);
  useEffect(() => { controller.current = new AbortController(); return () => controller.current?.abort(); }, []);
  const [admissionYear, setAdmissionYear] = useState("");
  const [track, setTrack] = useState("");
  // 폼 상태
  const [name, setName] = useState("");
  const [studentId, setStudentId] = useState("");
  const [grade, setGrade] = useState("");
  const [college, setCollege] = useState("");
  const [department, setDepartment] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  // 유효성
  const errors: Errors = useMemo(() => {
    const e: Errors = {};
    if (name.trim().length < 2 || name.trim().length > 5) {
      e.name = "2~5자 이내의 한글로 입력해주세요.";
    }
    // 영어+숫자 6자리(요청대로 고정)
    if (!/^[A-Za-z][0-9]{6}$/.test(studentId)) {
      e.studentId = "영어+숫자 6자리의 조합으로 입력해주세요.";
    }
    if (!/^[1-4]$/.test(grade)) {
      e.grade = "숫자 1~4로 입력해주세요.";
    }
    if (!college) e.college = "소속 대학을 선택해주세요.";
    if (!department) e.department = "소속 학부를 선택해주세요.";
    if (password.length < 8) e.password = "비밀번호는 8자 이상 입력해주세요.";
    if (!/^\d{4}$/.test(admissionYear) || Number(admissionYear) < 1900 || Number(admissionYear) > 2100) e.admissionYear = "입학 연도를 네 자리로 입력해주세요.";
    if (!track) e.track = "공학 인증 여부를 선택해주세요.";
    return e;
  }, [name, studentId, grade, college, department, password, admissionYear, track]);

  const isInvalid = (k: keyof Errors) => Boolean(errors[k] && touched[k]);
  const handleBlur = (k: keyof Errors) => setTouched((t) => ({ ...t, [k]: true }));

  const allFilled =
    name && studentId && grade && college && department && password && admissionYear && track;
  const canSubmit = allFilled && Object.keys(errors).every((k) => !(errors as any)[k]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched({
      name: true,
      studentId: true,
      grade: true,
      college: true,
      department: true,
      password: true,
      admissionYear: true,
      track: true,
    });
    setServerError(null);
    if (!canSubmit || loading) return;

    const payload = {
      student_id: studentId,
      full_name: name,
      current_year: Number(grade),
      major: department,
      password,
      ...profileSelection(admissionYear, track),
    };

    const signal = controller.current!.signal;
    try {
      setLoading(true);
      await api().request('/api/users/signup/', {
        method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      }, false);
      if (signal.aborted) return;
      alert("회원가입이 완료되었습니다. 로그인해주세요.");
      onClose();
    } catch (error) { if (!signal.aborted) setServerError(errorMessage(error)); }
    finally { if (!signal.aborted) setLoading(false); }
  }

  return (
    <>
      <div className={styles.dim} onClick={onClose} />

      <section role="dialog" aria-modal="true" aria-labelledby="signupTitle" className={styles.modal}>
        <button type="button" aria-label="닫기" className={styles.close} onClick={onClose}>×</button>

        <h1 id="signupTitle" className={styles.title}>회원가입</h1>
        <p className={styles.sub}>더 빠르고 간편하게 이용하세요.</p>

        {serverError && <div className={styles.serverError}>{serverError}</div>}

        <form className={styles.form} onSubmit={onSubmit}>
          {/* 성명 */}
          <label className={styles.label}>
            성명
            <input
              className={`${styles.input} ${isInvalid("name") ? styles.invalid : ""}`}
              aria-invalid={isInvalid("name")}
              placeholder="성명을 입력해주세요."
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => handleBlur("name")}
            />
            {isInvalid("name") && <span className={styles.helper}>{errors.name}</span>}
          </label>

          {/* 학번/학년 */}
          <div className={styles.row2}>
            <label className={styles.label}>
              학번
              <input
                className={`${styles.input} ${isInvalid("studentId") ? styles.invalid : ""}`}
                aria-invalid={isInvalid("studentId")}
                placeholder="학번을 입력해주세요."
                value={studentId}
                onChange={(e) =>
                  setStudentId(e.target.value)
                }
                onBlur={() => handleBlur("studentId")}
                autoCapitalize="characters"
              />
              {isInvalid("studentId") && (
                <span className={styles.helper}>{errors.studentId}</span>
              )}
            </label>

            <label className={styles.label}>
              학년
              <input
                className={`${styles.input} ${isInvalid("grade") ? styles.invalid : ""}`}
                aria-invalid={isInvalid("grade")}
                placeholder="숫자 1~4"
                value={grade}
                onChange={(e) => setGrade(e.target.value.replace(/\D+/g, ""))}
                onBlur={() => handleBlur("grade")}
                inputMode="numeric"
              />
              {isInvalid("grade") && (
                <span className={styles.helper}>{errors.grade}</span>
              )}
            </label>
          </div>

          {/* 소속 */}
          <div className={styles.row2}>
            <label className={styles.label}>
              소속 대학
              <div className={styles.selectWrap}>
                <select
                  className={`${styles.input} ${styles.select} ${isInvalid("college") ? styles.invalid : ""}`}
                  aria-invalid={isInvalid("college")}
                  value={college}
                  onChange={(e) => setCollege(e.target.value)}
                  onBlur={() => handleBlur("college")}
                >
                  <option value="">소속 대학을 선택해주세요.</option>
                  <option value="공과대학">공과대학</option>
                  <option value="미술대학">미술대학</option>
                </select>
              </div>
              {isInvalid("college") && (
                <span className={styles.helper}>{errors.college}</span>
              )}
            </label>

            <label className={styles.label}>
              소속 학부/학과
              <div className={styles.selectWrap}>
                <select
                  className={`${styles.input} ${styles.select} ${isInvalid("department") ? styles.invalid : ""}`}
                  aria-invalid={isInvalid("department")}
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  onBlur={() => handleBlur("department")}
                >
                  <option value="">소속 학부를 선택해주세요.</option>
                  <option value="컴퓨터공학과">컴퓨터공학과</option>
                </select>
              </div>
              {isInvalid("department") && (
                <span className={styles.helper}>{errors.department}</span>
              )}
            </label>
          </div>

          <div className={styles.row2}>
            <label className={styles.label}>입학 연도
              <input className={styles.input} value={admissionYear} onChange={e => setAdmissionYear(e.target.value)} inputMode="numeric" placeholder="예: 2024" onBlur={() => handleBlur('admissionYear')} />
              {isInvalid('admissionYear') && <span className={styles.helper}>{errors.admissionYear}</span>}
            </label>
            <label className={styles.label}>공학 인증 트랙
              <select className={styles.input} value={track} onChange={e => setTrack(e.target.value)} onBlur={() => handleBlur('track')}>
                <option value="">선택해주세요</option><option value="accredited">공학 인증</option><option value="non_accredited">비인증</option>
              </select>
              {isInvalid('track') && <span className={styles.helper}>{errors.track}</span>}
            </label>
          </div>
          {/* 비밀번호 */}
          <label className={styles.label}>
            비밀번호
            <input
              type="password"
              className={`${styles.input} ${isInvalid("password") ? styles.invalid : ""}`}
              aria-invalid={isInvalid("password")}
              placeholder="8자 이상 입력해주세요."
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onBlur={() => handleBlur("password")}
            />
            {isInvalid("password") && (
              <span className={styles.helper}>{errors.password}</span>
            )}
          </label>

          <button
            type="submit"
            className={`${styles.primary} ${(!canSubmit || loading) ? styles.primaryDisabled : ""}`}
            disabled={!canSubmit || loading}
          >
            {loading ? "가입 중..." : "다음"}
          </button>
        </form>
      </section>
    </>
  );
}
