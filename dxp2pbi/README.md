# dxp2pbi

Phase 1 of the Spotfire → Power BI migration. It turns a Spotfire `.dxp` into:

- `spec.json` / `spec.md`: the reference document (data sources, model, expressions, page and
  visual checklist, risks);
- `translations.json`: each Spotfire expression and its Power BI target (DAX measure, calculated
  column, visual setting);
- `<analysis>.SemanticModel/`: a TMDL semantic model with typed columns, measures,
  relationships, and a Power Query partition whose file path is a parameter.

It runs on macOS with no Spotfire and no Power BI.

## Run

From the repo root:

```sh
uv run --project dxp2pbi dxp2pbi all data/Viajes2024.dxp     # spec → translate → tmdl → validate
uv run --project dxp2pbi dxp2pbi spec data/*.dxp             # reference documents only
uv run --project dxp2pbi dxp2pbi translate out/Viajes2024    # (re)apply rules, keeps ai/human edits
uv run --project dxp2pbi dxp2pbi tmdl out/Viajes2024         # regenerate + validate the model
uv run --project dxp2pbi dxp2pbi validate out/               # check every generated model
uv run --project dxp2pbi dxp2pbi inspect data/Viajes2024.dxp --types 40
```

Output goes to `out/<analysis>/`, which is gitignored.

## How it works

1. `archive.py` opens the ZIP and picks the newest `AnalysisDocument.xml`.
2. `graph.py` resolves the serialized .NET object graph (`Object`/`ObjectRef`,
   `TypeObject`/`TypeRef`) into nodes.
3. `extract/` pulls tables, columns, sources, relations, pages, visual axes, scripts and risks
   into `spec.py`.
4. `translate/` applies deterministic Spotfire→DAX rules. Anything unsafe becomes `needs_review`
   for the Claude `dxp-tmdl` skill or a person.
5. `tmdl/emit.py` writes the model. Missing translations become `BLANK()` placeholders marked
   `TODO(dxp2pbi)`, so the model still loads.
6. `validate.py` does structural checks. A Claude Code hook runs it whenever a `.tmdl` file or
   `translations.json` changes.

The Claude Code skills are in `.claude/skills/` (`dxp-spec`, `dxp-tmdl`, `dxp-migrate`).

## Test

```sh
cd dxp2pbi && uv run pytest
```

The tests use the `.dxp` fixtures in `../data/`.

## Not covered yet

- Opening the model in Power BI Desktop. It needs Windows, and is step 5 of the flow.
- Generating the report pages (PBIR).
- Decoding the data embedded in `DataTables/*`.
- IronPython scripts and data functions. They are extracted and flagged, not converted.
