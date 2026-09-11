"""Emit a Power BI semantic model in TMDL (``<analysis>.SemanticModel/``).

Input is the spec plus translations.json. Nothing here guesses: an expression without a
ready translation (status rule / ai / human), or one that references a column the model does not
have, is emitted as ``BLANK()`` with a ``/// TODO(dxp2pbi)`` description so the model still loads
and the gap is visible in Power BI and in ``dxp2pbi validate``.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ..spec import ColumnSpec, Spec, TableSpec
from ..translate.store import READY_STATUSES, TranslationItem, Translations
from . import dax, m_sources
from .types import NUMERIC_TMDL_TYPES, format_string, tmdl_type

TODO = "TODO(dxp2pbi)"
_NAMESPACE = uuid.UUID("5b0c3c1e-7c43-4f8e-9d3a-2f6d7d0b9a11")
_SIMPLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def q(name: str) -> str:
    """Quote a TMDL object name when needed."""
    return name if _SIMPLE.match(name) else "'" + name.replace("'", "''") + "'"


def _lineage(*parts: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, "/".join(parts)))


def _one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _file_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name) + ".tmdl"


def _decl(head: str, expression: str, level: int) -> list[str]:
    if "\n" not in expression:
        return [f"{head} = {expression}"]
    pad = "\t" * (level + 2)
    return [f"{head} ="] + [pad + line if line.strip() else "" for line in expression.split("\n")]


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def _skip_reason(column: ColumnSpec) -> str | None:
    if column.origin == "tags":
        return "Spotfire tags column (saved marking state)"
    if column.spotfire_type == "Binary":
        return "binary column (e.g. map geometry)"
    if column.origin == "other":
        return "unknown column origin"
    return None


@dataclass
class EmitResult:
    root: Path
    todos: list[str] = field(default_factory=list)


class _Emitter:
    def __init__(self, spec: Spec, translations: Translations, out_dir: Path):
        self.spec = spec
        self.analysis = spec.analysis_name
        self.result = EmitResult(out_dir / f"{spec.analysis_name}.SemanticModel")
        self.params = m_sources.parameter_names(spec)
        self.by_key = {(i.kind, i.table, i.expression): i for i in translations.items}
        self.measures: dict[str, list[TranslationItem]] = {}
        for item in translations.items:
            if item.target_kind != "measure":
                continue
            if item.table and spec.table(item.table):
                self.measures.setdefault(item.table, []).append(item)
            else:
                self.todo(f"measure {item.name}: no host table for {_one_line(item.expression)}")
        self.columns: dict[str, dict[str, str]] = {
            t.name: {c.name: tmdl_type(c.spotfire_type) for c in t.columns if not _skip_reason(c)}
            for t in spec.tables
        }
        self.measure_names = {i.name for items in self.measures.values() for i in items if i.name}

    def todo(self, message: str) -> None:
        self.result.todos.append(message)

    def _ready_dax(self, item: TranslationItem | None, table: str) -> tuple[str | None, str]:
        """(dax, why-not). dax is None when a placeholder must be emitted."""
        if item is None:
            return None, "no translation entry"
        if item.status not in READY_STATUSES or not item.dax:
            return None, item.notes or f"status {item.status}"
        names = {t: set(cols) for t, cols in self.columns.items()}
        miss = dax.missing(item.dax, table, names, self.measure_names)
        if miss:
            return None, "references objects not in the model: " + ", ".join(miss)
        return item.dax, ""

    def table(self, t: TableSpec) -> list[str]:
        lines = [f"table {q(t.name)}", f"\tlineageTag: {_lineage(self.analysis, 'table', t.name)}", ""]

        for m in self.measures.get(t.name, []):
            expression, why = self._ready_dax(m, t.name)
            if expression:
                lines.append(f"\t/// Spotfire: {_one_line(m.expression)}")
            else:
                lines.append(f"\t/// {TODO}: translate Spotfire expression: {_one_line(m.expression)}")
                self.todo(f"measure {t.name}[{m.name}]: {why}")
                expression = "BLANK()"
            lines += _decl(f"\tmeasure {q(m.name)}", expression, 1)
            lines += [f"\t\tlineageTag: {_lineage(self.analysis, 'measure', t.name, m.name)}", ""]

        source_columns: list[ColumnSpec] = []
        for c in t.columns:
            reason = _skip_reason(c)
            if reason:
                self.todo(f"column {t.name}[{c.name}] not emitted: {reason}")
                continue
            data_type = tmdl_type(c.spotfire_type)
            if c.origin == "calculated":
                item = self.by_key.get(("calculated_column", t.name, c.expression))
                expression, why = self._ready_dax(item, t.name)
                if expression:
                    lines.append(f"\t/// Spotfire: {_one_line(c.expression or '')}")
                else:
                    lines.append(f"\t/// {TODO}: translate Spotfire expression: {_one_line(c.expression or '')}")
                    self.todo(f"column {t.name}[{c.name}]: {why}")
                    expression = "BLANK()"
                lines += _decl(f"\tcolumn {q(c.name)}", expression, 1)
            else:
                lines.append(f"\tcolumn {q(c.name)}")
                source_columns.append(c)
            lines.append(f"\t\tdataType: {data_type}")
            fmt = format_string(c.spotfire_type)
            if fmt:
                lines.append(f"\t\tformatString: {fmt}")
            lines.append(f"\t\tlineageTag: {_lineage(self.analysis, 'column', t.name, c.name)}")
            lines.append(f"\t\tsummarizeBy: {'sum' if data_type in NUMERIC_TMDL_TYPES else 'none'}")
            if c.origin == "source":
                lines.append(f"\t\tsourceColumn: {c.name}")
            lines += ["", "\t\tannotation SummarizationSetBy = Automatic"]
            if c.spotfire_type == "Date":
                lines += ["", "\t\tannotation UnderlyingDateTimeDataType = Date"]
            lines.append("")

        query, reason = m_sources.partition_query(
            t, source_columns, self.spec.source(t.source_id), self.params.get(t.source_id or "")
        )
        if reason:
            self.todo(f"table {t.name}: {reason}")
        lines += [f"\tpartition {q(t.name)} = m", "\t\tmode: import", "\t\tsource ="]
        lines += ["\t\t\t" + line if line.strip() else "" for line in query.split("\n")]
        lines += ["", "\tannotation PBI_ResultType = Table", ""]
        return lines

    def relationships(self) -> list[str]:
        lines: list[str] = []
        seen: set[frozenset[str]] = set()
        for r in self.spec.relations:
            label = f"relation {r.left_table} ↔ {r.right_table}"
            if len(r.pairs) != 1:
                self.todo(f"{label}: {len(r.pairs)} column pairs; build the relationship by hand ({r.expression})")
                continue
            a, b = r.pairs[0]
            left, right = self.columns.get(r.left_table, {}), self.columns.get(r.right_table, {})
            if a not in left or b not in right:
                self.todo(f"{label}: column not in the model ({r.expression})")
                continue
            if left[a] != right[b]:
                self.todo(f"{label}: data types differ ({left[a]} vs {right[b]})")
                continue
            pair = frozenset((r.left_table, r.right_table))
            lines += [
                f"relationship {_lineage(self.analysis, 'relationship', r.left_table, a, r.right_table, b)}",
                f"\tfromColumn: {q(r.left_table)}.{q(a)}",
                f"\ttoColumn: {q(r.right_table)}.{q(b)}",
                # Spotfire relations carry no cardinality; many-to-many always loads. Tighten
                # to many-to-one once the data is in.
                "\tfromCardinality: many",
                "\ttoCardinality: many",
                "\tcrossFilteringBehavior: bothDirections",
            ]
            if pair in seen:
                lines.append("\tisActive: false")
            seen.add(pair)
            lines.append("")
        return lines

    def run(self) -> EmitResult:
        root = self.result.root
        definition = root / "definition"
        if definition.exists():
            shutil.rmtree(definition)  # generated output only; never hand-edited
        (definition / "tables").mkdir(parents=True)

        pbism = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/"
                       "definitionProperties/1.0.0/schema.json",
            "version": "4.0",
            "settings": {},
        }
        (root / "definition.pbism").write_text(json.dumps(pbism, indent=2) + "\n", encoding="utf-8")
        _write(definition / "database.tmdl", ["database", "\tcompatibilityLevel: 1567"])

        culture = next((s.settings["culture"] for s in self.spec.data_sources
                        if s.settings.get("culture")), "en-US")
        order = list(self.params.values()) + [t.name for t in self.spec.tables]
        model = [
            "model Model",
            f"\tculture: {culture}",
            "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
            f"\tsourceQueryCulture: {culture}",
            "\tdataAccessOptions",
            "\t\tlegacyRedirects",
            "\t\treturnErrorValuesAsNull",
            "",
            f"\tannotation PBI_QueryOrder = {json.dumps(order, ensure_ascii=False)}",
            "",
            "\tannotation __PBI_TimeIntelligenceEnabled = 1",
            "",
        ] + [f"ref table {q(t.name)}" for t in self.spec.tables]
        _write(definition / "model.tmdl", model)

        if self.params:
            lines: list[str] = []
            for source_id, name in self.params.items():
                source = self.spec.source(source_id)
                lines += [
                    f"/// Spotfire source path; re-point to the delivered file",
                    f"expression {q(name)} = {m_sources.m_string(source.path or '')} meta "
                    '[IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                    f"\tlineageTag: {_lineage(self.analysis, 'expression', name)}",
                    "",
                    "\tannotation PBI_ResultType = Text",
                    "",
                ]
            _write(definition / "expressions.tmdl", lines)

        for t in self.spec.tables:
            _write(definition / "tables" / _file_name(t.name), self.table(t))

        relationships = self.relationships()
        if relationships:
            _write(definition / "relationships.tmdl", relationships)
        return self.result


def emit(spec: Spec, translations: Translations, out_dir: Path) -> EmitResult:
    return _Emitter(spec, translations, out_dir).run()
