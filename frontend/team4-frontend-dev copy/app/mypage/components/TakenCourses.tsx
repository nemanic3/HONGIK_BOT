"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import type { AnalysisReport } from "../../../lib/types";
import styles from "./TakenCourses.module.css";

export default function TakenCard({ report, loading = false }: { report: AnalysisReport | null; loading?: boolean }) {
  const semesters = Object.keys(report?.by_semester ?? {}).sort();
  const [selection, setSelected] = useState("");
  const selected = semesters.includes(selection) ? selection : semesters[0] ?? "";
  const courses = report?.by_semester?.[selected] ?? [];
  const [open, setOpen] = useState(false);
  const korLabel = (semester: string) => semester || "학기 선택";

  const wrapRef = useRef<HTMLDivElement | null>(null);

  // 외부 클릭으로 드롭다운 닫기
  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      const root = wrapRef.current;
      if (!root) return;
      if (!root.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const empty = useMemo(() => courses.length === 0, [courses]);

  return (
    <div className={styles.box}>
      <div className={styles.title}>수강 현황</div>

      <div className={styles.barbox}>
        <div className={styles.bar}>
          <div className={styles.selectWrap} ref={wrapRef}>
            <button
              type="button"
              className={styles.selBtn}
              aria-haspopup="listbox"
              aria-expanded={open}
              onClick={() => setOpen((v) => !v)}
              onKeyDown={(e) => {
                if (e.key === "Escape") setOpen(false);
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setOpen((v) => !v);
                }
              }}
              title="학기 선택"
            >
              {korLabel(selected)}
            </button>

            {open && (
              <ul className={styles.selMenu} role="listbox" aria-label="학기 선택">
                {semesters.length === 0 ? (
                  <li className={styles.menuItem} aria-disabled="true">
                    불러올 학기가 없습니다
                  </li>
                ) : (
                  semesters.map((s) => (
                    <li
                      key={s}
                      role="option"
                      aria-selected={selected === s}
                      className={`${styles.menuItem} ${selected === s ? styles.active : ""}`}
                      onClick={() => {
                        setSelected(s);
                        setOpen(false);
                      }}
                    >
                      {korLabel(s)}
                    </li>
                  ))
                )}
              </ul>
            )}
          </div>
        </div>
      </div>

      <div className={styles.statusbox}>
        <div className={`${styles.row} ${styles.headerRow}`}>
          <div className={styles.cell}>학수번호</div>
          <div className={styles.cell}>이수구분</div>
          <div className={styles.cellWide}>과목명</div>
          <div className={styles.cellCenter}>학점</div>
          <div className={styles.cellCenter}>성적</div>
        </div>

        <div className={styles.status}>
          {empty ? (
            <div className={styles.empty}>{loading ? "불러오는 중…" : report ? "해당 학기의 수강 내역이 없습니다." : "성적표를 업로드하고 확인해주세요."}</div>
          ) : (
            courses.map((c, index) => (
              <div key={`${c.code}-${c.name}-${index}`} className={styles.row}>
                <div className={styles.cell}>{c.code}</div>
                <div className={styles.cell}>{c.type}</div>
                <div className={styles.cellWide}>{c.name}{c.credit_counted === false && <small style={{ display: "block" }}>계산 제외 / 확인 필요</small>}</div>
                <div className={styles.cellCenter}>{c.credit}</div>
                <div className={styles.cellCenter}>{c.grade}</div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
