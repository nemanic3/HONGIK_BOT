import test from 'node:test';
import assert from 'node:assert/strict';

const contracts = () => import('../lib/contracts.ts');

test('profile selections are explicit and policy drafts never display an authoritative pass', async () => {
  const { profileSelection, criterionView, reportPath } = await contracts();
  assert.deepEqual(profileSelection('2024', 'non_accredited'), { admission_year: 2024, accreditation_track: 'non_accredited' });
  assert.throws(() => profileSelection('', 'accredited'), /입학/);
  assert.throws(() => profileSelection('2024', ''), /인증/);
  assert.equal(reportPath(), '/api/analysis/report/');
  assert.equal(reportPath('42'), '/api/analysis/report/?transcript_id=42');
  const criterion = { id: 'total', label: '총 학점', status: 'met', completed: 140.5, required: 140, source: { pdf_page: 12, printed_page: '10' } };
  assert.deepEqual(criterionView(criterion, false), { ...criterion, status: 'needs_verification', sourceLabel: 'PDF 12쪽 / 책자 10쪽' });
  assert.equal(criterionView(criterion, true).required, 140);
});

test('review edits retain leading zero codes, fractional credits and unknown metadata', async () => {
  const { parseDocument, editCourse } = await contracts();
  const raw = { schema_version: 1, origin: { page: 2 }, courses: [{ code: '001009', name: 'English', credit: 1.5, type: '교필', grade: 'P', semester: '2024-1', retake_of: null, confidence: 0.42 }] };
  const document = parseDocument(JSON.stringify(raw));
  const edited = editCourse(document, 0, 'credit', '2.5');
  assert.deepEqual(edited, { ...raw, courses: [{ ...raw.courses[0], credit: 2.5 }] });
  assert.equal(document.courses[0].credit, 1.5);
  assert.equal(editCourse(document, 0, 'code', '000007').courses[0].code, '000007');
  assert.throws(() => editCourse(document, 0, 'credit', '-1'), /학점/);
  assert.throws(() => parseDocument(JSON.stringify({ ...raw, courses: [{ ...raw.courses[0], code: 1009 }] })), /학수번호/);
  assert.throws(() => parseDocument('{"schema_version":2,"courses":[]}'), /schema/);
});

test('incomplete OCR draft null credit and semester can be parsed and corrected without losing metadata', async () => {
  const { parseDocument, editCourse } = await contracts();
  const raw = { schema_version: 1, source: { page: 2 }, courses: [{ code: '001009', name: 'Course', credit: null, type: '전필', grade: 'P', semester: null, confidence: 0.2, aliases: ['Original'], academic_year: null, term: null, retake: false, major_field: 'CS' }] };
  const draft = parseDocument(JSON.stringify(raw));
  assert.deepEqual(draft, raw);
  const credit = editCourse(draft, 0, 'credit', '1.5');
  const completed = editCourse(credit, 0, 'semester', '2024-1');
  assert.deepEqual(completed, { ...raw, courses: [{ ...raw.courses[0], credit: 1.5, semester: '2024-1', academic_year: 2024, term: '1' }] });
  assert.equal(editCourse(completed, 0, 'credit', '').courses[0].credit, null, 'blank edit stays unknown, never silently zero');
  assert.equal(editCourse(completed, 0, 'semester', '').courses[0].semester, null);
  assert.equal(draft.courses[0].credit, null);
});

test('upload result routes only to the server transcript ID, including OCR 503 recovery', async () => {
  const { reviewHref, uploadResult } = await contracts();
  assert.equal(reviewHref(uploadResult(201, { transcript_id: 42, status: 'processing' }).transcript_id), '/review?transcript_id=42');
  assert.equal(uploadResult(503, { transcript_id: 43, status: 'error' }).transcript_id, '43');
  assert.throws(() => uploadResult(201, { status: 'processing' }), /ID/);
  assert.throws(() => uploadResult(400, { transcript_id: 42 }), /업로드/);
  assert.throws(() => reviewHref('01'), /ID/);
  assert.throws(() => reviewHref('42/other'), /ID/);
});

test('uploads enforce the combined five MiB limit, not only each file', async () => {
  const { validateUploads } = await contracts();
  assert.throws(() => validateUploads([{ name: 'a.pdf', size: 3 * 1024 * 1024 }, { name: 'b.png', size: 3 * 1024 * 1024 }]), /5/);
  assert.doesNotThrow(() => validateUploads([{ name: 'a.pdf', size: 5 * 1024 * 1024 }]));
  assert.throws(() => validateUploads([]), /파일/);
  assert.throws(() => validateUploads([{ name: 'a.exe', size: 1 }]), /형식/);
});

test('excluded historical rows retain missing grade and credit without inventing values', async () => {
  const { parseDocument } = await import('../lib/contracts.ts');
  const doc = {schema_version:1,courses:[{code:'001009',name:'Historic',credit:null,type:'',grade:'',semester:'2030-1',credit_decision:'exclude'}]};
  assert.equal(parseDocument(JSON.stringify(doc),true).courses[0].grade,'');
  doc.courses[0].credit_decision='include';
  assert.throws(() => parseDocument(JSON.stringify(doc),true));
});


test('editing course identity fields invalidates stale matches and synchronizes actual semester', async () => {
  const { editCourse } = await contracts();
  const doc = { schema_version: 1, courses: [{ code: '001001', name: 'Fixture', credit: 3, type: '전필', grade: 'A0', semester: '2021-1', academic_year: 2021, term: '1',
    identification: { status: 'matched', version_id: 9, course_id: 'old' }, sources: [{ file_number: 1 }] }] };
  const next = editCourse(doc, 0, 'semester', '2024-2');
  assert.equal(next.courses[0].identification.status, 'needs_review');
  assert.equal(next.courses[0].identification.version_id, null);
  assert.equal(next.courses[0].academic_year, 2024);
  assert.equal(next.courses[0].term, '2');
  assert.deepEqual(next.courses[0].sources, doc.courses[0].sources);
  assert.equal(doc.courses[0].semester, '2021-1');
});
