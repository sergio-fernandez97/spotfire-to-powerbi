"""``overrides.json``: facts the .dxp does not hold, confirmed by a person or against the database.

``spec.json`` is regenerated from the .dxp, so corrections live next to it and are applied every
time the spec is loaded::

    {
      "sources": {"src1": {"server": "abc-xy123.snowflakecomputing.com", "database": "SALES"}},
      "column_types": {"CUSTOMERS": {"C_CUSTKEY": "NUMBER(38,0)"}}
    }

``sources`` sets connection settings (never credentials); ``column_types`` sets a column's
database type, e.g. from ``DESCRIBE TABLE``, which decides int64 vs decimal in the model.
"""

from __future__ import annotations

import json
from pathlib import Path

from .spec import Spec

SOURCE_KEYS = {"server", "warehouse", "role", "database", "schema", "table", "table_type", "mode"}
MODES = {"import", "directquery"}


def apply(spec: Spec, path: Path) -> Spec:
    """Return ``spec`` with the overrides in ``path`` applied (unchanged if the file is absent)."""
    if not path.exists():
        return spec
    data = json.loads(path.read_text(encoding="utf-8"))
    spec = spec.model_copy(deep=True)
    errors: list[str] = []

    for source_id, values in (data.get("sources") or {}).items():
        source = spec.source(source_id)
        if source is None:
            errors.append(f"sources.{source_id}: no such data source")
            continue
        for key, value in values.items():
            if key not in SOURCE_KEYS:
                errors.append(f"sources.{source_id}.{key}: not one of {sorted(SOURCE_KEYS)}")
            elif key == "mode" and value not in MODES:
                errors.append(f"sources.{source_id}.mode: must be one of {sorted(MODES)}")
            else:
                source.settings[key] = value
        if "table" in values:
            source.settings.pop("sql", None)  # an explicit table replaces a custom statement

    for table_name, columns in (data.get("column_types") or {}).items():
        table = spec.table(table_name)
        if table is None:
            errors.append(f"column_types.{table_name}: no such table")
            continue
        by_name = {c.name: c for c in table.columns}
        for column, external_type in columns.items():
            if column not in by_name:
                errors.append(f"column_types.{table_name}.{column}: no such column")
            else:
                by_name[column].external_type = external_type

    if errors:
        raise ValueError(f"{path}: " + "; ".join(errors))
    return spec
