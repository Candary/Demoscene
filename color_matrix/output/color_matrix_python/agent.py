"""Минимальный цикл tool-calling для любого OpenAI-совместимого клиента (в том числе GLM через совместимый endpoint
или SDK с тем же интерфейсом `client.chat.completions.create(model=..., messages=..., tools=...)`).

Клиент не импортируется здесь — достаточно утиной типизации, поэтому цикл тестируется без сети.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .tools import TOOL_SCHEMAS, ColorToolbox

POLICY_PATH = Path(__file__).resolve().parents[2] / "policy" / "color_policy.md"


def load_policy(path: str | Path | None = None) -> str:
    return Path(path or POLICY_PATH).read_text(encoding="utf-8")


def run_agent(client: Any, model: str, user_prompt: str, toolbox: ColorToolbox, *, system_prompt: str | None = None,
              max_steps: int = 8, extra_messages: list[dict] | None = None, **create_kwargs) -> dict:
    """Возвращает {"text": финальный ответ, "tool_calls": [{name, arguments, result}], "messages": история}."""
    messages: list[dict] = [{"role": "system", "content": system_prompt if system_prompt is not None else load_policy()}]
    messages += extra_messages or []
    messages.append({"role": "user", "content": user_prompt})
    trace: list[dict] = []

    for _ in range(max_steps):
        resp = client.chat.completions.create(model=model, messages=messages, tools=TOOL_SCHEMAS, **create_kwargs)
        msg = resp.choices[0].message
        calls = getattr(msg, "tool_calls", None) or []
        if not calls:
            messages.append({"role": "assistant", "content": msg.content or ""})
            return {"text": msg.content or "", "tool_calls": trace, "messages": messages}

        messages.append({
            "role": "assistant", "content": msg.content or "",
            "tool_calls": [{"id": c.id, "type": "function",
                            "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in calls],
        })
        for c in calls:
            result = toolbox.dispatch(c.function.name, c.function.arguments)
            trace.append({"name": c.function.name, "arguments": c.function.arguments, "result": result})
            messages.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(result, ensure_ascii=False)})

    return {"text": "", "tool_calls": trace, "messages": messages, "error": f"достигнут лимит {max_steps} шагов"}
