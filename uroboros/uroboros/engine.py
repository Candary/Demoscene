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
                 glm_propose: Callable | None = None, workers: int = 4,
                 strict: bool = False):
        """Initialize Uroboros engine.

        Args:
            root: memory root directory
            patches: patches directory path
            glm_propose: optional GLM-based feedback proposer
            workers: parallel execution workers
            strict: P1 — strict integration mode.
                When True, patches that return outputs with `_fallback: True`
                (i.e., a required subsystem was unavailable and was replaced
                with hardcoded defaults) are marked as execution failures.
                This prevents broken integrations from being silently masked
                by fallback behavior. Default False (demo mode) for back-compat.
        """
        self.memory = FileMemory(root)
        self.patches = PatchRegistry(patches)
        self.glm_propose = glm_propose
        self.workers = max(1, int(workers))
        self.strict = strict

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

        # P1 fix: include external data file hashes in cache key.
        # Patches may read external files (.npz matrices, .frag shaders, etc.)
        # whose contents affect outputs but aren't captured in params/inputs.
        # Without this, replacing a matrix file would still return stale cached
        # results. Reported by external review 2026-11-12.
        #
        # Convention: patch params may declare `data_dependencies` as a list
        # of file paths. Their mtime+size hashes are folded into the cache key.
        data_deps_hash = ""
        data_deps = patch["params"].get("data_dependencies") or []
        if isinstance(data_deps, list) and data_deps:
            import os as _os
            dep_info = []
            for path in data_deps:
                try:
                    st = _os.stat(path)
                    # Use nanosecond precision mtime — int(st.st_mtime) would
                    # miss changes within the same second (common in tests).
                    dep_info.append({
                        "path": path,
                        "mtime_ns": st.st_mtime_ns,
                        "size": st.st_size,
                    })
                except OSError:
                    dep_info.append({"path": path, "missing": True})
            data_deps_hash = digest({"data_dependencies": dep_info})

        key = digest({
            "target": patch["target"], "op": op,
            "script": self.patches.versions.get(op),
            "params": patch["params"], "input": input_hash,
            "data_deps": data_deps_hash,   # P1: external data version
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

        # P1 strict mode: if the patch reported a fallback (required subsystem
        # unavailable, replaced with hardcoded defaults), mark as execution
        # failure. Convention: outputs dict contains `_fallback: True` and
        # `_fallback_reason: str` keys.
        if self.strict and isinstance(outputs, dict) and outputs.get("_fallback") is True:
            reason = outputs.get("_fallback_reason", "subsystem unavailable")
            patch["status"] = "failed"
            patch["metrics"]["fallback_reason"] = reason
            patch["approval"] = "rejected"
            raise PatchError(
                f"{op} returned fallback in strict mode: {reason}. "
                f"Either install the required subsystem or run with strict=False."
            )

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

                # P0 fix: separate three states — execution, validation, approval.
                # Auto-approval (require_approval=False) is now BLOCKED when any
                # validate.* patch returned ok=False. The approval callback (if
                # provided) still wins — user can override validation rejection
                # explicitly, but silent auto-approval on failed validation is
                # no longer possible.
                #
                # Note: validation_status="not_checked" (no validate patch ran)
                # does NOT block auto-approval — only explicit validation
                # failure does.
                validation_failed = checklist.get("validation_status") == "failed"

                if approval is not None:
                    accepted = bool(approval(result))
                elif require_approval:
                    accepted = False
                elif validation_failed:
                    # Auto-approval forbidden when validation explicitly failed
                    accepted = False
                    self.memory.event({
                        "type": "validation_blocked_approval", "run": run_id,
                        "iteration": iteration,
                        "problems": checklist.get("validation_problems", []),
                    })
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
                    # P0 fix: previously `break` here prevented the approval
                    # callback from being called on subsequent iterations.
                    # Now: only break if no approval callback is provided
                    # (no point looping without feedback AND without an
                    # approval callback that can change its mind). When an
                    # approval callback IS provided, continue to next
                    # iteration — the callback decides when to accept.
                    if approval is None:
                        break
                    # else: continue to next iteration; approval callback
                    # may accept on a later call.
                    continue
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
        all_ops_succeeded = all(p["status"] in ("executed", "cache_hit") for p in patches)

        # P0 fix: scan patch outputs for validation results.
        # Convention: any patch with operation starting with "validate." or
        # whose output contains an "ok" boolean is treated as a validator.
        # If any validator returned ok=False, validation_status = "failed".
        validation_problems: list[str] = []
        validators_run: list[str] = []
        for p in patches:
            output = p.get("outputs") or {}
            op = p.get("operation", "")
            is_validator = (
                op.startswith("validate.") or op.startswith("validate_")
                or (isinstance(output, dict) and "ok" in output and "problems" in output)
            )
            if is_validator:
                validators_run.append(p.get("id", op))
                if isinstance(output, dict) and output.get("ok") is False:
                    for prob in output.get("problems", []):
                        validation_problems.append(f"[{p.get('id', op)}] {prob}")

        if validators_run and not validation_problems:
            validation_status = "passed"
        elif validation_problems:
            validation_status = "failed"
        else:
            validation_status = "not_checked"

        return {
            "iteration": iteration,
            "all_operations_succeeded": all_ops_succeeded,
            "cache_hits": sum(p["status"] == "cache_hit" for p in patches),
            "execution_count": sum(p["status"] == "executed" for p in patches),
            "patch_ids": [p["id"] for p in patches],
            "approval_required": True,
            # P0: explicit validation status, separate from execution status
            "validation_status": validation_status,
            "validators_run": validators_run,
            "validation_problems": validation_problems,
            "notes": ["Record user rejection reasons and GLM corrections as feedback events in the next iteration."],
        }