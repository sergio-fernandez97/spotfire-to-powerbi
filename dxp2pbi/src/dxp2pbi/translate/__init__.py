"""Map every expression in a Spec to its Power BI target (``translations.json``)."""

from __future__ import annotations

import hashlib

from ..spec import ExpressionUse, Spec
from . import rules
from .store import KEEP_STATUSES, TranslationItem, Translations


def item_id(use: ExpressionUse) -> str:
    """Stable across runs, so hand/AI edits can be matched back to their expression."""
    return "x" + hashlib.sha1(f"{use.kind}|{use.table}|{use.expression}".encode()).hexdigest()[:10]


def _apply_rules(use: ExpressionUse, spec: Spec) -> rules.Result:
    table = spec.table(use.table) if use.table else None
    if use.kind == "aggregation":
        return rules.aggregation(use.expression, table, spec)
    if use.kind == "calculated_column":
        result = rules.calculated(use.expression, table, spec)
        if use.table and use.locations:
            result.name = use.locations[0][len(use.table) + 1:]
        return result
    if use.kind == "categorical":
        return rules.categorical(use.expression)
    if use.kind == "relation":
        return rules.Result("not_applicable", "relationship", notes="emitted from spec.relations")
    if use.kind == "where_clause":
        return rules.Result("not_applicable", "visual", notes="apply as a visual or page filter")
    return rules.Result("not_applicable", "none", notes="report text")


def _name_measures(items: list[TranslationItem], spec: Spec) -> None:
    """Measure names must be unique in the model and must not collide with column names."""
    taken = {c.name.lower() for t in spec.tables for c in t.columns}
    measures = [i for i in items if i.target_kind == "measure"]
    # Names chosen by Claude or a person win; rule-generated names yield.
    measures.sort(key=lambda i: i.status not in KEEP_STATUSES)
    counter = 0
    for item in measures:
        base = item.name
        if not base:
            counter += 1
            base = f"Measure {counter}"
        name = base if base.lower() not in taken else f"{base} (measure)"
        n = 2
        while name.lower() in taken:
            name = f"{base} ({n})"
            n += 1
        taken.add(name.lower())
        item.name = name


def translate(spec: Spec, existing: Translations | None = None) -> Translations:
    kept = {i.id: i for i in existing.items if i.status in KEEP_STATUSES} if existing else {}
    items: list[TranslationItem] = []
    for use in spec.expressions:
        iid = item_id(use)
        if iid in kept:
            items.append(kept[iid])
            continue
        r = _apply_rules(use, spec)
        items.append(TranslationItem(
            id=iid, kind=use.kind, table=use.table, expression=use.expression,
            target_kind=r.target_kind, status=r.status, name=r.name, dax=r.dax, notes=r.notes,
        ))
    _name_measures(items, spec)
    return Translations(analysis_name=spec.analysis_name, spec_version=spec.spec_version, items=items)
