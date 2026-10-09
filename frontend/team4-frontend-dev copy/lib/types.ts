export type AccreditationTrack = '' | 'accredited' | 'non_accredited';
export interface UserProfile {
  id: number;
  student_id: string;
  full_name: string;
  major: string;
  current_year: number;
  admission_year: number | null;
  accreditation_track: AccreditationTrack;
}
export interface Course {
  code: string;
  name: string;
  credit: number;
  type: string;
  grade: string;
  semester: string;
  [key: string]: unknown;
}
export interface DraftCourse {
  code: string;
  name: string;
  credit: number | null;
  type: string;
  grade: string;
  semester: string | null;
  [key: string]: unknown;
}
export interface CourseDocument { schema_version: 1; courses: DraftCourse[]; [key: string]: unknown; }
export interface TranscriptDetail {
  id: number;
  status: string;
  error_message?: string;
  source?: unknown;
  sources?: { file_number: number; page_number?: number }[];
  ocr_raw_data?: unknown;
  document?: CourseDocument | null;
  confirmed_at?: string | null;
}
export interface Criterion {
  id: string;
  label: string;
  status: 'met' | 'not_met' | 'needs_verification';
  completed?: number;
  required?: number;
  remaining?: number;
  source?: { pdf_page: number; printed_page: string };
  missing?: string[];
}
export interface AnalysisReport {
  status: 'needs_verification' | 'pending' | 'complete' | 'needs_confirmation' | 'profile_required' | 'policy_unavailable';
  transcript_id: number;
  policy: { version: string; major: string; admission_year: number; accreditation_track: AccreditationTrack; source_document: string; source_verified: boolean } | null;
  criteria: Criterion[];
  courses: Course[];
  by_semester: Record<string, Course[]>;
  warnings: string[];
  confirmed_at?: string;
}
