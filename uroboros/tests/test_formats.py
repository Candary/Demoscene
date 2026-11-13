from uroboros.formats import FORMAT, canonical, digest


def test_format_constant():
    assert FORMAT == "uroboros.patch/2"


def test_canonical_is_stable():
    a = canonical({"b": 2, "a": 1})
    b = canonical({"a": 1, "b": 2})
    assert a == b
    assert a == b'{"a":1,"b":2}'


def test_digest_of_bytes_and_value():
    assert digest(b"hello") == digest(b"hello")
    assert digest({"a": 1}) == digest({"a": 1})
    assert digest({"a": 1}) != digest({"a": 2})