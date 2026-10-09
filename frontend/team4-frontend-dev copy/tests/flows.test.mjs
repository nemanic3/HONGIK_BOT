import test from 'node:test';
import assert from 'node:assert/strict';

test('confirmation posts the full versioned document then verifies confirmed detail', async () => {
  const { confirmTranscript, getReport, saveProfile } = await import('../lib/flows.ts');
  const calls = [];
  const doc = { schema_version: 1, source: 'manual', courses: [{ code: '000007', name: 'Course', credit: 1.5, type: '전필', grade: 'P', semester: '2024-1', transfer: null }] };
  const client = { me: async () => ({ id: 42, major: '컴퓨터공학과', admission_year: 2024, accreditation_track: 'accredited' }), request: async (path, init) => { calls.push([path, init]); return path.includes('/detail/') ? { id: 77, confirmed_at: '2026-10-09', document: doc } : {}; } };
  assert.equal((await confirmTranscript(client, '77', doc)).id, 77);
  assert.equal(calls[0][0], '/api/transcripts/confirm/77/');
  assert.deepEqual(JSON.parse(calls[0][1].body), doc);
  assert.equal(calls[1][0], '/api/transcripts/detail/77/');
  await assert.rejects(confirmTranscript({ ...client, request: async () => ({ id: 77 }) }, '77', doc), /확정/);
  await saveProfile(client, '2024', 'accredited', '컴퓨터공학과');
  assert.equal(calls[2][0], '/api/users/update-profile/');
  assert.equal(calls[2][1].method, 'PATCH');
  await getReport(client, '77');
  assert.equal(calls.at(-1)[0], '/api/analysis/report/?transcript_id=77');
});

test('confirmation rejects incomplete drafts locally; corrected draft posts the full metadata-bearing document', async () => {
  const { confirmTranscript } = await import('../lib/flows.ts');
  const { parseDocument, editCourse } = await import('../lib/contracts.ts');
  const calls = [];
  const row = { code: '000007', name: 'Course', credit: 1.5, type: '전필', grade: 'P', semester: '2024-1', confidence: 0.4, retake: false, academic_year: 2024, term: '1', major_field: 'CS', aliases: ['Original'] };
  const doc = { schema_version: 1, source: { pages: [2] }, courses: [row] };
  const client = { request: async (path, init) => { calls.push([path, init]); return { id: 77, confirmed_at: '2026-10-09' }; } };
  for (const [field, value] of [['name', ''], ['type', ' '], ['grade', ''], ['semester', ''], ['semester', null], ['credit', null]]) {
    await assert.rejects(confirmTranscript(client, '77', { ...doc, courses: [{ ...row, [field]: value }] }), /필요|학점|semester/);
  }
  assert.equal(calls.length, 0);
  const draft = parseDocument(JSON.stringify({ ...doc, courses: [{ ...row, credit: null, semester: null }] }));
  const edited = editCourse(editCourse(draft, 0, 'credit', '1.5'), 0, 'semester', '2024-1');
  await confirmTranscript(client, '77', edited);
  assert.deepEqual(JSON.parse(calls[0][1].body), doc);
});

test('profile correction sends explicit major and verifies the server readback', async () => {
  const { saveProfile } = await import('../lib/flows.ts');
  const calls = [];
  const client = { request: async (path, init) => { calls.push([path, init]); }, me: async () => ({ id: 42, major: '컴퓨터공학과', admission_year: 2024, accreditation_track: 'accredited' }) };
  await assert.rejects(saveProfile(client, '2024', 'accredited', ''), /학과|전공/);
  await assert.rejects(saveProfile(client, '2024', 'accredited', '컴퓨터데이터공학부'), /학과|전공/);
  assert.equal(calls.length, 0, 'ambiguous major must not be guessed or sent');
  await saveProfile(client, '2024', 'accredited', '컴퓨터공학과');
  assert.equal(calls[0][0], '/api/users/update-profile/');
  assert.deepEqual(JSON.parse(calls[0][1].body), { admission_year: 2024, accreditation_track: 'accredited', major: '컴퓨터공학과' });
  await assert.rejects(saveProfile({ ...client, me: async () => ({ major: '컴퓨터데이터공학부', admission_year: 2024, accreditation_track: 'accredited' }) }, '2024', 'accredited', '컴퓨터공학과'), /저장 결과/);
});

test('upload uses authenticated /me/ identity, files multipart and OCR failure ID recovery', async () => {
  const { uploadTranscript } = await import('../lib/flows.ts');
  const calls = [];
  const client = { me: async () => ({ id: 42 }), request: async (path, init) => { calls.push([path, init]); return { transcript_id: 77, status: 'processing' }; } };
  const file = new File(['pdf'], 'page.pdf');
  assert.equal((await uploadTranscript(client, [file])).transcript_id, '77');
  assert.equal(calls[0][0], '/api/transcripts/42/');
  assert.equal(calls[0][1].body.getAll('files').length, 1);
  assert.equal(calls[0][1].headers, undefined);
});
