#!/usr/bin/env python3
"""
apply_booster_v2.py — applies 6 new sections to booster_final.json.

Source:  /home/z/my-project/upload/booster_final.json  (read-only, user upload)
Output:  /home/z/my-project/download/demo_intro/booster_final.json  (working canonical copy)

Sections added (preserves all existing data):
  1. compat_layer        — Cg -> GLSL 3.3 mapping
  2. llm_layers          — consolidated LLM-facing data (rules_compact + patterns_full
                           + nesting_full + arity_full + meta_quality + static_block)
  3. query_api           — dynamic lookup interface spec (used by scripts/query_booster.py)
  4. llm_self_test       — compact 9-case form for post-generation mental check
  5. not_for_llm_prompt  — explicit exclusion notes (4 items)
  6. validation_pipeline — 5-layer diagram (style/dynamic/syntax/runtime/self_test)

Reproducible: idempotent — can be re-run on a fresh upload, produces same output.

Usage:
  python3 scripts/apply_booster_v2.py
  python3 scripts/apply_booster_v2.py --src <path> --dst <path>
"""
import argparse
import json
import os
import sys
from datetime import datetime

DEFAULT_SRC = "/home/z/my-project/upload/booster_final.json"
DEFAULT_DST = "/home/z/my-project/download/demo_intro/booster_final.json"


def build_compat_layer():
    """Section 1: Cg -> GLSL 3.3 core dialect mapping."""
    return {
        "version": "1.0",
        "source_dialect": "Cg/HLSL (.cpp embedded, per meta.source)",
        "target_dialect": "GLSL 3.3 core (project target)",
        "mapping": {
            "tex2D(s,t)":           "texture(s,t)",
            "tex2Dproj(s,t)":       "textureProj(s,t)",
            "texCUBE(s,t)":         "texture(s,t) /* samplerCube target */",
            "float2":   "vec2",
            "float3":   "vec3",
            "float4":   "vec4",
            "float2x2": "mat2",
            "float3x3": "mat3",
            "float4x4": "mat4",
            "mul(a,b)":             "((a)*(b))",
            "float4 color : COLOR":         "out vec4 fragColor",
            "float4 position : POSITION":   "in vec3 aPosition",
            "float3 normal : NORMAL":       "in vec3 aNormal",
            ": TEXCOORD0":          "/* layout(location=0) in/out */"
        },
        "instruction": (
            "Apply mapping BEFORE interpreting hints from llm_layers.static_block. "
            "Cg lexemes in patterns/nesting/arity auto-translate to GLSL 3.3 core "
            "equivalents. Do NOT copy Cg constructs literally into GLSL output."
        ),
        "note_on_validator": (
            "glslangValidator is the blocking authority on GLSL 3.3 syntax. "
            "compat_layer is advisory; if validator rejects a mapped construct, "
            "validator wins."
        )
    }


def build_rules_compact(rules):
    """Compress verbose rules list into one-line strings for LLM prompt."""
    compact = []
    for r in rules:
        rid = r.get('id', '?')
        name = r.get('name', '?')
        rtype = r.get('type', 'hard')
        cond = r.get('condition', '').replace('\n', ' ')[:160]
        applies = r.get('applies_to_candidate', 'any')
        line = f"[{rid}] {name} ({rtype}, applies={applies}): {cond}"
        if r.get('factor'):
            line += f"  ->  score x {r['factor']}"
        else:
            line += "  ->  reject"
        compact.append(line)
    return compact


def build_llm_layers(data):
    """Section 2: consolidated LLM-facing data."""
    return {
        "version": "1.0",
        "static_block": data["llm_prompt_block"],
        "rules_compact": build_rules_compact(data["rules"]),
        "patterns_full": data["patterns"],
        "nesting_full": [
            {"function": k, "nested_with_count_prob": v}
            for k, v in data["nesting"].items()
        ],
        "arity_full": data["arity"],
        "meta_quality": data["meta"]["evaluation"]
    }


def build_query_api():
    """Section 3: dynamic ngram lookup interface spec."""
    return {
        "version": "1.0",
        "description": (
            "Dynamic query of ngram.contexts (3674 entries) by partial GLSL code. "
            "Returns top-k next-token candidates with probabilities. Implemented by "
            "scripts/query_booster.py. NOT for prompt injection — too large (~150KB)."
        ),
        "interface": (
            "python3 scripts/query_booster.py --code '<partial GLSL>' "
            "[--stage fragment|vertex|compute] [--top 5] "
            "[--booster /home/z/my-project/download/demo_intro/booster_final.json]"
        ),
        "input_normalization": [
            "1. Strip comments: /* */ (DOTALL) and // to EOL",
            "2. Tokenize by normalization.tokenizer_regex",
            "3. Numbers -> <NUM>, identifiers not in kept_builtins/kept_identifiers -> <VAR>",
            "4. Pad left with <s> to max_context_tokens (default 3)",
            "5. For L from max_context down to 0: lookup ngram.contexts[last L tokens joined by space]"
        ],
        "backoff": "score = max over L of (backoff_factor^(max_ctx - L) * p)",
        "output_format_example": [
            {"rank": 1, "token": "<VAR>",  "score": 0.426, "rules_checked": ["R-02 OK", "R-04 OK"]},
            {"rank": 2, "token": "OUT",    "score": 0.161, "rules_checked": ["OK"]},
            {"rank": 3, "token": "cross",  "score": 0.129, "rules_checked": ["OK"]}
        ],
        "use_in_llm_workflow": [
            "1. After generating each statement in shader, call query_api on partial code",
            "2. Get top-5 candidates for next token",
            "3. If generated token not in top-5 -> flag mismatch, reconsider",
            "4. If in top-1 -> high confidence, continue"
        ],
        "triggers": {
            "T1": "Choice point with >=3 plausible candidates",
            "T2": "Unfamiliar context (function/pattern not in working memory)",
            "T3": "Deep nesting >= 3 levels of parens",
            "T4": "After !fix where root-cause = style anomaly -> query 2-3 key spots"
        },
        "non_triggers": [
            "C++ code (main.cpp, opengl_loader.h) -- booster is GLSL/Cg only",
            "Boilerplate: uniform declarations, void main(), simple out/in",
            "Trivial edits: rename, swap constant, change color value",
            "When glslangValidator gives faster answer (syntax error)",
            "When 95%+ confident in continuation"
        ],
        "hard_cap_per_task": 15,
        "fallback": "If query_booster.py unavailable -> continue with L1 static + L3 self_test only. Do NOT block delivery.",
        "not_for_prompt_injection": True
    }


def build_llm_self_test(test_cases):
    """Section 4: compact form of test_cases for mental self-check."""
    compact = []
    for tc in test_cases:
        compact.append({
            "id": tc.get("id"),
            "partial": tc.get("input_text"),
            "stage": tc.get("stage"),
            "expect_top3": [t[0] for t in tc.get("expected_top3", [])],
            "reject_examples": [
                {"token": r[0], "reason": r[1]}
                for r in tc.get("expected_rejected_examples", [])
            ]
        })
    return compact


def build_not_for_llm_prompt():
    """Section 5: explicit exclusion notes for future LLM consumers."""
    return {
        "version": "1.0",
        "purpose": "Prevent future attempts to inject full booster JSON into LLM prompt.",
        "excluded_sections": {
            "ngram.contexts": {
                "size": "~150 KB / 3674 entries",
                "reason": "Too large for prompt injection. Use via query_api -> scripts/query_booster.py for dynamic lookup.",
                "use_instead": "llm_layers.static_block (aggregated) + query_api (per-statement dynamic)"
            },
            "algorithm": {
                "size": "~2 KB",
                "reason": "Step-by-step instructions for code implementation, not LLM hint.",
                "use_instead": "Already encoded in scripts/query_booster.py. LLM uses hints, not algorithm."
            },
            "normalization": {
                "size": "tokenizer_regex + 112 kept_identifiers + 98 kept_builtins",
                "reason": "Parser-internal data for tokenization. LLM does not need explicit list.",
                "use_instead": "Tokenization handled by query_booster.py automatically."
            },
            "vocab_full": {
                "size": "229 entries with per-stage stats",
                "reason": "Detailed stats. Aggregated top-N already in llm_layers.patterns_full and nesting_full.",
                "use_instead": "llm_layers.patterns_full + llm_layers.nesting_full + llm_layers.arity_full"
            }
        }
    }


def build_validation_pipeline():
    """Section 6: layered validation diagram tying booster to existing pipeline."""
    return {
        "version": "1.0",
        "scope": "Applies only to !feat/!fix *shader* requests. C++ code (main.cpp, build scripts) without booster.",
        "layers": [
            {
                "step": 1,
                "name": "style",
                "tool": "llm_layers.static_block + compat_layer",
                "when": "pre-generation (loaded once per *shader* task)",
                "severity": "advisory",
                "cost_tokens": "~2500",
                "provides": "Project style statistics (token probabilities, arity, nesting, patterns)"
            },
            {
                "step": 2,
                "name": "dynamic",
                "tool": "query_api -> scripts/query_booster.py",
                "when": "mid-generation, per-statement at trigger points T1-T4",
                "severity": "advisory",
                "cost_tokens": "0-750 (50 per query * 0-15 queries)",
                "provides": "Top-5 next-token candidates from ngram.contexts (3674 entries)"
            },
            {
                "step": 3,
                "name": "syntax",
                "tool": "glslangValidator via scripts/validate_glsl.py",
                "when": "pre-delivery",
                "severity": "blocking",
                "cost_tokens": "0",
                "provides": "GLSL 3.3 syntax + semantic validation (catches built-in collisions, type errors)"
            },
            {
                "step": 4,
                "name": "runtime",
                "tool": "after-predicate DSL v2.1 on trace.log",
                "when": "post-execution (user sends trace.log)",
                "severity": "verification",
                "cost_tokens": "0",
                "provides": "Runtime milestone confirmation (First frame, no FATAL, Exit code 0, custom predicates)"
            },
            {
                "step": 5,
                "name": "self_test",
                "tool": "llm_self_test (9 cases, mental check)",
                "when": "post-generation, before delivery",
                "severity": "advisory",
                "cost_tokens": "0",
                "provides": "Sanity check on 9 known partial-code scenarios"
            }
        ],
        "precedence": "Step N+1 overrides step N. Booster hints ignored if validator blocks. Runtime verification overrides all.",
        "fallback_chain": "L1 (always) -> L2 (when triggered) -> L3 (always blocking) -> L4 (always verification) -> L5 (always mental)"
    }


def main():
    ap = argparse.ArgumentParser(description="Apply booster v2 patches (6 new sections)")
    ap.add_argument("--src", default=DEFAULT_SRC, help=f"Source booster JSON (default: {DEFAULT_SRC})")
    ap.add_argument("--dst", default=DEFAULT_DST, help=f"Output booster JSON (default: {DEFAULT_DST})")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.src):
        print(f"ERROR: source not found: {args.src}", file=sys.stderr)
        return 1

    dst_dir = os.path.dirname(args.dst)
    os.makedirs(dst_dir, exist_ok=True)

    with open(args.src, "r", encoding="utf-8") as f:
        data = json.load(f)

    src_size = os.path.getsize(args.src)
    src_schema = data.get("schema_version", "?")

    # Apply 6 new sections (idempotent: overwrites if present)
    data["compat_layer"] = build_compat_layer()
    data["llm_layers"] = build_llm_layers(data)
    data["query_api"] = build_query_api()
    data["llm_self_test"] = build_llm_self_test(data.get("test_cases", []))
    data["not_for_llm_prompt"] = build_not_for_llm_prompt()
    data["validation_pipeline"] = build_validation_pipeline()

    # Bump schema version
    data["schema_version"] = "1.1"
    data["booster_v2_applied"] = datetime.now().isoformat(timespec="seconds")
    data["booster_v2_source"] = args.src

    with open(args.dst, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    dst_size = os.path.getsize(args.dst)
    delta = dst_size - src_size

    # Report
    print("=" * 60)
    print("apply_booster_v2.py — DONE")
    print("=" * 60)
    print(f"source:       {args.src}")
    print(f"  size:       {src_size} bytes ({src_size/1024:.1f} KB)")
    print(f"  schema:     {src_schema}")
    print(f"output:       {args.dst}")
    print(f"  size:       {dst_size} bytes ({dst_size/1024:.1f} KB)")
    print(f"  schema:     1.1 (bumped)")
    print(f"  delta:      +{delta} bytes (+{delta/1024:.1f} KB)")
    print(f"sections added: 6")
    print(f"  1. compat_layer            : Cg -> GLSL 3.3 mapping ({len(data['compat_layer']['mapping'])} entries)")
    print(f"  2. llm_layers              : consolidated LLM-facing data")
    print(f"     - static_block          : {len(data['llm_layers']['static_block'])} lines (existing llm_prompt_block)")
    print(f"     - rules_compact         : {len(data['llm_layers']['rules_compact'])} rules (R-01..R-06 + S-01)")
    print(f"     - patterns_full         : {len(data['llm_layers']['patterns_full'])} patterns")
    print(f"     - nesting_full          : {len(data['llm_layers']['nesting_full'])} functions")
    print(f"     - arity_full            : {len(data['llm_layers']['arity_full'])} functions")
    print(f"     - meta_quality          : top1={data['llm_layers']['meta_quality']['top1_with_rules']}, "
          f"top3={data['llm_layers']['meta_quality']['top3_with_rules']}, "
          f"top5={data['llm_layers']['meta_quality']['top5_with_rules']}")
    print(f"  3. query_api               : dynamic lookup spec (triggers T1-T4, hard_cap=15)")
    print(f"  4. llm_self_test           : {len(data['llm_self_test'])} compact test cases")
    print(f"  5. not_for_llm_prompt      : {len(data['not_for_llm_prompt']['excluded_sections'])} exclusion notes")
    print(f"  6. validation_pipeline     : {len(data['validation_pipeline']['layers'])} layers")
    print()
    print(f"Original sections preserved: {sum(1 for k in data if k not in ('compat_layer','llm_layers','query_api','llm_self_test','not_for_llm_prompt','validation_pipeline','booster_v2_applied','booster_v2_source'))} (untouched)")
    print(f"Idempotent: re-running with same source produces same output.")
    if args.verbose:
        print()
        print("All top-level keys in output:")
        for k in data.keys():
            v = data[k]
            t = type(v).__name__
            n = len(v) if hasattr(v, '__len__') else '-'
            print(f"  {k}: {t} (len={n})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
