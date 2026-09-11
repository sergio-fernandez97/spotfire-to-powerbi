from __future__ import annotations

from ..graph import Node, items
from ..spec import DataSourceSpec

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


def describe(node: Node, source_id: str) -> DataSourceSpec:
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
