"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./NotTakenCourses.module.css";

type Category = { key: "majormust" | "generalmust" | "drbol"; label: string };

type RequiredItem = { code: string; name: string; semester?: string; credit?: number };
type RequiredMissingResp = {
  major_required_missing?: RequiredItem[];
  general_required_missing?: RequiredItem[];
};

type DrbolCourse = { code: string; name: string; credit?: number };
type DrbolArea = { area: string; available_courses: DrbolCourse[] };

const FILTERS: Category[] = [
  { key: "majormust", label: "전공필수" },
  { key: "generalmust", label: "교양필수" },
  { key: "drbol", label: "드래곤볼" },
];

export default function NotTakenCard() {
  const [active, setActive] = useState<Category["key"]>("majormust");

  // 데이터 상태
  const [required, setRequired] = useState<RequiredMissingResp | null>(null);
  const [drbolAreas, setDrbolAreas] = useState<DrbolArea[] | null>(null);

  // UI 상태
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [openAreas, setOpenAreas] = useState<Record<string, boolean>>({}); // 드볼 아코디언 토글 상태

  const API_BASE = "http://127.0.0.1:8000";
  const userId =
    typeof window !== "undefined"
      ? window.localStorage.getItem("userId")?.trim() || "1"
      : "1";

  // 로컬스토리지에서 토큰 얻기
  const getBearer = () => {
    if (typeof window === "undefined") return null;
    return (
      window.localStorage.getItem("token") ||
      window.localStorage.getItem("accessToken") ||
      window.localStorage.getItem("authToken")
    );
  };

  // 활성 탭이 바뀔 때마다 적절한 API 호출
  useEffect(() => {
    let abort = false;
    const fetcher = async () => {
      setLoading(true);
      setErr(null);
      try {
        const token = getBearer();
        const headers: HeadersInit = { Accept: "application/json" };
        if (token) headers["Authorization"] = `Bearer ${token}`;

        if (active === "drbol") {
          const res = await fetch(
            `${API_BASE}/api/analysis/drbol/missing/${encodeURIComponent(userId)}/`,
            { headers, cache: "no-store" }
          );
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const json = (await res.json()) as DrbolArea[];
          if (!abort) setDrbolAreas(json || []);
        } else {
          const res = await fetch(
            `${API_BASE}/api/analysis/required/missing/${encodeURIComponent(userId)}/`,
            { headers, cache: "no-store" }
          );
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const json = (await res.json()) as RequiredMissingResp;
          if (!abort) setRequired(json || {});
        }
      } catch (e: any) {
        if (!abort) setErr(e?.message || "불러오기 실패");
      } finally {
        if (!abort) setLoading(false);
      }
    };

    fetcher();
    return () => {
      abort = true;
    };
  }, [API_BASE, userId, active]);

  // 표용 데이터(전공필수/교양필수)
  const tableRows: RequiredItem[] = useMemo(() => {
    if (!required) return [];
    if (active === "majormust") return required.major_required_missing ?? [];
    if (active === "generalmust") return required.general_required_missing ?? [];
    return [];
  }, [required, active]);

  const isEmpty =
    !loading &&
    !err &&
    ((active === "drbol"
      ? !drbolAreas || drbolAreas.length === 0
      : tableRows.length === 0));

  // 드볼 영역 토글
  const toggleArea = (area: string) =>
    setOpenAreas((prev) => ({ ...prev, [area]: !prev[area] }));

  return (
    <section className={styles.card}>
      {/* 헤더 */}
      <header className={styles.header}>
        <div className={styles.titles}>
          <h2 className={styles.title}>
            <img src="/alert-triangle.svg" alt="경고" className={styles.icon} />
            미수강 과목
            </h2>
          <p className={styles.subtitle}>전체 학기에서 선택한 분류만 모아보기</p>
        </div>

        {/* 상단 필터 토글 칩 */}
        <div className={styles.filterChips}>
          {FILTERS.map((f) => (
            <button
              key={f.key}
              className={`${styles.chip} ${active === f.key ? styles.chipActive : ""}`}
              onClick={() => setActive(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </header>

      {/* ===== 전공필수/교양필수 : 표 형태 ===== */}
      {active !== "drbol" ? (
        <div className={styles.listArea}>
          <div className={styles.tableHeaderWrap}>
            <div className={styles.tableHeader}>
              <span>학수번호</span>
              <span>학기</span>
              <span>과목명</span>
              <span style={{ textAlign: "right" }}>학점</span>
            </div>
          </div>

          <div className={styles.rows}>
            {loading && <div className={styles.center}>불러오는 중…</div>}

            {err && (
              <div className={styles.centerError}>
                불러오기 실패: {err}{" "}
                <button className={styles.reset} onClick={() => setActive(active)}>
                  재시도
                </button>
              </div>
            )}

            {isEmpty && !loading && !err && (
              <div className={styles.emptyState}>
                <p>해당 분류에 해당하는 과목이 없습니다.</p>
                <button className={styles.reset} onClick={() => setActive("majormust")}>
                  필터 초기화
                </button>
              </div>
            )}

            {!isEmpty &&
              !loading &&
              !err &&
              tableRows.map((item) => (
                <div key={`${item.code}-${item.name}`} className={styles.row}>
                  <span className={styles.code}>{item.code}</span>
                  <span className={styles.sem}>{item.semester ?? "-"}</span>
                  <span className={styles.name}>{item.name}</span>
                  <span className={styles.credit}>{item.credit ?? "-"}</span>
                </div>
              ))}
          </div>
        </div>
      ) : (
        /* ===== 드래곤볼 : 영역 리스트 > 토글다운 시 과목표 ===== */
        <div className={styles.listArea}>
          <div className={styles.rows}>
            {loading && <div className={styles.center}>불러오는 중…</div>}

            {err && (
              <div className={styles.centerError}>
                불러오기 실패: {err}{" "}
                <button className={styles.reset} onClick={() => setActive(active)}>
                  재시도
                </button>
              </div>
            )}

            {isEmpty && !loading && !err && (
              <div className={styles.emptyState}>
                <p>미이수 드래곤볼 영역이 없습니다.</p>
              </div>
            )}

            {!isEmpty &&
              !loading &&
              !err &&
              (drbolAreas ?? []).map((area) => {
                const open = !!openAreas[area.area];
                return (
                  <div key={area.area} className={styles.semesterGroup}>
                    {/* 영역 헤더 (토글 버튼) */}
                    <button
                      onClick={() => toggleArea(area.area)}
                      className={styles.areaToggle}
                      aria-expanded={open}
                    >
                      <span>{area.area}</span>
                      <span className={styles.caret}>{open ? "▾" : "▸"}</span>
                    </button>

                    {/* 펼침: 가용 과목 표 */}
                    {open && (
                      <>
                        <div className={styles.tableHeader}>
                          <span>학수번호</span>
                          <span></span>
                          <span>과목명</span>
                          <span style={{ textAlign: "right" }}>학점</span>
                        </div>

                        {area.available_courses.map((c) => (
                          <div key={c.code} className={styles.row}>
                            <span className={styles.code}>{c.code}</span>
                            <span className={styles.sem}></span>
                            <span className={styles.name}>{c.name}</span>
                            <span className={styles.credit}>{c.credit ?? "-"}</span>
                          </div>
                        ))}
                      </>
                    )}
                  </div>
                );
              })}
          </div>
        </div>
      )}
    </section>
  );
}
