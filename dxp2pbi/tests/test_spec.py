from functools import lru_cache
from pathlib import Path

import pytest

from dxp2pbi.extract import build_spec
from dxp2pbi.render_md import render_md
from dxp2pbi.spec import Spec

DATA = Path(__file__).resolve().parents[2] / "data"
FIXTURES = sorted(DATA.glob("*.dxp"))

pytestmark = pytest.mark.skipif(not FIXTURES, reason="no .dxp fixtures in data/")


@lru_cache(maxsize=None)
def spec_for(name: str) -> Spec:
    path = DATA / f"{name}.dxp"
    if not path.exists():
        pytest.skip(f"{name}.dxp not present")
    spec, archive = build_spec(path)
    archive.close()
    return spec


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_every_fixture_builds_a_valid_spec(path):
    spec = spec_for(path.stem)
    assert spec.tables and spec.pages
    assert all(t.source_id for t in spec.tables)
    assert Spec.model_validate_json(spec.model_dump_json()) == spec
    md = render_md(spec)
    for t in spec.tables:
        assert f"### {t.name}" in md
    assert "<!-- narrative:begin -->" in md and "<!-- assessment:end -->" in md


def test_viajes_spec():
    spec = spec_for("Viajes2024")
    (table,) = spec.tables
    assert table.name == "Viajes2024" and len(table.columns) == 18
    (source,) = spec.data_sources
    assert source.kind == "text"
    assert source.path == r"\\Mac\Home\Downloads\Viajes2024.csv"
    assert source.settings["separator"] == "," and source.settings["header_rows"] == 1

    (page,) = spec.pages
    assert page.title == "Testing"
    (visual,) = page.visuals
    assert visual.spotfire_type == "GraphicalTable" and visual.data_table == "Viajes2024"
    exprs = {a.expression for a in visual.axes}
    assert {"Sum([Tarifa])", "<[Origen]>"} <= exprs

    kinds = {(e.expression, e.kind) for e in spec.expressions}
    assert ("Sum([Tarifa])", "aggregation") in kinds
    assert any(r.area == "data source" and "local" in r.message for r in spec.risks)


def test_stock_performance_calculated_columns_and_relations():
    spec = spec_for("Analyzing Stock Performance")
    calculated = [c for t in spec.tables for c in t.columns if c.origin == "calculated"]
    assert len(calculated) == 3 and all(c.expression for c in calculated)
    assert any("BinByEvenDistribution" in c.expression for c in calculated)
    assert len(spec.relations) == 4
    assert all(r.pairs for r in spec.relations)
    assert any(r.severity == "high" and "SBDF" in r.message for r in spec.risks)


def test_sales_and_marketing_pages():
    spec = spec_for("Sales and Marketing")
    assert [p.title for p in spec.pages] == [
        "Intro", "Sales performance", "Territory analysis", "Effect of promotions",
    ]
    assert spec.pages[0].visuals[0].text


def test_binning_axes_are_categorical_not_measures():
    spec = spec_for("Configuring Advanced Visualizations")
    binned = [e for e in spec.expressions if "BinByEvenIntervals" in e.expression]
    assert binned and all(e.kind == "categorical" for e in binned)


def test_render_md_keeps_hand_written_blocks():
    spec = spec_for("Viajes2024")
    first = render_md(spec).replace(
        "<!-- narrative:begin -->\n", "<!-- narrative:begin -->\nTravel fares by origin.\n", 1
    )
    first = first.replace("\n_Pending — run the `dxp-spec` skill to write the business narrative "
                          "(purpose, audience, questions the analysis answers)._", "", 1)
    assert "Travel fares by origin." in render_md(spec, existing=first)
