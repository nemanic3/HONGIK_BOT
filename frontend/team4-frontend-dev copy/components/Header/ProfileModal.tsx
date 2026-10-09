"use client";

import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../../lib/api";
import { saveProfile } from "../../lib/flows";
import { initialMajorSelection, SUPPORTED_MAJORS } from "../../lib/contracts";
import type { UserProfile } from "../../lib/types";
import styles from "./SignUpModal.module.css";

export default function ProfileModal({ profile, onSaved, onClose }: { profile: UserProfile; onSaved: (profile: UserProfile) => void; onClose: () => void }) {
  const [year, setYear] = useState(profile.admission_year == null ? "" : String(profile.admission_year));
  const [track, setTrack] = useState(profile.accreditation_track ?? "");
  const [major, setMajor] = useState(initialMajorSelection(profile.major));
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    controller.current = new AbortController();
    const key = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", key);
    return () => { controller.current?.abort(); document.removeEventListener("keydown", key); document.body.style.overflow = previous; };
  }, [onClose]);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); if (saving) return;
    const signal = controller.current!.signal;
    try {
      setSaving(true); setError("");
      const updated = await saveProfile(api(), year, track, major, signal);
      if (!signal.aborted) { onSaved(updated); onClose(); }
    } catch (error) { if (!signal.aborted) setError(errorMessage(error)); }
    finally { if (!signal.aborted) setSaving(false); }
  }
  return <>
    <div className={styles.dim} onClick={onClose} />
    <section className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="profileTitle">
      <button className={styles.close} aria-label="닫기" onClick={onClose}>×</button>
      <h1 className={styles.title} id="profileTitle">학과/전공 · 입학 연도 / 인증 트랙 설정</h1>
      <p className={styles.sub}>학과/전공을 확인하고 직접 선택해주세요. 학부명에서 전공이나 학번에서 입학 연도를 추측하지 않습니다. 현재 기준은 컴퓨터공학 전공을 지원합니다.</p>
      {error && <p className={styles.serverError} role="alert">{error}</p>}
      <form className={styles.form} onSubmit={submit}>
        <label className={styles.label}>학과/전공<select className={styles.input} value={major} onChange={event => setMajor(event.target.value)}><option value="">학과/전공을 직접 선택해주세요</option>{SUPPORTED_MAJORS.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
        <label className={styles.label}>입학 연도<input className={styles.input} value={year} onChange={event => setYear(event.target.value)} inputMode="numeric" placeholder="예: 2024" /></label>
        <label className={styles.label}>공학 인증 트랙<select className={styles.input} value={track} onChange={event => setTrack(event.target.value as UserProfile["accreditation_track"])}><option value="">선택해주세요</option><option value="accredited">공학 인증</option><option value="non_accredited">비인증</option></select></label>
        <button className={styles.primary} disabled={saving}>{saving ? "저장 중…" : "저장"}</button>
      </form>
    </section>
  </>;
}
