"""GLM client adapter.

The engine accepts a `glm_propose(result, iteration)` callable. This module
builds one wired to a GLM-compatible chat API (OpenAI-style).

Without GLM_API_KEY, returns None so the engine simply stops after one iteration
(status="awaiting_approval").
"""
from __future__ import annotations

import json
import os
from typing import Callable, Optional

from .formats import FORMAT


SYSTEM_PROMPT = (
    "You are the feedback step of an iterative scene-generation pipeline. "
    "The user has run a plan and got a result. If you think a patch parameter should change, "
    "propose a uroboros.patch/2 feedback.apply object. Otherwise return null. "
    "Only propose changes to node ids that exist in the plan. "
    "Do not include any other text outside the JSON."
)


def make_glm_proposer(api_key: Optional[str] = None, model: str = "glm-4-flash",
                     base_url: Optional[str] = None, max_retries: int = 2) -> Optional[Callable]:
    api_key = api_key or os.environ.get("GLM_API_KEY")
    if not api_key:
        return None
    try:
        import openai  # type: ignore
    except ImportError as exc:
        raise RuntimeError("install `openai` to use GLM feedback (`pip install uroboros[glm]`)") from exc

    client = openai.OpenAI(
        api_key=api_key,
        base_url=base_url or "https://open.bigmodel.cn/api/paas/v4/",
    )

    def propose(result: dict, iteration: int) -> Optional[dict]:
        summary = {
            "iteration": iteration,
            "nodes": [
                {"id": p["id"] if "id" in p else p.get("operation"),
                 "operation": p["operation"], "status": p["status"]}
                for p in result.get("patches", [])
            ],
            "outputs_preview": {
                node_id: _preview(v) for node_id, v in (result.get("outputs") or {}).items()
            },
        }
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(summary, ensure_ascii=False)},
                ],
                temperature=0.2,
                max_tokens=512,
                response_format={"type": "json_object"},
            )
            text = resp.choices[0].message.content or "null"
            proposal = json.loads(text)
        except Exception:
            return None
        if not isinstance(proposal, dict):
            return None
        # минимальная валидация
        if proposal.get("format") != FORMAT or proposal.get("operation") != "feedback.apply":
            return None
        if "params" not in proposal or "changes" not in proposal.get("params", {}):
            return None
        return proposal

    return propose


def _preview(value, limit: int = 400) -> str:
    try:
        s = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        s = repr(value)
    return s[:limit] + ("…" if len(s) > limit else "")