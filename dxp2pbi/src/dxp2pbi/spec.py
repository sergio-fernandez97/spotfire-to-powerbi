"""The migration spec: the machine-readable reference extracted from one .dxp.

``spec.json`` is the source of truth. ``spec.md`` (the human reference document) and the TMDL
semantic model are both generated from it.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SPEC_VERSION = "0.1"

Severity = Literal["high", "medium", "low"]
ExpressionKind = Literal[
    "aggregation",        # value axis, e.g. Sum([Tarifa]) -> DAX measure
    "categorical",        # category axis, e.g. <[Origen]> or <BinByDateTime(..)> -> visual config
    "calculated_column",  # column-level expression -> DAX calculated column / M step
    "where_clause",       # visual-level data limiting -> visual/page filter
    "relation",           # table relation -> model relationship
    "text",               # titles, descriptions with ${..} interpolation
]


class DataSourceSpec(BaseModel):
    id: str
    kind: Literal["text", "excel", "sbdf_file", "sbdf_library", "shapefile", "other"]
    spotfire_type: str
    path: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class ColumnSpec(BaseModel):
    name: str
    external_name: str | None = None
    spotfire_type: str
    origin: Literal["source", "calculated", "tags", "other"]
    expression: str | None = None


class TableSpec(BaseModel):
    name: str
    source_id: str | None = None
    columns: list[ColumnSpec]
    transformations: list[str] = Field(default_factory=list)


class RelationSpec(BaseModel):
    left_table: str
    right_table: str
    expression: str
    pairs: list[tuple[str, str]] = Field(default_factory=list)  # (left column, right column)


class AxisSpec(BaseModel):
    role: str
    expression: str


class VisualSpec(BaseModel):
    id: str
    spotfire_type: str
    title: str | None = None
    data_table: str | None = None
    axes: list[AxisSpec] = Field(default_factory=list)
    where_clause: str | None = None
    text: str | None = None  # text areas: HTML reduced to plain text


class PageSpec(BaseModel):
    title: str
    visuals: list[VisualSpec] = Field(default_factory=list)


class ExpressionUse(BaseModel):
    expression: str
    kind: ExpressionKind
    table: str | None = None
    locations: list[str] = Field(default_factory=list)


class Risk(BaseModel):
    severity: Severity
    area: str
    message: str


class Spec(BaseModel):
    spec_version: str = SPEC_VERSION
    analysis_name: str
    source_file: str
    spotfire_version: str | None = None
    document_version: str | None = None
    data_sources: list[DataSourceSpec] = Field(default_factory=list)
    tables: list[TableSpec] = Field(default_factory=list)
    relations: list[RelationSpec] = Field(default_factory=list)
    pages: list[PageSpec] = Field(default_factory=list)
    expressions: list[ExpressionUse] = Field(default_factory=list)
    scripts: list[dict[str, Any]] = Field(default_factory=list)
    data_functions: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    unparsed: list[str] = Field(default_factory=list)

    def table(self, name: str) -> TableSpec | None:
        return next((t for t in self.tables if t.name == name), None)

    def source(self, source_id: str | None) -> DataSourceSpec | None:
        return next((s for s in self.data_sources if s.id == source_id), None)
