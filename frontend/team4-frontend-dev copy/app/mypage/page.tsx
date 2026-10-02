"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import styles from "./MyPage.module.css";
import CreditBar from "./components/CreditBar";
import NotTakenCard from "./components/NotTakenCourses";
import TakenCard from "./components/TakenCourses";
import { useRouter } from "next/navigation";

function readNameAndSidFromStorage() {
  if (typeof window === "undefined")
    return { name: null as string | null, sid: null as string | null };

  const fullNameNew = localStorage.getItem("fullName");
  const studentIdNew = localStorage.getItem("studentId");

  const fullNameLegacy = localStorage.getItem("fullname");
  const studentIdLegacy = localStorage.getItem("StudentId");

  const name = (fullNameNew ?? fullNameLegacy) || null;
  const sid = (studentIdNew ?? studentIdLegacy) || null;

  return {
    name: name && name.trim() ? name.trim() : null,
    sid: sid && sid.trim() ? sid.trim().toUpperCase() : null,
  };
}

export default function MyPage() {
  const router = useRouter();

  const [{ name, sid }, setInfo] = useState<{ name: string | null; sid: string | null }>(() =>
    readNameAndSidFromStorage()
  );
  const [loading, setLoading] = useState(false);

  const onKeyActivate: React.KeyboardEventHandler<HTMLDivElement> = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      (e.currentTarget as HTMLDivElement).click();
    }
  };

  // ✅ 업로드 페이지로 이동
  const goUpload = () => {
    router.push("/upload");
  };

  // ✅ 로그아웃: 스토리지 비우고 메인 페이지("/")로 이동
  const logout = () => {
    [
      "accessToken",
      "refreshToken",
      "fullName",
      "fullname",
      "studentId",
      "StudentId",
      "userId",
      "currentYear",
      "major",
      "user",
    ].forEach((k) => localStorage.removeItem(k));

    // 상태 갱신 이벤트
    window.dispatchEvent(new Event("storage"));
    window.dispatchEvent(new Event("user-updated"));

    // 메인 페이지로 이동
    router.replace("/");
  };

  useEffect(() => {
    const { name: n, sid: s } = readNameAndSidFromStorage();
    setInfo({ name: n, sid: s });
  }, []);

  const displayName =
    name ? (name.endsWith("님") ? name : `${name}님`) : loading ? "불러오는 중…" : "이름 미등록";
  const displayStudentId = sid ?? (loading ? "불러오는 중…" : "학번 미등록");

  return (
    <div className={styles.page}>
      <img src="/Frame.svg" alt="frame" width={157} height={51} className={styles.frame} />

      <div className={styles.box}>
        <p className={styles.name}>{displayName}</p>
        <p className={styles.student_id}>{displayStudentId}</p>
        <p className={styles.major}>컴퓨터공학과</p>

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

          <div
            className={styles.menuItem}
            role="button"
            tabIndex={0}
            onKeyDown={onKeyActivate}
            onClick={goUpload}
          >
            <Image src="/Icon_trash.svg" alt="성적표 정보 삭제" width={20} height={20} />
            <span>성적표 정보 삭제</span>
          </div>

          <div className={styles.menuItem2}>
            <Image src="/Icon_home.svg" alt="컴퓨터공학과 홈페이지" width={20} height={20} />
            <span>컴퓨터공학과 홈페이지</span>
          </div>

          <div className={styles.menuItem}>
            <Image src="/Icon_texted file.svg" alt="2025 교과과정 책자 합본" width={20} height={20} />
            <span>2025 교과과정 책자 합본</span>
          </div>

          <div className={styles.menuItem2}>
            <Image src="/Icon_setting.svg" alt="설정" width={20} height={20} />
            <span>설정</span>
          </div>
        </div>

        {/* 하단 */}
        <div className={styles.sbox}>
          <div className={styles.Quest}>
            <Image src="/Icon_contact.svg" alt="문의하기" width={20} height={20} className={styles.Questimg} />
            <p className={styles.quest}>문의하기</p>
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

      <CreditBar />
      <NotTakenCard />
      <TakenCard />
    </div>
  );
}
