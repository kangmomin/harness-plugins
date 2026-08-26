import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

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
