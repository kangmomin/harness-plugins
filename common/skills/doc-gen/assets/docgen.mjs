#!/usr/bin/env node
import { createHash, randomUUID } from 'node:crypto';
import { readFile, mkdir, open, lstat, unlink } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import MarkdownIt from 'markdown-it';
import puppeteer from 'puppeteer';
import GithubSlugger from 'github-slugger';

const here = path.dirname(fileURLToPath(import.meta.url));
const hash = value => createHash('sha256').update(value).digest('hex');
const escape = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const md = new MarkdownIt({ html: false, linkify: false, typographer: false });
// Remote images cannot satisfy a standalone artifact. Keep their meaning and
// source visible as text instead of silently fetching or dropping them.
md.renderer.rules.image = (tokens, i) => `<span>${escape(tokens[i].content)} (image: ${escape(tokens[i].attrGet('src'))})</span>`;

export async function launchBrowser() {
  return puppeteer.launch({ headless: true, args: process.env.HARNESS_DOCGEN_NO_SANDBOX === '1' ? ['--no-sandbox'] : [] });
}

export async function renderDiagrams(markdown, browser) {
  const sources = md.parse(markdown, {}).filter(t => t.type === 'fence' && t.info.trim() === 'mermaid').map(t => t.content);
  const page = await browser.newPage();
  const requests = [];
  try {
    await page.setRequestInterception(true);
    page.on('request', request => { requests.push(request.url()); void request.abort(); });
    await page.setContent('<!doctype html><html><body></body></html>');
    await page.addScriptTag({ content: await readFile(path.join(here, 'node_modules/mermaid/dist/mermaid.min.js'), 'utf8') });
    const diagrams = new Map();
    for (const source of sources) {
      if (/^\s*---|%%\{/m.test(source)) throw new Error('Mermaid configuration directives are not supported');
      const key = hash(source);
      const svg = await page.evaluate(async ({ source, key }) => {
        mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'dark',
          htmlLabels: false, flowchart: { htmlLabels: false }, deterministicIds: true, deterministicIDSeed: key });
        const { svg } = await mermaid.render('diagram_' + key, source);
        const xml = new DOMParser().parseFromString(svg, 'image/svg+xml');
        const allowed = new Set(['svg', 'g', 'defs', 'marker', 'path', 'rect', 'circle', 'ellipse',
          'line', 'polyline', 'polygon', 'text', 'tspan', 'style', 'title', 'desc', 'clipPath',
          'linearGradient', 'radialGradient', 'stop', 'use', 'symbol']);
        for (const node of xml.querySelectorAll('*')) {
          if (!allowed.has(node.localName)) throw new Error('Unsupported active SVG element: ' + node.localName);
          for (const attr of node.attributes) {
            if (/^on/i.test(attr.name) || (/(^|:)href$/i.test(attr.name) && !attr.value.startsWith('#')))
              throw new Error('Active or external SVG attribute');
            if (attr.name === 'style' && /\\|@import|url\(\s*["']?[^#\s"']/i.test(attr.value))
              throw new Error('External SVG style');
          }
          if (node.localName === 'style' && /\\|@import|url\(\s*["']?[^#\s"']/i.test(node.textContent))
            throw new Error('External SVG stylesheet');
        }
        return new XMLSerializer().serializeToString(xml.documentElement);
      }, { source, key });
      diagrams.set(key, { source, svg });
    }
    if (requests.length) throw new Error('Diagram attempted a resource request');
    return diagrams;
  } finally { await page.close(); }
}

export function body(markdown, diagrams) {
  const renderer = new MarkdownIt({ html: false, linkify: false, typographer: false });
  renderer.renderer.rules.image = md.renderer.rules.image;
  const fence = renderer.renderer.rules.fence;
  renderer.renderer.rules.fence = (tokens, i, options, env, self) => {
    const token = tokens[i];
    if (token.info.trim() !== 'mermaid') return fence(tokens, i, options, env, self);
    const key = hash(token.content), diagram = diagrams.get(key);
    if (!diagram || diagram.source !== token.content) throw new Error('Missing rendered diagram');
    return `<figure data-mermaid="${key}"><img alt="다이어그램" src="data:image/svg+xml;base64,${Buffer.from(diagram.svg).toString('base64')}"><details><summary>다이어그램 원문</summary><pre><code>${escape(token.content)}</code></pre></details></figure>\n`;
  };
  const tokens = renderer.parse(markdown, {}), slugger = new GithubSlugger(), anchors = new Set();
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].type === 'heading_open') {
      const text = (tokens[i + 1]?.children ?? []).filter(t => ['text', 'code_inline', 'image'].includes(t.type)).map(t => t.content).join('');
      const id = slugger.slug(text);
      tokens[i].attrSet('id', id); anchors.add(id);
    }
  }
  for (const token of tokens) for (const child of token.children ?? []) {
    const href = child.type === 'link_open' ? child.attrGet('href') : null;
    if (href?.startsWith('#') && href.length > 1 && !anchors.has(decodeURIComponent(href.slice(1))))
      throw new Error('Unresolved document fragment: ' + href);
  }
  return renderer.renderer.render(tokens, renderer.options, {});
}

export function htmlDocument(markdown, diagrams) {
  return `<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>기술 문서</title><style>body{margin:0;background:#111827;color:#e5e7eb;font:16px/1.7 system-ui,sans-serif}main{max-width:900px;margin:auto;padding:24px}a{color:#93c5fd}pre,figure,table{overflow:auto}pre,figure{background:#1f2937;padding:16px;border-radius:10px}img{max-width:100%;height:auto}table{border-collapse:collapse;display:block}th,td{border:1px solid #4b5563;padding:8px}code{white-space:pre}h1,h2,h3{line-height:1.3}</style></head><body><main>\n${body(markdown, diagrams)}</main></body></html>\n`;
}

export function verifyTwin(markdown, html, diagrams) {
  // Compare the complete canonical transformation, including prose, table
  // cells, links, code and each source-bound SVG. Header counts aren't evidence.
  if (html !== htmlDocument(markdown, diagrams)) throw new Error('TWIN_MISMATCH: complete content differs');
  return true;
}

export async function publish(directory, outputs, options = {}) {
  await mkdir(directory, { recursive: true });
  const suffix = options.suffix ?? `${Math.floor(Date.now() / 1000)}-${randomUUID()}`;
  if (!/^[a-zA-Z0-9-]+$/.test(suffix)) throw new Error('Invalid output suffix');
  const created = [];
  try {
    for (const [extension, content] of Object.entries(outputs)) {
      if (!['md', 'html'].includes(extension)) throw new Error('Invalid output extension');
      const filename = path.resolve(directory, `doc-gen-${suffix}.${extension}`);
      const handle = await open(filename, 'wx', 0o644);
      try {
        const info = await handle.stat();
        created.push({ filename, dev: info.dev, ino: info.ino });
        await handle.writeFile(content); await handle.sync();
      } finally { await handle.close(); }
    }
    return created.map(entry => entry.filename);
  } catch (error) {
    const cleanup = [];
    for (const entry of created) {
      try {
        const now = await lstat(entry.filename);
        if (now.dev === entry.dev && now.ino === entry.ino) await unlink(entry.filename);
        else cleanup.push(entry.filename + ': owner changed; retained');
      } catch (failure) { if (failure.code !== 'ENOENT') cleanup.push(entry.filename + ': ' + failure.code); }
    }
    error.cleanupWarnings = cleanup; throw error;
  }
}

async function main() {
  const [input, directory, format = 'twin'] = process.argv.slice(2);
  if (!input || !directory || !['md', 'html', 'twin'].includes(format))
    throw new Error('Usage: node docgen.mjs SOURCE.md OUTPUT_DIRECTORY [md|html|twin]');
  const markdown = await readFile(input, 'utf8');
  const browser = await launchBrowser();
  try {
    const diagrams = await renderDiagrams(markdown, browser);
    const html = htmlDocument(markdown, diagrams);
    verifyTwin(markdown, html, diagrams);
    const outputs = format === 'md' ? { md: markdown } : format === 'html' ? { html } : { md: markdown, html };
    const paths = await publish(directory, outputs);
    console.log(JSON.stringify({ status: 'DONE', paths, diagrams: diagrams.size, offline: true }));
  } finally { await browser.close(); }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href)
  main().catch(error => { console.error(JSON.stringify({ status: 'FAIL', reason: error.message, cleanupWarnings: error.cleanupWarnings ?? [] })); process.exitCode = 1; });
