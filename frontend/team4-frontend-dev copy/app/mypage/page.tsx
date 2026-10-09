"use client";

import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, errorMessage, SESSION_GENERATION_KEY } from "../../lib/api";
import { getReport } from "../../lib/flows";
import { requireId, reviewHref } from "../../lib/contracts";
import type { AnalysisReport, UserProfile } from "../../lib/types";
import ProfileModal from "../../components/Header/ProfileModal";
import styles from "./MyPage.module.css";
import CreditBar from "./components/CreditBar";
import NotTakenCard from "./components/NotTakenCourses";
import TakenCard from "./components/TakenCourses";
import { useRouter } from "next/navigation";

export default function MyPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [profileOpen, setProfileOpen] = useState(false);
  const activeLoad = useRef<AbortController | null>(null);
  const useQueryTranscript = useRef(true);
  const closeProfile = useCallback(() => setProfileOpen(false), []);
  const onKeyActivate: React.KeyboardEventHandler<HTMLDivElement> = event => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); event.currentTarget.click(); }
  };
  const goUpload = () => router.push("/upload");
  const logout = () => { api().logout(); router.replace("/"); };
  useEffect(() => {
    const identity = () => JSON.stringify([localStorage.getItem(SESSION_GENERATION_KEY), localStorage.getItem('accessToken')]);
    let session = identity();
    const changed = (event: Event) => {
      if (event.type === 'storage') {
        const storageEvent = event as StorageEvent;
        if (storageEvent.storageArea && storageEvent.storageArea !== localStorage) return;
        if (storageEvent.key !== null && ![SESSION_GENERATION_KEY, 'accessToken', 'refreshToken'].includes(storageEvent.key)) return;
      }
      const next = identity();
      if (next === session) return;
      session = next;
      activeLoad.current?.abort();
      useQueryTranscript.current = false; // A URL-selected transcript belongs to the previous account.
      setProfile(null); setReport(null); setError(''); setProfileOpen(false);
      if (!localStorage.getItem('accessToken')) { setLoading(false); router.replace('/'); }
      else { setLoading(true); setRefresh(value => value + 1); }
    };
    window.addEventListener('user-updated', changed);
    window.addEventListener('storage', changed);
    return () => { window.removeEventListener('user-updated', changed); window.removeEventListener('storage', changed); };
  }, [router]);
  useEffect(() => {
    const controller = new AbortController();
    activeLoad.current = controller;
    const session = localStorage.getItem(SESSION_GENERATION_KEY);
    const isActive = () => !controller.signal.aborted && session === localStorage.getItem(SESSION_GENERATION_KEY);
    setLoading(true); setError(""); setProfile(null); setReport(null);
    (async () => {
      try {
        const query = useQueryTranscript.current ? new URLSearchParams(window.location.search).get('transcript_id') : null;
        const selected = query ?? localStorage.getItem('transcriptId') ?? undefined;
        if (selected != null) requireId(selected);
        const [user, analysis] = await Promise.all([api().me(controller.signal).then(user => { if (isActive()) setProfile(user); return user; }), getReport(api(), selected, controller.signal)]);
        if (!isActive()) return;
        setProfile(user); setReport(analysis);
        if (analysis.transcript_id != null) localStorage.setItem('transcriptId', requireId(analysis.transcript_id));
      } catch (error) {
        if (isActive()) {
          if (error instanceof ApiError && error.status === 401) router.replace('/');
          setError(error instanceof ApiError && error.status === 404 ? "성적표가 없거나 접근 권한이 없습니다. 성적표를 업로드해주세요." : errorMessage(error));
          // /me/ can still resolve when no transcript exists; it populates the editable profile independently below.
        }
      } finally { if (isActive()) setLoading(false); }
    })();
    return () => controller.abort();
  }, [refresh, router]);
  const displayName = profile?.full_name ? `${profile.full_name}님` : loading ? "불러오는 중…" : "이름 미등록";
  const displayStudentId = profile?.student_id ?? (loading ? "불러오는 중…" : "학번 미등록");
  const statusText = {
    needs_verification: "기준 출처 검증 필요 · 졸업 가능 여부를 확정할 수 없습니다.",
    pending: "계산이 완료되었으며 충족하지 못한 졸업 요건이 있습니다. 미충족 항목을 확인해주세요.",
    complete: "적용 기준의 계산이 완료되었습니다. 최종 졸업 판정은 학과에 확인해주세요.",
    needs_confirmation: "OCR 결과를 확인하고 확정 저장해주세요.",
    profile_required: "입학 연도와 공학 인증 트랙을 설정해주세요.",
    policy_unavailable: "이 프로필에 적용할 졸업 기준이 없습니다. 학과 확인이 필요합니다.",
  };

  return (
    <div className={styles.page}>
      <img src="/Frame.svg" alt="frame" width={157} height={51} className={styles.frame} />

      <div className={styles.box}>
        <p className={styles.name}>{displayName}</p>
        <p className={styles.student_id}>{displayStudentId}</p>
        <p className={styles.major}>{profile?.major ?? "학과 미등록"}</p>

        {/* 메뉴 리스트 */}
        <div className={styles.menu}>
          <div
            className={styles.menuItem2}
            role="button"
            tabIndex={0}
            onKeyDown={onKeyActivate}
            onClick={goUpload}
          >
            <Image src="/Icon_plus file.svg" alt="성적표 파일 추가" width={20} height={20} />
            <span>성적표 파일 추가하기</span>
          </div>

          <div className={styles.menuItem} aria-disabled="true" title="삭제 API가 제공되지 않아 사용할 수 없습니다.">
            <Image src="/Icon_trash.svg" alt="" width={20} height={20} />
            <span>성적표 삭제 (지원되지 않음)</span>
          </div>

          <div className={styles.menuItem2}>
            <Image src="/Icon_home.svg" alt="학과 정보" width={20} height={20} />
            <span>{profile?.major ?? "학과 정보 미등록"}</span>
          </div>

          <div className={styles.menuItem}>
            <Image src="/Icon_texted file.svg" alt="적용 기준 출처" width={20} height={20} />
            <span title={report?.policy?.source_document}>{report?.policy?.source_document ?? "기준 책자 미제공"}</span>
          </div>

          <div className={styles.menuItem2} role="button" tabIndex={0} onKeyDown={onKeyActivate} onClick={() => setProfileOpen(true)}>
            <Image src="/Icon_setting.svg" alt="설정" width={20} height={20} />
            <span>입학 연도 / 인증 트랙 설정</span>
          </div>
        </div>

        {/* 하단 */}
        <div className={styles.sbox}>
          <div className={styles.Quest}>
            <Image src="/Icon_contact.svg" alt="문의하기" width={20} height={20} className={styles.Questimg} />
            <p className={styles.quest}>문의 경로 미설정</p>
          </div>

          {/* ✅ 로그아웃 버튼 */}
          <div
            className={styles.Logout}
            role="button"
            tabIndex={0}
            onKeyDown={onKeyActivate}
            onClick={logout}
          >
            <Image src="/Icon_logout.svg" alt="로그아웃" width={20} height={20} className={styles.Logoutimg} />
            <p className={styles.logout}>로그아웃</p>
          </div>
        </div>
      </div>

      <CreditBar report={report} loading={loading} />
      <NotTakenCard report={report} loading={loading} />
      <TakenCard report={report} loading={loading} />
      <section aria-live="polite" style={{ marginLeft: "26rem", maxWidth: 940, padding: "24px 0" }}>
        {error && <p role="alert">{error}</p>}
        {report && <>
          <p>{statusText[report.status]}</p>
          {report.policy && <p>기준 {report.policy.version} · {report.policy.major} · 입학 {report.policy.admission_year} · {report.policy.accreditation_track === 'accredited' ? '공학 인증' : '비인증'} · 출처 {report.policy.source_verified ? '검증됨' : '미검증'}</p>}
          {(report.warnings ?? []).map((warning, index) => <p key={index}>{warning}</p>)}
          {report.status === 'needs_confirmation' && <button onClick={() => router.push(reviewHref(report.transcript_id))}>성적표 확인 / 수정</button>}
        </>}
        <button onClick={() => setRefresh(value => value + 1)} disabled={loading}>분석 새로고침</button>{' '}
        <button onClick={() => setProfileOpen(true)} disabled={!profile}>프로필 설정</button>
      </section>
      {profileOpen && profile && <ProfileModal profile={profile} onClose={closeProfile} onSaved={value => { setProfile(value); setRefresh(count => count + 1); }} />}
    </div>
  );
}
