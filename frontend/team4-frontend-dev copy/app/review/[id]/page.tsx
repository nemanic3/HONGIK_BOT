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

type CourseCandidate = { id?: number; code?: string; name?: string; year?: number; term?: string; credit?: number | null; type?: string; evidence?: { document?: string; pdf_page?: number; printed_page?: string; verified?: boolean } };

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
  const [preview, setPreview] = useState<{ image: string; label: string; bbox?: number[] } | null>(null);
  const [filter, setFilter] = useState("전체");
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
  async function showSource(source: { file_number: number; page_number?: number; bbox?: number[] }) {
    try {
      const result = await api().request<{ image: string }>(`/api/transcripts/source/${requireId(params.id)}/${source.file_number}/?page=${source.page_number ?? 1}`);
      setPreview({ image: result.image, label: `캡처 ${source.file_number} · ${source.page_number ?? 1}쪽`, bbox: source.bbox });
    } catch (error) { setMessage(errorMessage(error)); }
  }
  async function retryOcr() {
    try {
      setSaving(true);
      const result = await api().request<{ transcript_id: number }>(`/api/transcripts/retry/${requireId(params.id)}/`, { method: "POST" });
      router.push(`/review/${requireId(result.transcript_id)}`);
    } catch (error) { setMessage(errorMessage(error)); }
    finally { setSaving(false); }
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
        {!loading && document && !detail?.confirmed_at && document.courses.length === 0 && <p role="alert">과목을 자동으로 정리하지 못했습니다. 0학점을 의미하지 않습니다. OCR 원문을 확인하고 과목을 입력한 뒤 확정해주세요.</p>}
        {!loading && document && document.courses.length > 0 && document.incomplete === true && <p role="alert">확인할 항목이 있습니다. 누락된 정보와 중복·재수강 후보를 원본과 대조해주세요.</p>}
        {loading && <p aria-live="polite">OCR 결과를 기다리는 중입니다. 최대 2분 후 수동 확인할 수 있습니다.</p>}
        <div>
          <button onClick={() => setRetry(value => value + 1)} disabled={saving}>다시 조회</button>{" "}
          {detail && !loading && ["error", "pending", "processing"].includes(detail.status) && <button onClick={retryOcr} disabled={saving}>OCR 다시 처리</button>}{" "}
          {detail && <button onClick={manual} disabled={saving}>수동으로 확인하기</button>}{" "}
          <button onClick={() => router.push("/mypage")}>대시보드로 이동</button>
        </div>
      </div>
      {detail && !loading && <section className={styles.uploadbox} style={{ alignItems: "stretch" }}>
        <details><summary>OCR 원문 / 업로드 출처</summary><pre style={{ whiteSpace: "pre-wrap" }}>{typeof detail.ocr_raw_data === "string" ? detail.ocr_raw_data : JSON.stringify(detail.ocr_raw_data, null, 2)}</pre><pre>{JSON.stringify(detail.source, null, 2)}</pre></details>
        <details><summary>고급 편집 (JSON)</summary><label>확정할 원본 JSON (schema_version: 1, courses 배열; 추가 메타데이터 유지)
          <textarea aria-label="확정 자료 JSON" rows={12} value={raw} onChange={event => { setRaw(event.target.value); setDirty(true); }} disabled={saving} style={{ width: "100%", boxSizing: "border-box" }} />
        </label>
        <button onClick={applyRaw} disabled={saving}>JSON을 행에 반영하기</button></details>
        {dirty && <p>JSON 변경을 반영한 뒤 행 편집이 가능합니다. 저장 시에는 현재 JSON을 검증합니다.</p>}
        {document && Array.isArray(document.warnings) && document.warnings.length > 0 && <ul aria-label="OCR 확인 사항">{document.warnings.map((warning, index) => <li key={index}>{String((warning as { message?: string }).message ?? "원본 확인 필요")}</li>)}</ul>}
        {document && <>
          <p>겹친 캡처는 같은 학기·학수번호·내용이 모두 일치할 때만 합칩니다. 재수강은 원본과 대조해 인정할 기록을 하나만 선택해주세요. 선택 결과는 학교의 최종 인정 판정이 아닙니다.</p>
          <label>학기별 보기 <select aria-label="학기별 보기" value={filter} onChange={e => setFilter(e.target.value)}><option>전체</option>{Array.from(new Set(document.courses.map(c => c.semester || "학기 미확인"))).sort().map(term => <option key={term}>{term}</option>)}</select></label>
          <div>{(detail.sources ?? []).map(source => <button key={`${source.file_number}-${source.page_number ?? 1}`} onClick={() => showSource(source)}>캡처 {source.file_number} · {source.page_number ?? 1}쪽 전체 보기</button>)}</div>
          {preview && <aside aria-label="원본 비교"><strong>{preview.label}</strong><button onClick={() => setPreview(null)}>닫기</button><div style={{ position: "relative", maxWidth: 1000 }}><img src={preview.image} alt={preview.label} style={{ width: "100%", display: "block" }} />{preview.bbox && <div style={{ position: "absolute", pointerEvents: "none", border: "3px solid #c2410c", left: `${preview.bbox[0]*100}%`, top: `${preview.bbox[1]*100}%`, width: `${preview.bbox[2]*100}%`, height: `${preview.bbox[3]*100}%`, boxSizing: "border-box" }} />}</div></aside>}
          <div style={{ overflowX: "auto" }}><table><thead><tr>{["학수번호", "과목명", "학점", "이수구분", "성적", "학기", "확인 사항 / 인정 선택", "삭제"].map(label => <th key={label}>{label}</th>)}</tr></thead>
            <tbody>{document.courses.map((course, index) => <tr key={index} hidden={filter !== "전체" && filter !== (course.semester || "학기 미확인")} style={{ background: (Array.isArray(course.review_reasons) && course.review_reasons.length) || (course.identification as { status?: string } | undefined)?.status === "needs_review" ? "#fff4d6" : undefined }}>
              {["code", "name", "credit", "type", "grade", "semester"].map(field => <td key={field}><input aria-label={`${index + 1}행 ${field}`} value={String(course[field] ?? "")} onChange={event => update(index, field, event.target.value)} disabled={dirty || saving} style={{ width: field === "name" ? 180 : 90, border: course.credit_decision !== "exclude" && field !== "code" && (course[field] === null || course[field] === "" || (field === "grade" && !/^(?:[ABCD][+0]?|F|P|NP|PASS)$/.test(String(course[field])))) ? "2px solid #c2410c" : undefined }} /></td>)}
              <td style={{ minWidth: 220 }}>
                {course.capture_overlap === true && <p>겹친 캡처 병합</p>}
                {course.retake_candidate === true && <p>다른 학기 재수강 후보</p>}
                {course.capture_conflict === true && <p>같은 학기 중복 확인</p>}
                {course.identification != null && typeof course.identification === "object" && <div aria-label={`${index + 1}행 과목 이력 확인`}>
                  <strong>{(course.identification as { status?: string }).status === "matched" ? "수강학기 과목 정보 일치" : "과목 이력 확인 필요"}</strong>
                  <p>{((course.identification as { issues?: string[] }).issues ?? []).join(" · ")}</p>
                  <details><summary>학기별 기준 과목·근거 비교</summary>
                    <ul>{((course.identification as { candidates?: CourseCandidate[] }).candidates ?? []).map((candidate, n) => <li key={n}>
                      {candidate.year}-{candidate.term} · {candidate.code} {candidate.name}<br />
                      {candidate.credit ?? "미확인"}학점 · {candidate.type || "이수구분 미확인"}<br />
                      근거: {candidate.evidence?.document} · PDF {candidate.evidence?.pdf_page}쪽 (인쇄 {candidate.evidence?.printed_page}) · {candidate.evidence?.verified ? "공식 확인됨" : "공식 확인 필요"}
                    </li>)}</ul>
                    {!((course.identification as { candidates?: CourseCandidate[] }).candidates ?? []).length && <p>해당 학수번호와 수강학기의 등록된 과목 정보가 없습니다.</p>}
                  </details>
                  <small>필드 수정 후 확정하면 다시 대조합니다. 직접 확인해도 공식 과목 변경 관계가 생성되지는 않습니다.</small>
                </div>}
                {Array.isArray(course.review_reasons) && <small>{course.review_reasons.map(String).join(" · ")}</small>}
                <select aria-label={`${index + 1}행 학점 인정`} value={String(course.credit_decision ?? "unresolved")} disabled={dirty || saving} onChange={e => update(index, "credit_decision", e.target.value)}><option value="unresolved">기본 / 미확인</option><option value="include">원본 확인 · 계산에 포함</option><option value="exclude">계산에서 제외 · 기록 보존</option></select>
                {Array.isArray(course.sources) && (course.sources as { file_number: number; page_number: number; bbox?: number[] }[]).map((source, i) => <button key={i} onClick={() => showSource(source)}>원본 {source.file_number} · {source.page_number}쪽</button>)}
              </td>
              <td><button disabled={dirty || saving} onClick={() => loadDocument({ ...document, courses: document.courses.filter((_, row) => row !== index) })}>삭제</button></td>
            </tr>)}</tbody></table></div>
          <button disabled={dirty || saving} onClick={() => { setFilter("전체"); loadDocument({ ...document, courses: [...document.courses, { code: "", name: "", credit: null, type: "", grade: "", semester: null }] }); }}>빈 과목 행 추가</button>
        </>}
        <p>학수번호의 앞자리 0, 소수 학점과 학기·성적을 확인해주세요. JSON에서 추가 속성도 수정할 수 있습니다.</p>
        <button className={styles.btn} onClick={save} disabled={saving || loading || !raw}>{saving ? "확정 저장 중…" : "확인 완료 · 확정 저장"}</button>
      </section>}
    </main>
  </>;
}
