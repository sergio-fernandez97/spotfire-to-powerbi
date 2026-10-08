"""Spotfire data connections: ``DataArchive/DataAccessPlan.xml`` and data-access table schemas.

Tables loaded through a data connection (in-database / "keep data external", and imports made
with a connector) use a ``DataAccessColumnProducer``. The producer references its connection by
GUID; the connection itself (adapter and connection string) lives in the data access plan, and
the producer's ``TableSchema`` XML names the database object and the columns' database types.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from ..graph import Node

_SECRET_KEYS = {"pwd", "password", "token", "passcode", "private_key_file", "private_key_pwd",
                "priv_key_file_pwd", "authenticator_token"}
_DECLARATION = re.compile(r"^\s*<\?xml[^>]*\?>")
_SIZED = {"DECIMAL", "NUMERIC", "NUMBER"}


def guid(node: object) -> str | None:
    """A serialized ``System.Guid`` struct (fields ``_a``..``_k``) as its canonical string."""
    if not isinstance(node, Node) or "_a" not in node:
        return None
    try:
        a, b, c = node["_a"] & 0xFFFFFFFF, node["_b"] & 0xFFFF, node["_c"] & 0xFFFF
        rest = bytes(node[f"_{k}"] & 0xFF for k in "defghijk")
    except (KeyError, TypeError):
        return None
    return f"{a:08x}-{b:04x}-{c:04x}-{rest[:2].hex()}-{rest[2:].hex()}"


def parse_connection_string(text: str) -> dict[str, str]:
    """``key=value;...`` -> {lower-case key: value}, with credentials dropped."""
    out: dict[str, str] = {}
    for part in text.split(";"):
        key, sep, value = part.partition("=")
        key = key.strip().lower()
        if sep and key and key not in _SECRET_KEYS:
            out[key] = value.strip()
    return out


@dataclass
class Connection:
    id: str
    name: str | None
    adapter: str | None
    settings: dict[str, str] = field(default_factory=dict)  # parsed connection string


def connections(xml: bytes | None) -> dict[str, Connection]:
    """Connection id -> connection, from the embedded data access plan."""
    if not xml:
        return {}
    root = ET.fromstring(xml)
    out: dict[str, Connection] = {}
    for conn in root.iter("DataConnection"):
        link = conn.find(".//DataSourceLink")
        cs = conn.findtext(".//DataAdapter/ConnectionString") or ""
        out[(conn.get("Id") or "").lower()] = Connection(
            id=(conn.get("Id") or "").lower(),
            name=conn.get("Name"),
            adapter=link.get("AdapterTypeId") if link is not None else None,
            settings=parse_connection_string(cs),
        )
    return out


@dataclass
class TableSchema:
    attributes: dict[str, str] = field(default_factory=dict)
    column_types: dict[str, str] = field(default_factory=dict)  # column name -> e.g. DECIMAL(38,0)


def _attributes(el: ET.Element) -> dict[str, str]:
    return {a.get("Key", ""): a.get("Value", "") for a in el.findall("./Attributes/Attribute")}


def table_schema(xml: str | None) -> TableSchema:
    """Object and column types from a producer's ``TableSchema.Xml`` (a UTF-16-declared string)."""
    if not xml:
        return TableSchema()
    root = ET.fromstring(_DECLARATION.sub("", xml, count=1))
    schema = TableSchema(attributes=_attributes(root))
    for col in root.iter("DataColumnSchema"):
        attrs = _attributes(col)
        external = attrs.get("ExternalDataType")
        if not external:
            continue
        if external.upper() in _SIZED and attrs.get("ExternalPrecision"):
            external = f"{external}({attrs['ExternalPrecision']},{attrs.get('ExternalScale') or 0})"
        schema.column_types[col.get("Name", "")] = external
    return schema
