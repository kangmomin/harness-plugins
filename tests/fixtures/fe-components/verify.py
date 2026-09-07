#!/usr/bin/env python3
"""Generate current templates, then use installed compilers/runners. No downloads."""
import importlib.util
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('component_templates', ROOT / 'fe-harness/skills/component/assets/component_templates.py')
templates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(templates)


def verify():
    modules = HERE / 'node_modules'
    if not (modules / '.bin/vitest').is_file():
        raise RuntimeError('Install the pinned fixture dependencies with npm ci first; verify never downloads')
    observed = []
    with tempfile.TemporaryDirectory(prefix='harness-components-') as directory:
        root = Path(directory)
        (root / 'node_modules').symlink_to(modules, target_is_directory=True)
        (root / 'package.json').write_text('{"type":"module"}')
        exports, cases = [], []
        for framework, ts, runner in itertools.product(('nextjs', 'vite', 'cra', 'nuxt'), (True, False), ('vitest', 'jest')):
            if framework == 'nuxt' and runner == 'jest':
                try:
                    templates.templates('Unsupported', framework, ts, runner)
                except ValueError:
                    observed.append(dict(framework=framework, typescript=ts, runner=runner, verdict='BLOCKED_BEFORE_WRITE'))
                    continue
                raise AssertionError('Vue/Jest must not silently emit React templates')
            name = framework.title() + ('TypeScript' if ts else 'JavaScript') + runner.title()
            folder = root / name
            folder.mkdir()
            output = templates.templates(name, framework, ts, runner, storybook=True)
            for filename, content in output['files'].items():
                (folder / filename).write_text(content)
            exports.append(f"export {{ {name} }} from './{name}/index';")
            cases.append(dict(framework=framework, typescript=ts, runner=runner, name=name))
        # Exercise the two templates that emit separate style files as well.
        for framework, ui in (('vite', 'styled-components'), ('vite', 'css-modules'), ('nuxt', 'css-modules')):
            name = framework.title() + ui.title().replace('-', '') + 'Vitest'
            folder = root / name
            folder.mkdir()
            for filename, content in templates.templates(name, framework, True, 'vitest', ui=ui)['files'].items():
                (folder / filename).write_text(content)
            exports.append(f"export {{ {name} }} from './{name}/index';")
        (root / 'index.ts').write_text('\n'.join(exports))
        (root / 'styles.d.ts').write_text("declare module '*.module.css' { const styles: Record<string, string>; export default styles; }\n")
        (root / 'tsconfig.json').write_text(json.dumps(dict(compilerOptions=dict(target='ES2022', module='ESNext', moduleResolution='Bundler', jsx='react-jsx', strict=True, noEmit=True, skipLibCheck=True, esModuleInterop=True, allowJs=True, checkJs=False, lib=['ES2022', 'DOM']), include=['**/*.ts', '**/*.tsx', '**/*.vue', '**/*.js', '**/*.jsx'])))
        (root / 'vite.config.mjs').write_text("""import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import vue from '@vitejs/plugin-vue';
export default defineConfig({
  plugins: [react(), vue()],
  build: { lib: { entry: './index.ts', formats: ['es'], fileName: 'components' }, rollupOptions: { external: ['react', 'react/jsx-runtime', 'vue', 'styled-components'] } },
  test: { globals: false, environment: 'jsdom', include: ['*Vitest/*.test.*'], maxWorkers: 1, fileParallelism: false }
});
""")
        (root / 'babel.config.cjs').write_text("module.exports = { presets: [['@babel/preset-env', {targets: {node: 'current'}}], ['@babel/preset-react', {runtime: 'automatic'}], '@babel/preset-typescript'] };\n")
        (root / 'jest.config.cjs').write_text("module.exports = { testEnvironment: 'jsdom', testMatch: ['**/*Jest/*.test.*'], transform: {'^.+\\\\.[jt]sx?$': 'babel-jest'} };\n")
        for label, argv in (
            ('build', ['vite', 'build']),
            ('typecheck', ['vue-tsc', '--noEmit']),
            ('vitest', ['vitest', 'run', '--reporter=verbose']),
            ('jest', ['jest', '--runInBand', '--verbose']),
        ):
            result = subprocess.run([str(modules / '.bin' / argv[0]), *argv[1:]], cwd=root, text=True, capture_output=True, timeout=180,
                                    env={**os.environ, 'NO_COLOR': '1', 'CI': '1'})
            print(result.stdout, end='')
            print(result.stderr, end='', file=sys.stderr)
            if result.returncode:
                raise RuntimeError(label + ' failed')
            observed.append(dict(check=label, verdict='PASS'))
        for case in cases:
            observed.append({**case, 'verdict': 'PASS'})
    versions = {name: json.loads((modules / name / 'package.json').read_text())['version'] for name in ('vue', 'react', 'vite', 'typescript', 'vue-tsc', 'vitest', 'jest')}
    print(json.dumps(dict(versions=versions, cases=observed, scope='Framework-neutral components: React JSX and Nuxt-compatible Vue SFC; no Next/Nuxt/CRA application/router or Storybook UI build'), indent=2))


if __name__ == '__main__':
    verify()
