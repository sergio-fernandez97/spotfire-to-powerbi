"""A small TMDL reader: enough structure for the validator, not a full TMDL implementation.

Handles object declarations (``table X``, ``measure 'A b' = ...``, ``ref table X``),
``key: value`` properties, ``/// description`` lines, and multi-line expressions (``source =``
or ``measure X =`` followed by deeper-indented lines). Indentation must be tabs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_NAME = r"'(?:[^']|'')*'|[^\s=']+"
_DECL = re.compile(rf"^(?P<kind>[A-Za-z]\w*)(?:\s+(?P<name>{_NAME}))?(?:\s*=\s*(?P<expr>.*))?$")
_REF = re.compile(rf"^ref\s+(?P<target>\w+)\s+(?P<name>{_NAME})$")
_PROP = re.compile(r"^(?P<key>[A-Za-z]\w*)\s*:\s*(?P<value>.*)$")
_EXPR_PROP = re.compile(r"^(?P<key>source|expression|formatStringDefinition|defaultExpression)\s*=\s*(?P<expr>.*)$")
# Objects whose own properties sit one level below them, so their expression block is deeper.
_OBJECTS_WITH_BLOCK = {"measure", "column", "expression", "calculationItem", "table"}


@dataclass
class TmdlObject:
    kind: str
    name: str | None
    line: int
    expression: str | None = None
    target: str | None = None  # `ref <target> <name>`
    description: str | None = None
    properties: dict[str, str] = field(default_factory=dict)
    children: list["TmdlObject"] = field(default_factory=list)


def unquote(name: str | None) -> str | None:
    if name and len(name) >= 2 and name[0] == "'" and name[-1] == "'":
        return name[1:-1].replace("''", "'")
    return name


def _level(raw: str) -> int:
    return len(raw) - len(raw.lstrip("\t"))


def _block(lines: list[str], i: int, threshold: int, first: str) -> tuple[str, int]:
    """Collect the expression lines after line ``i`` that are indented deeper than ``threshold``."""
    parts = [first.strip()] if first.strip() else []
    j = i + 1
    while j < len(lines):
        raw = lines[j]
        if raw.strip() and _level(raw) <= threshold:
            break
        parts.append(raw.lstrip("\t"))
        j += 1
    while parts and not parts[-1].strip():
        parts.pop()
    return "\n".join(parts), j


def parse(text: str) -> tuple[list[TmdlObject], list[tuple[int, str]]]:
    lines = text.replace("\r\n", "\n").split("\n")
    roots: list[TmdlObject] = []
    errors: list[tuple[int, str]] = []
    stack: list[tuple[int, TmdlObject]] = []
    description: list[str] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            i += 1
            continue
        level = _level(raw)
        body = raw[level:]
        if body[:1] == " ":
            errors.append((i + 1, "indentation must use tabs"))
        body = body.strip()
        if body.startswith("///"):
            description.append(body[3:].strip())
            i += 1
            continue

        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else None

        if parent is not None:
            m = _EXPR_PROP.match(body)
            if m:
                parent.properties[m.group("key")], i = _block(lines, i, level, m.group("expr"))
                continue
            m = _PROP.match(body)
            if m:
                parent.properties[m.group("key")] = m.group("value").strip()
                i += 1
                continue

        m = _REF.match(body)
        if m:
            obj = TmdlObject("ref", unquote(m.group("name")), i + 1, target=m.group("target"))
            i += 1
        else:
            m = _DECL.match(body)
            if not m:
                errors.append((i + 1, f"cannot parse: {body[:60]}"))
                i += 1
                continue
            kind, expr = m.group("kind"), m.group("expr")
            obj = TmdlObject(kind, unquote(m.group("name")), i + 1)
            if expr is not None and not expr.strip():
                threshold = level + 1 if kind in _OBJECTS_WITH_BLOCK else level
                obj.expression, i = _block(lines, i, threshold, "")
            else:
                obj.expression = expr.strip() if expr is not None else None
                i += 1

        if description:
            obj.description = "\n".join(description)
            description = []
        (parent.children if parent else roots).append(obj)
        stack.append((level, obj))
    return roots, errors
