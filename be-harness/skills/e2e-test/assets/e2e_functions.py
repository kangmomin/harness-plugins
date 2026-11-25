#!/usr/bin/env python3
"""e2e 공통 스크립트(function) 목록·실행·저장 helper (스텁 — 구현 예정).

list --cwd C --harness be|fe
run  --cwd C --harness H --name N [--timeout S] -- args...
add  --cwd C --src F --name N --description D --harness be[,fe] --usage U
JSON 출력. 0 성공 / 1 실패 / 2 입력 오류.
"""
import sys


def list_scripts(cwd, harness, env=None, home=None):
    raise NotImplementedError


def run_script(cwd, harness, name, args=(), timeout=None, env=None, home=None):
    raise NotImplementedError


def add_script(cwd, src, name, description, harness, usage, env=None, home=None):
    raise NotImplementedError


def main(argv=None):
    raise NotImplementedError


if __name__ == '__main__':
    sys.exit(main())
