"""Build a ``Spec`` from a .dxp file."""

from __future__ import annotations

from pathlib import Path

from ..archive import DxpArchive
from ..graph import Graph
from ..spec import Spec
from . import pages, risks, scripts, tables
from ._context import Context


def build_spec(path: str | Path) -> tuple[Spec, DxpArchive]:
    archive = DxpArchive.open(path)
    graph = Graph(archive.document_xml())
    spec = Spec(
        analysis_name=archive.name,
        source_file=archive.path.name,
        spotfire_version=archive.saved_by_version,
        document_version=archive.document_version,
    )
    ctx = Context(graph, spec)
    tables.extract(ctx)
    pages.extract(ctx)
    scripts.extract(ctx, archive)
    risks.assess(spec)
    return spec, archive
