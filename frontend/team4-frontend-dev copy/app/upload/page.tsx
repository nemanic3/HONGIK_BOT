"use client";

import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../../lib/api";
import { reviewHref, validateUploads } from "../../lib/contracts";
import { uploadTranscript } from "../../lib/flows";
import { useRouter } from "next/navigation";
import styles from "./Upload.module.css";
import Header from "../../components/Header/Header";

export default function UploadPage() {
  const router = useRouter();
  const controller = useRef<AbortController | null>(null);
  useEffect(() => { controller.current = new AbortController(); return () => controller.current?.abort(); }, []);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const validateOne = (file: File): string | null => {
    try { validateUploads([file]); return null; } catch (error) { return errorMessage(error); }
  };

  // 여러 개 추가(파일 선택/드롭 공통)
  const addFiles = (list: FileList | null) => {
    if (!list?.length) return;
    setMessage(null);

    const incoming = Array.from(list);
    const errors: string[] = [];
    const exist = new Set(files.map((f) => `${f.name}-${f.size}`));
    const next: File[] = [...files];

    for (const f of incoming) {
      const err = validateOne(f);
      if (err) { errors.push(err); continue; }
      const key = `${f.name}-${f.size}`;
      if (exist.has(key)) continue; // 같은 파일 중복 추가 방지
      exist.add(key);
      next.push(f);
    }

    if (errors.length) setMessage(errors.join("\n"));
    try { validateUploads(next); setFiles(next); } catch (error) { setMessage(errorMessage(error)); }

    // 동일 파일 다시 선택 가능하게 초기화
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // 파일 인풋 선택
  const onPickFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    addFiles(e.target.files);
  };

  // 드래그&드롭
  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    addFiles(e.dataTransfer.files);
  };
  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!isDragging) setIsDragging(true);
  };
  const onDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  // 개별/전체 제거
  const removeOne = (name: string, size: number) =>
    setFiles((prev) => prev.filter((f) => !(f.name === name && f.size === size)));
  const clearAll = () => {
    setFiles([]);
    setMessage(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleUpload = async () => {
    if (isUploading) return;
    const signal = controller.current!.signal;
    try {
      setIsUploading(true); setMessage("업로드 중…");
      const result = await uploadTranscript(api(), files, signal);
      if (signal.aborted) return;
      localStorage.setItem('transcriptId', result.transcript_id);
      router.push(reviewHref(result.transcript_id));
    } catch (error) { if (!signal.aborted) setMessage(errorMessage(error)); }
    finally { if (!signal.aborted) setIsUploading(false); }
  };

  return (
    <>
      <div className={styles.headerWrapper}><Header /></div>
      <div className={styles.page}>
        <div className={styles.textbox}>
          <div className={styles.title}>성적표를 업로드 해 주세요.</div>
          <div className={styles.subtitle}>
            졸업요건 조회의 과목 표를 학기 제목·머리글이 보이도록 캡처해주세요. 긴 화면은 일부가 겹치도록 나눠 찍어도 됩니다. 합계 5MiB 이하의 PDF/PNG/JPG 파일을 최대 5개 선택하거나 드래그&드롭으로 추가할 수 있어요.
          </div>
          {message && <div className={styles.notice} aria-live="polite">{message}</div>}
        </div>

        {/* 드래그&드롭 영역 */}
        <div
          className={`${styles.uploadbox} ${isDragging ? styles.dragging : ""}`}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          role="region"
          aria-label="파일 업로드 영역"
        >
          <div className={styles.imagebox} onClick={() => fileInputRef.current?.click()}>
            {files.length > 0 ? (
              <div className={styles.fileDisplay} style={{ width: "100%" }}>
                <ul className={styles.fileList} aria-label="선택된 파일 목록">
                  {files.map((f) => (
                    <li key={`${f.name}-${f.size}`} className={styles.fileItem}>
                      <span className={styles.fileName}>{f.name}</span>
                      <button
                        className={styles.removeBtn}
                        onClick={(e) => { e.stopPropagation(); removeOne(f.name, f.size); }}
                        aria-label={`${f.name} 삭제`}
                        type="button"
                        disabled={isUploading}
                      >
                        ❌
                      </button>
                    </li>
                  ))}
                </ul>
                <div className={styles.fileActions}>
                  <button
                    type="button"
                    className={styles.removeBtn}
                    onClick={(e) => { e.stopPropagation(); clearAll(); }}
                    disabled={isUploading}
                    aria-label="모든 파일 삭제"
                  >
                    전체 비우기
                  </button>
                </div>
              </div>
            ) : (
              <img src="/Image_icon.svg" alt="아이콘" className={styles.icon} />
            )}
          </div>

          <div className={styles.message}>
            <p>여러 개 파일을 끌어다 놓거나, 아래 버튼으로 선택하세요.</p>
          </div>

          {/* 파일 선택 버튼 */}
          <button
            type="button"
            className={styles.btn}
            onClick={(e) => {
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
            disabled={isUploading}
          >
            <img src="/plus.svg" alt="" className={styles.plus} aria-hidden />
            <p>{isUploading ? "업로드 중..." : files.length > 0 ? `추가 선택 (${files.length}개 선택됨)` : "파일선택"}</p>
          </button>

          {/* 숨겨진 파일 인풋: multiple 지원 */}
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: "none" }}
            accept=".pdf,.png,.jpg,.jpeg"
            multiple
            onChange={onPickFiles}
            disabled={isUploading}
          />

          {/* 업로드 실행 버튼 */}
          <div style={{ height: 8 }} />
          <button
            type="button"
            className={styles.btn}
            onClick={handleUpload}
            disabled={isUploading || files.length === 0}
            aria-busy={isUploading}
          >
            <img src="/plus.svg" alt="" className={styles.plus} aria-hidden />
            <p>{isUploading ? "업로드 중..." : `업로드 (${files.length}개)`}</p>
          </button>
        </div>
      </div>
    </>
  );
}
