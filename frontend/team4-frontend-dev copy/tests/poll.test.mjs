import test from 'node:test';
import assert from 'node:assert/strict';

test('polling deadline aborts a stalled read and unmount cancellation stops timers', async () => {
  const { pollTranscript } = await import('../lib/poll.ts');
  let observed;
  await assert.rejects(pollTranscript(signal => { observed = signal; return new Promise(() => {}); }, { timeoutMs: 15 }), /시간/);
  assert.equal(observed.aborted, true);
  const controller = new AbortController();
  let count = 0;
  const job = pollTranscript(async () => { count++; return { id: 42, status: 'processing' }; }, { intervalMs: 100, signal: controller.signal });
  setTimeout(() => controller.abort(), 5);
  await assert.rejects(job, { name: 'AbortError' });
  assert.equal(count, 1);
});

test('polling stops on OCR error for manual editing, never loops forever', async () => {
  const { pollTranscript } = await import('../lib/poll.ts');
  let count = 0;
  const result = await pollTranscript(async () => ({ id: 42, status: ++count === 2 ? 'error' : 'processing', error_message: 'OCR unavailable' }), { intervalMs: 1, timeoutMs: 100 });
  assert.equal(count, 2);
  assert.equal(result.status, 'error');
});
