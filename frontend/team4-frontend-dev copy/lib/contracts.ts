import type { AccreditationTrack, Criterion, CourseDocument } from './types';

export const SUPPORTED_MAJORS = ['컴퓨터공학과', '컴퓨터공학전공', '컴퓨터·데이터공학부 컴퓨터공학전공', '정보·컴퓨터공학부 컴퓨터공학전공'] as const;
export function initialMajorSelection(major: string): string {
  return (SUPPORTED_MAJORS as readonly string[]).includes(major) ? major : '';
}
export function requireMajorSelection(major: string): string {
  if (!initialMajorSelection(major)) throw new Error('지원하는 학과/전공을 직접 선택해주세요. 학부명만으로 전공을 추측하지 않습니다.');
  return major;
}

export function profileSelection(year: string, track: string): { admission_year: number; accreditation_track: AccreditationTrack } {
  if (!/^\d{4}$/.test(year) || Number(year) < 1900 || Number(year) > 2100) throw new Error('입학 연도를 네 자리로 입력해주세요.');
  if (track !== 'accredited' && track !== 'non_accredited') throw new Error('공학 인증 여부를 선택해주세요.');
  return { admission_year: Number(year), accreditation_track: track };
}
export function reportPath(id?: unknown): string { return `/api/analysis/report/${id == null ? '' : `?transcript_id=${requireId(id)}`}`; }
export function criterionView(criterion: Criterion, verified: boolean): Criterion & { sourceLabel: string } {
  return { ...criterion, status: verified ? criterion.status : 'needs_verification', sourceLabel: criterion.source ? `PDF ${criterion.source.pdf_page}쪽 / 책자 ${criterion.source.printed_page}쪽` : '출처 페이지 미제공' };
}

export function parseDocument(raw: string, forConfirmation = false): CourseDocument {
  const doc = JSON.parse(raw);
  if (!doc || doc.schema_version !== 1 || !Array.isArray(doc.courses)) throw new Error('schema_version 1과 courses 배열이 필요합니다.');
  for (const [index, course] of doc.courses.entries()) {
    if (!course || typeof course.code !== 'string') throw new Error('학수번호는 문자열이어야 합니다. (앞자리 0 유지)');
    for (const key of ['name', 'type', 'grade']) if (typeof course[key] !== 'string') throw new Error(`${key}는 문자열이어야 합니다.`);
    if (course.semester !== null && typeof course.semester !== 'string') throw new Error('semester는 문자열 또는 null이어야 합니다.');
    if (course.credit !== null && (typeof course.credit !== 'number' || !Number.isFinite(course.credit) || course.credit < 0)) throw new Error('학점은 0 이상의 숫자 또는 null이어야 합니다.');
    if (course.credit_decision && !['unresolved', 'include', 'exclude'].includes(course.credit_decision)) throw new Error('학점 인정 선택이 올바르지 않습니다.');
    if (forConfirmation) {
      for (const key of (course.credit_decision === 'exclude' ? ['name', 'semester'] : ['name', 'type', 'grade', 'semester'])) if (typeof course[key] !== 'string' || !course[key].trim()) throw new Error(`${index + 1}행: 확정하려면 ${key}가 필요합니다.`);
      if (course.credit === null && course.credit_decision !== 'exclude') throw new Error(`${index + 1}행: 확정하려면 학점이 필요합니다.`);
    }
  }
  return doc;
}
export function editCourse(doc: CourseDocument, index: number, field: string, text: string): CourseDocument {
  if (field === 'credit' && text.trim() !== '' && (!Number.isFinite(Number(text)) || Number(text) < 0)) throw new Error('학점은 0 이상의 숫자여야 합니다.');
  const value = field === 'credit' ? (text.trim() === '' ? null : Number(text)) : field === 'semester' && !text.trim() ? null : text;
  return { ...doc, courses: doc.courses.map((course, i) => {
    if (i !== index) return course;
    const edited = { ...course, [field]: value };
    if (course.identification && ['code', 'name', 'credit', 'type', 'semester'].includes(field)) {
      edited.identification = { status: 'needs_review', issues: ['수정한 과목 정보는 확정 시 다시 대조합니다.'], candidates: [], course_id: null, version_id: null };
    }
    if (field === 'semester') {
      const term = /^(\d{4})-(1|2|summer|winter)$/.exec(text);
      if ('academic_year' in course) edited.academic_year = term ? Number(term[1]) : null;
      if ('term' in course) edited.term = term ? term[2] : null;
    }
    return edited;
  }) };
}

export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

export function requireId(value: unknown): string {
  const id = typeof value === 'number' && Number.isSafeInteger(value) ? String(value) : value;
  if (typeof id !== 'string' || !/^[1-9]\d*$/.test(id)) throw new Error('서버의 ID가 올바르지 않습니다.');
  return id;
}
export function reviewHref(id: unknown): string { return `/review/${requireId(id)}`; }
export function uploadResult(status: number, data: unknown): { transcript_id: string; status?: string } {
  if (status !== 201 && status !== 503) throw new Error('업로드에 실패했습니다.');
  const result = data as { transcript_id?: unknown; status?: string };
  return { transcript_id: requireId(result?.transcript_id), status: result?.status };
}

export function validateUploads(files: ReadonlyArray<{ name: string; size: number }>): void {
  if (files.length > 5) throw new Error('한 번에 최대 5개 파일을 선택해주세요.');
  if (!files.length) throw new Error('업로드할 파일을 선택해주세요.');
  if (files.some(file => !/\.(pdf|png|jpe?g)$/i.test(file.name))) throw new Error('지원하지 않는 파일 형식입니다. (PDF/PNG/JPG)');
  if (files.some(file => !Number.isFinite(file.size) || file.size < 0) || files.reduce((sum, file) => sum + file.size, 0) > MAX_UPLOAD_BYTES) throw new Error('파일 합계가 5MiB를 초과합니다.');
}
