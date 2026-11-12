"""Uroboros engine: one patch format drives operation, feedback, approval and memory."""
from __future__ import annotations

import concurrent.futures as cf
import uuid
from typing import Any, Callable

from .formats import FORMAT, PatchError, canonical, digest
from .memory import FileMemory
from .registry import PatchRegistry


class Uroboros:
    def __init__(self, root=".uroboros", patches="patches",
                 glm_propose: Callable | None = None, workers: int = 4):
        self.memory = FileMemory(root)
        self.patches = PatchRegistry(patches)
        self.glm_propose = glm_propose
        self.workers = max(1, int(workers))

    # ---- фабрики патчей -----------------------------------------------------
    def make_patch(self, target: str, operation: str, inputs=None, params=None, **meta) -> dict:
        return {
            "format": FORMAT, "id": uuid.uuid4().hex, "parent": meta.get("parent"),
            "run": meta.get("run"), "iteration": meta.get("iteration", 0),
            "target": target, "operation": operation, "inputs": inputs or {},
            "params": params or {}, "outputs": {}, "status": "proposed",
            "approval": "pending", "metrics": {}, "memory": {},
        }

    def make_feedback(self, changes: dict, *, run=None, iteration=0, parent=None, reason="") -> dict:
        return {
            "format": FORMAT, "id": uuid.uuid4().hex, "parent": parent, "run": run,
            "iteration": iteration, "target": "uroboros", "operation": "feedback.apply",
            "inputs": {}, "params": {"changes": changes, "reason": reason},
            "outputs": {}, "status": "proposed", "approval": "pending", "metrics": {}, "memory": {},
        }

    # ---- выполнение одного патча -------------------------------------------
    def _execute_one(self, patch: dict, context: dict, run_id: str):
        op = patch["operation"]
        input_hash = digest({"inputs": patch["inputs"], "upstream": context.get("upstream", {})})
        key = digest({
            "target": patch["target"], "op": op,
            "script": self.patches.versions.get(op),
            "params": patch["params"], "input": input_hash,
        })
        cached = self.memory.cache_get(key)
        if cached:
            patch["status"] = "cache_hit"
            patch["memory"]["cache_key"] = key
            patch["metrics"] = {"cache_hit": True, "elapsed_ms": 0.0}
            return patch, cached["outputs"]
        import time
        started = time.perf_counter()
        outputs = self.patches.apply(op, {**context, "inputs": patch["inputs"], "patch": patch}, patch["params"])
        elapsed = (time.perf_counter() - started) * 1000
        if not isinstance(outputs, dict):
            raise PatchError(f"{op} must return dict, got {type(outputs).__name__}")
        blob_refs = []
        for k, v in list(outputs.items()):
            if isinstance(v, bytes):
                ref = self.memory.put_blob(v)
                outputs[k] = {"$blob": ref}
                blob_refs.append(ref)
        patch["status"] = "executed"
        patch["metrics"] = {"cache_hit": False, "elapsed_ms": round(elapsed, 4)}
        patch["memory"]["cache_key"] = key
        self.memory.cache_put(key, {"outputs": outputs, "blob_refs": blob_refs, "operation": op})
        return patch, outputs

    # ---- основной цикл ------------------------------------------------------
    def run(self, plan: dict, *, max_iterations=4, require_approval=True,
            approval: Callable | None = None, feedback: Callable | None = None) -> dict:
        """Plan shape: {name, nodes:[{id,target,operation,params,needs:[node ids]}]}.

        feedback(previous_result, iteration) -> {node_id: {params: {...}}} | None
        approval(result) -> bool. GLM can be used by passing feedback=self.glm_propose.
        """
        if plan.get("format", FORMAT) != FORMAT:
            raise PatchError(f"Unsupported patch format: {plan.get('format')!r}")
        run_id = uuid.uuid4().hex
        pipeline_key = digest({"plan": plan, "patch_versions": self.patches.versions})
        nodes = plan.get("nodes", [])
        ids = [n["id"] for n in nodes]
        if len(ids) != len(set(ids)):
            raise PatchError("Duplicate node id")
        known = set(ids)
        for n in nodes:
            for dep in n.get("needs", []):
                if dep not in known:
                    raise PatchError(f"Unknown dependency {dep!r} in {n['id']!r}")

        state: dict[str, Any] = {
            "format": FORMAT, "run": run_id, "name": plan.get("name", "untitled"),
            "status": "running", "iterations": [], "approved": False, "final": None,
            "mental_checklist": [], "pipeline_cache_key": pipeline_key,
        }
        params = {n["id"]: dict(n.get("params", {})) for n in nodes}
        previous = None

        try:
            for iteration in range(max_iterations):
                pending = {n["id"]: n for n in nodes}
                done: dict[str, Any] = {}
                patches: list[dict] = []
                while pending:
                    ready = [n for n in pending.values() if all(d in done for d in n.get("needs", []))]
                    if not ready:
                        raise PatchError("Pipeline contains a dependency cycle")

                    def work(n):
                        patch = self.make_patch(
                            n["target"], n["operation"],
                            inputs={d: done[d] for d in n.get("needs", [])},
                            params=params[n["id"]], run=run_id, iteration=iteration,
                        )
                        ctx = {
                            "run": run_id, "iteration": iteration,
                            "upstream": {d: done[d] for d in n.get("needs", [])},
                        }
                        return self._execute_one(patch, ctx, run_id)

                    if len(ready) > 1 and self.workers > 1:
                        with cf.ThreadPoolExecutor(max_workers=min(self.workers, len(ready))) as pool:
                            results = list(pool.map(work, ready))
                    else:
                        results = [work(n) for n in ready]

                    for n, (patch, output) in zip(ready, results):
                        done[n["id"]] = output
                        patch["outputs"] = output
                        patches.append(patch)
                        del pending[n["id"]]
                        self.memory.event({
                            "type": "patch", "run": run_id, "iteration": iteration, "patch": patch,
                        })

                result = {"outputs": done, "patches": patches}
                checklist = self._checklist(result, iteration)
                state["mental_checklist"].append(checklist)
                state["iterations"].append({
                    "iteration": iteration, "result": result, "checklist": checklist,
                })
                previous = result

                if approval is not None:
                    accepted = bool(approval(result))
                elif require_approval:
                    accepted = False
                else:
                    accepted = True

                if accepted:
                    state.update(status="approved", approved=True, final=result)
                    self.memory.event({"type": "approval", "run": run_id, "iteration": iteration, "approved": True})
                    break
                if iteration == max_iterations - 1:
                    break

                proposal = (
                    feedback(result, iteration) if feedback
                    else (self.glm_propose(result, iteration) if self.glm_propose else None)
                )
                self.memory.event({"type": "feedback", "run": run_id, "iteration": iteration, "proposal": proposal})
                if not proposal:
                    # If custom approval is provided, continue iterating without feedback.
                    # The approval callback itself drives the iteration loop.
                    if approval is not None:
                        continue
                    break
                if proposal.get("format") != FORMAT or proposal.get("operation") != "feedback.apply":
                    raise PatchError("Feedback must use the uroboros.patch/2 feedback.apply format")
                changes = proposal.get("params", {}).get("changes", {})
                for node_id, change in changes.items():
                    if node_id not in params:
                        raise PatchError(f"Feedback references unknown node: {node_id}")
                    params[node_id].update(change.get("params", change))
                proposal["status"] = "applied"
                proposal["approval"] = "pending"

            if not state["approved"]:
                state["status"] = "awaiting_approval" if previous is not None else "failed"
                state["final"] = previous

        except Exception as exc:
            state["status"] = "failed"
            state["error"] = f"{type(exc).__name__}: {exc}"
            self.memory.save_run(run_id, state)
            self.memory.save_pipeline_trace(pipeline_key, run_id, state)
            self.memory.event({"type": "run_failed", "run": run_id, "error": state["error"]})
            raise

        self.memory.save_run(run_id, state)
        self.memory.save_pipeline_trace(pipeline_key, run_id, state)
        self.memory.event({
            "type": "run_finished", "run": run_id, "status": state["status"],
            "iterations": len(state["iterations"]),
        })
        return state

    @staticmethod
    def _checklist(result: dict, iteration: int) -> dict:
        patches = result["patches"]
        return {
            "iteration": iteration,
            "all_operations_succeeded": all(p["status"] in ("executed", "cache_hit") for p in patches),
            "cache_hits": sum(p["status"] == "cache_hit" for p in patches),
            "execution_count": sum(p["status"] == "executed" for p in patches),
            "patch_ids": [p["id"] for p in patches],
            "approval_required": True,
            "notes": ["Record user rejection reasons and GLM corrections as feedback events in the next iteration."],
        }