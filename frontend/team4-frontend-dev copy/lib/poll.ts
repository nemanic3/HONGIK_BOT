import type { TranscriptDetail } from './types';

export async function pollTranscript(read: (signal?: AbortSignal) => Promise<TranscriptDetail>, options: { intervalMs?: number; timeoutMs?: number; signal?: AbortSignal; onUpdate?: (detail: TranscriptDetail) => void } = {}): Promise<TranscriptDetail> {
  const controller = new AbortController();
  const abort = () => controller.abort(options.signal?.reason ?? new DOMException('Cancelled', 'AbortError'));
  if (options.signal?.aborted) abort();
  options.signal?.addEventListener('abort', abort, { once: true });
  const deadline = setTimeout(() => controller.abort(new Error('처리 대기 시간이 초과되었습니다. 수동으로 확인하거나 다시 조회해주세요.')), options.timeoutMs ?? 120000);
  let wake: ReturnType<typeof setTimeout> | undefined;
  let rejectAbort: () => void;
  const cancelled = new Promise<never>((_, reject) => {
    rejectAbort = () => reject(controller.signal.reason);
    controller.signal.addEventListener('abort', rejectAbort, { once: true });
    if (controller.signal.aborted) rejectAbort();
  });
  try {
    while (true) {
      const detail = await Promise.race([read(controller.signal), cancelled]);
      options.onUpdate?.(detail);
      if (!['processing', 'pending', 'queued'].includes(detail.status)) return detail;
      await Promise.race([new Promise(resolve => { wake = setTimeout(resolve, options.intervalMs ?? 1500); }), cancelled]);
    }
  } finally {
    clearTimeout(deadline);
    clearTimeout(wake);
    options.signal?.removeEventListener('abort', abort);
    controller.signal.removeEventListener('abort', rejectAbort!);
  }
}
