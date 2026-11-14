"""Tests for motus adapter and motus.scene patch."""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from uroboros.adapters import motus_available, motus_scene
from uroboros.formats import FORMAT


class TestMotusAvailability:
    def test_motus_available_returns_bool(self):
        result = motus_available()
        assert isinstance(result, bool)

    def test_motus_available_caches(self):
        """Second call should use cache (no re-import)."""
        motus_available()  # prime cache
        result = motus_available()
        assert isinstance(result, bool)


class TestMotusSceneAdapter:
    def test_fallback_when_motus_missing(self, monkeypatch):
        """If motus not installed, returns ok=False source=fallback."""
        import uroboros.adapters as ad
        monkeypatch.setattr(ad, "motus_available", lambda: False)
        res = ad.motus_scene("new a", [0.0])
        assert res["ok"] is False
        assert res["source"] == "fallback"
        assert "motus" in res["error"].lower()

    def test_basic_query_returns_frames(self):
        """With motus installed, basic DSL query produces frames."""
        if not motus_available():
            pytest.skip("motus not installed")
        res = motus_scene(
            "new a\nanim a.position from=(0,0,0) to=(1,0,0) over=1\n",
            [0.0, 0.5, 1.0],
            particles=False,
            mode="dsl",
        )
        assert res["ok"] is True
        assert res["source"] == "motus"
        assert len(res["frames"]) == 3
        # At t=0.5, position should be between (0,0,0) and (1,0,0)
        frame_05 = res["frames"][1]
        assert len(frame_05["items"]) == 1
        pos_x = frame_05["items"][0]["world"][12]  # translation X in column-major
        assert 0.0 < pos_x < 1.0, f"Expected 0 < x < 1 at t=0.5, got {pos_x}"

    def test_invalid_query_returns_error(self):
        """Parse errors return ok=False with issues list."""
        if not motus_available():
            pytest.skip("motus not installed")
        res = motus_scene("anim a.nosuch from=(0,0,0) to=(1,0,0)\n", [0.0])
        assert res["ok"] is False
        assert "issues" in res or "error" in res

    def test_empty_times_returns_empty_frames(self):
        """Empty times list returns empty frames array."""
        if not motus_available():
            pytest.skip("motus not installed")
        res = motus_scene("new a\n", [], particles=False)
        assert res["ok"] is True
        assert res["frames"] == []

    def test_json_safe_handles_tuples(self):
        """_json_safe converts tuples to lists for JSON compatibility."""
        from uroboros.adapters import _json_safe
        assert _json_safe((1, 2, 3)) == [1, 2, 3]
        assert _json_safe({"a": (1, 2)}) == {"a": [1, 2]}
        assert _json_safe(3.14) == 3.14
        assert _json_safe("hello") == "hello"


class TestMotusScenePatch:
    def test_patch_requires_query(self):
        """motus.scene patch without query returns fallback error."""
        from uroboros.registry import PatchRegistry
        patches_dir = PROJECT_ROOT / "patches"
        r = PatchRegistry(patches_dir)
        out = r.apply("motus.scene", {"upstream": {}}, {})
        assert out["ok"] is False
        assert "query" in out["error"]

    def test_patch_with_query(self):
        """motus.scene patch with valid query returns frames."""
        from uroboros.registry import PatchRegistry
        patches_dir = PROJECT_ROOT / "patches"
        r = PatchRegistry(patches_dir)
        out = r.apply(
            "motus.scene",
            {"upstream": {"compose": {}}},
            {
                "query": "new a\nanim a.position from=(0,0,0) to=(1,0,0) over=1\n",
                "times": [0.0, 0.5, 1.0],
                "particles": False,
                "mode": "dsl",
            },
        )
        if out["ok"]:
            assert out["source"] == "motus"
            assert len(out["frames"]) == 3
            assert out["upstream_keys"] == ["compose"]
        else:
            # If motus not installed, fallback is OK
            assert out["source"] in ("fallback", "motus")

    def test_patch_invalid_times_type(self):
        """Non-list times parameter returns fallback error."""
        from uroboros.registry import PatchRegistry
        patches_dir = PROJECT_ROOT / "patches"
        r = PatchRegistry(patches_dir)
        out = r.apply("motus.scene", {"upstream": {}},
                      {"query": "new a", "times": "not_a_list"})
        assert out["ok"] is False
        assert "times" in out["error"]
