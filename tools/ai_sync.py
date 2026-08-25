"""Generate and verify client-facing AI surfaces from the canonical ai/ layer.

Usage:
    python tools/ai_sync.py            regenerate .claude/skills from ai/skills
    python tools/ai_sync.py --check    verify only (no writes), exit 1 on drift

Canonical sources stay in ai/skills/; .claude/skills/ is generated output.
See ai/README.md for the adapter matrix and editing rules.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AI = ROOT / "ai"
SKILLS_SRC = AI / "skills"
SKILLS_DST = ROOT / ".claude" / "skills"
VENDOR_MANIFEST = SKILLS_SRC / "vendor" / "manifest.json"

CODEX_AGENTS_LIMIT = 32 * 1024

SECRET_PATTERNS = (
    re.compile(r"(sk|rk|pk)-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9+/_-]{16,}['\"]"),
)


def skill_dirs() -> list[Path]:
    """All skill sources, flattened: ai/skills/* plus ai/skills/vendor/*."""
    if not SKILLS_SRC.is_dir():
        return []
    dirs = [p for p in SKILLS_SRC.iterdir() if p.is_dir() and p.name != "vendor"]
    vendored = SKILLS_SRC / "vendor"
    if vendored.is_dir():
        dirs.extend(p for p in sorted(vendored.iterdir()) if p.is_dir())
    return dirs


def sync_skills() -> tuple[list[str], list[str]]:
    copied, removed = [], []
    SKILLS_DST.mkdir(parents=True, exist_ok=True)
    wanted: set[str] = set()
    for src in skill_dirs():
        wanted.add(src.name)
        dst = SKILLS_DST / src.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        copied.append(src.name)
    for existing in sorted(SKILLS_DST.iterdir()):
        if existing.name not in wanted:
            if existing.is_dir():
                shutil.rmtree(existing)
            else:
                existing.unlink()
            removed.append(existing.name)
    return copied, removed


def _tree_files(root: Path) -> dict[str, Path]:
    return {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}


def check_skills() -> list[str]:
    problems = []
    for src in skill_dirs():
        dst = SKILLS_DST / src.name
        if not dst.is_dir():
            problems.append(f".claude/skills/{src.name}: missing (run tools/ai_sync.py)")
            continue
        src_files = _tree_files(src)
        dst_files = _tree_files(dst)
        for rel in sorted(set(src_files) - set(dst_files)):
            problems.append(f".claude/skills/{src.name}/{rel}: missing from generated copy")
        for rel in sorted(set(dst_files) - set(src_files)):
            problems.append(f".claude/skills/{src.name}/{rel}: extra file in generated copy")
        for rel in sorted(set(src_files) & set(dst_files)):
            if src_files[rel].read_bytes() != dst_files[rel].read_bytes():
                problems.append(f".claude/skills/{src.name}/{rel}: content drift")
    for extra in sorted(p.name for p in SKILLS_DST.iterdir()) if SKILLS_DST.is_dir() else []:
        if extra not in {p.name for p in skill_dirs()}:
            problems.append(f".claude/skills/{extra}: stale copy, remove via tools/ai_sync.py")
    return problems


def check_layer() -> list[str]:
    problems = []
    agents_md = ROOT / "AGENTS.md"
    size = agents_md.stat().st_size if agents_md.exists() else 0
    if size == 0:
        problems.append("AGENTS.md missing")
    elif size > CODEX_AGENTS_LIMIT:
        problems.append(f"AGENTS.md is {size} bytes; Codex truncates beyond {CODEX_AGENTS_LIMIT}")

    claude_md = ROOT / "CLAUDE.md"
    if claude_md.exists():
        head = claude_md.read_text(encoding="utf-8").lstrip()
        if not head.startswith("@AGENTS.md"):
            problems.append("CLAUDE.md must start with '@AGENTS.md' import")

    gemini = ROOT / ".gemini" / "settings.json"
    if gemini.exists():
        try:
            data = json.loads(gemini.read_text(encoding="utf-8"))
            names = data.get("context", {}).get("fileName", [])
            if "AGENTS.md" not in names:
                problems.append(".gemini/settings.json context.fileName must include AGENTS.md")
        except (json.JSONDecodeError, AttributeError):
            problems.append(".gemini/settings.json is not valid JSON with context.fileName")

    registry = AI / "mcp-registry.json"
    if registry.exists():
        try:
            json.loads(registry.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"ai/mcp-registry.json invalid JSON: {exc}")

    manifest = VENDOR_MANIFEST
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if "pinned_commit" not in data.get("source", {}):
                problems.append("vendor/manifest.json missing source.pinned_commit")
            declared = {s["name"] for s in data.get("skills", [])}
            actual = {p.name for p in (SKILLS_SRC / "vendor").iterdir() if p.is_dir()} \
                if (SKILLS_SRC / "vendor").is_dir() else set()
            if declared != actual:
                problems.append(f"vendor skills {sorted(actual)} != manifest {sorted(declared)}")
        except json.JSONDecodeError as exc:
            problems.append(f"vendor/manifest.json invalid JSON: {exc}")

    for md in [agents_md, claude_md, *AI.rglob("*.md"), *SKILLS_DST.rglob("*.md")]:
        text = md.read_text(encoding="utf-8", errors="replace")
        for pat in SECRET_PATTERNS:
            m = pat.search(text)
            if m and "mask" not in m.group(0).lower():
                problems.append(f"possible secret literal in {md.relative_to(ROOT)}: {m.group(0)[:8]}...")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args()

    if args.check:
        problems = check_skills() + check_layer()
        for p in problems:
            print(f"DRIFT: {p}")
        print("OK" if not problems else f"{len(problems)} problem(s)")
        return 1 if problems else 0

    copied, removed = sync_skills()
    for name in copied:
        print(f"synced .claude/skills/{name}")
    for name in removed:
        print(f"removed stale .claude/skills/{name}")
    problems = check_layer()
    for p in problems:
        print(f"DRIFT: {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
