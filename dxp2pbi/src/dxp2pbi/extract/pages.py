"""Pages, visuals and the expressions on their axes."""

from __future__ import annotations

import html
import re

from ..graph import Node, items
from ..spec import AxisSpec, PageSpec, VisualSpec
from ._context import Context, text_of

# Fields of a visual that never lead to an axis; skipping them keeps the search small.
_SKIP_FIELDS = {
    "Data", "Legend", "LegendTitleItem", "LegendDescriptionItem", "RuleLegendItem",
    "HorizontalLegend", "DescriptionExpression", "DefaultFont", "LabelFont", "TitleFont",
    "Rules", "StyleOverrides", "ReferenceLines", "FittingModels", "MultipleTableMatches",
    "Configuration", "QualifiedNameMapper",
}
_MAX_DEPTH = 5
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
# Spotfire aggregation methods; an axis using none of them groups data (e.g. BinBy*) rather
# than aggregating it.
_AGGREGATION = re.compile(
    r"\b(?:Sum|Avg|Count|UniqueCount|CountBig|Min|Max|Median|Mode|StdDev|StdErr|Var|First|Last"
    r"|Percentile|P\d+|Q1|Q3|IQR|Range|Product|ValueForMax|ValueForMin|MeanDeviation"
    r"|MedianAbsoluteDeviation|L95|U95|LAV|UAV|Outliers)\s*\(|\bOVER\b",
    re.IGNORECASE,
)


def guid(node) -> str | None:
    """Format a serialized System.Guid struct (_a.._k) as a canonical GUID string."""
    if not isinstance(node, Node) or "_a" not in node:
        return None
    try:
        a, b, c = (int(node[k]) for k in ("_a", "_b", "_c"))
        rest = [int(node[k]) & 0xFF for k in ("_d", "_e", "_f", "_g", "_h", "_i", "_j", "_k")]
    except (KeyError, TypeError, ValueError):
        return None
    return (
        f"{a & 0xFFFFFFFF:08x}-{b & 0xFFFF:04x}-{c & 0xFFFF:04x}-"
        f"{rest[0]:02x}{rest[1]:02x}-" + "".join(f"{x:02x}" for x in rest[2:])
    )


def _axes(content: Node) -> list[AxisSpec]:
    """Every axis reachable from a visual's content (incl. trellis, sparklines, map layers)."""
    found: list[AxisSpec] = []
    seen: set[int] = set()

    def visit(node: Node, path: str, depth: int) -> None:
        if id(node) in seen or depth > _MAX_DEPTH:
            return
        seen.add(id(node))
        if "ExpressionTexts" in node and "Name" in node:
            expr = (text_of(node["ExpressionTexts"]) or "").strip()
            if expr and expr != "<>":
                found.append(AxisSpec(role=path or str(node["Name"]), expression=expr))
            return
        for key, value in node.fields.items():
            if key in _SKIP_FIELDS:
                continue
            step = key if key not in ("Items", "Nodes", "_items") else ""
            child_path = ".".join(p for p in (path, step) if p)
            if isinstance(value, Node):
                if not value.short_type.startswith("Spotfire.Dxp.Data."):
                    visit(value, child_path, depth + 1)
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    if isinstance(v, Node):
                        visit(v, f"{child_path}[{i}]", depth + 1)

    visit(content, "", 0)
    # A sparkline/trellis child repeats its parent's axis; keep the first occurrence only.
    unique, keys = [], set()
    for axis in found:
        key = (axis.role.rsplit(".", 1)[-1], axis.expression)
        if key not in keys:
            keys.add(key)
            unique.append(axis)
    return unique


def _html_to_text(raw: str, limit: int = 400) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _axis_kind(expression: str) -> str | None:
    if expression.startswith("<") and expression.endswith(">"):
        return "categorical"
    if _NUMBER.match(expression):
        return None
    return "aggregation" if _AGGREGATION.search(expression) else "categorical"


def _visual(v: Node, page_title: str, index: int, ctx: Context) -> VisualSpec:
    content = v.get("InternalContent")
    kind = content.class_name if isinstance(content, Node) else "Unknown"
    title = text_of(v.get("TitleExpression"))
    if title and title.strip() == "${AutoTitle}":  # Spotfire-generated title, nothing to migrate
        title = None
    location = f"{page_title} / {title or kind}"

    table, where = None, None
    data = content.get("Data") if isinstance(content, Node) else None
    if isinstance(data, Node):
        dt = data.get("DataTable")
        table = dt.get("Name") if isinstance(dt, Node) else None
        where = text_of(data.get("WhereClauseExpression")) or None

    text, axes = None, []
    if kind == "HtmlTextArea":
        text = _html_to_text(content.get("HtmlContent") or "")
    elif isinstance(content, Node):
        axes = _axes(content)
    else:
        ctx.unparsed(f"visual {location}: no content")

    for axis in axes:
        axis_kind = _axis_kind(axis.expression)
        if axis_kind:
            ctx.use(axis.expression, axis_kind, table, f"{location} [{axis.role}]")
    if where:
        ctx.use(where, "where_clause", table, location)
    if title and "${" in title:
        ctx.use(title, "text", table, location)

    return VisualSpec(
        id=guid(v.get("Id")) or f"visual{index}",
        spotfire_type=kind,
        title=title,
        data_table=table,
        axes=axes,
        where_clause=where,
        text=text,
    )


def extract(ctx: Context) -> None:
    manager = ctx.graph.root.get("Pages")
    pages = items(manager.get("Pages")) if isinstance(manager, Node) else []
    counter = 0
    for i, page in enumerate(pages, 1):
        title = text_of(page.get("TitleExpression")) or f"Page {i}"
        if "${" in title:
            ctx.use(title, "text", None, f"page {i}")
        visuals = []
        for v in items(page.get("Visuals")):
            counter += 1
            visuals.append(_visual(v, title, counter, ctx))
        ctx.spec.pages.append(PageSpec(title=title, visuals=visuals))
