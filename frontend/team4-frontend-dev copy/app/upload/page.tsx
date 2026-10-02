"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import styles from "./Upload.module.css";
import Header from "../../components/Header/Header";

const MAX_SIZE_BYTES = 5 * 1024 * 1024; // 5MB
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const ALLOWED_MIME = ["application/pdf", "image/png", "image/jpeg"] as const;
type AllowedMime = typeof ALLOWED_MIME[number];

// 토큰 payload(베이스64) 읽어서 user 식별자 추출(백엔드에 따라 'id' 또는 'user_id')
function readUserIdFromJWT(token: string | null): string | null {
  if (!token) return null;
  try {
    const payload = token.split(".")[1];
    const json = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    const val = json?.id ?? json?.user_id ?? json?.uid ?? null;
    return val != null ? String(val) : null;
  } catch {
    return null;
  }
}

export default function UploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  // 단일 파일 검증
  const validateOne = (f: File): string | null => {
    const okType = (ALLOWED_MIME as readonly string[]).includes(f.type as AllowedMime);
    if (!okType) return `지원하지 않는 파일 형식: ${f.name} (PDF/PNG/JPG만 가능)`;
    if (f.size > MAX_SIZE_BYTES) return `용량 초과(>5MB): ${f.name}`;
    return null;
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
    setFiles(next);

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

  // 업로드
  const handleUpload = async () => {
    if (files.length === 0) {
      setMessage("업로드할 파일을 선택해주세요.");
      return;
    }

    const token = localStorage.getItem("accessToken");
    const headers: HeadersInit = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    // 토큰의 사용자 id와 localStorage.userId 불일치 감지
    const tokenUserId = readUserIdFromJWT(token);
    const storedUserId = localStorage.getItem("userId") ?? tokenUserId ?? "";
    if (!storedUserId) {
      setMessage("userId가 없습니다. 로그인 후 다시 시도해주세요.");
      return;
    }
    if (tokenUserId && storedUserId && tokenUserId !== storedUserId) {
      setMessage(`경고: 토큰 사용자(${tokenUserId})와 URL 사용자(${storedUserId})가 다릅니다.`);
      // 진행은 계속하지만 서버에서 400/401 가능
    }

    const uploadUrl = `${API_BASE}/api/transcripts/${encodeURIComponent(storedUserId)}/`;

    try {
      setIsUploading(true);
      setMessage("업로드 중…");

      const fd = new FormData();
      // ✅ 포스트맨과 동일: 'files' 키로 여러 번 append
      for (const f of files) {
        fd.append("files", f, f.name);
      }

      const res = await fetch(uploadUrl, { method: "POST", headers, body: fd });

      const ct = res.headers.get("content-type") || "";
      const raw = await res.text();
      const data = ct.includes("application/json")
        ? (() => { try { return JSON.parse(raw); } catch { return null; } })()
        : null;

      if (res.status === 201) {
        setMessage("업로드 완료! 처리 중입니다…");
        setTimeout(() => router.push("/mypage"), 1500);
      } else if (res.status === 400) {
        setMessage(data?.error || "파일 형식 오류입니다.");
      } else if (res.status === 401) {
        setMessage("인증이 필요합니다. 로그인 후 다시 시도해주세요.");
      } else {
        setMessage(`업로드 실패(${res.status}). ${data?.error ?? raw ?? ""}`);
      }
    } catch (e: any) {
      setMessage(e?.message || "네트워크 오류가 발생했습니다.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <>
      <Header />
      <div className={styles.page}>
        <div className={styles.textbox}>
          <div className={styles.title}>성적표를 업로드 해 주세요.</div>
          <div className={styles.subtitle}>
            5MB 이하의 PDF/PNG/JPG 파일을 여러 개 선택하거나 드래그&드롭으로 추가할 수 있어요.
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
