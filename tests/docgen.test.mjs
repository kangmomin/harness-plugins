import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile, readdir } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { body, htmlDocument, launchBrowser, publish, renderDiagrams, verifyTwin } from '../common/skills/doc-gen/assets/docgen.mjs';

const markdown = `# 오프라인 검증

[흐름으로 이동](#핵심-흐름) / [두 번째 제목](#핵심-흐름-1)

## 핵심 흐름

본문 <script>globalThis.injected = true</script> & 특수문자.

| 항목 | 결과 |
|---|---|
| 값 | 42 |

\`\`\`js
const answer = 42;
\`\`\`

![원격 이미지](https://example.invalid/tracker.png)

\`\`\`mermaid
flowchart TD
  A["입력 & 검증"] --> B["저장 (완료)"]
\`\`\`

\`\`\`mermaid
sequenceDiagram
  participant U as 사용자
  participant S as 서비스
  U->>S: 요청 & 확인
  S-->>U: 완료
\`\`\`

## 핵심 흐름
`;
let browser, diagrams, directory;
before(async () => {
  directory = await mkdtemp(path.join(os.tmpdir(), 'harness-docgen-'));
  browser = await launchBrowser();
  diagrams = await renderDiagrams(markdown, browser);
});
after(async () => { await browser?.close(); if (directory) await rm(directory, { recursive: true, force: true }); });

test('actual flowchart and sequence SVG open offline without scripts or external requests', async () => {
  const html = htmlDocument(markdown, diagrams);
  assert.equal(diagrams.size, 2);
  assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('&lt;script&gt;'));
  assert.ok(!html.includes('securityLevel:'));
  const [filename] = await publish(directory, { html });
  const page = await browser.newPage();
  const external = [];
  try {
    await page.setOfflineMode(true);
    await page.setRequestInterception(true);
    page.on('request', request => {
      if (/^(file:|data:|about:)/.test(request.url())) void request.continue();
      else { external.push(request.url()); void request.abort(); }
    });
    await page.goto(pathToFileURL(filename).href, { waitUntil: 'load' });
    const result = await page.evaluate(() => ({
      images: [...document.images].map(image => ({ complete: image.complete, width: image.naturalWidth, height: image.naturalHeight })),
      injected: globalThis.injected, text: document.body.textContent,
      fragments: [...document.querySelectorAll('a[href^="#"]')].map(a => Boolean(document.getElementById(decodeURIComponent(a.hash.slice(1))))),
    }));
    assert.equal(result.images.length, 2);
    assert.ok(result.images.every(image => image.complete && image.width > 10 && image.height > 10));
    assert.equal(result.injected, undefined);
    assert.deepEqual(result.fragments, [true, true]);
    assert.ok(result.text.includes('const answer = 42;'));
    assert.ok(result.text.includes('사용자'));
    assert.deepEqual(external, []);
  } finally { await page.close(); }
});

test('full twin comparison detects prose code and table edits under unchanged headings', () => {
  const html = htmlDocument(markdown, diagrams);
  assert.ok(verifyTwin(markdown, html, diagrams));
  for (const changed of [html.replace('본문', '다른 본문'), html.replace('const answer = 42;', 'const answer = 43;'), html.replace('<td>42</td>', '<td>43</td>')]) {
    assert.notEqual(changed, html);
    assert.throws(() => verifyTwin(markdown, changed, diagrams), /TWIN_MISMATCH/);
  }
  assert.throws(() => body(markdown.replace('입력 & 검증', '변경'), diagrams), /Missing rendered diagram/);
  assert.throws(() => body('[missing](#absent)', new Map()), /Unresolved document fragment/);
});

test('invalid Mermaid and injected config fail before any publication', async () => {
  for (const source of ['flowchart TD\n A -->[ broken', '%%{init: {"securityLevel":"loose"}}%%\nflowchart TD\n A-->B']) {
    await assert.rejects(renderDiagrams('```mermaid\n' + source + '\n```\n', browser));
  }
});

test('concurrent exclusive twins never overwrite another output', async () => {
  const groups = await Promise.all(Array.from({ length: 20 }, (_, i) => publish(directory, { md: `run ${i}`, html: `html ${i}` })));
  assert.equal(new Set(groups.flat()).size, 40);
  for (let i = 0; i < groups.length; i++) {
    assert.equal(await readFile(groups[i][0], 'utf8'), `run ${i}`);
    assert.equal(await readFile(groups[i][1], 'utf8'), `html ${i}`);
  }
});

test('second file collision preserves existing file and removes only own partial twin', async () => {
  const collision = path.join(directory, 'doc-gen-collision.html');
  await writeFile(collision, 'existing user output');
  await assert.rejects(publish(directory, { md: 'partial', html: 'new' }, { suffix: 'collision' }), { code: 'EEXIST' });
  assert.equal(await readFile(collision, 'utf8'), 'existing user output');
  assert.ok(!(await readdir(directory)).includes('doc-gen-collision.md'));
  const original = path.join(directory, 'doc-gen-original.md');
  await writeFile(original, 'existing markdown');
  await assert.rejects(publish(directory, { md: 'new', html: 'new' }, { suffix: 'original' }), { code: 'EEXIST' });
  assert.equal(await readFile(original, 'utf8'), 'existing markdown');
});
