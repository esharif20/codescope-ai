"""Bounded, deterministic changed-definition mapping from private snapshot bytes."""

from collections import Counter
from collections.abc import Callable
from difflib import SequenceMatcher
from pathlib import Path

from app.analysis.models import ParseStatus, Symbol
from app.analysis.module_paths import module_path_for
from app.analysis.python_symbols import extract_symbols
from app.ingestion.models import (
    ChangedSymbol,
    IngestionError,
    MappingResult,
    SnapshotPair,
    validate_path,
)
from app.ingestion.source_links import source_reference


def _read(root: Path, path: str | None) -> bytes:
    if path is None or not path.endswith(".py"):
        return b""
    validate_path(path)
    try:
        target = root / path
        target.resolve().relative_to(root.resolve())
        # Reject symlinks even when they point within the snapshot.
        if any(part.is_symlink() for part in (target, *target.parents)):
            raise ValueError("snapshot symlink")
        return target.read_bytes()
    except (OSError, ValueError) as exc:
        raise IngestionError(
            "snapshot_read_failed", "Snapshot source is unavailable.", 422
        ) from exc


def _start(symbol: Symbol) -> int:
    return symbol.decorator_start_line or symbol.start_line


def map_snapshot_changes(
    pair: SnapshotPair,
    *,
    check_budget: Callable[[], None] = lambda: None,
) -> MappingResult:
    """Map owned changed lines, keeping unsupported locations as public evidence.

    Syntax-recovered files are conservatively unmapped as a whole: an incomplete
    inventory cannot prove additions/deletions in the opposite revision either.
    Upstream patch strings and executable source loading are never used.
    """
    result = MappingResult(
        diagnostics=sorted(set(pair.diagnostics)), partial=bool(pair.diagnostics)
    )
    changes = {}
    unmapped = {}
    identity_paths = {}

    def enforce_limits():
        if len(changes) > 1000 or len(unmapped) > 1000:
            raise IngestionError(
                "mapping_limit_exceeded", "Changed source exceeds mapping limits.", 422
            )

    for changed in sorted(pair.files, key=lambda item: (item.old_path or "", item.new_path or "")):
        check_budget()
        paths = [changed.old_path, changed.new_path]
        if not any(path and path.endswith(".py") for path in paths):
            continue
        sources = [_read(pair.base_root, paths[0]), _read(pair.head_root, paths[1])]
        lines = [source.splitlines(keepends=True) for source in sources]
        if max(map(len, lines)) > 2000 or len(lines[0]) * len(lines[1]) > 2_000_000:
            raise IngestionError(
                "diff_limit_exceeded", "Source diff exceeds processing limits.", 422
            )
        changed_lines = [set(), set()]
        check_budget()
        for tag, i, j, k, end in SequenceMatcher(
            a=lines[0], b=lines[1], autojunk=False
        ).get_opcodes():
            check_budget()
            if tag != "equal":
                changed_lines[0].update(range(i + 1, j + 1))
                changed_lines[1].update(range(k + 1, end + 1))
        parsed = [extract_symbols(source, path or "") for source, path in zip(sources, paths)]
        unsafe = any(
            p.status in (ParseStatus.SYNTAX_ERRORS, ParseStatus.DECODE_ERROR) for p in parsed
        )
        inventories = []
        spans = []
        for side in (0, 1):
            check_budget()
            root = pair.base_root if side == 0 else pair.head_root
            module = module_path_for(str(root / paths[side]), str(root)) if paths[side] else ""
            inventory = {}
            for symbol in parsed[side].symbols:
                check_budget()
                key = (f"{module}:{symbol.qualified_name}", symbol.kind)
                inventory.setdefault(key, []).append(symbol)
                identity_paths.setdefault((side, key), set()).add(paths[side])
            inventories.append(inventory)
            spans.append(
                {
                    key: b"".join(lines[side][_start(s[0]) - 1 : s[0].end_line])
                    for key, s in inventory.items()
                    if len(s) == 1
                }
            )
        ambiguous = {
            key for inv in inventories for key, symbols in inv.items() if len(symbols) != 1
        }
        if unsafe:
            result.diagnostics.append("source_parse_incomplete")
            result.partial = True
        if ambiguous:
            result.diagnostics.append("duplicate_symbol_identity")
            result.partial = True

        def reference(side, start, end):
            return source_reference(
                pair.metadata, "base" if side == 0 else "head", paths[side], start, end
            )

        owned = [set(), set()]
        for side in (0, 1):
            symbols = [
                (key, symbol) for key, values in inventories[side].items() for symbol in values
            ]
            for line in sorted(changed_lines[side]):
                check_budget()
                candidates = [
                    (key, symbol)
                    for key, symbol in symbols
                    if _start(symbol) <= line <= symbol.end_line
                ]
                candidates.sort(
                    key=lambda item: (item[1].end_line - _start(item[1]), -_start(item[1]))
                )
                owner = candidates[0][0] if candidates else None
                tied = len(candidates) > 1 and (
                    _start(candidates[0][1]),
                    candidates[0][1].end_line,
                ) == (_start(candidates[1][1]), candidates[1][1].end_line)
                if owner is not None and owner not in ambiguous and not unsafe and not tied:
                    owned[side].add(owner)
                else:
                    ref = reference(side, line, line)
                    unmapped[(ref.revision, ref.file_path, line)] = ref
                    result.partial = True
                    enforce_limits()
        if unsafe:
            continue
        for key in sorted(set(inventories[0]) | set(inventories[1])):
            check_budget()
            if key in ambiguous:
                continue
            old = inventories[0].get(key)
            new = inventories[1].get(key)
            if old and new:
                if key not in owned[0] | owned[1] or spans[0][key] == spans[1][key]:
                    continue
                status = "modified"
            else:
                status = "removed" if old else "added"
            record = ChangedSymbol(
                symbol_id=key[0],
                kind=key[1],
                status=status,
                old=reference(0, _start(old[0]), old[0].end_line) if old else None,
                new=reference(1, _start(new[0]), new[0].end_line) if new else None,
            )
            changes[record.model_dump_json()] = record
            enforce_limits()
    # A conflicting graph identity across changed files is equally ambiguous.
    counts = Counter({key: len(paths) for key, paths in identity_paths.items()})
    for record_key, change in list(changes.items()):
        key = (change.symbol_id, change.kind)
        if (change.old and counts[(0, key)] > 1) or (change.new and counts[(1, key)] > 1):
            result.partial = True
            result.diagnostics.append("duplicate_symbol_identity")
            for ref in (change.old, change.new):
                if ref:
                    unmapped[(ref.revision, ref.file_path, ref.start_line)] = ref
            del changes[record_key]
            enforce_limits()
    result.changes = sorted(
        changes.values(),
        key=lambda c: (
            (c.old or c.new).file_path,
            c.symbol_id,
            c.status,
            (c.old or c.new).start_line,
            (c.old or c.new).end_line,
        ),
    )
    result.unmapped_changes = [unmapped[key] for key in sorted(unmapped)]
    result.diagnostics = sorted(set(result.diagnostics))
    if result.unmapped_changes:
        result.diagnostics = sorted(set(result.diagnostics) | {"unmapped_changed_lines"})
    return result
