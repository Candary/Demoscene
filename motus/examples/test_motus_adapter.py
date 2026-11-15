def test_motus_adapter_fallback(monkeypatch):
    import uroboros.adapters as ad
    monkeypatch.setattr(ad, "motus_available", lambda: False)
    res = ad.motus_scene("new a", [0.0])
    assert res["ok"] is False
    assert res["source"] == "fallback"


def test_motus_patch_requires_query(patches_dir):
    from uroboros.registry import PatchRegistry
    r = PatchRegistry(patches_dir)
    out = r.apply("motus.scene", {"upstream": {}}, {})
    assert out["ok"] is False
    assert "query" in out["error"]


def test_motus_patch_with_query(patches_dir):
    from uroboros.registry import PatchRegistry
    r = PatchRegistry(patches_dir)
    out = r.apply(
        "motus.scene",
        {"upstream": {"compose": {}}},
        {
            "query": "new a\nanim a.position from=(0,0,0) to=(1,0,0) over=1\n",
            "times": [0.0, 0.5, 1.0],
            "particles": False,
        },
    )
    if out["ok"]:
        assert out["source"] == "motus"
        assert len(out["frames"]) == 3
        assert out["upstream_keys"] == ["compose"]
    else:
        assert out["source"] in ("fallback", "motus")