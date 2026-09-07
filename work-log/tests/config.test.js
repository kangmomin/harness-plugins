import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import {
  ConfigError,
  DEFAULT_EXCLUDES,
  globalConfigPaths,
  resolveConfig,
} from '../mcp/lib/config.js';

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'work-log-config-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));

  const home = path.join(root, 'home');
  const cwd = path.join(root, 'repo', 'nested');
  const vaults = {
    env: path.join(root, 'vault-env'),
    project: path.join(root, 'vault-project'),
    global: path.join(root, 'vault-global'),
    legacy: path.join(root, 'vault-legacy'),
  };
  fs.mkdirSync(home, { recursive: true });
  fs.mkdirSync(cwd, { recursive: true });
  for (const vault of Object.values(vaults)) fs.mkdirSync(vault, { recursive: true });

  const xdg = path.join(root, 'xdg');
  const env = { XDG_CONFIG_HOME: xdg };
  const paths = globalConfigPaths({ env, home });
  return { root, home, cwd, vaults, xdg, env, paths };
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(value));
}

test('WORK_LOG_ROOT가 project와 global 설정보다 우선한다', (t) => {
  const f = fixture(t);
  writeJson(path.join(f.root, 'repo', '.work-log.json'), {
    scope: 'project', root: f.vaults.project,
  });
  writeJson(f.paths.global, { scope: 'global', root: f.vaults.global });

  const result = resolveConfig({
    cwd: f.cwd,
    home: f.home,
    env: { ...f.env, WORK_LOG_ROOT: f.vaults.env },
  });

  assert.equal(result.root, f.vaults.env);
  assert.equal(result.configSource, 'env:WORK_LOG_ROOT');
});

test('project 설정이 XDG와 legacy 설정보다 우선한다', (t) => {
  const f = fixture(t);
  const projectConfig = path.join(f.root, 'repo', '.work-log.json');
  writeJson(projectConfig, {
    scope: 'project', root: f.vaults.project, excludes: ['drafts'],
  });
  writeJson(f.paths.global, { scope: 'global', root: f.vaults.global });
  writeJson(f.paths.legacy, { scope: 'global', root: f.vaults.legacy });

  const result = resolveConfig({ cwd: f.cwd, home: f.home, env: f.env });

  assert.equal(result.root, f.vaults.project);
  assert.equal(result.configSource, projectConfig);
  assert.deepEqual(result.excludes, ['drafts']);
});

test('XDG 설정이 legacy 설정보다 우선한다', (t) => {
  const f = fixture(t);
  writeJson(f.paths.global, {
    scope: 'global', root: f.vaults.global, excludes: ['private'],
  });
  writeJson(f.paths.legacy, { scope: 'global', root: f.vaults.legacy });

  const result = resolveConfig({ cwd: f.cwd, home: f.home, env: f.env });

  assert.equal(result.root, f.vaults.global);
  assert.equal(result.configSource, f.paths.global);
  assert.deepEqual(result.excludes, ['private']);
});

test('XDG 설정이 없으면 기존 Claude 설정을 읽는다', (t) => {
  const f = fixture(t);
  writeJson(f.paths.legacy, { scope: 'global', root: f.vaults.legacy });

  const result = resolveConfig({ cwd: f.cwd, home: f.home, env: f.env });

  assert.equal(result.root, f.vaults.legacy);
  assert.equal(result.configSource, f.paths.legacy);
  assert.deepEqual(result.excludes, DEFAULT_EXCLUDES);
});

test('손상된 XDG 설정은 legacy로 내려가지 않고 실패한다', (t) => {
  const f = fixture(t);
  fs.mkdirSync(path.dirname(f.paths.global), { recursive: true });
  fs.writeFileSync(f.paths.global, '{broken');
  writeJson(f.paths.legacy, { scope: 'global', root: f.vaults.legacy });

  assert.throws(
    () => resolveConfig({ cwd: f.cwd, home: f.home, env: f.env }),
    (error) => error instanceof ConfigError && error.source === f.paths.global,
  );
});

test('상대 XDG_CONFIG_HOME은 무시하고 ~/.config를 사용한다', (t) => {
  const f = fixture(t);
  const env = { XDG_CONFIG_HOME: 'relative-config' };
  const paths = globalConfigPaths({ env, home: f.home });
  writeJson(paths.global, { scope: 'global', root: f.vaults.global });

  const result = resolveConfig({ cwd: f.cwd, home: f.home, env });

  assert.equal(paths.global, path.join(f.home, '.config', 'work-log', 'config.json'));
  assert.equal(result.configSource, paths.global);
});

test('설정이 없으면 중립 경로가 포함된 init 안내를 반환한다', (t) => {
  const f = fixture(t);

  const result = resolveConfig({ cwd: f.cwd, home: f.home, env: f.env });

  assert.equal(result.needsInit, true);
  assert.equal(result.configSource, null);
  assert.match(result.hint, new RegExp(f.paths.global.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
});

test('잘못된 프로젝트 설정 값은 다른 vault로 fallback하지 않는다', (t) => {
  const f = fixture(t);
  writeJson(f.paths.global, { scope: 'global', root: f.vaults.global });
  const candidate = path.join(f.root, 'repo', '.work-log.json');
  const invalid = [null, false, 0, [], 'config',
    { scope: 'typo', root: f.vaults.project },
    { root: f.vaults.project, excludes: 'private' },
    { root: f.vaults.project, excludes: [null] },
  ];
  for (const value of invalid) {
    writeJson(candidate, value);
    assert.throws(() => resolveConfig({ cwd: f.cwd, home: f.home, env: f.env }),
      (e) => e instanceof ConfigError && e.source === candidate, JSON.stringify(value));
  }
  fs.unlinkSync(candidate);
  assert.equal(resolveConfig({ cwd: f.cwd, home: f.home, env: f.env }).root, f.vaults.global);
});

test('설정 CLI가 공백·한글·URL 예약 문자가 있는 경로에서도 JSON을 출력한다', (t) => {
  const f = fixture(t);
  for (const name of ['plain', 'plugin with space', '플러그인', 'plugin#fragment', 'plugin%encoded']) {
    const dir = path.join(f.root, name);
    fs.mkdirSync(dir);
    fs.writeFileSync(path.join(dir, 'package.json'), '{"type":"module"}');
    const cli = path.join(dir, 'config.js');
    fs.copyFileSync(fileURLToPath(new URL('../mcp/lib/config.js', import.meta.url)), cli);
    const result = spawnSync(process.execPath, [cli], {
      cwd: f.cwd, env: { ...process.env, WORK_LOG_ROOT: f.vaults.env }, encoding: 'utf8',
    });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(JSON.parse(result.stdout).root, f.vaults.env, name);
  }
});
