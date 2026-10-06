"""Power Query M for table partitions and their parameters (source paths, database connection)."""

from __future__ import annotations

import re

from dataclasses import dataclass

from ..spec import ColumnSpec, DataSourceSpec, Spec, TableSpec
from .types import m_type

_SIMPLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KEYWORDS = {
    "and", "as", "each", "else", "error", "false", "if", "in", "is", "let", "meta", "not", "null",
    "or", "otherwise", "section", "shared", "then", "true", "try", "type",
}
_PATH_LABEL = {"text": "CsvPath", "excel": "ExcelPath"}
# Database sources: (setting, parameter label, description). Role is only emitted when Spotfire set one.
_DB_PARAMETERS: dict[str, list[tuple[str, str, str]]] = {
    "snowflake": [
        ("server", "SnowflakeServer", "Snowflake account host, <account>.snowflakecomputing.com"),
        ("warehouse", "SnowflakeWarehouse", "Snowflake virtual warehouse that runs the queries"),
        ("database", "SnowflakeDatabase", "Snowflake database"),
        ("role", "SnowflakeRole", "Snowflake role used by the connection; prefer a read-only role"),
    ],
    "odbc": [("dsn", "OdbcDsn", "ODBC data source name on the Desktop / gateway machine")],
}
LOADABLE = set(_PATH_LABEL) | set(_DB_PARAMETERS)


@dataclass(frozen=True)
class Parameter:
    name: str
    value: str  # empty when the .dxp does not say; the model then needs a human to fill it in
    description: str


def m_string(value: str) -> str:
    escaped = (value.replace('"', '""').replace("\t", "#(tab)")
               .replace("\r", "#(cr)").replace("\n", "#(lf)"))
    return f'"{escaped}"'


def m_name(name: str) -> str:
    if _SIMPLE.match(name) and name.lower() not in _KEYWORDS:
        return name
    return '#"' + name.replace('"', '""') + '"'


def parameters(spec: Spec) -> dict[str, dict[str, Parameter]]:
    """source id -> {setting: parameter} for every source Power BI can load.

    Database parameters with the same value are shared, so tables on one Snowflake account use
    one SnowflakeServer parameter.
    """
    counts: dict[str, int] = {}
    shared: dict[tuple[str, str], Parameter] = {}
    out: dict[str, dict[str, Parameter]] = {}

    def new(label: str, value: str, description: str) -> Parameter:
        counts[label] = counts.get(label, 0) + 1
        return Parameter(label if counts[label] == 1 else f"{label}{counts[label]}", value, description)

    for s in spec.data_sources:
        if s.kind in _PATH_LABEL and s.path:
            out[s.id] = {"path": new(_PATH_LABEL[s.kind], s.path,
                                     "Spotfire source path; re-point to the delivered file")}
        for key, label, description in _DB_PARAMETERS.get(s.kind, []):
            value = str(s.settings.get(key) or "")
            if key == "role" and not value:
                continue
            param = shared.get((label, value)) if value else None
            if param is None:
                param = new(label, value, description)
                if value:
                    shared[(label, value)] = param
            out.setdefault(s.id, {})[key] = param
    return out


def _placeholder(columns: list[ColumnSpec], reason: str) -> str:
    # Always #"quoted" so every column name appears as a string literal in the query.
    fields = ", ".join(
        f"#{m_string(c.name)} = {m_type(c.spotfire_type, c.external_type).removeprefix('type ')}" for c in columns
    )
    return "\n".join([
        "let",
        f"    // TODO(dxp2pbi): {reason}",
        f"    Source = #table(type table [{fields}], {{}})",
        "in",
        "    Source",
    ])


def partition_query(
    table: TableSpec, columns: list[ColumnSpec], source: DataSourceSpec | None,
    params: dict[str, Parameter] | None,
) -> tuple[str, str | None]:
    """M for the table's partition. Returns (query, reason) — reason is set for placeholders."""
    params = params or {}
    settings = source.settings if source else {}
    if source is None or source.kind not in LOADABLE or not params:
        kind = source.kind if source else "unknown"
        reason = f"source kind '{kind}' cannot be loaded by Power BI as-is; replace this placeholder query"
        return _placeholder(columns, reason), reason
    if source.kind in _DB_PARAMETERS and not (settings.get("sql") or settings.get("table")):
        reason = f"{source.kind} source {source.id} names no table or SQL statement; replace this placeholder query"
        return _placeholder(columns, reason), reason

    steps: list[tuple[str, str]] = []
    prev = ""

    def add(name: str, expression: str) -> None:
        nonlocal prev
        steps.append((name, expression))
        prev = m_name(name)

    if source.kind == "text":
        options = [
            f"Delimiter={m_string(settings.get('separator', ','))}",
            f"Encoding={settings.get('code_page') or 65001}",
            "QuoteStyle=QuoteStyle.Csv" if settings.get("quote_char") else "QuoteStyle=QuoteStyle.None",
        ]
        add("Source", f"Csv.Document(File.Contents({params['path'].name}), [{', '.join(options)}])")
        if settings.get("header_rows", 1) > 0:
            add("Promoted Headers", f"Table.PromoteHeaders({prev}, [PromoteAllScalars=true])")
    elif source.kind == "excel":
        add("Source", f"Excel.Workbook(File.Contents({params['path'].name}), null, true)")
        sheet = settings.get("sheet")
        add("Sheet", f'Source{{[Item={m_string(sheet)},Kind="Sheet"]}}[Data]' if sheet else "Source{0}[Data]")
        add("Promoted Headers", f"Table.PromoteHeaders({prev}, [PromoteAllScalars=true])")
    elif source.kind == "snowflake":
        role = f", [Role={params['role'].name}]" if "role" in params else ""
        add("Source", f"Snowflake.Databases({params['server'].name}, {params['warehouse'].name}{role})")
        add("Database", f'{prev}{{[Name={params["database"].name},Kind="Database"]}}[Data]')
        if settings.get("sql"):
            add("Query", f"Value.NativeQuery({prev}, {m_string(settings['sql'])}, null, [EnableFolding=true])")
        else:
            add("Schema", f'{prev}{{[Name={m_string(settings.get("schema", ""))},Kind="Schema"]}}[Data]')
            kind = "View" if str(settings.get("table_type", "")).upper() == "VIEW" else "Table"
            add("Data", f'{prev}{{[Name={m_string(settings["table"])},Kind="{kind}"]}}[Data]')
    else:  # odbc
        add("Source", f'Odbc.Query("dsn=" & {params["dsn"].name}, {m_string(settings["sql"])})')

    renames = [(c.external_name, c.name) for c in columns if c.external_name]
    if renames:
        pairs = ", ".join(f"{{{m_string(a)}, {m_string(b)}}}" for a, b in renames)
        add("Renamed Columns", f"Table.RenameColumns({prev}, {{{pairs}}})")
    add("Selected Columns", f"Table.SelectColumns({prev}, {{{', '.join(m_string(c.name) for c in columns)}}})")
    types = ", ".join(f"{{{m_string(c.name)}, {m_type(c.spotfire_type, c.external_type)}}}" for c in columns)
    culture = f", {m_string(settings['culture'])}" if settings.get("culture") else ""
    add("Changed Type", f"Table.TransformColumnTypes({prev}, {{{types}}}{culture})")

    body = ",\n".join(f"    {m_name(name)} = {expression}" for name, expression in steps)
    return f"let\n{body}\nin\n    {prev}", None
