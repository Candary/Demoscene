import pytest


def _call(patches_dir, op, params, upstream=None):
    from uroboros.registry import PatchRegistry
    r = PatchRegistry(patches_dir)
    ctx = {"run": "test", "iteration": 0, "upstream": upstream or {}}
    return r.apply(op, ctx, params)


def test_geometry_generates_box(patches_dir):
    out = _call(patches_dir, "geometry.generate", {"width": 3.0, "depth": 2.0})
    assert out["asset"]["kind"] == "room_geometry"
    assert out["asset"]["width"] == 3.0
    assert out["asset"]["depth"] == 2.0


def test_palette_fallback(patches_dir, monkeypatch):
    # force Color Matrix unavailable
    import uroboros.adapters as ad
    monkeypatch.setattr(ad, "build_palette_via_matrix", lambda mood, scheme, size: {"ok": False, "error": "test"})
    out = _call(patches_dir, "color.palette", {"mood": "quiet_warm", "scheme": "analogous", "size": 3})
    assert out["source"] == "fallback_hardcoded"
    assert len(out["palette"]) == 3


def test_compose(patches_dir):
    upstream = {
        "geometry": {"asset": {"kind": "room_geometry", "width": 3, "depth": 2, "height": 2.7, "source": "test"}},
        "palette": {"palette": ["#000000", "#ffffff"], "mood": "quiet_warm", "source": "test"},
    }
    out = _call(patches_dir, "scene.compose", {}, upstream)
    assert out["scene"]["mood"] == "quiet_warm"
    assert out["scene"]["geometry"]["width"] == 3


def test_validate_ok(patches_dir):
    upstream = {"compose": {"scene": {
        "geometry": {"width": 3, "depth": 2, "height": 2.7, "source": "test"},
        "palette": ["#000000", "#ffffff"],
        "mood": "quiet_warm",
        "provenance": {"geometry_source": "test", "palette_source": "test"},
    }}}
    out = _call(patches_dir, "validate.scene", {}, upstream)
    assert out["ok"] is True


def test_validate_bad(patches_dir):
    upstream = {"compose": {"scene": {
        "geometry": {"width": -1, "depth": 0, "height": 0},
        "palette": ["not-a-color"],
        "mood": "",
    }}}
    out = _call(patches_dir, "validate.scene", {}, upstream)
    assert out["ok"] is False
    assert len(out["problems"]) >= 3


def test_color_matrix_fallback(patches_dir, monkeypatch):
    import uroboros.adapters as ad
    monkeypatch.setattr(ad, "describe_color_via_matrix",
                       lambda c: {"ok": False, "error": "not installed", "color": c})
    out = _call(patches_dir, "color.describe", {"color": "#123456"})
    assert out["ok"] is False