"""Open a Spotfire .dxp archive and index its parts.

A .dxp is a ZIP. ``Metadata.xml`` lists one or more ``AnalysisDocument`` variants, one per
compatibility version (e.g. 14.5, 14.4, 14.0); we read the newest. ``EmbeddedResources.xml``
maps ``EmbeddedResources/<n>.emb`` files to logical names such as ``EmbeddedScripts.xml``.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET


def _version_key(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split(".") if p.isdigit())


@dataclass
class DxpArchive:
    path: Path
    zf: zipfile.ZipFile
    document_path: str
    document_version: str
    saved_by_version: str | None
    resources: dict[str, str] = field(default_factory=dict)  # logical name -> archive path
    analysis_metadata: dict = field(default_factory=dict)

    @classmethod
    def open(cls, path: str | Path) -> "DxpArchive":
        path = Path(path)
        zf = zipfile.ZipFile(path)
        names = set(zf.namelist())

        doc_path, doc_version, saved_by = "AnalysisDocument.xml", "", None
        if "Metadata.xml" in names:
            meta = ET.fromstring(zf.read("Metadata.xml"))
            candidates = [
                (p.get("Version", ""), p.get("ArchiveElementPath", ""))
                for p in meta.iter("Property")
                if p.get("ArchiveElementType") == "AnalysisDocument"
            ]
            if candidates:
                doc_version, doc_path = max(candidates, key=lambda c: _version_key(c[0]))
            for p in meta.iter("Property"):
                if p.get("Key") == "SavedByAssemblyFileVersion":
                    saved_by = p.get("Value")
        if doc_path not in names:
            raise ValueError(f"{path.name}: no analysis document found (looked for {doc_path})")

        resources: dict[str, str] = {}
        if "EmbeddedResources.xml" in names:
            er = ET.fromstring(zf.read("EmbeddedResources.xml"))
            for r in er.iter("EmbeddedResource"):
                name, arc = r.get("Name"), r.get("ArchiveElementPath")
                if name and arc in names:
                    resources[name] = arc

        analysis_metadata = {}
        if "AnalysisMetadata.json" in names:
            try:
                analysis_metadata = json.loads(zf.read("AnalysisMetadata.json").decode("utf-8-sig"))
            except (ValueError, UnicodeDecodeError):
                analysis_metadata = {}

        return cls(path, zf, doc_path, doc_version, saved_by, resources, analysis_metadata)

    @property
    def name(self) -> str:
        return self.path.stem

    def read(self, archive_path: str) -> bytes:
        return self.zf.read(archive_path)

    def document_xml(self) -> bytes:
        return self.zf.read(self.document_path)

    def resource(self, logical_name: str) -> bytes | None:
        arc = self.resources.get(logical_name)
        return self.zf.read(arc) if arc else None

    def bookmark_paths(self) -> list[str]:
        return sorted(n for n in self.zf.namelist() if n.startswith("Bookmarks/"))

    def data_table_paths(self) -> list[str]:
        return sorted(n for n in self.zf.namelist() if n.startswith("DataTables/"))

    def preview_png(self) -> bytes | None:
        return self.zf.read("Preview.png") if "Preview.png" in self.zf.namelist() else None

    def close(self) -> None:
        self.zf.close()

    def __enter__(self) -> "DxpArchive":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
