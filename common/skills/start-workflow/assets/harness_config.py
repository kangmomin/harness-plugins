#!/usr/bin/env python3
"""harness_config.py — 공통 설정 파일(.claude/harness.config.json) 결정적 resolve.

be/fe/common start-workflow 가 Pre-flight 에서 1회 실행한다. 읽기 전용이며 파일을 쓰지 않는다.
  python3 harness_config.py resolve --cwd DIR --codex-mode MODE --codex-source SOURCE \
      [--e2e-enabled true|false] [--reflect]
우선순위: CLI 플래그 > harness.config.json > profile > 기본값.
"""
import argparse
import json
from pathlib import Path
import re
import sys

CONFIG_PATH = Path('.claude') / 'harness.config.json'
ENGINES = ('codex', 'gemini', 'claude')
CODEX_MODES = ('none', 'mix', 'max')
# 첫 글자를 영숫자로 제한한다: '-' 로 시작하면 gemini CLI 가 모델명이 아니라 플래그(--yolo 등)로 읽는다.
MODEL = re.compile(r'^(?:[A-Za-z0-9][A-Za-z0-9._:/-]*)?$')
# 허용 키 트리. dict = 하위 객체, 그 외 = 값 종류.
SCHEMA = {
    'version': 'version',
    'review': {
        'enabled': 'bool',
        'engine': 'engine',
        'points': {'plan': 'bool', 'quality': 'bool'},
        'gemini': {'model': 'model'},
    },
    'steps': {'ocr': 'bool', 'e2e': 'bool', 'simplifyLoop': 'bool', 'reflect': 'bool'},
}


def valid(kind, value):
    if kind == 'bool':
        return isinstance(value, bool)
    if kind == 'engine':
        return value in ENGINES
    if kind == 'model':
        return isinstance(value, str) and bool(MODEL.match(value))
    if kind == 'version':
        return value == 1
    return False


def flatten(node, schema, prefix, out, diagnostics):
    """유효한 leaf 만 dotted key 로 모은다. 무효 키는 그 키만 버리고 진단을 남긴다."""
    for key, value in node.items():
        path = prefix + key
        kind = schema.get(key)
        if kind is None:
            diagnostics.append({'code': 'UNKNOWN_KEY', 'key': path})
        elif isinstance(kind, dict):
            if isinstance(value, dict):
                flatten(value, kind, path + '.', out, diagnostics)
            else:
                diagnostics.append({'code': 'INVALID_KEY', 'key': path})
        elif valid(kind, value):
            out[path] = value
        else:
            diagnostics.append({'code': 'INVALID_KEY', 'key': path})


def load(cwd):
    path = Path(cwd) / CONFIG_PATH
    diagnostics = []
    if not path.is_file():
        return {}, diagnostics, None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        # 파싱 실패 = 파일 전체 무시. 일부만 신뢰하면 토글 의미가 뒤섞인다.
        return {}, [{'code': 'PARSE_ERROR', 'key': str(CONFIG_PATH), 'detail': str(exc)}], str(path)
    if not isinstance(data, dict):
        return {}, [{'code': 'PARSE_ERROR', 'key': str(CONFIG_PATH), 'detail': 'root is not an object'}], str(path)
    flat = {}
    flatten(data, SCHEMA, '', flat, diagnostics)
    return flat, diagnostics, str(path)


def resolve(cwd, codex_mode, codex_source, e2e_enabled=None, reflect_flag=False):
    flat, diagnostics, path = load(cwd)
    values, sources = {}, {}

    def pick(name, key, fallback, fallback_source):
        if key in flat:
            values[name], sources[name] = flat[key], 'config'
        else:
            values[name], sources[name] = fallback, fallback_source

    # codexMode: 명시 입력(--codex 플래그·질문 응답 = source flag)이 가장 우선.
    # config 가 실제로 codex 리뷰어를 남길 때만 profile none 을 mix 로 올린다.
    mode, mode_source = codex_mode, codex_source
    wants_codex = (flat.get('review.enabled', True) and flat.get('review.engine') == 'codex'
                   and (flat.get('review.points.plan', True) or flat.get('review.points.quality', True)))
    if mode == 'none' and codex_source != 'flag' and wants_codex:
        mode, mode_source = 'mix', 'config'
    values['codexMode'], sources['codexMode'] = mode, mode_source

    pick('review.enabled', 'review.enabled', True, 'default')
    default_engine = 'claude' if mode == 'none' else 'codex'
    pick('review.engine', 'review.engine', default_engine, 'profile' if codex_source == 'profile' else 'default')
    if mode == 'none' and values['review.engine'] == 'codex':
        # none 인데 codex 엔진이 남는 경우: 명시 none 이 이겼거나(진단) 리뷰가 꺼져 있어 쓰이지 않는다.
        values['review.engine'] = 'claude'
        sources['review.engine'] = 'flag' if codex_source == 'flag' else sources['review.engine']
        if codex_source == 'flag' and wants_codex:
            diagnostics.append({'code': 'CODEX_DISABLED_BY_FLAG', 'key': 'review.engine'})
    for point in ('plan', 'quality'):
        pick('review.points.' + point, 'review.points.' + point, True, 'default')
    pick('review.gemini.model', 'review.gemini.model', '', 'default')

    pick('steps.ocr', 'steps.ocr', True, 'default')
    pick('steps.e2e', 'steps.e2e', True if e2e_enabled is None else e2e_enabled,
         'default' if e2e_enabled is None else 'profile')
    pick('steps.simplifyLoop', 'steps.simplifyLoop', True, 'default')
    pick('steps.reflect', 'steps.reflect', False, 'default')
    if reflect_flag:
        values['steps.reflect'], sources['steps.reflect'] = True, 'flag'

    # 리뷰 off = 건너뛰기가 아니라 Claude 패널. 지점별 실행 주체를 확정한다.
    reviewers = {}
    for point in ('plan', 'quality'):
        on = values['review.enabled'] and values['review.points.' + point]
        reviewers[point] = values['review.engine'] if on else 'claude'

    on_off = lambda flag: 'on' if flag else 'off'
    flags = {
        'REVIEW': 'plan={plan},quality={quality}'.format(**reviewers),
        'STEPS': 'ocr={},e2e={},simplify={},reflect={}'.format(
            on_off(values['steps.ocr']), on_off(values['steps.e2e']),
            on_off(values['steps.simplifyLoop']), on_off(values['steps.reflect'])),
    }
    if 'gemini' in reviewers.values():
        flags['GEMINI_MODEL'] = values['review.gemini.model'] or '-'
    return {
        'config_path': path,
        'values': values,
        'sources': sources,
        'reviewers': reviewers,
        'flags': flags,
        'diagnostics': diagnostics,
    }


def parse_bool(text):
    if text not in ('true', 'false'):
        raise argparse.ArgumentTypeError('expected true|false')
    return text == 'true'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    r = sub.add_parser('resolve')
    r.add_argument('--cwd', required=True)
    r.add_argument('--codex-mode', required=True, choices=CODEX_MODES)
    r.add_argument('--codex-source', default='default', choices=('flag', 'profile', 'default'))
    r.add_argument('--e2e-enabled', type=parse_bool)
    r.add_argument('--reflect', action='store_true')
    args = parser.parse_args(argv)
    result = resolve(args.cwd, args.codex_mode, args.codex_source, args.e2e_enabled, args.reflect)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
