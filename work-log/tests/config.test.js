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
  projectVaultPath,
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

test('명시적인 flat root 전환은 기존 프로젝트 설정을 보존하고 CLI에도 같은 root를 전달한다', (t) => {
  const f = fixture(t);
  const projectConfig = path.join(f.root, 'repo', '.work-log.json');
  writeJson(projectConfig, { scope: 'project', root: f.vaults.project });
  const original = fs.readFileSync(projectConfig, 'utf8');
  const env = { ...process.env, ...f.env, WORK_LOG_ROOT: f.vaults.global };
  const cli = fileURLToPath(new URL('../mcp/lib/config.js', import.meta.url));
  const result = spawnSync(process.execPath, [cli], { encoding: 'utf8', cwd: f.cwd, env });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.equal(JSON.parse(result.stdout).root, f.vaults.global);
  assert.equal(resolveConfig({ cwd: f.cwd, home: f.home, env }).root, f.vaults.global);
  assert.equal(fs.readFileSync(projectConfig, 'utf8'), original);
  assert.equal(resolveConfig({ cwd: f.cwd, home: f.home, env: f.env }).root, f.vaults.project);
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

function git(cwd, args, options = {}) {
  const result = spawnSync('git', ['-C', cwd, ...args], { encoding: 'utf8', ...options });
  assert.equal(result.status, 0, result.error?.message || result.stderr);
  return result.stdout.trim();
}

function gitFixture(t) {
  const f = fixture(t);
  const repo = path.join(f.root, 'repo');
  git(repo, ['init']);
  return { ...f, repo };
}

test('중앙 프로젝트 경로 계산은 동명 저장소를 분리하고 파일을 만들지 않는다', (t) => {
  const f = gitFixture(t);
  const other = path.join(f.root, 'other', 'repo');
  fs.mkdirSync(other, { recursive: true });
  git(other, ['init']);
  const a = projectVaultPath({ baseRoot: f.vaults.global, projectDir: f.cwd });
  const b = projectVaultPath({ baseRoot: f.vaults.global, projectDir: other });

  assert.notEqual(a.root, b.root);
  assert.equal(a.configDir, fs.realpathSync(f.repo));
  assert.equal(a.identity, fs.realpathSync(path.join(f.repo, '.git')));
  assert.match(a.projectKey, /^repo-[a-f0-9]{16}$/);
  assert.deepEqual(fs.readdirSync(f.vaults.global), []);
  assert.equal(resolveConfig({ cwd: f.cwd, home: f.home, env: f.env }).needsInit, true);
});

test('상속된 Git 환경변수로 다른 저장소의 vault나 설정 위치를 선택하지 않는다', (t) => {
  const f = gitFixture(t);
  const other = path.join(f.root, 'other');
  fs.mkdirSync(other);
  git(other, ['init']);
  const expected = projectVaultPath({ baseRoot: f.vaults.global, projectDir: f.cwd });
  const cli = fileURLToPath(new URL('../mcp/lib/config.js', import.meta.url));
  const result = spawnSync(process.execPath, [cli, '--project-vault', f.vaults.global, '--project-dir', f.cwd], {
    encoding: 'utf8',
    env: {
      ...process.env,
      GIT_DIR: path.join(other, '.git'),
      GIT_WORK_TREE: other,
      GIT_COMMON_DIR: path.join(other, '.git'),
      GIT_CEILING_DIRECTORIES: f.repo,
    },
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const actual = JSON.parse(result.stdout);
  assert.equal(actual.root, expected.root);
  assert.equal(actual.configDir, expected.configDir);
  assert.equal(actual.identity, expected.identity);
});

test('하위 디렉토리·심볼릭 별칭·이름이 다른 worktree는 같은 중앙 경로를 선택한다', (t) => {
  const f = gitFixture(t);
  const tree = git(f.repo, ['mktree'], { input: '' });
  const commit = git(f.repo, ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
    'commit-tree', tree], { input: 'fixture\n' });
  const worktree = path.join(f.root, 'different-worktree-name');
  git(f.repo, ['worktree', 'add', '--detach', worktree, commit]);
  const alias = path.join(f.root, 'alias');
  fs.symlinkSync(f.repo, alias);
  const select = (projectDir) => projectVaultPath({ baseRoot: f.vaults.global, projectDir });
  const expected = select(f.repo);

  assert.equal(select(f.cwd).root, expected.root);
  assert.equal(select(alias).root, expected.root);
  assert.equal(select(worktree).root, expected.root);
  assert.equal(select(worktree).configDir, fs.realpathSync(worktree));
});

test('비Git 프로젝트와 한글·공백 이름을 안전한 단일 폴더명으로 계산한다', (t) => {
  const f = fixture(t);
  for (const name of ['한글 프로젝트', '---', 'a'.repeat(80)]) {
    const projectDir = path.join(f.root, name);
    fs.mkdirSync(projectDir);
    const selected = projectVaultPath({ baseRoot: f.vaults.global, projectDir });
    assert.equal(selected.identity, fs.realpathSync(projectDir));
    assert.equal(selected.configDir, fs.realpathSync(projectDir));
    assert.equal(path.dirname(selected.root), fs.realpathSync(f.vaults.global));
    assert.ok(selected.projectKey.length <= 65);
    assert.match(selected.projectKey, /^[\p{L}\p{N}_-]+-[a-f0-9]{16}$/u);
  }
});

test('중앙 base 별칭은 허용하되 프로젝트 폴더 symlink·파일·플러그인 소스는 거부한다', (t) => {
  const f = fixture(t);
  const baseAlias = path.join(f.root, 'base-alias');
  fs.symlinkSync(f.vaults.global, baseAlias);
  const selected = projectVaultPath({ baseRoot: baseAlias, projectDir: f.cwd });
  assert.equal(selected.baseRoot, fs.realpathSync(f.vaults.global));
  fs.symlinkSync(f.vaults.env, selected.root);
  assert.throws(() => projectVaultPath({ baseRoot: baseAlias, projectDir: f.cwd }), /심볼릭 링크/);
  fs.unlinkSync(selected.root);
  fs.writeFileSync(selected.root, 'file');
  assert.throws(() => projectVaultPath({ baseRoot: baseAlias, projectDir: f.cwd }), /디렉토리/);
  fs.unlinkSync(selected.root);
  fs.mkdirSync(selected.root);
  fs.mkdirSync(path.join(selected.root, '.claude-plugin'));
  assert.throws(() => projectVaultPath({ baseRoot: baseAlias, projectDir: f.cwd }), /플러그인 소스/);
  assert.throws(() => projectVaultPath({ baseRoot: 'relative', projectDir: f.cwd }), /절대경로/);
  assert.throws(() => projectVaultPath({ baseRoot: f.vaults.global, projectDir: path.join(f.root, 'missing') }));
});

test('손상된 Git 메타데이터를 비Git 프로젝트로 fallback하지 않는다', (t) => {
  const f = fixture(t);
  fs.writeFileSync(path.join(f.root, 'repo', '.git'), 'gitdir: missing-git-dir\n');
  assert.throws(() => projectVaultPath({ baseRoot: f.vaults.global, projectDir: f.cwd }), /Git 프로젝트 식별 실패/);
});

test('프로젝트 경로 CLI는 계산만 수행하고 잘못된 옵션을 거부한다', (t) => {
  const f = fixture(t);
  const cli = fileURLToPath(new URL('../mcp/lib/config.js', import.meta.url));
  const result = spawnSync(process.execPath, [cli, '--project-vault', f.vaults.global, '--project-dir', f.cwd], {
    encoding: 'utf8', cwd: f.cwd,
  });
  assert.equal(result.status, 0, result.stderr);
  const selected = JSON.parse(result.stdout);
  assert.equal(selected.root, projectVaultPath({ baseRoot: f.vaults.global, projectDir: f.cwd }).root);
  assert.equal(fs.existsSync(selected.root), false);
  const bad = spawnSync(process.execPath, [cli, '--project-vault', f.vaults.global], { encoding: 'utf8' });
  assert.equal(bad.status, 1);
  assert.match(JSON.parse(bad.stdout).error, /사용법/);
});
