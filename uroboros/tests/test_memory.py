from uroboros.memory import FileMemory


def test_blob_roundtrip(tmp_path):
    m = FileMemory(tmp_path / "mem")
    ref = m.put_blob(b"payload")
    assert ref["size"] == 7
    assert m.get_blob(ref) == b"payload"


def test_cache_roundtrip(tmp_path):
    m = FileMemory(tmp_path / "mem")
    m.cache_put("k1", {"outputs": {"x": 1}, "blob_refs": [], "operation": "op"})
    assert m.cache_get("k1") == {"outputs": {"x": 1}, "blob_refs": [], "operation": "op"}
    assert m.cache_get("missing") is None


def test_run_roundtrip(tmp_path):
    m = FileMemory(tmp_path / "mem")
    m.save_run("rid", {"status": "ok"})
    assert m.load_run("rid") == {"status": "ok"}
    assert m.load_run("missing") is None


def test_event_journal(tmp_path):
    m = FileMemory(tmp_path / "mem")
    m.event({"type": "x"})
    m.event({"type": "y"})
    lines = m.journal.read_text("utf-8").splitlines()
    assert len(lines) == 2


def test_stats(tmp_path):
    m = FileMemory(tmp_path / "mem")
    m.put_blob(b"abc")
    m.cache_put("k", {"outputs": {}, "blob_refs": [], "operation": "op"})
    m.save_run("r", {"status": "ok"})
    m.event({"type": "x"})
    s = m.stats()
    assert s["blobs"] == 1
    assert s["cache_entries"] == 1
    assert s["runs"] == 1
    assert s["journal_lines"] == 1