"""Hand-labelled local-byte mapping cases; fixture source is never executed."""

import pytest

from app.ingestion.diff_mapping import map_snapshot_changes
from app.ingestion.models import ChangedFile, IngestionError, SnapshotPair
from tests.test_source_links import metadata


def pair(tmp_path, old, new, old_path="m.py", new_path="m.py"):
    base, head = tmp_path / "base", tmp_path / "head"
    base.mkdir(exist_ok=True)
    head.mkdir(exist_ok=True)
    for root, path, content in ((base, old_path, old), (head, new_path, new)):
        if content is not None:
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
    return SnapshotPair(
        metadata(),
        base,
        head,
        [
            ChangedFile(
                old_path=old_path if old is not None else None,
                new_path=new_path if new is not None else None,
                status="added"
                if old is None
                else "removed"
                if new is None
                else "renamed"
                if old_path != new_path
                else "modified",
            )
        ],
        [],
    )


def identities(result):
    return [(change.symbol_id, change.status) for change in result.changes]


@pytest.mark.parametrize(
    "old,new,expected",
    [
        (None, b"def f():\n    pass\n", [("m:f", "added")]),
        (b"def f():\n    pass\n", None, [("m:f", "removed")]),
        (b"", b"def f():\n    pass\n", [("m:f", "added")]),
        (b"def f():\n    return 1\n", b"def f():\n    return 2\n", [("m:f", "modified")]),
        (b"def f(x):\n    pass\n", b"def f(y):\n    pass\n", [("m:f", "modified")]),
        (b"@old\ndef f():\n    pass\n", b"@new\ndef f():\n    pass\n", [("m:f", "modified")]),
        (
            b"def f():\n    x = 1\n    return 2\n",
            b"def f():\n    return 2\n",
            [("m:f", "modified")],
        ),
        (b"def f():\n    pass\n", b"def g():\n    pass\n", [("m:f", "removed"), ("m:g", "added")]),
        (b"def f():\n    pass\n", b"\n\ndef f():\n    pass\n", []),
        (b"def f():\n    pass\n", b"def f():\n    pass", [("m:f", "modified")]),
        (b"def f():\r\n    pass\r\n", b"def f():\n    pass\n", [("m:f", "modified")]),
    ],
)
def test_basic_classification(tmp_path, old, new, expected):
    result = map_snapshot_changes(pair(tmp_path, old, new))
    assert identities(result) == expected
    for change in result.changes:
        if change.old:
            assert change.old.commit_sha == "b" * 40
            assert change.old.revision == "base"
        if change.new:
            assert change.new.commit_sha == "c" * 40


def test_nested_ownership_and_methods(tmp_path):
    old = (
        b"class C:\n    def f(self):\n        def inner():\n"
        b"            return 1\n        return inner()\n"
    )
    result = map_snapshot_changes(pair(tmp_path, old, old.replace(b"return 1", b"return 2")))
    assert identities(result) == [("m:C.f.<locals>.inner", "modified")]
    assert result.changes[0].old.start_line == 3
    assert result.changes[0].new.end_line == 4
    result = map_snapshot_changes(pair(tmp_path, old, old.replace(b"class C:", b"class C(Base):")))
    assert identities(result) == [("m:C", "modified")]


def test_nested_addition_does_not_modify_ancestor(tmp_path):
    old = b"def f():\n    return 1\n"
    new = b"def f():\n    def inner():\n        pass\n    return 1\n"
    assert identities(map_snapshot_changes(pair(tmp_path, old, new))) == [
        ("m:f.<locals>.inner", "added")
    ]


def test_rename_has_both_revision_paths(tmp_path):
    result = map_snapshot_changes(
        pair(tmp_path, b"def f():\n    pass\n", b"def f():\n    pass\n", "old.py", "new.py")
    )
    assert set(identities(result)) == {("old:f", "removed"), ("new:f", "added")}
    assert next(c for c in result.changes if c.old).old.file_path == "old.py"
    assert next(c for c in result.changes if c.new).new.file_path == "new.py"


def test_decorator_ranges_and_shifted_untouched(tmp_path):
    old = b"@old\ndef f():\n    return 1\n\ndef untouched():\n    pass\n"
    new = old.replace(b"@old", b"@new\n@other")
    result = map_snapshot_changes(pair(tmp_path, old, new))
    assert identities(result) == [("m:f", "modified")]
    assert (result.changes[0].old.start_line, result.changes[0].old.end_line) == (1, 3)
    assert (result.changes[0].new.start_line, result.changes[0].new.end_line) == (1, 4)


@pytest.mark.parametrize(
    "old,new",
    [
        (b"x = 1\n", b"x = 2\n"),
        (b"", b"# comment\n"),
        (b"def f():\n    pass\n", b"def f():\n    pass\n# EOF\n"),
        (b"def f():\n    pass\n", b"def f(:\n    pass\n"),
        (b"def f():\n    pass\n", b"\xff\n"),
        (
            b"def f():\n    pass\ndef f():\n    pass\n",
            b"def f():\n    return 1\ndef f():\n    pass\n",
        ),
    ],
)
def test_unsupported_changes_explicit(tmp_path, old, new):
    result = map_snapshot_changes(pair(tmp_path, old, new))
    assert result.partial
    assert result.unmapped_changes
    assert not result.changes
    assert all(ref.start_line > 0 for ref in result.unmapped_changes)


def test_multiregion_and_determinism(tmp_path):
    old = b"def f():\n    return 1\n\ndef g():\n    return 3\n"
    snapshot = pair(tmp_path, old, old.replace(b"1", b"2").replace(b"3", b"4"))
    snapshot.diagnostics = ["upstream_patch_unavailable"]
    one = map_snapshot_changes(snapshot)
    assert identities(one) == [("m:f", "modified"), ("m:g", "modified")]
    assert one.model_dump() == map_snapshot_changes(snapshot).model_dump()
    assert "upstream_patch_unavailable" in one.diagnostics


@pytest.mark.parametrize("old,new", [(b"\n" * 2001, b""), (b"x\n" * 1500, b"y\n" * 1500)])
def test_diff_ceiling_precedes_sequence_matcher(tmp_path, old, new, monkeypatch):
    monkeypatch.setattr(
        "app.ingestion.diff_mapping.SequenceMatcher", lambda **kw: pytest.fail("unbounded diff")
    )
    with pytest.raises(IngestionError) as error:
        map_snapshot_changes(pair(tmp_path, old, new))
    assert error.value.code == "diff_limit_exceeded"


def test_output_ceiling_and_budget(tmp_path):
    source = b"".join(f"def f{i}(): pass\n".encode() for i in range(1001))
    with pytest.raises(IngestionError) as error:
        map_snapshot_changes(pair(tmp_path, None, source))
    assert error.value.code == "mapping_limit_exceeded"
    calls = []
    map_snapshot_changes(pair(tmp_path, b"x=1\n", b"x=2\n"), check_budget=lambda: calls.append(1))
    assert len(calls) >= 5


def test_missing_expected_source_fails_closed(tmp_path):
    snapshot = pair(tmp_path, b"def f(): pass\n", b"def f(): pass\n")
    (snapshot.base_root / "m.py").unlink()
    with pytest.raises(IngestionError) as error:
        map_snapshot_changes(snapshot)
    assert error.value.code == "snapshot_read_failed"


def test_unmapped_ceiling(tmp_path):
    with pytest.raises(IngestionError) as error:
        map_snapshot_changes(pair(tmp_path, None, b"# module edit\n" * 1001))
    assert error.value.code == "mapping_limit_exceeded"


def test_order_and_duplicate_file_records(tmp_path):
    snapshot = pair(tmp_path, b"def f(): return 1\n", b"def f(): return 2\n")
    (snapshot.base_root / "z.py").write_bytes(b"def g(): return 3\n")
    (snapshot.head_root / "z.py").write_bytes(b"def g(): return 4\n")
    snapshot.files.append(ChangedFile(old_path="z.py", new_path="z.py", status="modified"))
    expected = map_snapshot_changes(snapshot).model_dump()
    snapshot.files.reverse()
    snapshot.files.append(snapshot.files[0])
    assert map_snapshot_changes(snapshot).model_dump() == expected


def test_insertion_at_definition_boundary_and_nested_removal(tmp_path):
    old = b"def f():\n    pass\n\ndef g():\n    pass\n"
    new = old.replace(b"def g():", b"def added():\n    pass\n\ndef g():")
    assert identities(map_snapshot_changes(pair(tmp_path, old, new))) == [("m:added", "added")]
    old = b"def f():\n    def inner():\n        pass\n    return 1\n"
    new = b"def f():\n    return 1\n"
    assert identities(map_snapshot_changes(pair(tmp_path, old, new))) == [
        ("m:f.<locals>.inner", "removed")
    ]


def test_snapshot_symlink_rejected(tmp_path):
    snapshot = pair(tmp_path, b"def f(): pass\n", b"def f(): pass\n")
    path = snapshot.base_root / "m.py"
    path.rename(snapshot.base_root / "real.py")
    path.symlink_to("real.py")
    with pytest.raises(IngestionError) as error:
        map_snapshot_changes(snapshot)
    assert error.value.code == "snapshot_read_failed"


def test_trusted_root_beneath_symlinked_ancestor(tmp_path):
    actual_parent = tmp_path / "actual"
    actual_parent.mkdir()
    snapshot = pair(actual_parent, b"def f(): return 1\n", b"def f(): return 2\n")
    alias = tmp_path / "alias"
    alias.symlink_to(actual_parent, target_is_directory=True)
    snapshot.base_root = alias / "base"
    snapshot.head_root = alias / "head"
    result = map_snapshot_changes(snapshot)
    assert identities(result) == [("m:f", "modified")]
    assert not result.partial


@pytest.mark.parametrize("escape", [False, True])
def test_repository_directory_symlink_rejected(tmp_path, escape):
    snapshot = pair(
        tmp_path,
        b"def f(): return 1\n",
        b"def f(): return 2\n",
        old_path="pkg/m.py",
        new_path="pkg/m.py",
    )
    real = tmp_path / "outside" if escape else snapshot.base_root / "real"
    (snapshot.base_root / "pkg").rename(real)
    (snapshot.base_root / "pkg").symlink_to(real, target_is_directory=True)
    with pytest.raises(IngestionError) as error:
        map_snapshot_changes(snapshot)
    assert error.value.code == "snapshot_read_failed"


def test_cross_file_module_identity_collision(tmp_path):
    snapshot = pair(tmp_path, None, b"def f(): pass\n", new_path="pkg.py")
    directory = snapshot.head_root / "pkg"
    directory.mkdir()
    (directory / "__init__.py").write_bytes(b"def f(): return 1\n")
    snapshot.files.append(ChangedFile(new_path="pkg/__init__.py", status="added"))
    result = map_snapshot_changes(snapshot)
    assert not result.changes
    assert result.partial
    assert len(result.unmapped_changes) == 2
    assert "duplicate_symbol_identity" in result.diagnostics
