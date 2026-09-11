"""Render the human reference document (``spec.md``) from a Spec.

Two blocks are written by Claude (the ``dxp-spec`` skill), not by this renderer: ``narrative``
and ``assessment``. They sit between HTML comment markers and survive regeneration.
"""

from __future__ import annotations

import re

from .spec import Spec
from .tmdl.types import tmdl_type

PBI_VISUAL = {
    "BarChart": "Clustered / stacked bar or column chart",
    "LineChart": "Line chart",
    "CombinationChart": "Line and column chart",
    "PieChart": "Pie / donut chart",
    "ScatterPlot": "Scatter chart",
    "CrossTablePlot": "Matrix",
    "TablePlot": "Table",
    "GraphicalTable": "Table with sparklines / conditional formatting",
    "Treemap": "Treemap",
    "MapChart": "Azure Map / filled map",
    "HtmlTextArea": "Text box (slicers/buttons if the area holds controls)",
    "KpiChart": "Card / KPI",
    "SummaryTable": "Matrix of measures",
    "Heatmap": "Matrix with conditional formatting",
    "WaterfallChart": "Waterfall chart",
    "BoxPlot": "Custom visual (box and whisker)",
}

_BLOCKS = {
    "narrative": "_Pending — run the `dxp-spec` skill to write the business narrative "
                 "(purpose, audience, questions the analysis answers)._",
    "assessment": "_Pending — run the `dxp-spec` skill to write the migration assessment "
                  "(effort, blockers, recommended order of work)._",
}


def _block(name: str, existing: str | None) -> str:
    body = _BLOCKS[name]
    if existing:
        m = re.search(rf"<!-- {name}:begin -->\n(.*?)\n<!-- {name}:end -->", existing, re.S)
        if m:
            body = m.group(1)
    return f"<!-- {name}:begin -->\n{body}\n<!-- {name}:end -->"


def _cell(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _code(value: str | None) -> str:
    if not value:
        return ""
    fence = "``" if "`" in value else "`"
    pad = " " if fence == "``" else ""
    return f"{fence}{pad}{_cell(value)}{pad}{fence}"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def render_md(
    spec: Spec,
    existing: str | None = None,
    has_preview: bool = False,
    translations: dict[str, dict] | None = None,
) -> str:
    """``translations`` maps expression text -> {"status", "target"} (from translations.json)."""
    translations = translations or {}
    out: list[str] = [f"# {spec.analysis_name} — migration reference", ""]
    out.append(_table(
        ["Source file", "Spotfire build", "Document version", "Spec version"],
        [[_cell(spec.source_file), _cell(spec.spotfire_version), _cell(spec.document_version),
          spec.spec_version]],
    ))
    out.append("")
    counts = (f"**{len(spec.tables)}** tables · **{sum(len(t.columns) for t in spec.tables)}** columns · "
              f"**{len(spec.relations)}** relations · **{len(spec.pages)}** pages · "
              f"**{sum(len(p.visuals) for p in spec.pages)}** visuals · "
              f"**{len(spec.expressions)}** expressions · **{len(spec.risks)}** risks")
    out += [counts, ""]
    if has_preview:
        out += ["![Spotfire preview](preview.png)", ""]
    out += ["## Overview", "", _block("narrative", existing), ""]

    out += ["## 1. Data sources", ""]
    if spec.data_sources:
        out.append(_table(
            ["Id", "Kind", "Path", "Settings"],
            [[s.id, s.kind, _code(s.path),
              _cell(", ".join(f"{k}={v!r}" for k, v in s.settings.items()))] for s in spec.data_sources],
        ))
    else:
        out.append("_No file data sources found._")
    out.append("")

    out += ["## 2. Data model", ""]
    for t in spec.tables:
        out += [f"### {t.name}", ""]
        meta = [f"source: `{t.source_id}`" if t.source_id else "source: _unknown_",
                f"{len(t.columns)} columns"]
        if t.transformations:
            meta.append("transformations: " + ", ".join(t.transformations))
        out += [" · ".join(meta), ""]
        out.append(_table(
            ["Column", "Spotfire type", "Power BI type", "Origin", "Expression"],
            [[_cell(c.name), c.spotfire_type, tmdl_type(c.spotfire_type), c.origin,
              _code(c.expression)] for c in t.columns],
        ))
        out.append("")

    out += ["## 3. Relationships", ""]
    if spec.relations:
        out.append(_table(
            ["Left table", "Right table", "Column pairs", "Spotfire expression"],
            [[_cell(r.left_table), _cell(r.right_table),
              _cell(", ".join(f"{a} = {b}" for a, b in r.pairs)), _code(r.expression)]
             for r in spec.relations],
        ))
    else:
        out.append("_No relations._")
    out.append("")

    out += ["## 4. Expressions", "",
            "Aggregations become DAX measures, calculated columns become DAX calculated columns, "
            "categorical axes are visual configuration.", ""]
    if spec.expressions:
        rows = []
        for e in spec.expressions:
            tr = translations.get(e.expression, {})
            where = "; ".join(e.locations[:3]) + (f" (+{len(e.locations) - 3} more)" if len(e.locations) > 3 else "")
            rows.append([e.kind, _code(e.expression), _cell(e.table), _cell(where),
                         _cell(tr.get("status", "")), _code(tr.get("target"))])
        out.append(_table(["Kind", "Spotfire expression", "Table", "Used in", "Status", "Power BI"], rows))
    else:
        out.append("_No expressions._")
    out.append("")

    out += ["## 5. Pages and visuals — build checklist", ""]
    for page in spec.pages:
        out += [f"### {page.title}", ""]
        if not page.visuals:
            out += ["_Empty page._", ""]
            continue
        for v in page.visuals:
            target = PBI_VISUAL.get(v.spotfire_type, "_no direct mapping — decide by hand_")
            line = f"- [ ] **{_cell(v.title or v.spotfire_type)}** — Spotfire `{v.spotfire_type}` → {target}"
            if v.data_table:
                line += f" · table `{v.data_table}`"
            out.append(line)
            for a in v.axes:
                out.append(f"  - {a.role}: {_code(a.expression)}")
            if v.where_clause:
                out.append(f"  - limit data: {_code(v.where_clause)}")
            if v.text:
                out.append(f"  - text: {_cell(v.text)}")
        out.append("")

    out += ["## 6. Scripts and data functions", ""]
    if spec.scripts or spec.data_functions:
        for s in spec.scripts:
            out.append(f"- script `{s.get('kind')}`: {_cell(', '.join(f'{k}' for k in s if k != 'kind'))}")
        for f in spec.data_functions:
            out.append(f"- data function `{f.get('kind')}`")
    else:
        out.append("_None found._")
    out.append("")

    out += ["## 7. Migration risks", ""]
    order = {"high": 0, "medium": 1, "low": 2}
    if spec.risks:
        out.append(_table(
            ["Severity", "Area", "Risk"],
            [[r.severity, r.area, _cell(r.message)] for r in sorted(spec.risks, key=lambda r: order[r.severity])],
        ))
    else:
        out.append("_No risks detected._")
    out += ["", "## Assessment", "", _block("assessment", existing), ""]

    if spec.unparsed:
        out += ["## Appendix — not parsed", ""] + [f"- {_cell(u)}" for u in spec.unparsed] + [""]
    return "\n".join(out)
