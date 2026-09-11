from functools import lru_cache
from pathlib import Path

import pytest

from dxp2pbi.archive import DxpArchive
from dxp2pbi.graph import Graph, Node, items

DATA = Path(__file__).resolve().parents[2] / "data"
FIXTURES = sorted(DATA.glob("*.dxp"))

pytestmark = pytest.mark.skipif(not FIXTURES, reason="no .dxp fixtures in data/")


@lru_cache(maxsize=None)
def load(path: Path) -> tuple[DxpArchive, Graph]:
    archive = DxpArchive.open(path)
    return archive, Graph(archive.document_xml())


def metadata_count(archive: DxpArchive, key: str) -> int | None:
    for prop in archive.analysis_metadata.get("Properties", []):
        if prop["Key"] == key and prop["Value"]:
            return int(prop["Value"][0])
    return None


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_archive_picks_newest_document(path):
    archive, _ = load(path)
    assert archive.document_path == "AnalysisDocument.xml"
    assert archive.document_version == "14.5"
    assert "EmbeddedScripts.xml" in archive.resources


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_graph_resolves_and_matches_metadata_counts(path):
    archive, g = load(path)
    assert g.root.short_type == "Spotfire.Dxp.Application.Document"
    assert not g.unknown_tags

    tables = items(g.root["DataManager"]["Tables"])
    assert len(tables) == metadata_count(archive, "Spotfire.TableCount")
    assert sum(len(items(t["Columns"])) for t in tables) == metadata_count(
        archive, "Spotfire.ColumnCount"
    )
    pages = items(g.root["Pages"]["Pages"])
    assert len(pages) == metadata_count(archive, "Spotfire.PageCount")


def test_viajes_core_objects():
    path = DATA / "Viajes2024.dxp"
    if not path.exists():
        pytest.skip("Viajes2024.dxp not present")
    _, g = load(path)

    (table,) = g.find_all("Spotfire.Dxp.Data.DataTable")
    assert table["Name"] == "Viajes2024"
    columns = items(table["Columns"])
    assert len(columns) == 18
    assert {"Tarifa", "Fecha", "Origen"} <= {c["Name"] for c in columns}
    assert all(isinstance(c["DataType"], Node) and c["DataType"]["name"] for c in columns)

    (source,) = g.find_all("Spotfire.Dxp.Data.Import.TextFileDataSource")
    assert source["FilePath"] == r"\\Mac\Home\Downloads\Viajes2024.csv"
    assert source["Settings"]["separator"] == ","
