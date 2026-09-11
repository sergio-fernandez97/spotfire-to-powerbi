---
name: dxp-tmdl
description: Translate the Spotfire expressions that dxp2pbi's rules could not handle (needs_review items in translations.json) into DAX, then generate and validate the Power BI TMDL semantic model. Use after dxp-spec, or when the user asks to build, fix or complete the .tmdl for an analysis.
---

# dxp-tmdl — Spotfire expressions → DAX → TMDL semantic model

`dxp2pbi` translates simple expressions by rule and marks the rest `needs_review`. You fill in
those, by editing `translations.json` only. The `.tmdl` files are always regenerated from
`spec.json` + `translations.json` — **never hand-edit them**, your changes would be lost.

## Steps

1. Refresh the translations (keeps anything already marked `ai` or `human`):

   ```sh
   uv run --project dxp2pbi dxp2pbi translate "out/<analysis>"
   ```

2. Read `out/<analysis>/translations.json` and `spec.json` (for table and column names and types).

3. For every item with `"status": "needs_review"` and `target_kind` `measure` or `calculated_column`:
   - Read `expression`, `notes`, `table`, and where it is used (`spec.json` → `expressions[].locations`).
   - Write DAX following [references/spotfire-to-dax.md](references/spotfire-to-dax.md).
   - Set `dax`, `"status": "ai"`, and in `notes` state any assumption or semantic difference.
   - For measures you may improve `name` (unique; must not equal a column name).
   - If it cannot be translated faithfully (IronPython, TERR/R/Python functions, marking-driven
     logic, document properties with no fixed value), set `"status": "unsupported"` and explain in
     `notes`. **Do not guess.**

4. Leave items with status `rule`, `ai`, `human` or `not_applicable` alone unless the user asks.

5. Regenerate and validate (the PostToolUse hook also does this after you edit `translations.json`):

   ```sh
   uv run --project dxp2pbi dxp2pbi tmdl "out/<analysis>"
   ```

   Errors mean a translation references something that does not exist — fix the translation and
   run it again. Warnings are remaining `TODO(dxp2pbi)` placeholders (`BLANK()`).

6. Report back: counts per status, the TODOs that remain, and anything that needs a human decision.

## DAX conventions

- Columns always as `'Table'[Column]`; measures as `[Measure]`.
- `DIVIDE(a, b)` instead of `/` (Spotfire returns empty on division by zero).
- No calculated tables; no changes to Power Query here (that is in the generated partition).
- Only reference columns that exist in `spec.json` and are emitted (tags and binary columns are not).
