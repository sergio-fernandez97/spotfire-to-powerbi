"""IronPython scripts and data functions — extracted verbatim and always flagged."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from ..archive import DxpArchive
from ..graph import Node, items
from ._context import Context

_MAX_TEXT = 4000


def _strings(node: Node) -> dict:
    """String/number/bool fields of a node and of its direct child nodes."""
    out: dict = {}
    for key, value in node.fields.items():
        if key == "DocumentNodeId":
            continue
        if isinstance(value, (str, int, float, bool)):
            out[key] = value[:_MAX_TEXT] if isinstance(value, str) else value
        elif isinstance(value, Node):
            for k2, v2 in value.fields.items():
                if isinstance(v2, str) and k2 != "DocumentNodeId":
                    out[f"{key}.{k2}"] = v2[:_MAX_TEXT]
    return out


def extract(ctx: Context, archive: DxpArchive) -> None:
    manager = ctx.graph.root.get("ScriptManager")
    if isinstance(manager, Node):
        for s in items(manager.get("ManagedScripts")):
            if isinstance(s, Node):
                ctx.spec.scripts.append({"kind": s.class_name, **_strings(s)})
        for h in items(manager.get("ScriptEventHandlers")):
            if isinstance(h, Node):
                ctx.spec.scripts.append({"kind": h.class_name, **_strings(h)})

    raw = archive.resource("EmbeddedScripts.xml")
    if raw:
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            ctx.unparsed("EmbeddedScripts.xml: not parseable")
        else:
            for child in root:
                ctx.spec.scripts.append(
                    {"kind": f"Embedded:{child.tag}", **child.attrib,
                     "code": (child.text or "")[:_MAX_TEXT]}
                )

    for f in items(ctx.graph.root["DataManager"].get("DataFunctions")):
        if isinstance(f, Node):
            ctx.spec.data_functions.append({"kind": f.class_name, **_strings(f)})
