"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Header from "../../../components/Header/Header";
import { api, ApiError, errorMessage } from "../../../lib/api";
import { editCourse, parseDocument, requireId } from "../../../lib/contracts";
import { confirmTranscript, getDetail } from "../../../lib/flows";
import { pollTranscript } from "../../../lib/poll";
import type { CourseDocument, TranscriptDetail } from "../../../lib/types";
import styles from "../../upload/Upload.module.css";

export default function ReviewPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [detail, setDetail] = useState<TranscriptDetail | null>(null);
  const [document, setDocument] = useState<CourseDocument | null>(null);
  const [raw, setRaw] = useState("");
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [retry, setRetry] = useState(0);
  const polling = useRef<AbortController | null>(null);
  const savingController = useRef<AbortController | null>(null);
  useEffect(() => {
    savingController.current = new AbortController();
    return () => savingController.current?.abort();
  }, []);
  function loadDocument(value: unknown) {
    const text = JSON.stringify(value ?? { schema_version: 1, courses: [] }, null, 2);
    setRaw(text); setDirty(false);
    try { setDocument(parseDocument(text)); }
    catch (error) { setDocument(null); setMessage(errorMessage(error)); }
  }
  useEffect(() => {
    const controller = new AbortController();
    polling.current = controller;
    setLoading(true); setMessage(""); setDetail(null); setDocument(null); setRaw("");
    (async () => {
      try {
        const id = requireId(params.id);
        const result = await pollTranscript(signal => getDetail(api(), id, signal), {
          signal: controller.signal,
          onUpdate: value => { if (!controller.signal.aborted) setDetail(value); },
        });
        if (controller.signal.aborted) return;
        loadDocument(result.document);
        if (result.error_message) setMessage(result.error_message);
        else if (!result.document) setMessage("구조화된 OCR 결과가 없습니다. 원문을 참고해 수동으로 과목을 입력해주세요.");
      } catch (error) {
        if (!controller.signal.aborted) {
          setMessage(error instanceof ApiError && error.status === 404 ? "성적표를 찾을 수 없거나 접근 권한이 없습니다." : errorMessage(error));
        }
      } finally { if (!controller.signal.aborted) setLoading(false); }
    })();
    return () => controller.abort();
  }, [params.id, retry]);
  function manual() {
    polling.current?.abort(); setLoading(false);
    loadDocument(detail?.document);
    setMessage("수동 확인 모드입니다. OCR 원문과 모든 행을 확인한 후 확정해주세요.");
  }
  function applyRaw() {
    try { setDocument(parseDocument(raw)); setDirty(false); setMessage(""); }
    catch (error) { setMessage(errorMessage(error)); }
  }
  function update(index: number, field: string, value: string) {
    if (!document || dirty) return;
    try {
      const next = editCourse(document, index, field, value);
      setDocument(next); setRaw(JSON.stringify(next, null, 2)); setMessage("");
    } catch (error) { setMessage(errorMessage(error)); }
  }
  async function save() {
    if (!detail || saving || loading) return;
    const signal = savingController.current!.signal;
    try {
      setSaving(true); setMessage("");
      await confirmTranscript(api(), params.id, parseDocument(raw), signal);
      if (signal.aborted) return;
      localStorage.setItem("transcriptId", requireId(params.id));
      router.push(`/mypage?transcript_id=${requireId(params.id)}`);
    } catch (error) { if (!signal.aborted) setMessage(errorMessage(error)); }
    finally { if (!signal.aborted) setSaving(false); }
  }
  return <>
    <div className={styles.headerWrapper}><Header /></div>
    <main className={styles.page} style={{ height: "auto", minHeight: "100vh" }}>
      <div className={styles.textbox}>
        <h1 className={styles.title}>성적표 확인 및 수정</h1>
        <p>성적표 #{params.id} · {detail?.status ?? "조회 중"} · {detail?.confirmed_at ? "확정된 자료 (수정 후 다시 확정 가능)" : "확정 전"}</p>
        {message && <p role="alert">{message}</p>}
        {loading && <p aria-live="polite">OCR 결과를 기다리는 중입니다. 최대 2분 후 수동 확인할 수 있습니다.</p>}
        <div>
          <button onClick={() => setRetry(value => value + 1)} disabled={saving}>다시 조회</button>{" "}
          {detail && <button onClick={manual} disabled={saving}>수동으로 확인하기</button>}{" "}
          <button onClick={() => router.push("/mypage")}>대시보드로 이동</button>
        </div>
      </div>
      {detail && !loading && <section className={styles.uploadbox} style={{ alignItems: "stretch" }}>
        <details><summary>OCR 원문 / 업로드 출처</summary><pre style={{ whiteSpace: "pre-wrap" }}>{typeof detail.ocr_raw_data === "string" ? detail.ocr_raw_data : JSON.stringify(detail.ocr_raw_data, null, 2)}</pre><pre>{JSON.stringify(detail.source, null, 2)}</pre></details>
        <label>확정할 원본 JSON (schema_version: 1, courses 배열; 추가 메타데이터 유지)
          <textarea aria-label="확정 자료 JSON" rows={12} value={raw} onChange={event => { setRaw(event.target.value); setDirty(true); }} disabled={saving} style={{ width: "100%", boxSizing: "border-box" }} />
        </label>
        <button onClick={applyRaw} disabled={saving}>JSON을 행에 반영하기</button>
        {dirty && <p>JSON 변경을 반영한 뒤 행 편집이 가능합니다. 저장 시에는 현재 JSON을 검증합니다.</p>}
        {document && <>
          <div style={{ overflowX: "auto" }}><table><thead><tr>{["학수번호", "과목명", "학점", "이수구분", "성적", "학기", "삭제"].map(label => <th key={label}>{label}</th>)}</tr></thead>
            <tbody>{document.courses.map((course, index) => <tr key={index}>
              {["code", "name", "credit", "type", "grade", "semester"].map(field => <td key={field}><input aria-label={`${index + 1}행 ${field}`} value={String(course[field] ?? "")} onChange={event => update(index, field, event.target.value)} disabled={dirty || saving} style={{ width: field === "name" ? 180 : 90 }} /></td>)}
              <td><button disabled={dirty || saving} onClick={() => loadDocument({ ...document, courses: document.courses.filter((_, row) => row !== index) })}>삭제</button></td>
            </tr>)}</tbody></table></div>
          <button disabled={dirty || saving} onClick={() => loadDocument({ ...document, courses: [...document.courses, { code: "", name: "", credit: null, type: "", grade: "", semester: null }] })}>빈 과목 행 추가</button>
        </>}
        <p>학수번호의 앞자리 0, 소수 학점과 학기·성적을 확인해주세요. JSON에서 추가 속성도 수정할 수 있습니다.</p>
        <button className={styles.btn} onClick={save} disabled={saving || loading || !raw}>{saving ? "확정 저장 중…" : "확인 완료 · 확정 저장"}</button>
      </section>}
    </main>
  </>;
}
