#!/usr/bin/env python3
"""harness-plugin 공통 폴더 경로 규칙과 문서 저장 helper (스텁 — 구현 예정).

resolve    --cwd C [--ensure]
report-dir --cwd C --domain be|fe
save-doc   --cwd C --name F [--prefer P]   (본문 stdin)
find-docs  --cwd C --contains S
JSON 출력. 0 성공 / 1 실패 / 2 입력 오류.
"""
import os
import sys


class ConfigError(ValueError):
    """경로·설정·git 오류를 한 종류로 묶는다."""


def is_abs_strict(value, platform):
    raise NotImplementedError


def slug(name):
    raise NotImplementedError


def remote_project_name(url):
    raise NotImplementedError


def project_name(cwd, env=None):
    raise NotImplementedError


def is_plugin_source(path):
    raise NotImplementedError


def resolve(cwd, env=None, home=None, ensure=False):
    raise NotImplementedError


def profile_report_dir(cwd, domain):
    raise NotImplementedError


def report_dir(cwd, domain, env=None, home=None):
    raise NotImplementedError


def save_doc(cwd, name, body, prefer=None, env=None, home=None):
    raise NotImplementedError


def find_docs(cwd, contains, env=None, home=None):
    raise NotImplementedError


def main(argv=None):
    raise NotImplementedError


if __name__ == '__main__':
    sys.exit(main())
