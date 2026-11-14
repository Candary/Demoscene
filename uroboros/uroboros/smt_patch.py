"""smt_patch — inject param deltas into .smt files.

Parses .smt line-by-line, finds uniform declarations per clip,
replaces values for specified (clip_id, uniform_name) pairs.

.smt format (simplified):
  clip s1 10 scene nebula_raymarch 0.0 27.0 ...
  uni uPrimaryColor vec3 3
  prog 1 n:0.05
  prog 1 n:0.1
  prog 1 n:0.3
  uni uIntensity float 1
  prog 1 n:0.8
  endclip

Injection: {"s1.uIntensity": 1.5} → replaces n:0.8 with n:1.5
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Regex for clip header: clip <id> <track> <kind> <effect> ...
_CLIP_RE = re.compile(r"^clip\s+(\S+)\s+\d+\s+(\S+)\s+(\S+)")
# Regex for uniform declaration: uni <name> <type> <count>
_UNI_RE = re.compile(r"^uni\s+(\S+)\s+(\S+)\s+(\d+)")
# Regex for prog value: prog 1 n:<float>
_PROG_RE = re.compile(r"^prog\s+1\s+n:(-?\d+\.?\d*)")


def parse_smt(smt_path: str | Path) -> List[dict]:
    """Parse .smt into structured records.

    Returns list of dicts:
      {"type": "clip", "line": N, "clip_id": "s1", "effect": "nebula_raymarch", "raw": "..."}
      {"type": "uni", "line": N, "name": "uIntensity", "dtype": "float", "count": 1, "raw": "..."}
      {"type": "prog", "line": N, "value": 0.8, "raw": "..."}
      {"type": "endclip", "line": N, "raw": "..."}
      {"type": "other", "line": N, "raw": "..."}
    """
    smt_path = Path(smt_path)
    if not smt_path.exists():
        raise FileNotFoundError(f"smt file not found: {smt_path}")

    lines = smt_path.read_text("utf-8").splitlines(keepends=True)
    records: List[dict] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        m_clip = _CLIP_RE.match(stripped)
        if m_clip:
            records.append({
                "type": "clip", "line": i, "clip_id": m_clip.group(1),
                "effect": m_clip.group(3), "raw": line,
            })
            continue
        m_uni = _UNI_RE.match(stripped)
        if m_uni:
            records.append({
                "type": "uni", "line": i, "name": m_uni.group(1),
                "dtype": m_uni.group(2), "count": int(m_uni.group(3)),
                "raw": line,
            })
            continue
        m_prog = _PROG_RE.match(stripped)
        if m_prog:
            records.append({
                "type": "prog", "line": i, "value": float(m_prog.group(1)),
                "raw": line,
            })
            continue
        if stripped == "endclip":
            records.append({"type": "endclip", "line": i, "raw": line})
            continue
        records.append({"type": "other", "line": i, "raw": line})
    return records


def inject_params(smt_path: str | Path,
                  deltas: Dict[str, float],
                  output_path: Optional[str | Path] = None) -> str:
    """Inject param deltas into .smt file.

    Args:
        smt_path: path to original .smt
        deltas: {"s1.uIntensity": 1.5, "s4.uExposure": 0.45, ...}
                 Key format: "<clip_id>.<uniform_name>"
        output_path: where to write modified .smt (default: overwrite)

    Returns:
        path to modified .smt file
    """
    smt_path = Path(smt_path)
    if output_path is None:
        output_path = smt_path
    output_path = Path(output_path)

    records = parse_smt(smt_path)
    lines = [r["raw"] for r in records]  # original lines

    current_clip: Optional[str] = None
    pending_uniform: Optional[str] = None
    pending_count: int = 0
    pending_consumed: int = 0
    injected_count: int = 0

    for rec in records:
        if rec["type"] == "clip":
            current_clip = rec["clip_id"]
            pending_uniform = None
        elif rec["type"] == "uni":
            pending_uniform = rec["name"]
            pending_count = rec["count"]
            pending_consumed = 0
        elif rec["type"] == "prog":
            if pending_uniform is not None and current_clip is not None:
                key = f"{current_clip}.{pending_uniform}"
                if key in deltas:
                    # For vec3 (count=3), we only inject if delta is a list or
                    # if it's a single float for a float uniform (count=1).
                    if pending_count == 1:
                        new_val = deltas[key]
                        if isinstance(new_val, (int, float)):
                            line_idx = rec["line"]
                            old_raw = lines[line_idx]
                            # Preserve leading whitespace + trailing newline
                            prefix = old_raw[:len(old_raw) - len(old_raw.lstrip())]
                            suffix = "\n" if old_raw.endswith("\n") else ""
                            lines[line_idx] = f"{prefix}prog 1 n:{new_val}{suffix}"
                            injected_count += 1
                    pending_consumed += 1
                    if pending_consumed >= pending_count:
                        pending_uniform = None
                else:
                    pending_consumed += 1
                    if pending_consumed >= pending_count:
                        pending_uniform = None
            elif pending_uniform is not None:
                pending_consumed += 1
                if pending_consumed >= pending_count:
                    pending_uniform = None
        elif rec["type"] == "endclip":
            current_clip = None
            pending_uniform = None

    output_path.write_text("".join(lines), "utf-8")
    return str(output_path)


def extract_params(smt_path: str | Path) -> Dict[str, float]:
    """Extract all float uniform values from .smt as {clip.uniform: value}.

    Only extracts count=1 (float) uniforms. Vec3 values are skipped.
    """
    records = parse_smt(smt_path)
    params: Dict[str, float] = {}
    current_clip: Optional[str] = None
    pending_uniform: Optional[str] = None
    pending_count: int = 0
    pending_consumed: int = 0

    for rec in records:
        if rec["type"] == "clip":
            current_clip = rec["clip_id"]
            pending_uniform = None
        elif rec["type"] == "uni":
            pending_uniform = rec["name"]
            pending_count = rec["count"]
            pending_consumed = 0
        elif rec["type"] == "prog":
            if pending_uniform is not None and current_clip is not None:
                if pending_count == 1 and pending_consumed == 0:
                    params[f"{current_clip}.{pending_uniform}"] = rec["value"]
                pending_consumed += 1
                if pending_consumed >= pending_count:
                    pending_uniform = None
            elif pending_uniform is not None:
                pending_consumed += 1
                if pending_consumed >= pending_count:
                    pending_uniform = None
        elif rec["type"] == "endclip":
            current_clip = None
            pending_uniform = None

    return params
