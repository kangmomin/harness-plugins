#!/usr/bin/env python3
"""sync-codex-mode.py — codex-mode.md 공통 블록 동기화.

be-harness 정본의 `<!-- codex-mode:common-begin -->` … `<!-- codex-mode:common-end -->` 블록을
fe-harness / common 사본의 같은 마커 구간에 복사한다. 마커 밖(플러그인 매핑)은 건드리지 않는다.
  python3 scripts/sync-codex-mode.py          # 사본 갱신
  python3 scripts/sync-codex-mode.py --check  # 복사 없이 parity 검증 (불일치 시 exit 1)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REL = Path("skills/start-workflow/references/codex-mode.md")
SOURCE = ROOT / "be-harness" / REL
TARGETS = [ROOT / "fe-harness" / REL, ROOT / "common" / REL]
BEGIN = "<!-- codex-mode:common-begin -->"
END = "<!-- codex-mode:common-end -->"


def block_span(text: str, path: Path):
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        sys.exit(f"FAIL: 마커가 정확히 1쌍이 아님: {path.relative_to(ROOT)}")
    b, e = text.index(BEGIN), text.index(END) + len(END)
    if e <= b:
        sys.exit(f"FAIL: 마커 순서 오류: {path.relative_to(ROOT)}")
    return b, e


def main() -> int:
    check = "--check" in sys.argv[1:]
    src = SOURCE.read_text(encoding="utf-8")
    sb, se = block_span(src, SOURCE)
    canonical = src[sb:se]
    bad = 0
    for target in TARGETS:
        rel = target.relative_to(ROOT)
        if not target.exists():
            print(f"FAIL: 사본 없음: {rel}")
            bad = 1
            continue
        text = target.read_text(encoding="utf-8")
        b, e = block_span(text, target)
        if text[b:e] == canonical:
            continue
        if check:
            print(f"FAIL: 공통 블록 불일치: {rel}")
            bad = 1
        else:
            target.write_text(text[:b] + canonical + text[e:], encoding="utf-8")
            print(f"synced: {rel}")
    if check and not bad:
        print("sync-codex-mode --check: OK")
    return bad


if __name__ == "__main__":
    sys.exit(main())
