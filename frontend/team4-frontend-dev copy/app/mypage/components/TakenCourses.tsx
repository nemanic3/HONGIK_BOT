"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import styles from "./TakenCourses.module.css";

type Course = {
  code: string;
  name: string;
  credit: number;
  type: string;
  grade: string;
  semester: string;
};

export default function StatusPage() {
  const [semesters, setSemesters] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [courses, setCourses] = useState<Course[]>([]);
  const [open, setOpen] = useState<boolean>(false);

  // ----- 더미 데이터 -----
  const dummyData: Record<string, Course[]> = {
    "1-2": [
      { code: "001009", name: "영어", credit: 3, type: "교필", grade: "B0", semester: "1-2" },
      { code: "002605", name: "교양한문(1)", credit: 3, type: "일교5", grade: "A+", semester: "1-2" },
      { code: "008751", name: "디자인씽킹(DESIGN THINKING)", credit: 3, type: "교선", grade: "B+", semester: "1-2" },
      { code: "012104", name: "대학물리(2)", credit: 3, type: "M과학", grade: "B0", semester: "1-2" },
      { code: "012202", name: "대학수학(2)", credit: 3, type: "M수학", grade: "C0", semester: "1-2" },
      { code: "101810", name: "C-프로그래밍", credit: 3, type: "M전산", grade: "D+", semester: "1-2" },
    ],
    "2-2": [
      { code: "002056", name: "미술의이해", credit: 3, type: "일교4", grade: "A+", semester: "2-2" },
      { code: "012205", name: "선형대수학", credit: 3, type: "M수학", grade: "A+", semester: "2-2" },
      { code: "013312", name: "자료구조및프로그래밍", credit: 4, type: "전필", grade: "A+", semester: "2-2" },
      { code: "101408", name: "어셈블리언어및실습", credit: 3, type: "전선", grade: "A+", semester: "2-2" },
      { code: "101410", name: "데이터통신", credit: 3, type: "전선", grade: "A0", semester: "2-2" },
    ],
  };

  const korLabel = (s: string) => {
    if (!s) return "학기 선택";
    const [y, t] = s.split("-");
    if (!y || !t) return s;
    return `${y}학년 ${t}학기`;
  };

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

  // ----- 학기 목록 불러오기 (더미) -----
  useEffect(() => {
    const list = Object.keys(dummyData);
    setSemesters(list);
    if (list.length > 0) setSelected(list[0]);
  }, []);

  // ----- 선택 학기 과목 불러오기 (더미) -----
  useEffect(() => {
    if (!selected) return;
    setCourses(dummyData[selected] || []);
  }, [selected]);

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
            <div className={styles.empty}>해당 학기의 수강 내역이 없습니다.</div>
          ) : (
            courses.map((c) => (
              <div key={`${c.code}-${c.name}`} className={styles.row}>
                <div className={styles.cell}>{c.code}</div>
                <div className={styles.cell}>{c.type}</div>
                <div className={styles.cellWide}>{c.name}</div>
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
