"""Power Query M for table partitions and source-path parameters."""

from __future__ import annotations

import re

from ..spec import ColumnSpec, DataSourceSpec, Spec, TableSpec
from .types import m_type

_SIMPLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KEYWORDS = {
    "and", "as", "each", "else", "error", "false", "if", "in", "is", "let", "meta", "not", "null",
    "or", "otherwise", "section", "shared", "then", "true", "try", "type",
}
_PARAMETER_LABEL = {"text": "CsvPath", "excel": "ExcelPath"}
LOADABLE = set(_PARAMETER_LABEL)


def m_string(value: str) -> str:
    escaped = (value.replace('"', '""').replace("\t", "#(tab)")
               .replace("\r", "#(cr)").replace("\n", "#(lf)"))
    return f'"{escaped}"'


def m_name(name: str) -> str:
    if _SIMPLE.match(name) and name.lower() not in _KEYWORDS:
        return name
    return '#"' + name.replace('"', '""') + '"'


def parameter_names(spec: Spec) -> dict[str, str]:
    """source id -> parameter name, for every source Power BI can load from a path."""
    counts: dict[str, int] = {}
    names: dict[str, str] = {}
    for s in spec.data_sources:
        if s.kind in LOADABLE and s.path:
            label = _PARAMETER_LABEL[s.kind]
            counts[label] = counts.get(label, 0) + 1
            names[s.id] = label if counts[label] == 1 else f"{label}{counts[label]}"
    return names


def _placeholder(columns: list[ColumnSpec], reason: str) -> str:
    # Always #"quoted" so every column name appears as a string literal in the query.
    fields = ", ".join(
        f"#{m_string(c.name)} = {m_type(c.spotfire_type).removeprefix('type ')}" for c in columns
    )
    return "\n".join([
        "let",
        f"    // TODO(dxp2pbi): {reason}",
        f"    Source = #table(type table [{fields}], {{}})",
        "in",
        "    Source",
    ])


def partition_query(
    table: TableSpec, columns: list[ColumnSpec], source: DataSourceSpec | None, parameter: str | None
) -> tuple[str, str | None]:
    """M for the table's partition. Returns (query, reason) — reason is set for placeholders."""
    if source is None or source.kind not in LOADABLE or not parameter:
        kind = source.kind if source else "unknown"
        reason = f"source kind '{kind}' cannot be loaded by Power BI as-is; replace this placeholder query"
        return _placeholder(columns, reason), reason

    steps: list[tuple[str, str]] = []
    prev = ""

    def add(name: str, expression: str) -> None:
        nonlocal prev
        steps.append((name, expression))
        prev = m_name(name)

    settings = source.settings
    if source.kind == "text":
        options = [
            f"Delimiter={m_string(settings.get('separator', ','))}",
            f"Encoding={settings.get('code_page') or 65001}",
            "QuoteStyle=QuoteStyle.Csv" if settings.get("quote_char") else "QuoteStyle=QuoteStyle.None",
        ]
        add("Source", f"Csv.Document(File.Contents({parameter}), [{', '.join(options)}])")
        if settings.get("header_rows", 1) > 0:
            add("Promoted Headers", f"Table.PromoteHeaders({prev}, [PromoteAllScalars=true])")
    else:
        add("Source", f"Excel.Workbook(File.Contents({parameter}), null, true)")
        sheet = settings.get("sheet")
        add("Sheet", f'Source{{[Item={m_string(sheet)},Kind="Sheet"]}}[Data]' if sheet else "Source{0}[Data]")
        add("Promoted Headers", f"Table.PromoteHeaders({prev}, [PromoteAllScalars=true])")

    renames = [(c.external_name, c.name) for c in columns if c.external_name]
    if renames:
        pairs = ", ".join(f"{{{m_string(a)}, {m_string(b)}}}" for a, b in renames)
        add("Renamed Columns", f"Table.RenameColumns({prev}, {{{pairs}}})")
    add("Selected Columns", f"Table.SelectColumns({prev}, {{{', '.join(m_string(c.name) for c in columns)}}})")
    types = ", ".join(f"{{{m_string(c.name)}, {m_type(c.spotfire_type)}}}" for c in columns)
    culture = f", {m_string(settings['culture'])}" if settings.get("culture") else ""
    add("Changed Type", f"Table.TransformColumnTypes({prev}, {{{types}}}{culture})")

    body = ",\n".join(f"    {m_name(name)} = {expression}" for name, expression in steps)
    return f"let\n{body}\nin\n    {prev}", None
