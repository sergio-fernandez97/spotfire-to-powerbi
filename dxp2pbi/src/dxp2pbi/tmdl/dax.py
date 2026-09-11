"""Find the column / measure references in a DAX expression."""

from __future__ import annotations

import re

_STRING = re.compile(r'"(?:[^"]|"")*"')
_QUOTED_REF = re.compile(r"'((?:[^']|'')+)'\[((?:[^\]]|\]\])+)\]")
_BARE_REF = re.compile(r"(?<![\w'\]])([A-Za-z_]\w*)\[((?:[^\]]|\]\])+)\]")
_LONE_REF = re.compile(r"(?<![\w'\]])\[((?:[^\]]|\]\])+)\]")


def references(expression: str) -> list[tuple[str | None, str]]:
    """``('Table', 'Column')`` for qualified refs, ``(None, 'Name')`` for ``[Name]``."""
    text = _STRING.sub('""', expression)
    refs = [(t.replace("''", "'"), c.replace("]]", "]")) for t, c in _QUOTED_REF.findall(text)]
    text = _QUOTED_REF.sub(" ", text)
    refs += [(t, c.replace("]]", "]")) for t, c in _BARE_REF.findall(text)]
    text = _BARE_REF.sub(" ", text)
    refs += [(None, c.replace("]]", "]")) for c in _LONE_REF.findall(text)]
    return refs


def missing(
    expression: str, table: str, columns: dict[str, set[str]], measures: set[str]
) -> list[str]:
    """References that resolve to no column of the model and no measure."""
    out = []
    for t, c in references(expression):
        if t is None:
            if c not in columns.get(table, set()) and c not in measures:
                out.append(f"[{c}]")
        elif t not in columns:
            out.append(f"'{t}' (table)")
        elif c not in columns[t] and c not in measures:
            out.append(f"'{t}'[{c}]")
    return out
