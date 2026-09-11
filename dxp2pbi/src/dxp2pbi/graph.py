"""Resolve the serialized .NET object graph inside ``AnalysisDocument.xml``.

The document is a graph, not a tree. Every object is written once as
``<Object Id=..><Type>..</Type><Fields><Field Name=..>value</Field>..</Fields></Object>`` and
referenced afterwards with ``<ObjectRef Value=id/>``. Types work the same way: the first use is a
``<TypeObject Id=.. FullTypeName=..>`` (with its ``BaseType`` chain), and later uses are
``<TypeRef Value=id/>``. Object ids and type ids share one counter.

``Graph`` indexes every element that carries an ``Id``, then decodes lazily and memoizes by id,
so forward references and cycles (``Owner`` back-pointers are common) resolve without trouble.
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterator
from xml.etree import ElementTree as ET

NS = "{http://www.spotfire.com/schemas/Document1.0.xsd}"

_ID_TAGS = {"Object", "Struct", "Array", "String", "MultiDimensionalArray"}
_INT_TAGS = {"Int", "Short", "Long", "Byte", "SByte", "UInt", "UShort", "ULong"}
_FLOAT_TAGS = {"Float", "Double", "Decimal"}
_INT_TYPES = {
    "System.Int16", "System.Int32", "System.Int64", "System.Byte", "System.SByte",
    "System.UInt16", "System.UInt32", "System.UInt64",
}
_FLOAT_TYPES = {"System.Single", "System.Double", "System.Decimal"}


def _tag(el: ET.Element) -> str:
    return el.tag[len(NS):] if el.tag.startswith(NS) else el.tag


def short_name(full_type_name: str) -> str:
    """``Ns.PersistedZombieCollection`1[[...]]`` -> ``Ns.PersistedZombieCollection``."""
    return full_type_name.split("`")[0].split("[")[0]


def _to_float(raw: str) -> float | str:
    try:
        return float(raw)
    except ValueError:
        return raw


def _parse_primitive_list(text: str, elem_type: str) -> list:
    parts = text.split(",")
    if elem_type in _INT_TYPES:
        return [int(p) for p in parts]
    if elem_type in _FLOAT_TYPES:
        return [_to_float(p) for p in parts]
    if elem_type == "System.Boolean":
        return [p.strip().lower() == "true" for p in parts]
    return parts


@dataclass(eq=False)
class Node:
    """One deserialized ``Object`` or ``Struct``."""

    id: str | None
    type: str
    fields: dict[str, Any] = field(default_factory=dict)

    @property
    def short_type(self) -> str:
        return short_name(self.type)

    @property
    def class_name(self) -> str:
        return self.short_type.rsplit(".", 1)[-1]

    def get(self, name: str, default: Any = None) -> Any:
        return self.fields.get(name, default)

    def __getitem__(self, name: str) -> Any:
        return self.fields[name]

    def __contains__(self, name: str) -> bool:
        return name in self.fields

    def __repr__(self) -> str:
        return f"<{self.class_name} #{self.id}>"


class Graph:
    def __init__(self, xml: bytes):
        root_el = ET.fromstring(xml)
        self._types: dict[str, str] = {}             # type id -> full type name
        self._bases: dict[str, str | None] = {}      # full type name -> base full type name
        self._elements: dict[str, ET.Element] = {}   # value id -> defining element
        self._values: dict[str, Any] = {}            # value id -> decoded value
        self.unknown_tags: set[str] = set()

        for el in root_el.iter():
            tag = _tag(el)
            if tag == "TypeObject":
                self._types[el.get("Id")] = el.get("FullTypeName") or ""
            elif tag in _ID_TAGS and el.get("Id") is not None:
                self._elements[el.get("Id")] = el
        for el in root_el.iter(NS + "TypeObject"):
            base = el.find(f"{NS}NonSystemTypeInfo/{NS}BaseType")
            self._bases[el.get("FullTypeName") or ""] = self._type_of(base) or None

        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(old_limit, 20000))
        try:
            self.root: Node = self._decode(next(iter(root_el)))
            for id_, el in self._elements.items():
                if id_ not in self._values:
                    self._decode(el)
        finally:
            sys.setrecursionlimit(old_limit)

        self.nodes: list[Node] = [v for v in self._values.values() if isinstance(v, Node)]

    # -- decoding ---------------------------------------------------------------------------

    def _type_of(self, container: ET.Element | None) -> str:
        if container is None:
            return ""
        for child in container:
            tag = _tag(child)
            if tag == "TypeObject":
                return child.get("FullTypeName") or ""
            if tag == "TypeRef":
                return self._types.get(child.get("Value"), "")
        return ""

    def _decode(self, el: ET.Element) -> Any:
        tag = _tag(el)
        id_ = el.get("Id")
        if id_ is not None and id_ in self._values:
            return self._values[id_]

        if tag in ("Object", "Struct"):
            node = Node(id_, self._type_of(el.find(NS + "Type")))
            if id_ is not None:
                self._values[id_] = node
            fields_el = el.find(NS + "Fields")
            if fields_el is not None:
                for f in fields_el:
                    children = list(f)
                    node.fields[f.get("Name")] = self._decode(children[0]) if children else None
            return node

        if tag == "ObjectRef":
            target = self._elements.get(el.get("Value"))
            return self._decode(target) if target is not None else None

        if tag == "String":
            value = "" if el.get("IsEmpty") == "true" else el.get("Value")
            if id_ is not None:
                self._values[id_] = value
            return value

        if tag == "Array":
            elem_type = self._type_of(el.find(NS + "Type"))
            values: list = []
            if id_ is not None:
                self._values[id_] = values
            elements = el.find(NS + "Elements")
            if elements is not None:
                if len(elements):
                    values.extend(self._decode(c) for c in elements)
                elif elements.text and elements.text.strip():
                    values.extend(_parse_primitive_list(elements.text.strip(), elem_type))
            return values

        if tag == "MultiDimensionalArray":
            cells: dict[tuple[int, ...], Any] = {}
            if id_ is not None:
                self._values[id_] = cells
            elements = el.find(NS + "Elements")
            for c in elements if elements is not None else []:
                if _tag(c) == "IndexedElement":
                    index = tuple(int(i) for i in c.get("Index", "").split(",") if i)
                    kids = list(c)
                    cells[index] = self._decode(kids[0]) if kids else None
            return cells

        # A field of type System.Type holds the type itself as its value.
        if tag == "TypeObject":
            return el.get("FullTypeName") or ""
        if tag == "TypeRef":
            return self._types.get(el.get("Value"), "")
        if tag == "Bool":
            return el.get("Value") == "true"
        if tag in _INT_TAGS:
            return int(el.get("Value"))
        if tag in _FLOAT_TAGS:
            return _to_float(el.get("Value"))
        if tag == "Char":
            return chr(int(el.get("Value")))
        if tag in ("DateTime", "Enum"):
            return el.get("Value")
        if tag == "NullableNull":
            return None

        self.unknown_tags.add(tag)
        return el.get("Value")

    # -- queries ----------------------------------------------------------------------------

    def is_a(self, full_type_name: str, target: str) -> bool:
        """True if the type, or any base type, has short name ``target``."""
        seen: set[str] = set()
        current: str | None = full_type_name
        while current and current not in seen:
            if short_name(current) == target:
                return True
            seen.add(current)
            current = self._bases.get(current)
        return False

    def find_all(self, target: str, subclasses: bool = False) -> list[Node]:
        if subclasses:
            return [n for n in self.nodes if self.is_a(n.type, target)]
        return [n for n in self.nodes if n.short_type == target]

    def type_inventory(self) -> Counter[str]:
        return Counter(n.short_type for n in self.nodes)


def items(value: Any) -> list:
    """Unwrap Spotfire / .NET collection wrappers into a plain list.

    Handles ``XxxCollection.Items -> PersistedZombieCollection.Nodes -> [..]`` and
    ``List<T>`` (``_items`` array padded to capacity, trimmed to ``_size``).
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, Node):
        if "_items" in value and "_size" in value:
            return list(value["_items"] or [])[: value["_size"]]
        for key in ("Items", "Nodes", "items"):
            if key in value:
                return items(value[key])
    return []


def walk(value: Any) -> Iterator[Node]:
    """Yield every Node reachable from ``value`` (each once)."""
    seen: set[int] = set()
    stack = [value]
    while stack:
        v = stack.pop()
        if isinstance(v, Node):
            if id(v) in seen:
                continue
            seen.add(id(v))
            yield v
            stack.extend(v.fields.values())
        elif isinstance(v, list):
            stack.extend(v)
        elif isinstance(v, dict):
            stack.extend(v.values())
