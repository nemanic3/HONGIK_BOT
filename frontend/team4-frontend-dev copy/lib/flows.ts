import { ApiError } from './api.ts';
import { requireId, uploadResult, validateUploads, parseDocument, profileSelection, requireMajorSelection, reportPath } from './contracts.ts';
import type { AnalysisReport, CourseDocument, TranscriptDetail } from './types';
import type { createApiClient } from './api.ts';

type Client = Pick<ReturnType<typeof createApiClient>, 'request' | 'me'>;
export function getDetail(client: Client, id: unknown, signal?: AbortSignal) {
  return client.request<TranscriptDetail>(`/api/transcripts/detail/${requireId(id)}/`, { signal });
}
export function getReport(client: Client, id?: unknown, signal?: AbortSignal) {
  return client.request<AnalysisReport>(reportPath(id), { signal });
}
export async function confirmTranscript(client: Client, id: unknown, document: CourseDocument, signal?: AbortSignal) {
  const doc = parseDocument(JSON.stringify(document), true);
  await client.request(`/api/transcripts/confirm/${requireId(id)}/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(doc), signal });
  const detail = await getDetail(client, id, signal);
  if (requireId(detail.id) !== requireId(id) || !detail.confirmed_at) throw new Error('저장 후 확정 상태를 확인할 수 없습니다. 다시 조회해주세요.');
  return detail;
}
export async function saveProfile(client: Client, year: string, track: string, major: string, signal?: AbortSignal) {
  const selection = { ...profileSelection(year, track), major: requireMajorSelection(major) };
  await client.request('/api/users/update-profile/', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(selection), signal });
  const profile = await client.me(signal);
  if (profile.admission_year !== selection.admission_year || profile.accreditation_track !== selection.accreditation_track || profile.major !== selection.major) throw new Error('프로필 저장 결과를 확인할 수 없습니다.');
  return profile;
}
export async function uploadTranscript(client: Client, files: File[], signal?: AbortSignal) {
  validateUploads(files);
  const user = await client.me(signal);
  const form = new FormData();
  files.forEach(file => form.append('files', file, file.name));
  try {
    const result = await client.request(`/api/transcripts/${requireId(user.id)}/`, { method: 'POST', body: form, signal });
    return uploadResult(201, result);
  } catch (error) {
    if (error instanceof ApiError && error.status === 503) return uploadResult(503, error.data);
    throw error;
  }
}
