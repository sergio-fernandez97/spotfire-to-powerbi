from pathlib import Path

import pytest

from dxp2pbi.extract import build_spec
from dxp2pbi.tmdl.emit import emit
from dxp2pbi.tmdl.parse import parse
from dxp2pbi.translate import translate
from dxp2pbi.validate import validate_model

DATA = Path(__file__).resolve().parents[2] / "data"
FIXTURES = sorted(DATA.glob("*.dxp"))

pytestmark = pytest.mark.skipif(not FIXTURES, reason="no .dxp fixtures in data/")


def build(name: str, out: Path):
    path = DATA / f"{name}.dxp"
    if not path.exists():
        pytest.skip(f"{name}.dxp not present")
    spec, archive = build_spec(path)
    archive.close()
    return spec, emit(spec, translate(spec), out)


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_emitted_model_validates(path, tmp_path):
    _, result = build(path.stem, tmp_path)
    report = validate_model(result.root)
    assert report.ok, report.render()


def test_viajes_model(tmp_path):
    _, result = build("Viajes2024", tmp_path)
    definition = result.root / "definition"
    text = (definition / "tables" / "Viajes2024.tmdl").read_text(encoding="utf-8")
    assert "measure 'Sum Tarifa' = SUM('Viajes2024'[Tarifa])" in text

    roots, errors = parse(text)
    assert not errors
    (table,) = roots
    assert len([c for c in table.children if c.kind == "column"]) == 18
    (partition,) = [c for c in table.children if c.kind == "partition"]
    assert "Csv.Document(File.Contents(CsvPath)" in partition.properties["source"]

    expressions = (definition / "expressions.tmdl").read_text(encoding="utf-8")
    assert r'expression CsvPath = "\\Mac\Home\Downloads\Viajes2024.csv"' in expressions


def test_emit_is_deterministic(tmp_path):
    _, a = build("Viajes2024", tmp_path / "a")
    _, b = build("Viajes2024", tmp_path / "b")
    files_a = sorted(p.relative_to(a.root) for p in a.root.rglob("*") if p.is_file())
    assert files_a == sorted(p.relative_to(b.root) for p in b.root.rglob("*") if p.is_file())
    for rel in files_a:
        assert (a.root / rel).read_bytes() == (b.root / rel).read_bytes()


def test_stock_relationships_and_todos(tmp_path):
    _, result = build("Analyzing Stock Performance", tmp_path)
    relationships, errors = parse((result.root / "definition" / "relationships.tmdl").read_text(encoding="utf-8"))
    assert not errors
    assert len([r for r in relationships if r.kind == "relationship"]) == 4
    assert any("Binned Sales Growth" in t for t in result.todos)
    assert validate_model(result.root).warnings  # TODO placeholders surface as warnings


def test_validator_catches_dangling_reference(tmp_path):
    _, result = build("Viajes2024", tmp_path)
    f = result.root / "definition" / "tables" / "Viajes2024.tmdl"
    f.write_text(f.read_text(encoding="utf-8").replace("'Viajes2024'[Tarifa]", "'Viajes2024'[Nope]"),
                 encoding="utf-8")
    report = validate_model(result.root)
    assert not report.ok and any("Nope" in e for e in report.errors)


def test_validator_rejects_space_indentation(tmp_path):
    _, result = build("Viajes2024", tmp_path)
    f = result.root / "definition" / "tables" / "Viajes2024.tmdl"
    f.write_text(f.read_text(encoding="utf-8").replace("\tlineageTag", "    lineageTag", 1), encoding="utf-8")
    assert not validate_model(result.root).ok
