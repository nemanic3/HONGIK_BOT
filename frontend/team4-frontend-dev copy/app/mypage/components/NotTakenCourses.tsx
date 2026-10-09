"use client";

import { useState } from "react";
import { criterionView } from "../../../lib/contracts";
import type { AnalysisReport } from "../../../lib/types";
import styles from "./NotTakenCourses.module.css";

export default function NotTakenCard({ report, loading = false }: { report: AnalysisReport | null; loading?: boolean }) {
  const [active, setActive] = useState("");
  const criteria = (report?.criteria ?? []).map(criterion => criterionView(criterion, report?.policy?.source_verified === true));
  const visible = criteria.filter(criterion => !active || criterion.id === active);
  const statusLabel = { met: "충족", not_met: "미충족", needs_verification: "검증 필요" };
  return <section className={styles.card}>
    <header className={styles.header}>
      <div className={styles.titles}>
        <h2 className={styles.title}><img src="/alert-triangle.svg" alt="경고" className={styles.icon} />미수강 과목</h2>
        <p className={styles.subtitle}>미충족 항목과 검증이 필요한 기준 확인</p>
      </div>
      <div className={styles.filterChips}>
        <button className={`${styles.chip} ${!active ? styles.chipActive : ""}`} onClick={() => setActive("")}>전체</button>
        {criteria.map(criterion => <button key={criterion.id} className={`${styles.chip} ${active === criterion.id ? styles.chipActive : ""}`} onClick={() => setActive(criterion.id)}>{criterion.label}</button>)}
      </div>
    </header>
    <div className={styles.listArea}><div className={styles.rows}>
      {loading && <div className={styles.center}>불러오는 중…</div>}
      {!loading && !criteria.length && <div className={styles.emptyState}>확정된 성적표와 적용 기준이 필요합니다.</div>}
      {!loading && visible.map(criterion => <section key={criterion.id} className={styles.semesterGroup}>
        <p className={styles.semesterTitle}>{criterion.label} · {statusLabel[criterion.status]}</p>
        <small>{criterion.sourceLabel}</small>
        {(criterion.missing ?? []).map((item, index) => <div key={index} className={styles.row} style={{ display: "block" }}>{item}</div>)}
        {!criterion.missing?.length && <p className={styles.subtitle}>{criterion.status === "met" ? "이 기준을 충족했습니다." : "추가 필요 과목 목록이 제공되지 않았습니다. 기준과 자료를 확인해주세요."}</p>}
      </section>)}
    </div></div>
  </section>;
}
