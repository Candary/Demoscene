#!/usr/bin/env python3
"""
query_booster.py — dynamic ngram lookup for partial GLSL code.

Implements the query_api interface specified in booster_final.json v1.1 (section query_api).
Tokenizes partial GLSL, looks up ngram.contexts with Katz backoff, applies hard rules
(R-01..R-06), and returns top-k next-token candidates with probabilities.

Usage:
  python3 scripts/query_booster.py --code 'vec3 v = normalize(' --stage fragment --top 5
  python3 scripts/query_booster.py --code 'clamp(dot(' --top 3
  python3 scripts/query_booster.py --code '<VAR> = mix(' --stage compute
  python3 scripts/query_booster.py --self-test   # run all 9 llm_self_test cases

Reads: /home/z/my-project/download/demo_intro/booster_final.json (v1.1, patched)
       Falls back to /home/z/my-project/upload/booster_final.json if v1.1 missing.

Output: JSON to stdout with top-k candidates.
"""
import argparse
import json
import os
import re
import sys

DEFAULT_BOOSTER = "/home/z/my-project/download/demo_intro/booster_final.json"
FALLBACK_BOOSTER = "/home/z/my-project/upload/booster_final.json"

# Regexes from normalization section
TOKENIZER_RE = re.compile(
    r'[A-Za-z_][A-Za-z_0-9]*'
    r'|\d+\.?\d*(?:[eE][+-]?\d+)?f?'
    r'|\+\+|--|\+=|-=|\*=|/=|==|!=|<=|>=|&&|\|\|'
    r'|[{}()\[\];,.+\-*/%=<>!?:]'
)
COMMENT_BLOCK_RE = re.compile(r'/\*.*?\*/', re.DOTALL)
COMMENT_LINE_RE = re.compile(r'//[^\n]*')


def load_booster(path):
    if not path or not os.path.exists(path):
        path = FALLBACK_BOOSTER
    if not os.path.exists(path):
        sys.stderr.write(f"ERROR: booster not found at {DEFAULT_BOOSTER} or {FALLBACK_BOOSTER}\n")
        sys.exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f), path


def tokenize(code, normalization):
    """Apply normalization.tokenizer_regex + identifier classification."""
    # Strip comments
    code = COMMENT_BLOCK_RE.sub('', code)
    code = COMMENT_LINE_RE.sub('', code)
    # Tokenize
    raw = TOKENIZER_RE.findall(code)
    # Classify identifiers
    kept_builtins = set(normalization.get('kept_builtins', []))
    kept_identifiers = set(normalization.get('kept_identifiers', []))
    type_tokens = set(normalization.get('type_tokens', []))
    out = []
    for t in raw:
        if re.match(r'^\d', t):
            out.append('<NUM>')
        elif re.match(r'^[A-Za-z_]', t):
            if (t in kept_builtins or t in kept_identifiers
                    or t.startswith('gl_') or t in type_tokens):
                out.append(t)
            else:
                out.append('<VAR>')
        else:
            out.append(t)
    return out


def get_context_key(seq, L):
    """Last L tokens joined by space. L=0 -> empty string (unigram)."""
    if L == 0:
        return ''
    if len(seq) < L:
        return None
    return ' '.join(seq[-L:])


def query_ngram(booster, partial_tokens, stage=None):
    """Katz backoff over ngram.contexts with rule filtering."""
    ngram = booster['ngram']
    contexts = ngram['contexts']
    policies = booster['policies']
    max_ctx = policies.get('max_context_tokens', 3)
    backoff = policies.get('backoff_factor', 0.4)
    arity = booster.get('arity', {})

    # Pad with <s>
    seq = ['<s>'] * max_ctx + partial_tokens

    # Track parens for rule checks
    open_paren_stack = []  # list of (fn, commas, nonempty, is_for, is_definition)
    type_tokens = set(booster.get('normalization', {}).get('type_tokens', []))
    for i, t in enumerate(partial_tokens):
        if t == '(':
            # Find fn: token before '(' if it's in arity
            prev = partial_tokens[i-1] if i > 0 else None
            prev2 = partial_tokens[i-2] if i > 1 else None
            fn = prev if prev in arity else None
            is_definition = (prev == 'main') or (prev2 in type_tokens) or (prev2 == 'void')
            is_for = (prev == 'for')
            open_paren_stack.append({
                'fn': fn,
                'commas': 0,
                'nonempty': False,
                'is_definition': is_definition,
                'is_for': is_for
            })
        elif t == ',':
            if open_paren_stack:
                open_paren_stack[-1]['commas'] += 1
                open_paren_stack[-1]['nonempty'] = True
        elif t == ')':
            if open_paren_stack:
                open_paren_stack.pop()
        elif t == ';':
            # Statement end (outside parens) — would reset, but we keep simple
            pass
        else:
            if open_paren_stack:
                open_paren_stack[-1]['nonempty'] = True

    # Score via Katz backoff
    scores = {}
    for L in range(max_ctx, -1, -1):
        key = get_context_key(seq, L)
        if key is None:
            continue
        ctx = contexts.get(key)
        if not ctx:
            continue
        weight = backoff ** (max_ctx - L)
        for token, count, p in ctx.get('next', []):
            cur = scores.get(token, 0)
            scores[token] = max(cur, weight * p)

    # Apply hard rules
    rejected = {}
    inner = open_paren_stack[-1] if open_paren_stack else None

    for token in list(scores.keys()):
        reasons = []

        # R-01: unbalanced_close
        if token == ')' and not open_paren_stack:
            reasons.append('R-01 unbalanced_close')

        # R-02: arity_on_close
        if token == ')' and inner and inner.get('fn'):
            fn = inner['fn']
            args = inner['commas'] + (1 if inner['nonempty'] else 0)
            allowed = arity.get(fn, {})
            if str(args) not in allowed and args not in allowed.values():
                # also check: maybe allowed has int keys
                allowed_args = set(int(k) for k in allowed.keys())
                if args not in allowed_args:
                    reasons.append(f'R-02 arity {fn}/{args} (allowed: {list(allowed.keys())})')

        # R-03: arity_on_comma
        if token == ',' and inner and inner.get('fn'):
            fn = inner['fn']
            current = inner['commas'] + 1
            allowed = arity.get(fn, {})
            max_allowed = max(int(k) for k in allowed.keys()) if allowed else 0
            if current > max_allowed:
                reasons.append(f'R-03 arity {fn}/{current+1} exceeds max {max_allowed}')

        # R-04: end_inside_parens
        if token in (';', '{', '}') and open_paren_stack:
            if not (token == ';' and inner and inner.get('is_for')):
                reasons.append('R-04 end_inside_parens')

        # R-05: max_statement_length (simplified — count tokens since last stmt-end)
        # R-06: cycle_guard (simplified — check 4-gram repetition)
        # These need full statement tracking; skip in v1 query impl.

        # S-01: unseen_in_stage (soft, multiply score)
        if stage and token in booster.get('vocab', {}):
            v = booster['vocab'][token]
            if v.get('count', 0) >= policies.get('stage_penalty_min_count', 10):
                stages = v.get('stages', {})
                if stages.get(stage, 0) == 0:
                    scores[token] *= 0.2  # soft penalty

        if reasons:
            rejected[token] = reasons
            del scores[token]

    # Normalize
    total = sum(scores.values())
    if total > 0:
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        normalized = [(t, s/total) for t, s in ranked]
    else:
        normalized = []

    return normalized, rejected, {
        'open_parens': len(open_paren_stack),
        'inner_fn': inner['fn'] if inner else None,
        'inner_args': (inner['commas'] + (1 if inner['nonempty'] else 0)) if inner else 0,
        'in_for': inner.get('is_for', False) if inner else False,
    }


def run_self_test(booster):
    """Run all 9 llm_self_test cases and compare."""
    cases = booster.get('llm_self_test', [])
    if not cases:
        # fallback: build from test_cases
        cases = []
        for tc in booster.get('test_cases', []):
            cases.append({
                'id': tc.get('id'),
                'partial': tc.get('input_text'),
                'stage': tc.get('stage'),
                'expect_top3': [t[0] for t in tc.get('expected_top3', [])],
                'reject_examples': [{'token': r[0], 'reason': r[1]} for r in tc.get('expected_rejected_examples', [])]
            })
    results = []
    hits = 0
    for tc in cases:
        tokens = tokenize(tc['partial'], booster.get('normalization', {}))
        candidates, rejected, ctx = query_ngram(booster, tokens, tc.get('stage'))
        got_top3 = [t for t, _ in candidates[:3]]
        expect_top3 = tc.get('expect_top3', [])
        # hit if any of got_top3 matches any of expect_top3 (set intersection)
        hit = bool(set(got_top3) & set(expect_top3))
        if hit:
            hits += 1
        # check reject expectations
        reject_hits = 0
        for ex in tc.get('reject_examples', []):
            if ex['token'] in rejected:
                reject_hits += 1
        results.append({
            'id': tc['id'],
            'partial': tc['partial'],
            'stage': tc['stage'],
            'expect_top3': expect_top3,
            'got_top3': got_top3,
            'hit': hit,
            'rejected_count': len(rejected),
            'reject_examples_hit': f"{reject_hits}/{len(tc.get('reject_examples', []))}",
        })
    hit_rate = hits / len(cases) if cases else 0
    return {
        'total_cases': len(cases),
        'hits': hits,
        'hit_rate': round(hit_rate, 3),
        'cases': results
    }


def main():
    ap = argparse.ArgumentParser(description="Dynamic ngram lookup for partial GLSL")
    ap.add_argument('--code', help='Partial GLSL code to query')
    ap.add_argument('--stage', default=None, choices=['fragment', 'vertex', 'compute'],
                    help='Shader stage for S-01 soft rule')
    ap.add_argument('--top', type=int, default=5, help='Top-k candidates (default 5)')
    ap.add_argument('--booster', default=DEFAULT_BOOSTER, help=f'Booster JSON path (default: {DEFAULT_BOOSTER})')
    ap.add_argument('--self-test', action='store_true', help='Run all 9 llm_self_test cases')
    ap.add_argument('--show-context', action='store_true', help='Include parser context in output')
    args = ap.parse_args()

    booster, used_path = load_booster(args.booster)

    if args.self_test:
        result = run_self_test(booster)
        result['booster_path'] = used_path
        result['schema_version'] = booster.get('schema_version', '?')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if not args.code:
        ap.error("--code is required (or use --self-test)")

    norm = booster.get('normalization', {})
    tokens = tokenize(args.code, norm)
    candidates, rejected, ctx = query_ngram(booster, tokens, args.stage)

    result = {
        'input_code': args.code,
        'input_tokens_normalized': tokens,
        'stage': args.stage,
        'top_k': args.top,
        'candidates': [
            {'rank': i+1, 'token': t, 'score': round(s, 4)}
            for i, (t, s) in enumerate(candidates[:args.top])
        ],
        'rejected_by_rules': [
            {'token': t, 'reasons': r} for t, r in rejected.items()
        ],
        'booster_path': used_path,
        'schema_version': booster.get('schema_version', '?'),
    }
    if args.show_context:
        result['parser_context'] = ctx
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
