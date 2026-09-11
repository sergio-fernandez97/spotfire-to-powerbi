"""Migration risks derived from a finished spec."""

from __future__ import annotations

import re

from ..spec import Risk, Severity, Spec
from ..tmdl.types import is_known

# Characters typical of a Mac Roman / UTF-8 file read with the wrong code page (e.g. "á" -> "‡").
_MOJIBAKE = re.compile(r"[†‡‰ƒ]|Ã.|â€")
_INLINE_SCRIPT = re.compile(r"\b(?:TERR|R|Python)_\w+\s*\(")

_VISUAL_NOTES: dict[str, tuple[Severity, str]] = {
    "MapChart": ("medium", "map chart: geocoding and map layers must be rebuilt (Azure Maps / shape map)"),
    "GraphicalTable": ("medium", "graphical table (sparklines/icons): rebuild as a table with sparklines or conditional formatting"),
    "KpiChart": ("low", "KPI chart: rebuild with card / KPI visuals"),
    "BoxPlot": ("medium", "box plot: no native Power BI visual, needs a custom visual"),
    "Heatmap": ("low", "heat map: rebuild as a matrix with conditional formatting"),
    "WaterfallChart": ("low", "waterfall chart: native visual exists but configuration differs"),
    "ParallelCoordinatePlot": ("medium", "parallel coordinate plot: needs a custom visual"),
    "ScatterPlot3D": ("high", "3D scatter plot: no Power BI equivalent"),
    "SummaryTable": ("low", "summary table: rebuild as a matrix of measures"),
}


def assess(spec: Spec) -> None:
    def add(severity: Severity, area: str, message: str) -> None:
        if not any(r.message == message for r in spec.risks):
            spec.risks.append(Risk(severity=severity, area=area, message=message))

    for s in spec.data_sources:
        if s.kind in ("text", "excel", "sbdf_file") and s.path:
            add("medium", "data source",
                f"{s.id}: file path is local to the author's machine ({s.path}); deliver the file "
                "with the export and re-point the path parameter")
        if s.kind in ("sbdf_file", "sbdf_library"):
            add("high", "data source",
                f"{s.id}: SBDF is Spotfire-only; re-export as CSV/Parquet (or convert with the "
                "`spotfire` Python package) before Power BI can load it")
        if s.kind == "shapefile":
            add("medium", "data source",
                f"{s.id}: shape file ({s.path}) feeds map geometry; use Power BI map geography / "
                "Azure Maps instead of importing it")
        if s.kind == "other":
            add("high", "data source", f"{s.id}: unsupported source type {s.spotfire_type}")

    for t in spec.tables:
        if t.source_id is None:
            add("high", "data model", f"table {t.name}: not loaded from a file source; origin must be rebuilt by hand")
        if t.transformations:
            add("medium", "data model",
                f"table {t.name}: data transformations to port to Power Query: {', '.join(t.transformations)}")
        for c in t.columns:
            if c.origin == "tags":
                add("medium", "data model",
                    f"{t.name}.{c.name}: Spotfire tags column (saved marking state); no Power BI equivalent, usually dropped")
            if not is_known(c.spotfire_type):
                add("medium", "data model", f"{t.name}.{c.name}: unknown Spotfire data type {c.spotfire_type}")
            if _MOJIBAKE.search(c.name):
                add("low", "data model",
                    f"{t.name}.{c.name}: column name looks mis-encoded (source file code page); "
                    "check the header in the delivered file")

    for e in spec.expressions:
        if re.search(r"\bOVER\b", e.expression, re.IGNORECASE):
            add("medium", "expression", f"OVER expression needs a hand-written DAX equivalent: {e.expression}")
        if e.kind != "text" and "${" in e.expression:
            add("medium", "expression",
                f"expression driven by a document property (field parameter / what-if in Power BI): {e.expression}")
        if _INLINE_SCRIPT.search(e.expression):
            add("high", "expression", f"inline R/Python expression function: {e.expression[:160]}")
        if e.kind == "where_clause":
            add("medium", "report", f"visual data-limiting expression → visual/page filter: {e.expression}")
        if e.kind == "text":
            add("low", "report", f"dynamic text with property interpolation: {e.expression}")

    for page in spec.pages:
        for v in page.visuals:
            note = _VISUAL_NOTES.get(v.spotfire_type)
            if note:
                add(note[0], "report", f"{page.title} / {v.title or v.spotfire_type}: {note[1]}")

    for s in spec.scripts:
        add("high", "scripting",
            f"IronPython script ({s.get('kind')}): no Power BI equivalent; re-implement with "
            "bookmarks / field parameters / Power Automate, or drop")
    for f in spec.data_functions:
        add("high", "scripting",
            f"data function ({f.get('kind')}): re-implement in Power Query, a Python/R visual, or upstream")
    for item in spec.unparsed:
        add("low", "parser", f"not parsed: {item}")
