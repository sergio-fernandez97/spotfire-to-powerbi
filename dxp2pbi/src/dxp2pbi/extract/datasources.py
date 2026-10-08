from __future__ import annotations

import re

from ..graph import Node, items
from ..spec import DataSourceSpec
from .data_access import Connection, TableSchema, parse_connection_string

_KINDS = {
    "TextFileDataSource": "text",
    "Excel2FileDataSource": "excel",
    "ExcelFileDataSource": "excel",
    "SbdfFileDataSource": "sbdf_file",
    "SbdfLibraryDataSource": "sbdf_library",
    "ShapeFileDataSource": "shapefile",
}


def _text_settings(s: Node) -> dict:
    code_page = s.get("codePage")
    settings = {
        "separator": s.get("separator"),
        "culture": s.get("culture"),
        "code_page": code_page if isinstance(code_page, int) and code_page > 0 else None,
        "quote_char": s.get("quoteChar") if s.get("hasQuoteChar") else None,
        "comment_prefix": s.get("commentPrefix") or None,
        "header_rows": len(items(s.get("columnNameRows"))),
    }
    return {k: v for k, v in settings.items() if v is not None}


# Connection-string keys kept as source settings (ODBC / Snowflake driver names).
_CONNECTION_KEYS = {"server": "server", "warehouse": "warehouse", "role": "role",
                    "database": "database", "db": "database", "schema": "schema", "dsn": "dsn"}
# SELECT "S"."T".* FROM "S"."T" (optionally with a leading "DB".) is a plain table read.
_IDENT = r'"((?:[^"]|"")+)"'
_SELECT_STAR = re.compile(
    rf"^\s*SELECT\s+(?:{_IDENT}\.)?{_IDENT}\.{_IDENT}\.\*\s+FROM\s+(?:{_IDENT}\.)?{_IDENT}\.{_IDENT}\s*;?\s*$",
    re.IGNORECASE,
)


def _connection_settings(conn: dict[str, str]) -> dict:
    return {_CONNECTION_KEYS[k]: v for k, v in conn.items() if k in _CONNECTION_KEYS and v}


def _is_snowflake(conn: dict[str, str], *hints: str | None) -> bool:
    text = " ".join([*conn.values(), *(h or "" for h in hints)]).lower()
    return "snowflake" in text


def _table_read(sql: str) -> dict | None:
    """Settings for a SQL statement that only selects every column of one table, else None."""
    m = _SELECT_STAR.match(sql)
    if not m:
        return None
    db1, schema1, table1, db2, schema2, table2 = (g.replace('""', '"') if g else g for g in m.groups())
    if (db1, schema1, table1) != (db2, schema2, table2):
        return None
    out = {"schema": schema2, "table": table2}
    if db2:
        out["database"] = db2
    return out


def _database(node: Node, source_id: str) -> DataSourceSpec:
    """``DatabaseDataSource``: an ADO.NET/ODBC connection string plus a SQL statement (import)."""
    s = node.get("Settings")
    s = s if isinstance(s, Node) else Node(None, "")
    conn = parse_connection_string(s.get("ConnectionString") or "")
    sql = (s.get("SqlStatement") or "").replace("\r\n", "\n").strip()
    settings = {"provider": s.get("Provider"), **_connection_settings(conn), "mode": "import"}
    table = _table_read(sql) if sql else None
    if table:
        settings.update(table)
    elif sql:
        settings["sql"] = sql
    if _is_snowflake(conn):
        kind = "snowflake"
    elif s.get("Provider") == "System.Data.Odbc" and conn.get("dsn"):
        kind = "odbc"
        settings["sql"] = sql  # ODBC loads always go through the statement
    else:
        kind = "other"
    return DataSourceSpec(
        id=source_id, kind=kind, spotfire_type=node.short_type,
        settings={k: v for k, v in settings.items() if v},
    )


def describe_connection(connection: Connection, schema: TableSchema, source_id: str,
                        live: bool) -> DataSourceSpec:
    """A table loaded through an embedded Spotfire data connection."""
    attrs = schema.attributes
    settings = {
        "connection": connection.name,
        **_connection_settings(connection.settings),
        "database": attrs.get("ODBC.TableCatalog"),
        "schema": attrs.get("ODBC.SchemaName"),
        "table": attrs.get("ODBC.TableName"),
        "table_type": attrs.get("ODBC.TableType"),
        "mode": "directquery" if live else "import",
    }
    kind = "snowflake" if _is_snowflake(connection.settings, connection.adapter) else "other"
    return DataSourceSpec(
        id=source_id, kind=kind, spotfire_type=connection.adapter or "DataConnection",
        settings={k: v for k, v in settings.items() if v},
    )


def describe(node: Node, source_id: str) -> DataSourceSpec:
    if node.class_name == "DatabaseDataSource":
        return _database(node, source_id)
    kind = _KINDS.get(node.class_name, "other")
    path = node.get("FilePath")
    settings: dict = {}
    s = node.get("Settings")
    if kind == "text" and isinstance(s, Node):
        settings = _text_settings(s)
    elif kind == "excel" and isinstance(s, Node) and s.get("WorkSheetName"):
        settings = {"sheet": s.get("WorkSheetName")}
    elif kind == "sbdf_library":
        path = node.get("path")
    return DataSourceSpec(
        id=source_id,
        kind=kind,
        spotfire_type=node.short_type,
        path=path if isinstance(path, str) else None,
        settings=settings,
    )
