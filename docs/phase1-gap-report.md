# Phase 1 gap report: `.dxp` → reference spec → TMDL

**Date:** 2026-09-11
**Tool:** [`dxp2pbi/`](../dxp2pbi/README.md) (Python CLI) plus Claude Code skills `dxp-spec`,
`dxp-tmdl` and `dxp-migrate`, and a validation hook (`.claude/`).
**Covers:** steps 2–3 of the Viajes2024 flow diagram: parse the XML, then generate the `.tmdl`.

## Result on the 5 fixtures in `data/`

Every analysis parses, produces a reference document (`spec.md`) and a TMDL semantic model, and
**validates with 0 errors**. The table, column and page counts match the counts Spotfire records
in each file (`AnalysisMetadata.json`).

| Analysis | Tables | Columns | Pages / visuals | Sources | Expressions: rule / review / n.a. | TODO in model | Risks H / M / L |
|---|---|---|---|---|---|---|---|
| Viajes2024 | 1 | 18 | 1 / 1 | CSV | 1 / 0 / 2 | 0 | 0 / 2 / 1 |
| Expense Analyzer Dashboard | 1 | 14 | 1 / 11 | TXT | 1 / 0 / 6 | 0 | 0 / 1 / 0 |
| Configuring Advanced Visualizations | 2 | 44 | 6 / 11 | Excel ×2 | 3 / 0 / 5 | 2 | 0 / 4 / 0 |
| Sales and Marketing | 2 | 85 | 4 / 8 | TXT, shapefile | 3 / 0 / 15 | 3 | 0 / 6 / 1 |
| Analyzing Stock Performance | 7 | 61 | 4 / 12 | SBDF ×5, Excel, SBDF library | 6 / 4 / 17 | 12 | 7 / 14 / 2 |

- **rule**: the rules produced valid DAX (measures such as `SUM('Viajes2024'[Tarifa])`, and
  `case when` calculated columns as `SWITCH(TRUE(), …)`).
- **review**: left for the `dxp-tmdl` skill or a person. The model holds a `BLANK()` placeholder
  with a `TODO(dxp2pbi)` description until then.
- **n.a.**: visual configuration, not model content (category axes, date binning → date
  hierarchy, relation expressions, titles).

**Viajes2024**, the pilot, is complete end to end. It has 18 typed columns, measure
`Sum Tarifa`, and a `Csv.Document` partition that reads the `CsvPath` parameter with `en-US`
culture. It has no TODOs.

## What remains, by cause

| Gap | Where | Who / how |
|---|---|---|
| **Data files are not in the `.dxp`.** Only the author's path is stored (`\\Mac\Home\Downloads\Viajes2024.csv`, `C:\Users\…`) | all | Colleagues send the CSV/Excel files; set the `CsvPath` / `ExcelPath` parameter (diagram step 4) |
| SBDF sources (5 files plus 1 library table) | Stock Performance | Re-export as CSV from Spotfire, or convert with the `spotfire` Python package. The tables get a typed empty placeholder until then |
| Shapefile / binary geometry columns | Sales and Marketing, Stock Performance | Not imported. Maps use Power BI geography or Azure Maps (Phase 2 visuals) |
| Spotfire tags columns (saved marking state) | 3 analyses | Dropped on purpose: no Power BI equivalent |
| Document-property expressions (`Sum([${twoRightCharts}])`) | Stock Performance | Field parameter in Power BI. Needs a design decision |
| `OVER` expression (`… OVER (FirstNode([Date]))`) | Stock Performance | `dxp-tmdl` skill: window/`CALCULATE` pattern |
| Data-driven binning (`BinByEvenDistribution`) | Stock Performance | Choose explicit thresholds, or mark unsupported |
| Inline R (`TERR_Integer(… kmeans …)`) | Stock Performance | No DAX equivalent: re-implement upstream or drop |
| Column name mis-encoded (`est‡` for `está`) | Viajes2024 | Confirm the header against the original CSV; set the right code page |
| IronPython scripts / data functions | none in fixtures | Extracted and flagged `high` when present |

## Not yet verified

- **Power BI Desktop has not opened any generated model** (step 5 needs Windows). The checks are
  structural only: indentation, names, DAX and relationship references, and partition columns.
  First test on Windows: copy `out/Viajes2024/Viajes2024.SemanticModel` into a PBIP project, set
  `CsvPath`, and refresh.
- Relationships are emitted as many-to-many, both directions, because Spotfire stores no
  cardinality. Tighten them once real data is loaded.
- The five fixtures are Spotfire demos plus Viajes2024. Real analyses from the colleagues' server
  may bring information links, database connectors or scripts. These are reported under
  `unparsed[]` / `risks[]`, not converted.

## Next phase (from the plan)

A. PBIP + PBIR report generation, using the visual checklist in `spec.md` (step 6).
B. MCP library access ([`spotfire-mcp-findings.md`](./spotfire-mcp-findings.md)). Blocked on
   credentials.
C. Data migration: SBDF/CSV to a shared location.
D. `TmdlSerializer` / Power BI Desktop validation on Windows.
E. Portfolio inventory across many `.dxp` files.
