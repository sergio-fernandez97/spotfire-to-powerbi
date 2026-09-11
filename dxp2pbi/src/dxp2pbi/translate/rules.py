"""Deterministic Spotfire -> DAX rules.

Only translations that are safe by construction get status ``rule``. Everything else is
``needs_review`` with a note saying why; the ``dxp-tmdl`` skill (Claude) or a person fills those in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..spec import Spec, TableSpec

_NAME = r"(?:[^\]]|\]\])+"
_AGG = re.compile(
    rf"(?i)\b(?P<f>Sum|Avg|Count|Min|Max|Median|UniqueCount|StdDev|Var)\s*\(\s*"
    rf"(?:(?:\[(?P<t>{_NAME})\]\.)?\[(?P<c>{_NAME})\])?\s*\)"
)
_DAX_AGG = {
    "sum": "SUM", "avg": "AVERAGE", "min": "MIN", "max": "MAX", "median": "MEDIAN",
    "uniquecount": "DISTINCTCOUNTNOBLANK", "stddev": "STDEV.S", "var": "VAR.S",
}
_LABEL = {
    "sum": "Sum", "avg": "Avg", "count": "Count", "min": "Min", "max": "Max", "median": "Median",
    "uniquecount": "Unique count", "stddev": "StdDev", "var": "Var",
}
_ALIAS = re.compile(rf"(?is)^(?P<body>.*?)\s+as\s+\[(?P<alias>{_NAME})\]\s*$")
_ARITH = re.compile(r"^[\s\d.+\-*/()]*$")
_NUMERIC = {"Integer", "LongInteger", "Real", "SingleReal", "Currency"}
_CASE = re.compile(r"(?is)^\s*case\s+(?P<body>.+?)\s+end\s*$")
_TOKEN = re.compile(
    rf"""(?P<ws>\s+)
      |(?P<dq>"(?:[^"]|"")*")
      |(?P<sq>'(?:[^']|'')*')
      |(?:\[(?P<t>{_NAME})\]\.)?\[(?P<c>{_NAME})\]
      |(?P<num>\d+(?:\.\d+)?)[lL]?
      |(?P<op><=|>=|<>|!=|[-+*/()<>=])
      |(?P<word>\b(?:and|or|not|true|false|null)\b)
      |(?P<other>.)""",
    re.IGNORECASE | re.VERBOSE,
)
_WORDS = {"and": "&&", "or": "||", "not": "NOT", "true": "TRUE()", "false": "FALSE()", "null": "BLANK()"}


@dataclass
class Result:
    status: str
    target_kind: str
    name: str | None = None
    dax: str | None = None
    notes: str | None = None


def unescape(name: str) -> str:
    return name.replace("]]", "]")


def dax_table(table: str) -> str:
    return "'" + table.replace("'", "''") + "'"


def dax_column(table: str, column: str) -> str:
    return f"{dax_table(table)}[{column.replace(']', ']]')}]"


def _review(target_kind: str, notes: str) -> Result:
    return Result("needs_review", target_kind, notes=notes)


def _functions(expr: str) -> list[str]:
    return sorted(set(re.findall(r"([A-Za-z_]\w*)\s*\(", expr)))


def _skip(text: str, i: int, close: str) -> int:
    """Index just past a quoted/bracketed run starting at ``i`` (doubled ``close`` escapes it)."""
    j = i + 1
    while j < len(text):
        if text[j] == close:
            if j + 1 < len(text) and text[j + 1] == close:
                j += 2
                continue
            return j + 1
        j += 1
    return j


def _divide(dax: str) -> str:
    """``a / b`` at top level -> ``DIVIDE(a, b)`` (Spotfire returns empty on /0, like DIVIDE)."""
    depth, ops, i = 0, [], 0
    while i < len(dax):
        ch = dax[i]
        if ch in "'[":
            i = _skip(dax, i, "'" if ch == "'" else "]")
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and ch in "+-*/" and dax[:i].strip():
            ops.append((i, ch))
        i += 1
    if len(ops) == 1 and ops[0][1] == "/":
        i = ops[0][0]
        return f"DIVIDE({dax[:i].strip()}, {dax[i + 1:].strip()})"
    return dax


def _column(spec: Spec, table: str, column: str):
    t = spec.table(table)
    return next((c for c in t.columns if c.name == column), None) if t else None


# -- aggregations -> measures ---------------------------------------------------------------

def aggregation(expr: str, table: TableSpec | None, spec: Spec) -> Result:
    if "${" in expr:
        return _review("measure", "driven by a document property (${...}); use a field parameter or fix the column")
    if re.search(r"\bOVER\b", expr, re.IGNORECASE):
        return _review("measure", "OVER expression; rewrite with CALCULATE + ALL/ALLEXCEPT or window functions")
    if table is None:
        return _review("measure", "visual has no data table")

    m = _ALIAS.match(expr)
    body, alias = (m.group("body"), unescape(m.group("alias"))) if m else (expr, None)
    problems: list[str] = []
    used: list[tuple[str, str]] = []

    def replace(mm: re.Match) -> str:
        func = mm.group("f").lower()
        tname = unescape(mm.group("t")) if mm.group("t") else table.name
        if mm.group("c") is None:
            if func == "count":
                used.append((func, "rows"))
                return f"COUNTROWS({dax_table(tname)})"
            problems.append(f"{mm.group('f')}() without a column")
            return "0"
        cname = unescape(mm.group("c"))
        column = _column(spec, tname, cname)
        if column is None:
            problems.append(f"unknown column [{tname}].[{cname}]")
            return "0"
        if func == "count":
            fn = "COUNT" if column.spotfire_type in _NUMERIC else "COUNTA"
        else:
            fn = _DAX_AGG[func]
        used.append((func, cname))
        return f"{fn}({dax_column(tname, cname)})"

    dax = _AGG.sub(replace, body).strip()
    residue = _AGG.sub("", body)
    if problems:
        return _review("measure", "; ".join(problems))
    if not used:
        return _review("measure", "no recognised aggregation; functions: " + (", ".join(_functions(expr)) or "none"))
    if not _ARITH.match(residue):
        funcs = _functions(residue)
        return _review("measure", "unsupported functions: " + ", ".join(funcs) if funcs else "unsupported syntax")

    simple = len(used) == 1 and not residue.strip()
    name = alias or (f"{_LABEL[used[0][0]]} {used[0][1]}" if simple else None)
    notes = None
    if any(f == "uniquecount" for f, _ in used):
        notes = "UniqueCount -> DISTINCTCOUNTNOBLANK (both ignore empty values)"
    return Result("rule", "measure", name=name, dax=_divide(dax), notes=notes)


# -- calculated columns ---------------------------------------------------------------------

def _simple(expr: str, table: TableSpec, spec: Spec) -> tuple[str | None, str | None]:
    """Column refs, literals and operators only. Returns (dax, error)."""
    out: list[str] = []
    for m in _TOKEN.finditer(expr):
        if m.group("ws"):
            out.append(" ")
        elif m.group("dq"):
            out.append(m.group("dq"))
        elif m.group("sq"):
            text = m.group("sq")[1:-1].replace("''", "'").replace('"', '""')
            out.append(f'"{text}"')
        elif m.group("c") is not None:
            tname = unescape(m.group("t")) if m.group("t") else table.name
            cname = unescape(m.group("c"))
            if _column(spec, tname, cname) is None:
                return None, f"unknown column [{tname}].[{cname}]"
            if tname != table.name:
                return None, f"column from another table [{tname}].[{cname}] (needs RELATED)"
            out.append(dax_column(tname, cname))
        elif m.group("num") is not None:
            out.append(m.group("num"))
        elif m.group("op"):
            out.append("<>" if m.group("op") == "!=" else m.group("op"))
        elif m.group("word"):
            out.append(_WORDS[m.group("word").lower()])
        else:
            return None, f"unsupported syntax near {m.group('other')!r}"
    return re.sub(r"\s+", " ", "".join(out)).strip(), None


def _case(expr: str, table: TableSpec, spec: Spec) -> tuple[str | None, str | None]:
    m = _CASE.match(expr)
    if not m:
        return None, "not a case expression"
    parts = re.split(r"(?i)\b(when|then|else)\b", m.group("body"))
    if parts[0].strip():
        return None, "CASE <expr> WHEN ... form not supported"
    keywords = [p.lower() for p in parts[1::2]]
    pairs = keywords[:-1] if keywords and keywords[-1] == "else" else keywords
    if not pairs or pairs != ["when", "then"] * (len(pairs) // 2) or len(pairs) % 2:
        return None, "unbalanced WHEN/THEN"
    args, default = [], None
    for keyword, text in zip(keywords, parts[2::2]):
        dax, err = _simple(text, table, spec)
        if err:
            return None, err
        if keyword == "else":
            default = dax
        else:
            args.append(dax)
    tail = f", {default}" if default else ""
    return f"SWITCH(TRUE(), {', '.join(args)}{tail})", None


def calculated(expr: str, table: TableSpec | None, spec: Spec) -> Result:
    if table is None:
        return _review("calculated_column", "table not found")
    if "${" in expr:
        return _review("calculated_column", "driven by a document property (${...})")
    funcs = _functions(expr)
    if any(f.lower().startswith("binby") for f in funcs):
        return _review("calculated_column",
                       f"binning ({', '.join(funcs)}): Spotfire computes bins from the data; "
                       "implement as SWITCH over explicit thresholds or bucket in Power Query")
    if re.match(r"(?is)^\s*case\b", expr):
        dax, err = _case(expr, table, spec)
    elif not funcs:
        dax, err = _simple(expr, table, spec)
    else:
        dax, err = None, "Spotfire functions to translate: " + ", ".join(funcs)
    if err:
        return _review("calculated_column", err)
    return Result("rule", "calculated_column", dax=dax)


# -- categorical axes -> visual configuration -----------------------------------------------

def categorical(expr: str) -> Result:
    inner = expr[1:-1] if expr.startswith("<") and expr.endswith(">") else expr
    columns = [unescape(c) for c in re.findall(rf"\[({_NAME})\]", inner)]
    m = re.search(rf"BinByDateTime\(\s*\[(?P<c>{_NAME})\]\s*,\s*\"(?P<levels>[^\"]*)\"", inner)
    if m:
        notes = f"date hierarchy on [{unescape(m.group('c'))}]: {m.group('levels').replace('.', ' > ')}"
    elif re.search(r"\bNEST\b", inner, re.IGNORECASE):
        notes = "hierarchy: " + " > ".join(columns)
    elif re.search(r"\bCROSS\b", inner, re.IGNORECASE):
        notes = "all combinations of: " + ", ".join(columns)
    elif columns:
        notes = "axis field: " + ", ".join(columns)
    else:
        notes = "axis expression: configure by hand"
    return Result("not_applicable", "visual", notes=notes)
