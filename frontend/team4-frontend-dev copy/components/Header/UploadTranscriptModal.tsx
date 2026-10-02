"use client";

import { useRef, useState, useEffect } from "react";
import styles from "./UploadTranscriptModal.module.css";

type Props = {
  onClose: () => void;
  onUploaded?: (file?: File) => void; // 업로드 후 후처리 필요하면 사용
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
const MAX_SIZE = 5 * 1024 * 1024; // 5MB
const ALLOW_EXT = ["pdf", "png", "jpg", "jpeg"];

function decodeJwtPayload(token: string): any | null {
  try {
    const [, payload] = token.split(".");
    if (!payload) return null;
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(base64));
  } catch {
    return null;
  }
}

function getUserIdFromStorage(): string | null {
  try {
    const u = JSON.parse(localStorage.getItem("user") || "{}");
    if (u?.id != null) return String(u.id);
  } catch {}
  const saved = localStorage.getItem("userId");
  if (saved) return saved;
  const token = localStorage.getItem("accessToken") || "";
  if (!token) return null;
  const p = decodeJwtPayload(token);
  return p?.user_id ?? p?.sub ?? p?.uid ?? p?.id ?? null;
}

export default function UploadTranscriptModal({ onClose, onUploaded }: Props) {
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
    // 5MB 제한
    if (f.size > MAX_SIZE) {
      setServerError("파일 크기가 5MB를 초과합니다.");
      return;
    }
    // 확장자 체크 (accept로 1차 제한하고 한 번 더 체크)
    const ext = f.name.split(".").pop()?.toLowerCase() || "";
    if (!ALLOW_EXT.includes(ext)) {
      setServerError("지원하지 않는 파일 형식입니다. (PDF/JPG/PNG)");
      return;
    }
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

  // 실제 업로드
  const handleConfirm = async () => {
    if (!file) return;
    const userId = getUserIdFromStorage();
    if (!userId) {
      setServerError("로그인이 필요합니다. 다시 로그인해 주세요.");
      return;
    }

    try {
      setLoading(true);
      const form = new FormData();
      form.append("file", file);

      const access = localStorage.getItem("accessToken") || "";

      const res = await fetch(`${API_BASE}/api/transcripts/${userId}/`, {
        method: "POST",
        headers: access ? { Authorization: `Bearer ${access}` } : undefined,
        body: form, // ← FormData 사용 시 Content-Type 직접 지정 금지
      });

      const data = await res.json().catch(() => ({}));

      if (res.status === 201) {
        // { message: "업로드 완료", status: "processing" }
        onUploaded?.(file);
        onClose();
        return;
      }

      if (res.status === 401) {
        setServerError("인증이 필요합니다. 다시 로그인해 주세요.");
        return;
      }

      if (res.status === 400) {
        setServerError(
          typeof data?.error === "string"
            ? data.error
            : "지원하지 않는 파일 형식입니다."
        );
        return;
      }

      setServerError(
        typeof data?.error === "string" ? data.error : "업로드에 실패했습니다."
      );
    } catch (e) {
      console.error(e);
      setServerError("네트워크 오류로 업로드에 실패했습니다.");
    } finally {
      setLoading(false);
    }
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
          <img src="/image-placeholder.svg" alt="" className={styles.placeholder} />
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
