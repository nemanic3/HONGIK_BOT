"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import styles from "./SuccessPage.module.css";
import Header from "../../components/Header/Header";
import { useRouter } from "next/navigation";

export default function SuccessPage() {
  const router = useRouter();

  // 기본값: "김컴공"
  const [fullName, setFullName] = useState("김컴공");

  useEffect(() => {
    if (typeof window === "undefined") return;

    try {
      // 1) full_name이 문자열로 저장된 경우
      const direct = localStorage.getItem("full_name");
      if (direct && direct.trim()) {
        setFullName(direct.trim());
        return;
      }

      // 2) 혹시 유저 객체(JSON)로 저장했을 때도 대비 (선택)
      const userJson = localStorage.getItem("user");
      if (userJson) {
        try {
          const obj = JSON.parse(userJson);
          const candidate =
            obj?.full_name ?? obj?.fullName ?? obj?.profile?.full_name;
          if (typeof candidate === "string" && candidate.trim()) {
            setFullName(candidate.trim());
          }
        } catch {
          /* noop */
        }
      }
    } catch (e) {
      console.warn("failed to read full_name from localStorage", e);
    }
  }, []);

  // 자동 이동이 필요하면 사용
  useEffect(() => {const id = setTimeout(() => {router.replace("/mypage");}, 2000);
  return () => clearTimeout(id);
  }, [router]);

  return (
    <div className={styles.page}>
      <Header />
      <div className={styles.title}>
        {fullName}님,
        <br />
        환영합니다!
      </div>
      <div className={styles.ImageWrapper}>
        <Image
          src="/bottom.gif"
          alt="가입 성공 애니메이션"
          width={558}
          height={353}
          priority
        />
      </div>
    </div>
  );
}
