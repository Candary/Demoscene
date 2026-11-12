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