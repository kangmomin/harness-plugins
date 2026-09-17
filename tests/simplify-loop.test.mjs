import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const vectors = JSON.parse(await readFile(new URL('./fixtures/simplify-arbiter.json', import.meta.url), 'utf8'));
const perspectives = ['Correctness', 'Readability', 'Performance', 'Stability'];
const candidate = { file: 'src/example.js', line: 20, summary: 'Remove redundant branch', current: 'if (items.length) return items[0];', proposed: 'return items[0];', rationale: 'Caller guards empty input' };
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

for (const product of ['be-harness', 'fe-harness']) {
  const document = await readFile(new URL(`../${product}/skills/simplify-loop/references/workflow-script.md`, import.meta.url), 'utf8');
  const source = document.match(/```javascript\n([\s\S]*?)\n```/)[1];
  const execute = new AsyncFunction('args', 'agent', 'parallel', 'phase', 'log', source.replace('export const meta', 'const meta'));

  async function run({ votes = ['KEEP', 'CHANGE', 'CHANGE', 'CHANGE'], ruling = vectors.ruling, response, missingDa = false, missingReview = false, mixed = false } = {}) {
    const calls = [];
    const agent = async (prompt, options) => {
      calls.push({ prompt, ...options });
      const label = options.label;
      if (label.startsWith('scan')) return label === 'scan#1'
        ? { diffEmpty: false, totalFound: mixed ? 2 : 1, candidates: mixed ? [candidate, { ...candidate, file: 'src/other.js' }] : [candidate] }
        : { diffEmpty: false, totalFound: 0, candidates: [] };
      if (label.startsWith('review:') || label.startsWith('review-retry:')) {
        const perspective = label.split(':')[1].split('#')[0];
        if (missingReview && perspective === 'Correctness') return { verdicts: [] };
        return { verdicts: options.schema.properties.verdicts.items.properties.candidateId.enum.map(candidateId => ({ candidateId,
          verdict: mixed && candidateId === 'i1-c2' ? 'CHANGE' : votes[perspectives.indexOf(perspective)],
          confidence: 'High', rationale: `${perspective} rationale`, risks: `${perspective}: empty input behavior at src/example.js:20`,
        })) };
      }
      if (label.startsWith('devils-advocate')) return missingDa ? null : { dissents: options.schema.properties.dissents.items.properties.candidateId.enum.map(candidateId => ({ candidateId, reasonsToKeep: 'Preserve empty input', riskScenario: 'Empty input', alternative: 'Keep guard', strength: 'Strong' })) };
      if (label.startsWith('arbiter')) return response !== undefined ? response : ruling === null ? null : { rulings: [ruling] };
      if (label.startsWith('apply')) return { results: options.schema.properties.results.items.properties.candidateId.enum.map(candidateId => ({ candidateId, result: 'APPLIED' })) };
      throw new Error(`Unexpected agent ${label}`);
    };
    const result = await execute({ diffCommand: 'scope-fixture', maxIterations: 4, candidateCap: 8, retryLimit: 1 }, agent, tasks => Promise.all(tasks.map(task => task())), () => {}, () => {});
    return { result, calls };
  }

  test(`${product}: every minority perspective reaches Arbiter with raw risks before writer`, async () => {
    for (const perspective of perspectives) {
      const votes = perspectives.map(p => p === perspective ? 'KEEP' : 'CHANGE');
      const { result, calls } = await run({ votes });
      assert.equal(result.applied.length, 1);
      const arbitration = calls.findIndex(c => c.label.startsWith('arbiter'));
      assert.ok(arbitration >= 0);
      assert.ok(calls.findIndex(c => c.label.startsWith('apply')) > arbitration);
      assert.ok(!calls.some(c => c.label.startsWith('devils-advocate')));
      for (const p of perspectives) assert.ok(calls[arbitration].prompt.includes(`${p}: empty input behavior`));
      assert.equal(result.iterLog[0].candidates[0].arbiter.evidence, vectors.ruling.evidence);
    }
  });

  test(`${product}: conditional minority cannot bypass unresolved objection`, async () => {
    const { result, calls } = await run({ votes: ['CONDITIONAL', 'CHANGE', 'CHANGE', 'CHANGE'], ruling: { ...vectors.ruling, objectionsResolved: false } });
    assert.equal(result.applied.length, 0);
    assert.equal(result.holds.length, 1);
    assert.ok(!calls.some(c => c.label.startsWith('apply')));
  });

  for (const vector of vectors.cases) test(`${product}: ${vector.name}`, async () => {
    const ruling = { ...vectors.ruling, ...vector.patch };
    if (vector.omit) delete ruling[vector.omit];
    const { result, calls } = await run({ ruling });
    assert.equal(result.applied.length, vector.expected === 'APPROVED' ? 1 : 0);
    if (vector.expected === 'ARBITER_FAILURE') {
      assert.equal(result.status, 'BLOCKED:REVIEW_INCOMPLETE');
      assert.match(result.holds[0].reason, /ARBITER_FAILURE/);
      assert.equal(calls.filter(c => c.label.startsWith('arbiter')).length, 2);
    } else if (vector.expected === 'HOLD') assert.equal(result.holds.length, 1);
    else if (vector.expected === 'RECONSIDER') assert.equal(result.rejected[0].kind, 'RECONSIDER');
  });

  test(`${product}: unanimous DA path also requires resolved evidence`, async () => {
    for (const objectionsResolved of [true, false]) {
      const { result, calls } = await run({ votes: Array(4).fill('CHANGE'), ruling: { ...vectors.ruling, objectionsResolved } });
      assert.equal(result.applied.length, objectionsResolved ? 1 : 0);
      const da = calls.findIndex(c => c.label.startsWith('devils-advocate'));
      assert.ok(da >= 0);
      assert.ok(calls.findIndex(c => c.label.startsWith('arbiter')) > da);
    }
  });

  test(`${product}: missing DA blocks unanimous candidate without blocking minority arbitration`, async () => {
    const { result, calls } = await run({ mixed: true, missingDa: true });
    assert.deepEqual(result.applied.map(c => c.candidateId), ['i1-c1']);
    assert.equal(result.holds[0].candidateId, 'i1-c2');
    const arb = calls.find(c => c.label.startsWith('arbiter'));
    assert.deepEqual(arb.schema.properties.rulings.items.properties.candidateId.enum, ['i1-c1']);
  });

  test(`${product}: absent reviewer or Arbiter never reaches writer`, async () => {
    for (const input of [{ missingReview: true }, { ruling: null }]) {
      const { result, calls } = await run(input);
      assert.equal(result.status, 'BLOCKED:REVIEW_INCOMPLETE');
      assert.equal(result.applied.length, 0);
      assert.ok(!calls.some(c => c.label.startsWith('apply')));
    }
  });

  test(`${product}: malformed envelopes and ambiguous duplicate rulings fail closed`, async () => {
    const hold = { ...vectors.ruling, verdict: 'HOLD', objectionsResolved: false };
    for (const response of [{}, { rulings: {} }, { rulings: [] },
      { rulings: [vectors.ruling, hold] }, { rulings: [hold, vectors.ruling] },
      { rulings: [vectors.ruling, hold, vectors.ruling] }]) {
      const { result, calls } = await run({ response });
      assert.equal(result.status, 'BLOCKED:REVIEW_INCOMPLETE');
      assert.equal(result.applied.length, 0);
      assert.ok(!calls.some(c => c.label.startsWith('apply')));
    }
  });

  test(`${product}: duplicate ruling blocks only its own candidate`, async () => {
    const response = { rulings: [vectors.ruling, { ...vectors.ruling, verdict: 'HOLD', objectionsResolved: false }, { ...vectors.ruling, candidateId: 'i1-c2' }] };
    const { result } = await run({ mixed: true, response });
    assert.deepEqual(result.applied.map(c => c.candidateId), ['i1-c2']);
    assert.equal(result.holds[0].candidateId, 'i1-c1');
  });

  test(`${product}: at most two CHANGE votes retain hold/reject paths`, async () => {
    for (const count of [0, 1, 2]) {
      const { result, calls } = await run({ votes: perspectives.map((_, i) => i < count ? 'CHANGE' : 'KEEP') });
      assert.equal(result.applied.length, 0);
      assert.ok(!calls.some(c => /^(arbiter|apply|devils-advocate)/.test(c.label)));
      assert.equal(count === 2 ? result.holds.length : result.rejected.length, 1);
    }
  });
}
