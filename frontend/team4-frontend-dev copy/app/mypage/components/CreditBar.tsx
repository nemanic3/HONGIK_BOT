"use client";

import Image from "next/image";
import { criterionView } from "../../../lib/contracts";
import type { AnalysisReport } from "../../../lib/types";
import styles from "./CreditBar.module.css";

export default function CreditBar({ report, loading = false }: { report: AnalysisReport | null; loading?: boolean }) {
  const criteria = (report?.criteria ?? []).map(criterion => criterionView(criterion, report?.policy?.source_verified === true));
  const label = { met: "충족", not_met: "미충족", needs_verification: "검증 필요" };
  return <div className={styles.box}>
    <p className={styles.title}>졸업 요건 이수 현황</p>
    {criteria.length === 0 && <p>{loading ? "불러오는 중…" : "졸업 요건 정보가 아직 없습니다."}</p>}
    <div className={styles.cards}>
      {criteria.map((criterion, index) => <div key={criterion.id} className={index === 0 ? styles.total : styles.major} style={{ margin: 0, height: "auto", minHeight: 85, flexShrink: 0 }}>
        {index === 0 && <Image src="/Group.svg" alt="" width={15} height={15} className={styles.icon} />}
        <p className={index === 0 ? styles.tcredit : styles.mcredit} style={{ width: "auto", margin: 0 }}>{criterion.label}</p>
        <p className={index === 0 ? styles.tc : styles.mc} style={{ width: "auto", height: "auto", margin: 0 }}>{criterion.completed ?? "—"} / {criterion.required ?? "—"}</p>
        <small>{label[criterion.status]}{criterion.remaining != null && ` · 남은 수치 ${criterion.remaining}`}</small>
        <small>{criterion.sourceLabel}</small>
      </div>)}
    </div>
  </div>;
}
