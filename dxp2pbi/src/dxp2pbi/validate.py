"""Structural checks on a TMDL semantic model (used by the CLI and the Claude Code hook).

This does not replace loading the model in Power BI Desktop; it catches the mistakes that make a
model fail to open: bad indentation, duplicate names, dangling DAX / relationship references,
columns the partition query does not produce, unknown parameters and invalid data types.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .tmdl import dax
from .tmdl.parse import TmdlObject, parse, unquote

DATA_TYPES = {"string", "int64", "double", "decimal", "dateTime", "boolean", "binary"}
TODO = "TODO(dxp2pbi)"
_COLUMN_REF = re.compile(r"^('(?:[^']|'')*'|[^.']+)\.('(?:[^']|'')*'|.+)$")
_FILE_CONTENTS = re.compile(r"File\.Contents\(\s*([^)]+?)\s*\)")


@dataclass
class Report:
    root: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        status = "OK" if self.ok else "FAILED"
        lines = [f"{self.root.name}: {status} ({len(self.errors)} errors, {len(self.warnings)} warnings)"]
        lines += [f"  error: {e}" for e in self.errors]
        lines += [f"  warning: {w}" for w in self.warnings]
        return "\n".join(lines)


def validate_model(root: Path) -> Report:
    report = Report(root)
    err, warn = report.errors.append, report.warnings.append
    definition = root / "definition"
    if not (root / "definition.pbism").exists():
        err("definition.pbism missing")
    if not definition.is_dir():
        err("definition/ folder missing")
        return report
    for required in ("database.tmdl", "model.tmdl"):
        if not (definition / required).exists():
            err(f"definition/{required} missing")

    parsed: dict[Path, list[TmdlObject]] = {}
    for f in sorted(definition.rglob("*.tmdl")):
        rel = f.relative_to(root)
        text = f.read_text(encoding="utf-8")
        objects, problems = parse(text)
        for line, message in problems:
            err(f"{rel}:{line}: {message}")
        for n, line in enumerate(text.splitlines(), 1):
            if TODO in line:
                warn(f"{rel}:{n}: {line.strip().lstrip('/').strip()}")
        parsed[f] = objects

    params = {o.name for o in parsed.get(definition / "expressions.tmdl", []) if o.kind == "expression"}
    tables: dict[str, TmdlObject] = {}
    for f, objects in parsed.items():
        if f.parent.name != "tables":
            continue
        found = [o for o in objects if o.kind == "table"]
        if len(found) != 1:
            err(f"{f.relative_to(root)}: expected exactly one table, found {len(found)}")
            continue
        if found[0].name in tables:
            err(f"table {found[0].name} defined twice")
        tables[found[0].name] = found[0]

    for o in parsed.get(definition / "model.tmdl", []):
        if o.kind == "ref" and o.target == "table" and o.name not in tables:
            err(f"model.tmdl: ref table {o.name} has no table file")

    columns = {t: {c.name for c in obj.children if c.kind == "column"} for t, obj in tables.items()}
    measures = {c.name for obj in tables.values() for c in obj.children if c.kind == "measure"}
    for name, n in Counter(m.lower() for obj in tables.values()
                           for m in (c.name for c in obj.children if c.kind == "measure")).items():
        if n > 1:
            err(f"measure name used {n} times in the model: {name}")

    lineage: Counter[str] = Counter()
    for tname, t in tables.items():
        where = f"table {tname}"
        if "lineageTag" in t.properties:
            lineage[t.properties["lineageTag"]] += 1
        partitions = [c for c in t.children if c.kind == "partition"]
        if len(partitions) != 1:
            err(f"{where}: expected one partition, found {len(partitions)}")
        query = partitions[0].properties.get("source", "") if partitions else ""
        for arg in _FILE_CONTENTS.findall(query):
            name = arg[2:-1] if arg.startswith('#"') else arg
            if not arg.startswith('"') and name not in params:
                err(f"{where}: partition reads unknown parameter {arg}")

        names: Counter[str] = Counter()
        for c in t.children:
            if c.kind not in ("column", "measure"):
                continue
            label = f"{where} {c.kind} [{c.name}]"
            names[(c.name or "").lower()] += 1
            if "lineageTag" in c.properties:
                lineage[c.properties["lineageTag"]] += 1
            if c.kind == "measure" and not c.expression:
                err(f"{label}: no expression")
            if c.kind == "column":
                data_type = c.properties.get("dataType")
                if data_type not in DATA_TYPES:
                    err(f"{label}: invalid dataType {data_type!r}")
                source_column = c.properties.get("sourceColumn")
                if c.expression is None:
                    if not source_column:
                        err(f"{label}: neither an expression nor a sourceColumn")
                    elif query and '"' + source_column.replace('"', '""') + '"' not in query:
                        err(f"{label}: sourceColumn '{source_column}' is not produced by the partition query")
            if c.expression:
                for ref in dax.missing(c.expression, tname, columns, measures):
                    err(f"{label}: DAX references {ref}, which is not in the model")
        for name, n in names.items():
            if n > 1:
                err(f"{where}: name used {n} times: {name}")

    for r in parsed.get(definition / "relationships.tmdl", []):
        if r.kind != "relationship":
            continue
        for key in ("fromColumn", "toColumn"):
            ref = r.properties.get(key, "")
            m = _COLUMN_REF.match(ref)
            if not m:
                err(f"relationship {r.name}: malformed {key} {ref!r}")
                continue
            t, c = unquote(m.group(1)), unquote(m.group(2))
            if t not in tables or c not in columns[t]:
                err(f"relationship {r.name}: {key} {ref} does not exist")

    for tag, n in lineage.items():
        if n > 1:
            err(f"lineageTag {tag} used {n} times")
    return report
