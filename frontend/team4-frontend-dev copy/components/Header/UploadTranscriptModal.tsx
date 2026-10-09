"use client";

import { useRef, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, errorMessage } from "../../lib/api";
import { reviewHref, validateUploads } from "../../lib/contracts";
import { uploadTranscript } from "../../lib/flows";
import styles from "./UploadTranscriptModal.module.css";

type Props = {
  onClose: () => void;
  onUploaded?: (transcriptId: string) => void; // 업로드 후 후처리 필요하면 사용
};

export default function UploadTranscriptModal({ onClose, onUploaded }: Props) {
  const router = useRouter();
  const controller = useRef<AbortController | null>(null);
  useEffect(() => { controller.current = new AbortController(); return () => controller.current?.abort(); }, []);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // ESC로 닫기 + 스크롤 잠금
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  useEffect(() => {
    if (serverError) setServerError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file]);

  const openPicker = () => inputRef.current?.click();

  const pickFile = (f?: File | null) => {
    if (!f) return setFile(null);
    try { validateUploads([f]); } catch (error) { setFile(null); setServerError(errorMessage(error)); return; }
    setFile(f);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    pickFile(e.dataTransfer.files?.[0] ?? null);
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };
  const onDragLeave = () => setDragOver(false);

  const handleConfirm = async () => {
    if (!file || loading) return;
    const signal = controller.current!.signal;
    try {
      setLoading(true);
      const result = await uploadTranscript(api(), [file], signal);
      if (signal.aborted) return;
      localStorage.setItem('transcriptId', result.transcript_id);
      onUploaded?.(result.transcript_id);
      router.push(reviewHref(result.transcript_id));
      onClose();
    } catch (error) { if (!signal.aborted) setServerError(errorMessage(error)); }
    finally { if (!signal.aborted) setLoading(false); }
  };

  return (
    <>
      <div className={styles.dim} onClick={onClose} />

      <section role="dialog" aria-modal="true" aria-labelledby="uploadTitle" className={styles.modal}>
        <button type="button" aria-label="닫기" className={styles.close} onClick={onClose}>×</button>

        <h1 id="uploadTitle" className={styles.title}>성적표를 업로드 해 주세요.</h1>
        <p className={styles.sub}>5MB 이하의 PDF, JPG, PNG 형식의 파일만 업로드 가능합니다.</p>
        <p className={styles.note}>
          <span className={styles.info}>ⓘ</span> OCR 인식 정확도 향상을 위해, <b>한 장의 파일에 하나의 학기 정보만 포함</b>되도록 해 주세요!
        </p>

        <div
          className={`${styles.dropzone} ${dragOver ? styles.dropzoneActive : ""}`}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onClick={openPicker}
        >
          <img src="/Image_icon.svg" alt="" className={styles.placeholder} />
        </div>

        <div className={styles.helperText}>
          첨부할 파일을 직접 끌어다 놓거나, 파일 선택 버튼을 눌러주세요.
        </div>

        {serverError && <div className={styles.serverError}>{serverError}</div>}

        <div className={styles.actions}>
          <button type="button" className={styles.pick} onClick={openPicker} disabled={loading}>
            <span className={styles.plus}>＋</span> 파일 선택
          </button>
          <button
            type="button"
            className={`${styles.primary} ${(!file || loading) ? styles.primaryDisabled : ""}`}
            onClick={handleConfirm}
            disabled={!file || loading}
          >
            {loading ? "업로드 중..." : "업로드"}
          </button>
        </div>

        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg"
          hidden
          onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
        />

        {file && <div className={styles.fileName}>선택됨: {file.name}</div>}
      </section>
    </>
  );
}
