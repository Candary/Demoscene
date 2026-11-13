import json

import pytest

from uroboros.formats import FORMAT, PatchError


def test_run_simple_plan_auto_approve(uroboros_instance, project_root):
    plan = json.loads((project_root / "examples" / "plan_simple.json").read_text("utf-8"))
    state = uroboros_instance.run(plan, max_iterations=1, require_approval=False)
    assert state["status"] == "approved"
    assert state["approved"] is True
    out = state["final"]["outputs"]
    assert "geometry" in out
    assert "palette" in out
    assert "compose" in out
    assert out["compose"]["scene"]["geometry"]["kind"] == "room_geometry"


def test_run_without_approval_awaits(uroboros_instance, project_root):
    plan = json.loads((project_root / "examples" / "plan_simple.json").read_text("utf-8"))
    state = uroboros_instance.run(plan, max_iterations=1, require_approval=True, approval=None)
    assert state["status"] == "awaiting_approval"
    assert state["approved"] is False


def test_run_with_custom_approval(uroboros_instance, project_root):
    plan = json.loads((project_root / "examples" / "plan_simple.json").read_text("utf-8"))
    calls = []
    def approve(result):
        calls.append(result)
        return len(calls) >= 2  # approve on second iteration
    state = uroboros_instance.run(plan, max_iterations=3, require_approval=True, approval=approve)
    assert state["status"] == "approved"
    assert len(state["iterations"]) == 2


def test_validation_failure_blocks_auto_approval(uroboros_instance, project_root):
    """P0 regression test: invalid scene must NOT be auto-approved even with
    require_approval=False, when a validate.* patch returned ok=False.

    Reproduces the bug from the external review (2026-11-12):
    'Невалидная сцена получает статус approved'.
    """
    plan = json.loads((project_root / "examples" / "plan_with_validation.json").read_text("utf-8"))
    # Make geometry invalid (negative width)
    for node in plan["nodes"]:
        if node["id"] == "geometry":
            node["params"]["width"] = -5.0

    state = uroboros_instance.run(plan, max_iterations=1, require_approval=False)

    # Must NOT be approved despite require_approval=False
    assert state["status"] != "approved", \
        f"Invalid scene was auto-approved despite validation failure: {state['status']}"
    assert state["approved"] is False, "approved flag must be False when validation failed"

    # Verify validation_status is recorded in checklist
    checklist = state["iterations"][0]["checklist"]
    assert checklist["validation_status"] == "failed"
    assert len(checklist["validation_problems"]) > 0
    assert any("width" in p for p in checklist["validation_problems"]), \
        f"width problem missing in {checklist['validation_problems']}"


def test_validation_success_allows_auto_approval(uroboros_instance, project_root):
    """P0 regression test: valid scene with passing validation auto-approves
    normally (sanity check — validation gate doesn't break happy path)."""
    plan = json.loads((project_root / "examples" / "plan_with_validation.json").read_text("utf-8"))
    state = uroboros_instance.run(plan, max_iterations=1, require_approval=False)
    assert state["status"] == "approved"
    assert state["approved"] is True
    checklist = state["iterations"][0]["checklist"]
    assert checklist["validation_status"] == "passed"


def test_cache_hit_on_second_run(uroboros_instance, project_root):
    plan = json.loads((project_root / "examples" / "plan_simple.json").read_text("utf-8"))
    s1 = uroboros_instance.run(plan, max_iterations=1, require_approval=False)
    s2 = uroboros_instance.run(plan, max_iterations=1, require_approval=False)
    hit1 = s1["iterations"][0]["checklist"]["cache_hits"]
    hit2 = s2["iterations"][0]["checklist"]["cache_hits"]
    assert hit2 > hit1  # second run hit cache more


def test_bad_format(uroboros_instance):
    with pytest.raises(PatchError):
        uroboros_instance.run({"format": "wrong", "nodes": []})


def test_duplicate_node(uroboros_instance):
    plan = {"format": FORMAT, "nodes": [
        {"id": "a", "target": "t", "operation": "geometry.generate"},
        {"id": "a", "target": "t", "operation": "geometry.generate"},
    ]}
    with pytest.raises(PatchError):
        uroboros_instance.run(plan)