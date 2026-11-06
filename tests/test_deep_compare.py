import random
import time
from unittest.mock import patch

from ztf.utils import deep_compare
from ztf.utils.deep_compare import deep_equal


def test_deep_equal_simple_dicts():
    assert deep_equal({"a": 1}, {"a": 1})
    assert not deep_equal({"a": 1}, {"a": 2})
    assert not deep_equal({"a": 1}, {"b": 1})


def test_deep_equal_nested_dicts():
    a = {"a": {"b": 2, "c": [1, 2]}}
    b = {"a": {"b": 2, "c": [2, 1]}}
    assert deep_equal(a, b)


def test_deep_equal_lists_ignore_order():
    assert deep_equal([1, 2, 3], [3, 2, 1])
    assert not deep_equal([1, 2, 2], [2, 1, 1])
    assert deep_equal([{"a": 1}, {"b": 2}], [{"b": 2}, {"a": 1}])


def test_deep_equal_lists_with_duplicates():
    assert deep_equal([1, 2, 2], [2, 1, 2])
    assert not deep_equal([1, 2, 2], [2, 1, 1])


def test_deep_equal_mixed_types():
    assert not deep_equal({"a": 1}, [{"a": 1}])
    assert not deep_equal([1, 2], 2)
    assert not deep_equal("a", 1)


def test_deep_equal_empty_structures():
    assert deep_equal({}, {})
    assert deep_equal([], [])
    assert not deep_equal({}, [])
    assert not deep_equal([], None)


def test_deep_equal_complex():
    a = {"x": [1, {"y": [2, 3]}, 4]}
    b = {"x": [4, {"y": [3, 2]}, 1]}
    assert deep_equal(a, b)


def test_deep_equal_lists_of_lists():
    a = [[1, 2], [3, 4]]
    b = [[3, 4], [2, 1]]
    assert deep_equal(a, b)


def test_deep_equal_lists_of_lists_with_duplicates():
    a = [[1, 2], [1, 2], [3, 4]]
    b = [[3, 4], [1, 2], [1, 2]]
    assert deep_equal(a, b)
    c = [[1, 2], [3, 4], [3, 4]]
    d = [[1, 2], [3, 4], [1, 2]]
    assert not deep_equal(c, d)


def test_deep_equal_different_length_lists():
    """Lists with different lengths return False immediately (line 11)."""
    assert not deep_equal([1, 2, 3], [1, 2])
    assert not deep_equal([], [1])
    assert not deep_equal([1], [])


def test_deep_equal_ignore_keys_basic():
    """ignore_keys excludes specified keys from comparison at all levels."""
    a = {"$objectType": "Foo", "name": "test"}
    b = {"name": "test"}
    assert not deep_equal(a, b)
    assert deep_equal(a, b, ignore_keys={"$objectType"})


def test_deep_equal_ignore_keys_nested():
    """ignore_keys works recursively through nested dicts and lists."""
    a = {
        "title": "policy",
        "conditions": [
            {
                "$objectType": "Condition",
                "value": {
                    "$objectType": "IntValue",
                    "intValue": 100,
                },
            }
        ],
    }
    b = {
        "title": "policy",
        "conditions": [
            {
                "value": {
                    "intValue": 100,
                },
            }
        ],
    }
    assert not deep_equal(a, b)
    assert deep_equal(a, b, ignore_keys={"$objectType"})


def test_deep_equal_ignore_keys_detects_real_changes():
    """Changing actual data fields is still detected even with ignore_keys."""
    a = {"$objectType": "IntValue", "intValue": 100}
    b = {"$objectType": "DoubleValue", "doubleValue": 50.0}
    assert not deep_equal(a, b, ignore_keys={"$objectType"})


def test_deep_equal_ignore_keys_none_default():
    """Passing ignore_keys=None (default) behaves like the original."""
    a = {"$objectType": "Foo", "name": "test"}
    b = {"name": "test"}
    assert not deep_equal(a, b, ignore_keys=None)


def test_deep_equal_large_list_of_dicts_is_fast():
    """1000-element permuted list comparison completes well under 1s.

    Regression guard for the O(n^2) multiset matcher -- the old matcher
    needed ~600 ms on this input, the hash-based fast path needs ~5 ms.
    A loose 1-second threshold catches an accidental quadratic regression
    while staying safely non-flaky under CI jitter.
    """
    size = 1000
    base = [
        {"id": i, "name": f"item-{i}", "tags": [i % 7, i % 13]} for i in range(size)
    ]
    rng = random.Random(0xC0DE)
    shuffled = base.copy()
    rng.shuffle(shuffled)

    start = time.perf_counter()
    result = deep_equal(base, shuffled)
    elapsed = time.perf_counter() - start

    assert result is True
    assert elapsed < 1.0, f"deep_equal took {elapsed:.3f}s on {size}-element list"


def test_deep_equal_fast_path_detects_multiset_difference():
    """Counter semantics on the fast path: duplicates matter."""
    assert not deep_equal(
        [{"x": 1}, {"x": 1}, {"x": 2}], [{"x": 1}, {"x": 2}, {"x": 2}]
    )


def test_deep_equal_fast_path_detects_structural_difference():
    """Hash-based fast path detects a single swapped field."""
    a = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
    b = [{"id": 1, "name": "a"}, {"id": 2, "name": "c"}]
    assert not deep_equal(a, b)


def test_deep_equal_ignore_keys_respected_under_fast_path():
    """ignore_keys must filter out skipped fields before freezing."""
    a = [{"$objectType": "A", "name": "x"}, {"$objectType": "B", "name": "y"}]
    b = [{"$objectType": "C", "name": "y"}, {"$objectType": "D", "name": "x"}]
    assert not deep_equal(a, b)
    assert deep_equal(a, b, ignore_keys={"$objectType"})


def test_deep_equal_unhashable_leaf_falls_back_to_quadratic():
    """Sets inside dicts are unhashable; freeze raises TypeError and the
    quadratic fallback must produce the correct answer.
    """
    a = [{"name": "n1", "members": {1, 2, 3}}, {"name": "n2", "members": {4, 5}}]
    b = [{"name": "n2", "members": {4, 5}}, {"name": "n1", "members": {3, 2, 1}}]
    assert deep_equal(a, b)

    c = [{"name": "n1", "members": {1, 2, 3}}, {"name": "n2", "members": {4, 5}}]
    d = [{"name": "n1", "members": {1, 2, 3}}, {"name": "n2", "members": {4, 6}}]
    assert not deep_equal(c, d)


def test_deep_equal_fallback_exercised_when_freeze_raises(monkeypatch):
    """When _freeze raises, the matcher must dispatch to the quadratic path."""
    calls = {"freeze": 0, "fallback": 0}
    real_fallback = deep_compare._match_quadratic

    def fake_freeze(obj, ignore_keys):
        calls["freeze"] += 1
        raise TypeError("forced fallback for test")

    def tracking_fallback(a, b, ignore_keys):
        calls["fallback"] += 1
        return real_fallback(a, b, ignore_keys)

    monkeypatch.setattr(deep_compare, "_freeze", fake_freeze)
    monkeypatch.setattr(deep_compare, "_match_quadratic", tracking_fallback)

    assert deep_equal([{"a": 1}, {"b": 2}], [{"b": 2}, {"a": 1}])
    assert calls["freeze"] == 1
    assert calls["fallback"] == 1


def test_deep_equal_fallback_preserves_ignore_keys():
    """The quadratic fallback must still honour ignore_keys."""
    a = [{"$objectType": "X", "members": {1, 2}}]
    b = [{"$objectType": "Y", "members": {1, 2}}]
    assert not deep_equal(a, b)
    assert deep_equal(a, b, ignore_keys={"$objectType"})


def test_deep_equal_fast_path_tags_dict_vs_list_distinctly():
    """The internal _DICT_TAG and _LIST_TAG must discriminate empty
    dicts from empty lists so their freezes never collide.
    """
    with patch.object(deep_compare, "_match_quadratic") as fallback_spy:
        assert not deep_equal([{}, {}], [[], []])
        fallback_spy.assert_not_called()


def test_deep_equal_fast_path_nested_lists():
    """Lists inside lists remain order-insensitive at every depth."""
    assert deep_equal([[1, 2, 3], [4, 5]], [[5, 4], [3, 2, 1]])
    assert not deep_equal([[1, 2], [3, 4]], [[1, 2], [3, 5]])
