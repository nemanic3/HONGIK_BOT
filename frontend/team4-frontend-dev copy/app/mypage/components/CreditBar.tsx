"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import styles from "./CreditBar.module.css";

const API_BASE = "http://127.0.0.1:8000"; // ✅ 고정 BASE URL

// 서버 응답 타입
type TotalResp = { total_credit?: number };
type GeneralResp = { general_credit?: number };
type MajorResp = { major_credit?: number };
type PartResp = { drbol_completed?: number };

// 화면 상태
type StatusResp = {
  total_completed?: number;
  major_completed?: number;
  general_completed?: number;
  drbol_completed?: number;
};

// ✅ 고정 Required 값
const REQUIRED = { total: 132, major: 50, general: 8, drbol: 18 };

// (옵션) JWT에서 userId 폴백 추출
function readUserIdFromJWT(token: string | null): string | null {
  if (!token) return null;
  try {
    const payload = token.split(".")[1];
    const json = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    const val = json?.id ?? json?.user_id ?? json?.uid ?? null;
    return val != null ? String(val) : null;
  } catch {
    return null;
  }
}

export default function Horizonbar() {
  const [credits, setCredits] = useState<StatusResp>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const access = localStorage.getItem("accessToken") || "";
    let id =
      localStorage.getItem("userId") ||
      localStorage.getItem("user_id") ||
      readUserIdFromJWT(access);

    if (!id) {
      setError("로그인이 필요합니다. (userId 없음)");
      setLoading(false);
      return;
    }

    const headers: HeadersInit = {
      "Content-Type": "application/json",
      ...(access ? { Authorization: `Bearer ${access}` } : {}),
    };

    (async () => {
      try {
        const [totalRes, generalRes, majorRes, partRes] = await Promise.all([
          fetch(`${API_BASE}/api/analysis/credit/total/${id}/`, {
            method: "GET",
            headers,
            cache: "no-store",
          }),
          fetch(`${API_BASE}/api/analysis/credit/general/${id}/`, {
            method: "GET",
            headers,
            cache: "no-store",
          }),
          fetch(`${API_BASE}/api/analysis/credit/major/${id}/`, {
            method: "GET",
            headers,
            cache: "no-store",
          }),
          fetch(`${API_BASE}/api/analysis/credit/part/${id}/`, {
            method: "GET",
            headers,
            cache: "no-store",
          }),
        ]);

        if (!totalRes.ok) throw new Error(`총 학점 조회 실패 (${totalRes.status})`);
        if (!generalRes.ok) throw new Error(`교양 학점 조회 실패 (${generalRes.status})`);
        if (!majorRes.ok) throw new Error(`전공 학점 조회 실패 (${majorRes.status})`);
        if (!partRes.ok) throw new Error(`파트 조회 실패 (${partRes.status})`);

        const [total, general, major, part]: [TotalResp, GeneralResp, MajorResp, PartResp] =
          await Promise.all([totalRes.json(), generalRes.json(), majorRes.json(), partRes.json()]);

        setCredits({
          total_completed: total.total_credit,
          major_completed: major.major_credit,
          general_completed: general.general_credit,
          drbol_completed: part.drbol_completed,
        });
      } catch (e: any) {
        setError(e?.message ?? "상태 조회 중 오류 발생");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const fmt = (v?: number) => (typeof v === "number" ? v : "—");

  return (
    <div className={styles.box}>
      <p className={styles.title}>졸업 요건 이수 현황</p>

      {/* 총 이수학점 */}
      <div className={styles.total}>
        <Image src="/Group.svg" alt="group" width={15} height={15} className={styles.icon} />
        <div className={styles.totalRow}>
          <p className={styles.tcredit}>총 이수학점</p>
          <p className={styles.tc}>
            {loading ? "로딩중…" : fmt(credits.total_completed)} / {REQUIRED.total} 점
          </p>
        </div>
      </div>

      {/* 전공 */}
      <div className={styles.major}>
        <p className={styles.mcredit}>전공</p>
        <p className={styles.mc}>
          {loading ? "로딩중…" : fmt(credits.major_completed)} / {REQUIRED.major} 점
        </p>
      </div>

      {/* 교양필수 */}
      <div className={styles.general}>
        <p className={styles.gcredit}>교양필수</p>
        <p className={styles.gc}>
          {loading ? "로딩중…" : fmt(credits.general_completed)} / {REQUIRED.general} 점
        </p>
      </div>

      {/* 드래곤볼 */}
      <div className={styles.dvbol}>
        <p className={styles.dcredit}>드래곤볼</p>
        <p className={styles.dc}>
          {loading ? "로딩중…" : fmt(credits.drbol_completed)} / {REQUIRED.drbol} 점
        </p>
      </div>

      {error && <p className={styles.error}>{error}</p>}
    </div>
  );
}
