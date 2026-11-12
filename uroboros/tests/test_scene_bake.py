"""test_scene_bake — test Scene Manager adapter patch."""
import json
import pytest
from pathlib import Path


def test_scene_bake_fallback(uroboros_instance, project_root):
    """Test scene.bake without Scene Manager — should produce show_json only."""
    plan = json.loads((project_root / "examples" / "plan_demo_intro.json").read_text("utf-8"))
    state = uroboros_instance.run(plan, max_iterations=1, require_approval=False)
    assert state["status"] == "approved"
    outputs = state["final"]["outputs"]
    assert "bake" in outputs
    bake_out = outputs["bake"]
    assert "show_json" in bake_out
    assert bake_out["scene_count"] > 0
    assert bake_out["duration"] == 211


def test_scene_bake_show_json_structure(uroboros_instance, project_root):
    """Verify show JSON has correct structure."""
    plan = json.loads((project_root / "examples" / "plan_demo_intro.json").read_text("utf-8"))
    state = uroboros_instance.run(plan, max_iterations=1, require_approval=False)
    show = state["final"]["outputs"]["bake"]["show_json"]
    assert show["format"] == "scene-manager/1"
    assert show["meta"]["duration"] == 211
    assert show["meta"]["resolution"] == [1280, 720]
    assert len(show["clips"]) > 15  # 7 scenes + 6 transitions + 4 bloom + vig + grn + fin
    # Check seeds
    s1 = [c for c in show["clips"] if c["id"] == "s1"][0]
    assert s1["seed"] == 11111
    # Check energy
    assert len(show["audio"]["energy"]) == 53
    # Check sections
    assert len(show["audio"]["sections"]) == 5


def test_scene_bake_with_smt(uroboros_instance, project_root):
    """If Scene Manager is available, .smt should be generated."""
    plan = json.loads((project_root / "examples" / "plan_demo_intro.json").read_text("utf-8"))
    state = uroboros_instance.run(plan, max_iterations=1, require_approval=False)
    bake_out = state["final"]["outputs"]["bake"]
    # smt may be None if Scene Manager not in path — that's OK
    if bake_out["smt"]:
        assert "SMT 1" in bake_out["smt"]
        assert "clip s1" in bake_out["smt"]
        assert bake_out["source"] == "scene_manager"
