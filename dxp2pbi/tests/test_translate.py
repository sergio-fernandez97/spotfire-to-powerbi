from functools import lru_cache
from pathlib import Path

import pytest

from dxp2pbi.extract import build_spec
from dxp2pbi.spec import Spec
from dxp2pbi.translate import translate
from dxp2pbi.translate.store import Translations

DATA = Path(__file__).resolve().parents[2] / "data"


@lru_cache(maxsize=None)
def spec_for(name: str) -> Spec:
    path = DATA / f"{name}.dxp"
    if not path.exists():
        pytest.skip(f"{name}.dxp not present")
    spec, archive = build_spec(path)
    archive.close()
    return spec


def by_expression(translations: Translations) -> dict:
    return {i.expression: i for i in translations.items}


def test_viajes_sum_becomes_measure():
    tr = by_expression(translate(spec_for("Viajes2024")))
    item = tr["Sum([Tarifa])"]
    assert (item.status, item.target_kind) == ("rule", "measure")
    assert item.name == "Sum Tarifa"
    assert item.dax == "SUM('Viajes2024'[Tarifa])"
    date_axis = tr['<BinByDateTime([Fecha],"Year.Month.DayOfMonth",0)>']
    assert date_axis.status == "not_applicable" and "Fecha" in date_axis.notes


def test_stock_performance_rules():
    spec = spec_for("Analyzing Stock Performance")
    tr = translate(spec)
    items = by_expression(tr)

    pe = next(i for i in tr.items if "P/E Ratio" in i.expression and i.kind == "calculated_column")
    assert pe.status == "rule"
    assert pe.dax.startswith("SWITCH(TRUE(), 'sp1500 overview'[P/E Ratio]>=20, \"High P/E\"")
    cap = next(i for i in tr.items if "Market Value" in i.expression and i.kind == "calculated_column")
    assert cap.status == "rule" and "10000000000l" not in cap.dax
    assert items["BinByEvenDistribution([Sales Growth], 5)"].status == "needs_review"
    assert items["Sum([Price]) / Sum([Price]) OVER (FirstNode([Date]))"].status == "needs_review"
    assert items["Sum([${twoRightCharts}])"].status == "needs_review"

    measures = [i for i in tr.items if i.target_kind == "measure"]
    names = [m.name.lower() for m in measures]
    assert len(names) == len(set(names))
    columns = {c.name.lower() for t in spec.tables for c in t.columns}
    assert not columns & set(names)


def test_rerun_keeps_ai_and_human_items():
    spec = spec_for("Viajes2024")
    first = translate(spec)
    item = next(i for i in first.items if i.expression == "Sum([Tarifa])")
    item.status, item.dax, item.name = "ai", "SUMX('Viajes2024', 'Viajes2024'[Tarifa])", "Total fare"
    second = by_expression(translate(spec, first))["Sum([Tarifa])"]
    assert (second.status, second.dax, second.name) == ("ai", item.dax, "Total fare")
