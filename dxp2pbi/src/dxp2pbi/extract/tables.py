"""Data tables, columns, calculated columns, data sources and relations."""

from __future__ import annotations

import re

from ..graph import Node, items
from ..spec import ColumnSpec, RelationSpec, TableSpec
from . import datasources
from ._context import Context, text_of

_ORIGINS = {
    "SourceColumnImpl": "source",
    "CalculatedColumnImpl": "calculated",
    "TagsColumnImpl": "tags",
}
_REF = r"\[((?:[^\]]|\]\])+)\]"
_PAIR = re.compile(rf"{_REF}\.{_REF}\s*=\s*{_REF}\.{_REF}")


def _unescape(name: str) -> str:
    return name.replace("]]", "]")


def _column(col: Node, table: str, ctx: Context) -> ColumnSpec:
    src = col.get("Source")
    origin = _ORIGINS.get(src.class_name, "other") if isinstance(src, Node) else "other"
    expression = None
    if origin == "calculated":
        producer = src.get("OwnedColumnProducer")
        expression = text_of(producer.get("ExpressionTexts")) if isinstance(producer, Node) else None
        if expression:
            ctx.use(expression, "calculated_column", table, f"{table}.{col['Name']}")
        else:
            ctx.unparsed(f"calculated column {table}.{col['Name']}: expression not found")
    elif origin == "other":
        kind = src.class_name if isinstance(src, Node) else repr(src)
        ctx.unparsed(f"column {table}.{col.get('Name')}: unknown column source {kind}")

    data_type = col.get("DataType")
    external = col.get("ExternalName")
    return ColumnSpec(
        name=col["Name"],
        external_name=external if isinstance(external, str) and external != col["Name"] else None,
        spotfire_type=data_type.get("name") if isinstance(data_type, Node) else str(data_type),
        origin=origin,
        expression=expression,
    )


def extract(ctx: Context) -> None:
    dm = ctx.graph.root["DataManager"]
    source_ids: dict[int, str] = {}

    for t in items(dm.get("Tables")):
        name = t["Name"]
        producer = t.get("ColumnProducer")
        source_id, transformations = None, []
        # Derived producers (e.g. RemoveRowsColumnProducer) wrap the original one.
        while (isinstance(producer, Node) and producer.class_name != "SourceColumnProducer"
               and isinstance(producer.get("OriginalData"), Node)):
            transformations.append(producer.class_name.removesuffix("ColumnProducer"))
            producer = producer["OriginalData"]
        if isinstance(producer, Node) and producer.class_name == "SourceColumnProducer":
            flow = producer.get("DataFlow")
            ds = flow.get("DataSource") if isinstance(flow, Node) else None
            if isinstance(ds, Node):
                source_id = source_ids.get(id(ds))
                if source_id is None:
                    source_id = source_ids[id(ds)] = f"src{len(source_ids) + 1}"
                    ctx.spec.data_sources.append(datasources.describe(ds, source_id))
            if isinstance(flow, Node):
                transformations += [x.class_name for x in items(flow.get("Transformations"))]
        else:
            kind = producer.class_name if isinstance(producer, Node) else repr(producer)
            ctx.unparsed(f"table {name}: unsupported column producer {kind}")

        columns = [_column(c, name, ctx) for c in items(t.get("Columns"))]
        ctx.spec.tables.append(
            TableSpec(name=name, source_id=source_id, columns=columns, transformations=transformations)
        )

    for r in items(dm.get("Relations")):
        left, right = r.get("LeftTableName"), r.get("RightTableName")
        expression = r.get("Expression") or ""
        pairs = []
        for m in _PAIR.finditer(expression):
            t1, c1, t2, c2 = (_unescape(g) for g in m.groups())
            pairs.append((c2, c1) if t1 == right and t2 == left else (c1, c2))
        ctx.spec.relations.append(
            RelationSpec(left_table=left, right_table=right, expression=expression, pairs=pairs)
        )
        ctx.use(expression, "relation", None, f"{left} ↔ {right}")
