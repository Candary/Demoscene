#!/usr/bin/env python3
"""Migrate .smt files from position-based to canonical format.

Position-based:   prog 1 n:1.0
Canonical:        prog opacity 1 n:1.0

Only changes `prog` lines that appear BEFORE the first `uni` line in each clip.
The 1st such line → prog opacity, the 2nd → prog progress.
`prog` lines AFTER `uni` (uniform components) stay unchanged.
"""
import sys
from pathlib import Path


def migrate_smt(content: str) -> str:
    lines = content.splitlines()
    output = []
    in_clip = False
    seen_uni = False
    prog_count_before_uni = 0

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("clip "):
            in_clip = True
            seen_uni = False
            prog_count_before_uni = 0
            output.append(line)
            continue

        if stripped == "endclip":
            in_clip = False
            seen_uni = False
            prog_count_before_uni = 0
            output.append(line)
            continue

        if in_clip:
            if stripped.startswith("uni "):
                seen_uni = True
                output.append(line)
                continue

            if stripped.startswith("prog ") and not seen_uni:
                # This is opacity or progress (before any uniform)
                prog_count_before_uni += 1
                parts = stripped.split()
                # parts[0] = "prog", parts[1] = count, parts[2:] = tokens
                if prog_count_before_uni == 1:
                    # opacity
                    parts.insert(1, "opacity")
                elif prog_count_before_uni == 2:
                    # progress
                    parts.insert(1, "progress")
                else:
                    # Shouldn't happen (max 2 progs before uni)
                    # Leave as-is
                    pass
                output.append(" ".join(parts))
                continue

        output.append(line)

    return "\n".join(output) + ("\n" if content.endswith("\n") else "")


def check_canonical(content: str) -> bool:
    """Check if .smt already uses canonical format."""
    for line in content.splitlines():
        if line.startswith("prog opacity ") or line.startswith("prog progress "):
            return True
        if line.startswith("prog ") and not line.startswith("prog opacity") and not line.startswith("prog progress"):
            # Check if it's a uniform component (after uni) or position-based (before uni)
            # Simple heuristic: if any line has "prog opacity", it's canonical
            pass
    # More precise check: look for prog lines that DON'T have a word prefix
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("prog "):
            parts = stripped.split()
            if len(parts) >= 2 and parts[1].isdigit():
                # parts[1] is a number → position-based
                return False
    return True


if __name__ == "__main__":
    files_to_migrate = [
        "/home/z/demo-runtime-publish/milestone_v51_stable/demo.smt",
        "/home/z/demo-runtime-publish/milestone_v52_stable/demo.smt",
        "/home/z/demo-runtime-publish/milestone_v58_stable/demo.smt",
        "/home/z/demo-runtime-publish/demo_intro_v58/demo.smt",
        # Also migrate local copies
        "/home/z/my-project/download/milestone_v51_stable/demo.smt",
        "/home/z/my-project/download/milestone_v52_stable/demo.smt",
        "/home/z/my-project/download/milestone_v58_stable/demo.smt",
        "/home/z/my-project/download/demo_intro_v58/demo.smt",
        "/home/z/my-project/download/demo_intro/demo.smt",
        "/home/z/my-project/download/demo_intro_v51_clean/demo.smt",
        "/home/z/my-project/download/demo_intro_v53/demo.smt",
    ]

    migrated = 0
    skipped = 0

    for path in files_to_migrate:
        p = Path(path)
        if not p.exists():
            print(f"SKIP (not found): {path}")
            continue

        content = p.read_text()

        if check_canonical(content):
            print(f"SKIP (already canonical): {path}")
            skipped += 1
            continue

        # Backup
        backup = p.with_suffix(".smt.bak")
        if not backup.exists():
            backup.write_text(content)

        # Migrate
        new_content = migrate_smt(content)
        p.write_text(new_content)

        # Verify
        if check_canonical(new_content):
            print(f"✅ MIGRATED: {path}")
            migrated += 1
        else:
            print(f"❌ FAILED: {path} — still position-based after migration")
            # Restore backup
            p.write_text(content)

    print(f"\n=== Summary ===")
    print(f"Migrated: {migrated}")
    print(f"Skipped (already canonical): {skipped}")
